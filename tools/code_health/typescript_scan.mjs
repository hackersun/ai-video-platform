import fs from 'node:fs';
import path from 'node:path';
import {createRequire} from 'node:module';


const [toolRoot, repoRoot, fileListPath, policyPath] = process.argv.slice(2);
if (!toolRoot || !repoRoot || !fileListPath || !policyPath) {
  throw new Error(
    'usage: node typescript_scan.mjs <tool-root> <repo-root> <file-list-json> <policy-json>',
  );
}

const require = createRequire(import.meta.url);
let ts;
try {
  ts = require(path.join(toolRoot, 'frontend/node_modules/typescript'));
} catch (error) {
  throw new Error(`TypeScript compiler is unavailable; run npm ci --prefix frontend (${error.message})`);
}
const policy = JSON.parse(fs.readFileSync(policyPath, 'utf8'));
const files = JSON.parse(fs.readFileSync(fileListPath, 'utf8'));


function effectiveLines(text) {
  return text.split(/\r?\n/).filter((line) => line.trim() && !line.trimStart().startsWith('//')).length;
}


function functionName(node, source) {
  if (node.name) return node.name.getText(source);
  if (ts.isVariableDeclaration(node.parent) && node.parent.name) return node.parent.name.getText(source);
  return '<anonymous>';
}


function isFunctionLike(node) {
  return ts.isFunctionDeclaration(node)
    || ts.isMethodDeclaration(node)
    || ts.isArrowFunction(node)
    || ts.isFunctionExpression(node);
}


function violation(code, relative, line, actual, allowed, message) {
  return {code, path: relative, line, actual, allowed, message};
}


function scanFile(filePath) {
  const text = fs.readFileSync(filePath, 'utf8');
  const relative = path.relative(repoRoot, filePath).split(path.sep).join('/');
  const scriptKind = filePath.endsWith('.tsx') ? ts.ScriptKind.TSX : ts.ScriptKind.TS;
  const source = ts.createSourceFile(filePath, text, ts.ScriptTarget.Latest, true, scriptKind);
  const functions = [];
  const violations = [];
  const imports = [];
  const page = relative.startsWith('frontend/src/app/') && relative.endsWith('/page.tsx');
  const fileLines = effectiveLines(text);
  if (page && fileLines > policy.limits.react_page_lines) {
    violations.push(violation(
      'react_page_too_long', relative, 1, fileLines, policy.limits.react_page_lines,
      `${relative} has ${fileLines} effective lines`,
    ));
  }
  for (const diagnostic of source.parseDiagnostics) {
    const line = source.getLineAndCharacterOfPosition(diagnostic.start || 0).line + 1;
    violations.push(violation(
      'typescript_syntax_error', relative, line,
      ts.flattenDiagnosticMessageText(diagnostic.messageText, '\n'), 'valid TypeScript syntax',
      `${relative} cannot be parsed`,
    ));
  }
  function visit(node) {
    if (ts.isImportDeclaration(node) && ts.isStringLiteral(node.moduleSpecifier)) {
      imports.push(node.moduleSpecifier.text);
    }
    if (isFunctionLike(node)) {
      const name = functionName(node, source);
      const start = source.getLineAndCharacterOfPosition(node.getStart(source)).line + 1;
      const end = source.getLineAndCharacterOfPosition(node.end).line + 1;
      const count = effectiveLines(text.slice(node.getStart(source), node.end));
      const component = filePath.endsWith('.tsx') && /^[A-Z]/.test(name);
      const limit = component ? policy.limits.react_component_lines : policy.limits.function_lines;
      functions.push({name, line: start, end_line: end, effective_lines: count, is_route: false});
      if (count > limit) {
        violations.push(violation(
          component ? 'react_component_too_long' : 'function_too_long',
          relative, start, count, limit, `${name} has ${count} effective lines`,
        ));
      }
    }
    ts.forEachChild(node, visit);
  }
  visit(source);
  return {
    path: relative,
    language: filePath.endsWith('.tsx') ? 'tsx' : 'typescript',
    effective_lines: fileLines,
    functions,
    route_count: 0,
    imports: [...new Set(imports)],
    violations,
  };
}


process.stdout.write(JSON.stringify({files: files.map(scanFile)}));
