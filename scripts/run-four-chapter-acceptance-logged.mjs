import { createHash, randomUUID } from 'node:crypto';
import { spawn } from 'node:child_process';
import { mkdir, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');

export function redactLog(value) {
  return value
    .replace(/(Authorization\s*:\s*Bearer\s+)[^\s]+/gi, '$1[REDACTED]')
    .replace(/((?:api[_-]?key|password|access[_-]?token|refresh[_-]?token)\s*[=:]\s*)[^\s,;]+/gi, '$1[REDACTED]')
    .replace(/\bsk-[A-Za-z0-9_-]{8,}\b/g, '[REDACTED_KEY]');
}

export async function main() {
  const outputDir = `/tmp/ai-video-platform-four-chapter-output-${randomUUID()}`;
  await mkdir(outputDir, { recursive: false, mode: 0o700 });
  const startedAt = new Date().toISOString();
  const child = spawn(process.execPath, [path.join(repoRoot, 'scripts/run-four-chapter-acceptance.mjs')], {
    cwd: repoRoot,
    env: { ...process.env, FOUR_CHAPTER_OUTPUT_DIR: outputDir },
    stdio: ['ignore', 'pipe', 'pipe'],
  });
  const chunks = [];
  for (const stream of [child.stdout, child.stderr]) stream.on('data', (chunk) => { chunks.push(Buffer.from(chunk)); (stream === child.stdout ? process.stdout : process.stderr).write(chunk); });
  const { code, signal } = await new Promise((resolve, reject) => {
    child.once('error', reject);
    child.once('close', (exitCode, exitSignal) => resolve({ code: exitCode, signal: exitSignal }));
  });
  const redacted = redactLog(Buffer.concat(chunks).toString('utf8'));
  const logPath = path.join(outputDir, 'acceptance.log');
  await writeFile(logPath, redacted, { mode: 0o600 });
  const sha256 = createHash('sha256').update(redacted).digest('hex');
  const metadata = { command: 'npm run verify:four-chapter', started_at: startedAt, finished_at: new Date().toISOString(), exit_code: code, signal, log_path: logPath, log_sha256: sha256 };
  await writeFile(path.join(outputDir, 'run-manifest.json'), `${JSON.stringify(metadata, null, 2)}\n`, { mode: 0o600 });
  console.log(`脱敏原始日志：${logPath}`);
  console.log(`脱敏日志 SHA-256：${sha256}`);
  if (code !== 0) process.exitCode = code ?? 1;
}

const invokedPath = process.argv[1] ? pathToFileURL(path.resolve(process.argv[1])).href : '';
if (import.meta.url === invokedPath) main().catch((error) => { console.error(error); process.exitCode = 1; });
