"""AG-blast: Blast-radius import graph for agent-guard.

Builds a forward (file → imports) and reverse (file → importers) dependency
graph by parsing Python source files with ast.  The blast radius of a file is
the number of other project files that import it directly; files with a blast
radius above HIGH_RISK_THRESHOLD are flagged as high-risk change targets.

Usage (module):
    from agent_guard.blast_radius import build_import_graph, blast_radius, is_high_risk

Usage (CLI):
    python3 agent-guard/blast_radius.py [--dir PATH] [--threshold N] [--json]
    python3 agent-guard/blast_radius.py --file path/to/module.py

Stdlib only. No external dependencies.
"""
from __future__ import annotations

import ast
import argparse
import json
import os
import sys
from pathlib import Path
from typing import Dict, Set, Optional

HIGH_RISK_THRESHOLD = 5  # files with more importers than this are flagged


# ---------------------------------------------------------------------------
# Import extraction (pure, no I/O)
# ---------------------------------------------------------------------------

def _imports_from_ast(tree: ast.Module, this_file: Path, root: Path) -> Set[str]:
    """Extract project-local import paths from a parsed AST.

    Handles:
      import foo            → foo.py (if it exists in root)
      import foo.bar        → foo/bar.py
      from foo import bar   → foo.py  (bar may be a name, not a file)
      from . import bar     → sibling bar.py  (relative)
      from .sub import bar  → sub/bar.py relative to parent

    Returns a set of canonical project-relative path strings (e.g. "foo/bar.py").
    Only paths that resolve to actual .py files under root are included.
    """
    imports: Set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                resolved = _resolve_absolute(alias.name, root)
                if resolved:
                    imports.add(resolved)

        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            level = node.level  # 0 = absolute, 1 = ., 2 = ..
            if level > 0:
                # Relative import — resolve from this_file's package
                if module:
                    resolved = _resolve_relative(module, this_file, root, level)
                    if resolved:
                        imports.add(resolved)
                # Also try each name as a sibling module: `from . import utils`
                for alias in node.names:
                    sub = f"{module}.{alias.name}" if module else alias.name
                    resolved2 = _resolve_relative(sub, this_file, root, level)
                    if resolved2:
                        imports.add(resolved2)
            else:
                # Absolute import
                resolved = _resolve_absolute(module, root)
                if resolved:
                    imports.add(resolved)
                # Also try "from package import submodule"
                for alias in node.names:
                    full = f"{module}.{alias.name}" if module else alias.name
                    resolved2 = _resolve_absolute(full, root)
                    if resolved2 and resolved2 != resolved:
                        imports.add(resolved2)

    return imports


def _resolve_absolute(dotted: str, root: Path) -> Optional[str]:
    """Try to resolve a dotted import to a .py file under root."""
    parts = dotted.split(".")
    # Try full path first, then progressively shorter (e.g. "foo.bar" → foo/bar.py)
    for n in range(len(parts), 0, -1):
        candidate = root / Path(*parts[:n]).with_suffix(".py")
        if candidate.is_file():
            return str(candidate.relative_to(root))
        # Also check __init__.py for packages
        pkg = root / Path(*parts[:n]) / "__init__.py"
        if pkg.is_file():
            return str(pkg.relative_to(root))
    return None


def _resolve_relative(module: str, this_file: Path, root: Path, level: int) -> Optional[str]:
    """Resolve a relative import to a project-relative path."""
    # Walk up `level` directories from this_file's package
    pkg_dir = this_file.parent
    for _ in range(level - 1):
        pkg_dir = pkg_dir.parent

    if module:
        parts = module.split(".")
        candidate = pkg_dir / Path(*parts).with_suffix(".py")
        if candidate.is_file():
            try:
                return str(candidate.relative_to(root))
            except ValueError:
                return None
        pkg = pkg_dir / Path(*parts) / "__init__.py"
        if pkg.is_file():
            try:
                return str(pkg.relative_to(root))
            except ValueError:
                return None
    return None


# ---------------------------------------------------------------------------
# Graph builders (I/O)
# ---------------------------------------------------------------------------

def build_import_graph(root_dir: str | Path) -> Dict[str, Set[str]]:
    """Scan all .py files under root_dir and return forward dependency map.

    Returns:
        {relative_path: set_of_relative_paths_it_imports}

    Files that fail to parse (syntax errors, encoding issues) are included
    with an empty dependency set — they are not skipped entirely, because they
    still exist as nodes other files might import.
    """
    root = Path(root_dir).resolve()
    forward: Dict[str, Set[str]] = {}

    _SKIP_DIRS = {".venv", "venv", "env", ".env", "__pycache__", ".git",
                  "node_modules", "site-packages", "dist-packages"}

    def _should_skip(path: Path) -> bool:
        return any(part in _SKIP_DIRS for part in path.parts)

    for py_file in sorted(root.rglob("*.py")):
        if _should_skip(py_file.relative_to(root)):
            continue
        rel = str(py_file.relative_to(root))
        try:
            source = py_file.read_text(encoding="utf-8", errors="replace")
            tree = ast.parse(source, filename=str(py_file))
            forward[rel] = _imports_from_ast(tree, py_file, root)
        except SyntaxError:
            forward[rel] = set()

    return forward


def build_reverse_deps(forward: Dict[str, Set[str]]) -> Dict[str, Set[str]]:
    """Invert the forward dependency map into a reverse dependency map.

    Returns:
        {file: set_of_files_that_import_it}
    """
    reverse: Dict[str, Set[str]] = {f: set() for f in forward}

    for importer, deps in forward.items():
        for dep in deps:
            if dep not in reverse:
                reverse[dep] = set()
            reverse[dep].add(importer)

    return reverse


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def blast_radius(file: str, reverse_deps: Dict[str, Set[str]]) -> int:
    """Return the blast radius of file: how many other files import it."""
    return len(reverse_deps.get(file, set()))


def is_high_risk(file: str, reverse_deps: Dict[str, Set[str]],
                 threshold: int = HIGH_RISK_THRESHOLD) -> bool:
    """Return True if the file's blast radius exceeds the threshold."""
    return blast_radius(file, reverse_deps) > threshold


def high_risk_files(
    reverse_deps: Dict[str, Set[str]],
    threshold: int = HIGH_RISK_THRESHOLD,
) -> list[tuple[str, int]]:
    """Return [(file, radius), ...] for all high-risk files, sorted desc by radius."""
    results = [
        (f, blast_radius(f, reverse_deps))
        for f in reverse_deps
        if is_high_risk(f, reverse_deps, threshold)
    ]
    return sorted(results, key=lambda x: x[1], reverse=True)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _format_table(reverse_deps: Dict[str, Set[str]], threshold: int) -> str:
    rows = []
    for f in sorted(reverse_deps):
        r = blast_radius(f, reverse_deps)
        flag = " !! HIGH RISK" if r > threshold else ""
        if r > 0 or flag:
            rows.append(f"  {r:3d}  {f}{flag}")
    if not rows:
        return "  (no inter-file imports detected)"
    return "\n".join(rows)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="python3 agent-guard/blast_radius.py",
        description="Show import blast-radius for Python files in a project",
    )
    parser.add_argument(
        "--dir", default=".", metavar="PATH",
        help="Project root to scan (default: current directory)",
    )
    parser.add_argument(
        "--file", metavar="PATH",
        help="Show blast radius for a single file only",
    )
    parser.add_argument(
        "--threshold", type=int, default=HIGH_RISK_THRESHOLD, metavar="N",
        help=f"High-risk threshold (default: {HIGH_RISK_THRESHOLD})",
    )
    parser.add_argument(
        "--json", action="store_true",
        help="Output raw reverse-dep map as JSON",
    )
    args = parser.parse_args(argv)

    root = Path(args.dir).resolve()
    if not root.is_dir():
        print(f"Error: not a directory: {root}", file=sys.stderr)
        return 1

    forward = build_import_graph(root)
    reverse = build_reverse_deps(forward)

    if args.json:
        serialisable = {k: sorted(v) for k, v in reverse.items()}
        print(json.dumps(serialisable, indent=2))
        return 0

    if args.file:
        rel = str(Path(args.file).resolve().relative_to(root)) if Path(args.file).is_absolute() else args.file
        r = blast_radius(rel, reverse)
        risk = "HIGH RISK" if is_high_risk(rel, reverse, args.threshold) else "ok"
        importers = sorted(reverse.get(rel, set()))
        print(f"{rel}")
        print(f"  blast radius : {r}  [{risk}]")
        if importers:
            print(f"  imported by  :")
            for imp in importers:
                print(f"    {imp}")
        return 0

    # Full report
    risky = high_risk_files(reverse, args.threshold)
    print(f"Blast Radius Report — {root}")
    print(f"Files scanned : {len(forward)}")
    print(f"High-risk (>{args.threshold} importers) : {len(risky)}")
    print()
    if risky:
        print("HIGH RISK FILES:")
        for f, r in risky:
            print(f"  {r:3d} importers  {f}")
        print()
    print("All files with importers:")
    print(_format_table(reverse, args.threshold))
    return 0


if __name__ == "__main__":
    sys.exit(main())
