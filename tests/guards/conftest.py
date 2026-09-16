"""Every test under tests/guards/ is release-blocking and owned by the user (AGENT.md §3).

Do not weaken, skip or delete a guard to make a feature pass; that needs explicit sign-off
recorded in DECISIONS.md.
"""

from __future__ import annotations

import ast
from collections.abc import Iterator
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[2] / "src" / "mabat"


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    for item in items:
        if "guards" in item.path.parts:
            item.add_marker("guard")


def source_files() -> Iterator[Path]:
    """Every Python file that ships in the mabat package."""
    yield from sorted(SRC.rglob("*.py"))


def module_name(path: Path) -> str:
    """``src/mabat/sections/cpu/collector.py`` -> ``mabat.sections.cpu.collector``."""
    relative = path.relative_to(SRC.parent).with_suffix("")
    parts = list(relative.parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def imports_of(path: Path) -> list[tuple[str, int]]:
    """Absolute dotted names imported by a file, with line numbers (relative imports resolved)."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    package = module_name(path)
    if path.name != "__init__.py":
        package = package.rpartition(".")[0]
    found: list[tuple[str, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.extend((alias.name, node.lineno) for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                base = ".".join(package.split(".")[: len(package.split(".")) - node.level + 1])
                target = f"{base}.{node.module}" if node.module else base
            else:
                target = node.module or ""
            found.append((target, node.lineno))
            found.extend((f"{target}.{alias.name}", node.lineno) for alias in node.names)
    return found


def attribute_uses(path: Path, dotted_names: set[str]) -> list[tuple[str, int]]:
    """Occurrences of e.g. ``os.environ`` / ``os.system`` as attribute chains in a file."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: list[tuple[str, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute):
            chain = _dotted(node)
            if chain in dotted_names:
                found.append((chain, node.lineno))
    return found


def _dotted(node: ast.AST) -> str:
    if isinstance(node, ast.Attribute):
        return f"{_dotted(node.value)}.{node.attr}"
    if isinstance(node, ast.Name):
        return node.id
    return "?"
