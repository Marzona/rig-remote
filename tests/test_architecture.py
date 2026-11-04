"""Architecture invariants enforced as unit tests.

Each ``test_*_real_source`` style test enforces one row of the "Boundaries and
Invariants" table in .claude/architecture.md; the rationale lives in the ADR
that row cites.

Every rule is a ``find_*`` function that takes source text (or, for the ADR-3
registry check, a mapping) and returns a list of human-readable violations. The
same function runs against the real files under ``src/`` and against known-bad
and known-good snippets, so each check is proven able to fail.

Source files are parsed with ``ast`` and never imported. The only imports are
``ScannerCore``/``ScanningConfig`` (queue-event consistency check) and the
``scanning`` module (ADR-3 registry check).
"""

import ast
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any, Generic, Protocol

import pytest

from rig_remote import scanning
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
# ADR-2: domain code = models + scanner modules (see _is_domain_config_file); no config objects in signatures.
CONFIG_PARAM_NAMES = {"config", "app_config"}
# Parameters named ``config`` are allowed when annotated with one of these types: ScanningConfig is the
# scanner's timing/signal-constants dataclass (ScannerCore.__init__, create_scanner), not AppConfig.
CONFIG_PARAM_ALLOWED_ANNOTATIONS = {"ScanningConfig"}
# Queue events whose value needs unit conversion handled explicitly in process_queue.
SPECIAL_QUEUE_KEYS = {"range_min", "range_max"}
# ADR-3: bases a registered strategy may have in its MRO (structural typing only).
ALLOWED_STRATEGY_BASES = {object, Protocol, Generic}
REQUIRED_STRATEGY_METHODS = ("scan", "terminate")


def _rel(path: Path) -> str:
    return path.relative_to(SRC_DIR).as_posix()


def _is_domain_config_file(path: Path) -> bool:
    rel = _rel(path)
    return (
        rel.startswith("rig_remote/models/")
        or path.name in {"scanning.py", "scanner_core.py", "scanning_config.py"}
        or path.name.endswith("_scanner_strategy.py")
    )


DOMAIN_FILES = [p for p in SOURCE_FILES if _is_domain_config_file(p)]


def _parse(source: str, label: str = "<snippet>") -> ast.Module:
    return ast.parse(source, filename=label)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _imported_top_level(tree: ast.Module) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            names.add(node.module.split(".")[0])
    return names


# ---------------------------------------------------------------------------
# Rule functions: source text in, list of violation messages out.
# ---------------------------------------------------------------------------


def find_size_violations(source: str, label: str, limit: int = MAX_MODULE_LINES) -> list[str]:
    count = len(source.splitlines())
    if count <= limit:
        return []
    return [f"{label} has {count} lines; split it by responsibility (limit {limit})"]


def find_async_violations(source: str, label: str = "<snippet>") -> list[str]:
    tree = _parse(source, label)
    found = [
        f"{label}:{node.lineno}: async syntax; the app is threads + Qt event loop, remove it (ADR-1)"
        for node in ast.walk(tree)
        if isinstance(node, ast.AsyncFunctionDef | ast.AsyncFor | ast.AsyncWith | ast.Await)
    ]
    bad = sorted(_imported_top_level(tree) & ASYNC_MODULES)
    if bad:
        found.append(f"{label}: imports async framework {bad}; use threads (ADR-1)")
    return found


def find_abc_violations(source: str, label: str = "<snippet>") -> list[str]:
    if "abc" in _imported_top_level(_parse(source, label)):
        return [f"{label}: imports abc; use typing.Protocol instead (ADR-7)"]
    return []


def find_orm_violations(source: str, label: str = "<snippet>") -> list[str]:
    bad = sorted(_imported_top_level(_parse(source, label)) & ORM_MODULES)
    if bad:
        return [f"{label}: imports {bad}; file I/O is configparser + csv, remove the database (ADR-8)"]
    return []


def find_app_config_import_violations(source: str, label: str = "<snippet>") -> list[str]:
    for node in ast.walk(_parse(source, label)):
        modules: list[str] = []
        if isinstance(node, ast.ImportFrom) and node.module:
            modules = [node.module]
        elif isinstance(node, ast.Import):
            modules = [a.name for a in node.names]
        if any(m.endswith("app_config") for m in modules):
            return [f"{label}:{node.lineno}: imports app_config; pass plain values instead (ADR-2)"]
    return []


def _annotation_names(annotation: ast.expr | None) -> set[str]:
    """Names mentioned in an annotation, including string annotations like ``"AppConfig"``."""
    if annotation is None:
        return set()
    names: set[str] = set()
    for node in ast.walk(annotation):
        if isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.Attribute):
            names.add(node.attr)
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            try:
                names |= _annotation_names(ast.parse(node.value, mode="eval").body)
            except SyntaxError:
                names.add(node.value)
    return names


def find_config_param_violations(source: str, label: str = "<snippet>") -> list[str]:
    found: list[str] = []
    for node in ast.walk(_parse(source, label)):
        if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        args = node.args
        for arg in [*args.posonlyargs, *args.args, *args.kwonlyargs, args.vararg, args.kwarg]:
            if arg is None:
                continue
            where = f"{label}:{arg.lineno}: {node.name}({arg.arg})"
            names = _annotation_names(arg.annotation)
            if "AppConfig" in names:
                found.append(f"{where} is annotated AppConfig; pass plain values instead (ADR-2)")
            elif arg.arg in CONFIG_PARAM_NAMES and not names & CONFIG_PARAM_ALLOWED_ANNOTATIONS:
                found.append(
                    f"{where} takes a config object; pass plain values, or annotate it with a "
                    f"domain-owned type such as ScanningConfig (ADR-2)"
                )
    return found


def _self_attribute_targets(target: ast.expr) -> list[ast.Attribute]:
    if isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name) and target.value.id == "self":
        return [target]
    if isinstance(target, ast.Tuple | ast.List):
        return [a for elt in target.elts for a in _self_attribute_targets(elt)]
    if isinstance(target, ast.Starred):
        return _self_attribute_targets(target.value)
    return []


def find_mixin_violations(source: str, class_name: str, label: str = "<snippet>") -> list[str]:
    tree = _parse(source, label)
    cls = next((n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == class_name), None)
    if cls is None:
        return [f"{label}: class {class_name} not found"]
    found: list[str] = []
    declared: set[str] = set()
    for node in cls.body:
        if isinstance(node, ast.FunctionDef) and node.name == "__init__":
            found.append(f"{label}:{node.lineno}: {class_name} defines __init__; instance state belongs to RigRemote")
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            declared.add(node.target.id)
        targets = node.targets if isinstance(node, ast.Assign) else []
        if isinstance(node, ast.AnnAssign) and node.value is not None:
            targets = [node.target]
        for target in targets:
            name = target.id if isinstance(target, ast.Name) else ast.unparse(target)
            if not name.lstrip("_").isupper():
                found.append(
                    f"{label}:{node.lineno}: {class_name}.{name}: mixins may declare annotations "
                    "and UPPER_CASE constants only"
                )
            declared.add(name)
    for method in (n for n in ast.walk(cls) if isinstance(n, ast.FunctionDef | ast.AsyncFunctionDef)):
        for node in ast.walk(method):
            if isinstance(node, ast.Assign):
                targets = node.targets
            elif isinstance(node, ast.AugAssign | ast.AnnAssign):
                targets = [node.target]
            else:
                continue
            for attr in (a for t in targets for a in _self_attribute_targets(t)):
                if attr.attr not in declared:
                    found.append(
                        f"{label}:{attr.lineno}: {class_name}.{method.name} assigns self.{attr.attr}, which is not "
                        f"annotated on the class; declare '{attr.attr}: <type>' on {class_name} "
                        "or move the state to RigRemote"
                    )
    return found


def find_registry_violations(registry: Mapping[str, Any]) -> list[str]:
    found: list[str] = []
    if not registry:
        found.append("scanner registry is empty; register at least one strategy (ADR-3)")
    for key, entry in registry.items():
        for method in REQUIRED_STRATEGY_METHODS:
            if not callable(getattr(entry, method, None)):
                found.append(f"registry entry {key!r} has no callable {method}(); strategies are structural (ADR-3)")
        mro = getattr(entry, "__mro__", None)
        if mro is None:
            found.append(f"registry entry {key!r} is not a class; register the strategy class (ADR-3)")
            continue
        shared = [b.__name__ for b in mro[1:] if b not in ALLOWED_STRATEGY_BASES]
        if shared:
            found.append(
                f"registry entry {key!r} inherits from {shared}; compose and satisfy the Protocol "
                "instead of subclassing (ADR-3)"
            )
    return found


# ---------------------------------------------------------------------------
# Rule self-tests: known-bad snippets must fail, known-good must pass.
# ---------------------------------------------------------------------------

_MIXIN_GOOD_ANNOTATED = """
class M:
    count: int
    LIMIT = 3
    def go(self):
        self.count = 1
        self.count += 2
"""

RULE_CASES: list[tuple[str, Callable[[str], list[str]], str, bool]] = [
    # (id, rule, snippet, expect_violation)
    ("size-bad", lambda s: find_size_violations(s, "x.py", limit=2), "a\nb\nc\n", True),
    ("size-good", lambda s: find_size_violations(s, "x.py", limit=2), "a\nb\n", False),
    ("async-def-bad", find_async_violations, "async def f():\n    pass\n", True),
    ("async-await-bad", find_async_violations, "async def f():\n    await g()\n", True),
    ("async-import-bad", find_async_violations, "import asyncio\n", True),
    ("async-from-import-bad", find_async_violations, "from trio import run\n", True),
    ("async-good", find_async_violations, "import threading\ndef f():\n    pass\n", False),
    ("abc-import-bad", find_abc_violations, "import abc\n", True),
    ("abc-from-import-bad", find_abc_violations, "from abc import ABC\n", True),
    ("abc-good", find_abc_violations, "from typing import Protocol\n", False),
    ("orm-sqlite-bad", find_orm_violations, "import sqlite3\n", True),
    ("orm-sqlalchemy-bad", find_orm_violations, "from sqlalchemy.orm import Session\n", True),
    ("orm-good", find_orm_violations, "import csv\nimport configparser\n", False),
    ("app-config-from-bad", find_app_config_import_violations, "from rig_remote.app_config import AppConfig\n", True),
    ("app-config-import-bad", find_app_config_import_violations, "import rig_remote.app_config\n", True),
    (
        "app-config-good",
        find_app_config_import_violations,
        "from rig_remote.scanning_config import ScanningConfig\n",
        False,
    ),
    ("config-param-annotated-bad", find_config_param_violations, "def f(x: AppConfig):\n    pass\n", True),
    ("config-param-string-annotated-bad", find_config_param_violations, 'def f(x: "AppConfig"):\n    pass\n', True),
    ("config-param-optional-bad", find_config_param_violations, "def f(x: AppConfig | None = None):\n    pass\n", True),
    ("config-param-named-config-bad", find_config_param_violations, "def f(config):\n    pass\n", True),
    (
        "config-param-named-app-config-bad",
        find_config_param_violations,
        "class C:\n    def __init__(self, app_config: dict):\n        pass\n",
        True,
    ),
    ("config-param-kwonly-bad", find_config_param_violations, "def f(*, config: dict):\n    pass\n", True),
    (
        "config-param-scanning-config-good",
        find_config_param_violations,
        "def f(config: ScanningConfig):\n    pass\n",
        False,
    ),
    (
        "config-param-optional-scanning-config-good",
        find_config_param_violations,
        "def f(config: ScanningConfig | None = None):\n    pass\n",
        False,
    ),
    ("config-param-plain-values-good", find_config_param_violations, "def f(host: str, port: int):\n    pass\n", False),
    (
        "mixin-new-state-bad",
        lambda s: find_mixin_violations(s, "M"),
        "class M:\n    def go(self):\n        self.brand_new_state = 1\n",
        True,
    ),
    (
        "mixin-augassign-bad",
        lambda s: find_mixin_violations(s, "M"),
        "class M:\n    def go(self):\n        self.n += 1\n",
        True,
    ),
    (
        "mixin-annassign-bad",
        lambda s: find_mixin_violations(s, "M"),
        "class M:\n    def go(self):\n        self.n: int = 1\n",
        True,
    ),
    (
        "mixin-tuple-assign-bad",
        lambda s: find_mixin_violations(s, "M"),
        "class M:\n    def go(self):\n        self.a, self.b = 1, 2\n",
        True,
    ),
    (
        "mixin-init-bad",
        lambda s: find_mixin_violations(s, "M"),
        "class M:\n    def __init__(self):\n        pass\n",
        True,
    ),
    ("mixin-lowercase-class-attr-bad", lambda s: find_mixin_violations(s, "M"), "class M:\n    shared = []\n", True),
    ("mixin-annotated-state-good", lambda s: find_mixin_violations(s, "M"), _MIXIN_GOOD_ANNOTATED, False),
    (
        "mixin-read-only-good",
        lambda s: find_mixin_violations(s, "M"),
        "class M:\n    x: int\n    def go(self):\n        return self.x + self.other()\n",
        False,
    ),
    (
        "mixin-local-var-good",
        lambda s: find_mixin_violations(s, "M"),
        "class M:\n    def go(self):\n        value = 1\n        return value\n",
        False,
    ),
]


@pytest.mark.parametrize(
    ("rule", "snippet", "expect_violation"), [c[1:] for c in RULE_CASES], ids=[c[0] for c in RULE_CASES]
)
def test_rule_flags_bad_and_accepts_good_snippets(
    rule: Callable[[str], list[str]], snippet: str, expect_violation: bool
) -> None:
    assert bool(rule(snippet)) is expect_violation


def test_mixin_violation_message_names_line_and_fix() -> None:
    msg = find_mixin_violations("class M:\n    def go(self):\n        self.brand_new_state = 1\n", "M", "ui_x.py")[0]
    assert "ui_x.py:3" in msg
    assert "brand_new_state" in msg
    assert "declare" in msg


class _Proto(Protocol):
    def scan(self) -> None: ...
    def terminate(self) -> None: ...


class _GoodStrategy:
    def scan(self) -> None: ...
    def terminate(self) -> None: ...


class _ProtocolStrategy(_Proto):
    pass


class _NoTerminate:
    def scan(self) -> None: ...


class _NotCallable:
    scan = 1
    terminate = 2


class _SharedBase:
    def scan(self) -> None: ...
    def terminate(self) -> None: ...


class _SubclassedStrategy(_SharedBase):
    pass


@pytest.mark.parametrize(
    ("registry", "expect_violation"),
    [
        ({"good": _GoodStrategy}, False),
        ({"proto": _ProtocolStrategy}, True),
        ({"a": _GoodStrategy, "b": _SharedBase}, False),
        ({}, True),
        ({"no-terminate": _NoTerminate}, True),
        ({"not-callable": _NotCallable}, True),
        ({"subclass": _SubclassedStrategy}, True),
        ({"instance": _GoodStrategy()}, True),
        ({"function": lambda core: core}, True),
    ],
    ids=[
        "good",
        "protocol-subclass-bad",
        "plain-classes-good",
        "empty-bad",
        "missing-terminate-bad",
        "non-callable-methods-bad",
        "subclass-bad",
        "instance-not-class-bad",
        "bare-function-bad",
    ],
)
def test_registry_rule_flags_bad_and_accepts_good_registries(
    registry: Mapping[str, Any], expect_violation: bool
) -> None:
    assert bool(find_registry_violations(registry)) is expect_violation


# ---------------------------------------------------------------------------
# Real-source checks.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("path", SOURCE_FILES, ids=_rel)
def test_module_size_within_limit(path: Path) -> None:
    assert not find_size_violations(_read(path), _rel(path))


@pytest.mark.parametrize("path", SOURCE_FILES, ids=_rel)
def test_no_async_code(path: Path) -> None:
    assert not find_async_violations(_read(path), _rel(path))


@pytest.mark.parametrize("path", SOURCE_FILES, ids=_rel)
def test_no_abc_inheritance(path: Path) -> None:
    assert not find_abc_violations(_read(path), _rel(path))


@pytest.mark.parametrize("path", SOURCE_FILES, ids=_rel)
def test_no_database_or_orm(path: Path) -> None:
    assert not find_orm_violations(_read(path), _rel(path))


@pytest.mark.parametrize("path", SOURCE_FILES, ids=_rel)
def test_app_config_only_imported_by_composition_root_and_ui(path: Path) -> None:
    if _rel(path) in APP_CONFIG_IMPORTERS:
        return
    assert not find_app_config_import_violations(_read(path), _rel(path))


@pytest.mark.parametrize("path", DOMAIN_FILES, ids=_rel)
def test_domain_code_takes_no_config_parameter(path: Path) -> None:
    assert not find_config_param_violations(_read(path), _rel(path))


def test_domain_config_rule_covers_expected_files() -> None:
    covered = {_rel(p) for p in DOMAIN_FILES}
    assert {
        "rig_remote/scanning.py",
        "rig_remote/scanner_core.py",
        "rig_remote/scanning_config.py",
        "rig_remote/bookmark_scanner_strategy.py",
        "rig_remote/frequency_scanner_strategy.py",
        "rig_remote/models/bookmark.py",
    } <= covered


@pytest.mark.parametrize(("rel_path", "class_name"), sorted(MIXIN_FILES.items()))
def test_mixins_hold_no_instance_state(rel_path: str, class_name: str) -> None:
    assert not find_mixin_violations(_read(SRC_DIR / rel_path), class_name, rel_path)


def test_scanner_registry_entries_are_structural_strategies() -> None:
    assert not find_registry_violations(scanning._SCANNER_REGISTRY)


def test_queue_event_names_and_converters_match() -> None:
    event_keys = {name.split("_", 1)[1] for name in ScanningConfig().valid_scan_update_event_names}
    converter_keys = set(ScannerCore._QUEUE_EVENT_CONVERTERS)
    assert event_keys - SPECIAL_QUEUE_KEYS == converter_keys, (
        "valid_scan_update_event_names and _QUEUE_EVENT_CONVERTERS disagree: "
        f"events without converter={sorted(event_keys - SPECIAL_QUEUE_KEYS - converter_keys)}, "
        f"converters without event={sorted(converter_keys - event_keys)}"
    )
