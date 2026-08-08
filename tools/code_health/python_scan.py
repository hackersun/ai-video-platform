"""Read-only Python AST metrics and dependency-boundary checks."""

from __future__ import annotations

import ast
import fnmatch
from pathlib import Path

from tools.code_health.models import FileMetrics, FunctionMetrics, Violation
from tools.code_health.policy import Policy


ROUTE_METHODS = {"delete", "get", "head", "options", "patch", "post", "put"}


def _relative_path(path: Path, repo_root: Path) -> str:
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def _effective_line_count(lines: list[str], start: int = 1, end: int | None = None) -> int:
    selected = lines[start - 1:end]
    return sum(bool(line.strip()) and not line.lstrip().startswith("#") for line in selected)


def _is_route(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    for decorator in node.decorator_list:
        target = decorator.func if isinstance(decorator, ast.Call) else decorator
        if (
            isinstance(target, ast.Attribute)
            and target.attr in ROUTE_METHODS
            and isinstance(target.value, ast.Name)
            and target.value.id == "router"
        ):
            return True
    return False


def _imports(tree: ast.AST) -> tuple[str, ...]:
    values: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            values.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            values.append(node.module)
    return tuple(dict.fromkeys(values))


def _matches(path: str, pattern: str) -> bool:
    return fnmatch.fnmatchcase(path, pattern) or fnmatch.fnmatchcase(path, pattern.replace("**/", ""))


def _boundary_violations(path: str, imports: tuple[str, ...], policy: Policy) -> list[Violation]:
    violations = []
    for rule in policy.boundaries:
        if not _matches(path, rule.source_glob):
            continue
        for imported in imports:
            if imported == rule.forbidden_module_prefix or imported.startswith(f"{rule.forbidden_module_prefix}."):
                violations.append(Violation(
                    code=rule.code,
                    path=path,
                    line=1,
                    actual=imported,
                    allowed=f"not {rule.forbidden_module_prefix}",
                    message=f"{path} imports forbidden module {imported}",
                    subject=imported,
                ))
    return violations


def _function_metrics(tree: ast.AST, lines: list[str]) -> tuple[FunctionMetrics, ...]:
    functions = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        end_line = int(node.end_lineno or node.lineno)
        functions.append(FunctionMetrics(
            name=node.name,
            line=node.lineno,
            end_line=end_line,
            effective_lines=_effective_line_count(lines, node.lineno, end_line),
            is_route=_is_route(node),
        ))
    return tuple(sorted(functions, key=lambda item: (item.line, item.name)))


def scan_python_file(path: Path, repo_root: Path, policy: Policy) -> FileMetrics:
    relative = _relative_path(path, repo_root)
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    try:
        tree = ast.parse(text, filename=relative)
    except SyntaxError as error:
        violation = Violation(
            code="python_syntax_error",
            path=relative,
            line=int(error.lineno or 1),
            actual=error.msg,
            allowed="valid Python syntax",
            message=f"{relative} cannot be parsed: {error.msg}",
            subject=relative,
        )
        return FileMetrics(relative, "python", _effective_line_count(lines), (), 0, (), (violation,))
    functions = _function_metrics(tree, lines)
    imports = _imports(tree)
    violations = _boundary_violations(relative, imports, policy)
    for function in functions:
        limit = policy.limits.route_lines if function.is_route else policy.limits.function_lines
        if function.effective_lines > limit:
            violations.append(Violation(
                code="route_too_long" if function.is_route else "function_too_long",
                path=relative,
                line=function.line,
                actual=function.effective_lines,
                allowed=limit,
                message=f"{function.name} has {function.effective_lines} effective lines; limit is {limit}",
                subject=function.name,
            ))
    route_count = sum(function.is_route for function in functions)
    if route_count > policy.limits.endpoint_routes:
        violations.append(Violation(
            code="endpoint_has_too_many_routes", path=relative, line=1,
            actual=route_count, allowed=policy.limits.endpoint_routes,
            message=f"{relative} defines {route_count} routes; limit is {policy.limits.endpoint_routes}",
            subject=relative,
        ))
    return FileMetrics(
        relative, "python", _effective_line_count(lines), functions,
        route_count, imports, tuple(violations),
    )


__all__ = ["scan_python_file"]
