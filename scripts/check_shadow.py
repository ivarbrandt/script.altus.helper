#!/usr/bin/env python3
"""Verify no function-local import shadows a module-level name.

Python binds names per-function, not per-statement: a single `from x import foo`
anywhere inside a function makes `foo` local to that *entire* function body. If
that import sits in a conditional branch, every other branch that calls `foo`
raises UnboundLocalError -- even though the module-level `from y import foo` at
the top of the file looks like it should resolve.

This is invisible at the call site, which is what makes it dangerous in a large
dispatcher like router.routing(): nothing in the `generate_xml` branch hints
that the `generate_search_xml` branch 40 lines above rebound the name for the
whole function. Shipped broken 2026-05-07, found 2026-09-04.

Fix by aliasing the local import (`import foo as local_foo`) or deleting it when
it merely re-imports the module-level symbol.
"""
import ast
import os
import sys

SKIP_DIRS = {"__pycache__", ".git"}


def _imported_names(node):
    for alias in node.names:
        yield alias.asname or alias.name.split(".")[0]


def _walk_scope(node):
    """Walk a node's descendants without crossing into a nested scope."""
    for child in ast.iter_child_nodes(node):
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
            continue
        yield child
        yield from _walk_scope(child)


def module_scope_names(tree):
    names = set()
    for node in _walk_scope(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names.update(_imported_names(node))
        elif isinstance(node, ast.Assign):
            names.update(t.id for t in node.targets if isinstance(t, ast.Name))
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
    return names


def check_file(path, issues):
    try:
        with open(path, "r", encoding="utf-8") as fh:
            tree = ast.parse(fh.read(), filename=path)
    except (OSError, SyntaxError) as e:
        issues.append(f"  PARSE ERR {path}: {e}")
        return

    mod_names = module_scope_names(tree)
    rel = os.path.relpath(path)
    if rel.startswith(".."):
        rel = path

    for func in ast.walk(tree):
        if not isinstance(func, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        body_ids = {id(stmt) for stmt in func.body}
        uses = {}
        imports = []
        for node in _walk_scope(func):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                for name in _imported_names(node):
                    imports.append((name, node, id(node) in body_ids))
            elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
                uses.setdefault(node.id, []).append(node.lineno)

        for name, node, top_level in imports:
            if name not in mod_names:
                continue
            first_use = min(uses.get(name, [node.lineno]))
            if top_level and first_use >= node.lineno:
                # Straight-line and binds before any use -- redundant, not fatal.
                continue
            issues.append(
                f"  SHADOW {rel}:{node.lineno}  {func.name}() imports '{name}', "
                f"which is also bound at module level"
            )


def main(root: str) -> int:
    if not os.path.isdir(root):
        print(f"ERROR: not a directory: {root}")
        return 2

    issues = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
        for fn in sorted(filenames):
            if fn.endswith(".py"):
                check_file(os.path.join(dirpath, fn), issues)

    if issues:
        print(
            "ERROR: function-local import shadows a module-level name — "
            "callers in other branches will raise UnboundLocalError:"
        )
        for i in issues:
            print(i)
        print("  Fix: alias the local import, or drop it if it duplicates the module-level one.")
        return 1

    print("check_shadow: ok")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "resources/lib"))
