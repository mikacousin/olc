# -*- coding: utf-8 -*-
# Open Lighting Console
# Copyright (c) 2026 Mika Cousin <mika.cousin@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.
"""Architecture boundary tests enforcing modular decoupling."""

from __future__ import annotations

import ast
from pathlib import Path

SRC_ROOT = Path(__file__).resolve().parent.parent / "src"

HEADLESS_PACKAGES = (
    "dmx_engine",
    "devices",
    "show",
    "files",
    "core",
    "actions",
    "controllers",
)

LOW_LEVEL_PACKAGES = (
    "dmx_engine",
    "devices",
)

FORBIDDEN_GUI_PREFIXES = ("gi", "olc.gtk3")
FORBIDDEN_HIGH_LEVEL_PREFIXES = (
    "olc.show",
    "olc.core",
    "olc.actions",
    "olc.controllers",
    "olc.files",
)


def _is_type_checking_guard(node: ast.If) -> bool:
    test = node.test
    if isinstance(test, ast.Name) and test.id == "TYPE_CHECKING":
        return True
    return (
        isinstance(test, ast.Attribute)
        and isinstance(test.value, ast.Name)
        and test.value.id == "typing"
        and test.attr == "TYPE_CHECKING"
    )


def _iter_imported_modules(
    py_file: Path, *, include_type_checking: bool = True
) -> list[tuple[int, str]]:
    """Return (lineno, module_name) for every import statement in *py_file*."""
    tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
    imports: list[tuple[int, str]] = []

    def _visit(node: ast.AST) -> None:
        if (
            not include_type_checking
            and isinstance(node, ast.If)
            and _is_type_checking_guard(node)
        ):
            for child in node.orelse:
                _visit(child)
            return
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append((node.lineno, alias.name))
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imports.append((node.lineno, node.module))
        for child in ast.iter_child_nodes(node):
            _visit(child)

    _visit(tree)
    return imports


def _matches_prefix(module: str, prefixes: tuple[str, ...]) -> bool:
    return any(
        module == prefix or module.startswith(f"{prefix}.") for prefix in prefixes
    )


def _find_violations(
    packages: tuple[str, ...],
    forbidden_prefixes: tuple[str, ...],
    *,
    include_type_checking: bool = True,
) -> list[str]:
    violations: list[str] = []
    for pkg in packages:
        pkg_dir = SRC_ROOT / pkg
        if not pkg_dir.is_dir():
            continue
        for py_file in sorted(pkg_dir.rglob("*.py")):
            rel = py_file.relative_to(SRC_ROOT)
            for lineno, module in _iter_imported_modules(
                py_file, include_type_checking=include_type_checking
            ):
                if _matches_prefix(module, forbidden_prefixes):
                    violations.append(f"{rel}:{lineno}: imports {module}")
    return violations


def test_headless_packages_do_not_import_gtk3_or_gi() -> None:
    """Headless domain, engine, IO, and controller packages must not import GTK/gi."""
    violations = _find_violations(HEADLESS_PACKAGES, FORBIDDEN_GUI_PREFIXES)
    assert not violations, "Forbidden GUI imports in headless packages:\n" + "\n".join(
        violations
    )


def test_low_level_packages_do_not_import_high_level_layers() -> None:
    """Low-level engine and devices packages must stay independent of upper layers."""
    violations = _find_violations(
        LOW_LEVEL_PACKAGES,
        FORBIDDEN_HIGH_LEVEL_PREFIXES,
        include_type_checking=False,
    )
    assert not violations, (
        "Forbidden high-level imports in dmx_engine/devices:\n" + "\n".join(violations)
    )
