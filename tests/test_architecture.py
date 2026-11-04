"""Architecture invariants enforced as unit tests.

Each test enforces one row of the "Boundaries and Invariants" table in
.claude/architecture.md; the rationale lives in the ADR that row cites.
The tests parse source files with ``ast`` only — nothing is imported.
"""

import ast
from pathlib import Path

import pytest

from rig_remote.scanner_core import ScannerCore
from rig_remote.scanning_config import ScanningConfig

SRC_DIR = Path(__file__).resolve().parent.parent / "src"
SOURCE_FILES = sorted(p for p in SRC_DIR.rglob("*.py") if "egg-info" not in p.parts)
MAX_MODULE_LINES = 600

# ADR-2: only the composition root and the UI may know about AppConfig.
APP_CONFIG_IMPORTERS = {
    "rig_remote/app_config.py",
    "rig_remote/rig_remote.py",
    "rig_remote/ui_qt.py",
    "rig_remote/ui_handlers.py",
    "rig_remote/ui_scan_handlers.py",
    "config_checker/config_checker.py",
}
# ADR-1 / ADR-8: forbidden top-level packages.
ASYNC_MODULES = {"asyncio", "anyio", "trio", "curio"}
ORM_MODULES = {"sqlite3", "sqlalchemy", "sqlmodel", "peewee", "pony", "tortoise", "django"}
# ADR-6: the main-window mixins.
MIXIN_FILES = {
    "rig_remote/ui_handlers.py": "RigRemoteHandlersMixin",
    "rig_remote/ui_scan_handlers.py": "RigRemoteScanHandlersMixin",
    "rig_remote/ui_renderer.py": "RigRemoteUIBuilder",
}
# Queue events whose value needs unit conversion handled explicitly in process_queue.
SPECIAL_QUEUE_KEYS = {"range_min", "range_max"}


def _rel(path: Path) -> str:
    return path.relative_to(SRC_DIR).as_posix()


def _tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _imported_top_level(tree: ast.Module) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            names.add(node.module.split(".")[0])
    return names


def _imports_app_config(tree: ast.Module) -> bool:
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module and node.module.endswith("app_config"):
            return True
        if isinstance(node, ast.Import) and any(a.name.endswith("app_config") for a in node.names):
            return True
    return False


@pytest.mark.parametrize("path", SOURCE_FILES, ids=_rel)
def test_module_size_within_limit(path: Path) -> None:
    line_count = len(path.read_text(encoding="utf-8").splitlines())
    assert line_count <= MAX_MODULE_LINES, f"{_rel(path)} has {line_count} lines; split it (limit {MAX_MODULE_LINES})"


@pytest.mark.parametrize("path", SOURCE_FILES, ids=_rel)
def test_no_async_code(path: Path) -> None:
    tree = _tree(path)
    async_nodes = [
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.AsyncFunctionDef | ast.AsyncFor | ast.AsyncWith | ast.Await)
    ]
    assert not async_nodes, f"{_rel(path)}: async syntax at lines {async_nodes} (ADR-1)"
    assert not _imported_top_level(tree) & ASYNC_MODULES, f"{_rel(path)} imports an async framework (ADR-1)"


@pytest.mark.parametrize("path", SOURCE_FILES, ids=_rel)
def test_no_abc_inheritance(path: Path) -> None:
    tree = _tree(path)
    assert "abc" not in _imported_top_level(tree), f"{_rel(path)} imports abc; use typing.Protocol (ADR-7)"


@pytest.mark.parametrize("path", SOURCE_FILES, ids=_rel)
def test_no_database_or_orm(path: Path) -> None:
    forbidden = _imported_top_level(_tree(path)) & ORM_MODULES
    assert not forbidden, f"{_rel(path)} imports {sorted(forbidden)}; file I/O is configparser + csv (ADR-8)"


@pytest.mark.parametrize("path", SOURCE_FILES, ids=_rel)
def test_app_config_only_imported_by_composition_root_and_ui(path: Path) -> None:
    if _rel(path) in APP_CONFIG_IMPORTERS:
        return
    assert not _imports_app_config(_tree(path)), f"{_rel(path)} imports app_config; pass values instead (ADR-2)"


@pytest.mark.parametrize(("rel_path", "class_name"), sorted(MIXIN_FILES.items()))
def test_mixins_hold_no_instance_state(rel_path: str, class_name: str) -> None:
    tree = _tree(SRC_DIR / rel_path)
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == class_name)
    assert not any(
        isinstance(n, ast.FunctionDef) and n.name == "__init__" for n in cls.body
    ), f"{class_name} defines __init__; instance state belongs to RigRemote (ADR-6)"
    for node in cls.body:
        targets = node.targets if isinstance(node, ast.Assign) else []
        if isinstance(node, ast.AnnAssign) and node.value is not None:
            targets = [node.target]
        for target in targets:
            name = target.id if isinstance(target, ast.Name) else ast.unparse(target)
            assert name.lstrip(
                "_"
            ).isupper(), f"{class_name}.{name}: mixins may declare annotations and UPPER_CASE constants only (ADR-6)"


def test_queue_event_names_and_converters_match() -> None:
    event_keys = {name.split("_", 1)[1] for name in ScanningConfig().valid_scan_update_event_names}
    converter_keys = set(ScannerCore._QUEUE_EVENT_CONVERTERS)
    assert event_keys - SPECIAL_QUEUE_KEYS == converter_keys, (
        "valid_scan_update_event_names and _QUEUE_EVENT_CONVERTERS disagree: "
        f"events without converter={sorted(event_keys - SPECIAL_QUEUE_KEYS - converter_keys)}, "
        f"converters without event={sorted(converter_keys - event_keys)}"
    )
