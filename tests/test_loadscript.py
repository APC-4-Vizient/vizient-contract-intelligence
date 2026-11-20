"""Offline tests for scripts/loadscript.py: a script with a hyphen in its name can be run as a module."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))

import loadscript  # noqa: E402

DATACLASS_SCRIPT = """from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Point:
    x: int


ORIGIN = Point(0)
"""


def test_a_script_with_a_hyphen_in_its_name_loads_and_its_dataclasses_resolve(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "my-script.py").write_text(DATACLASS_SCRIPT, encoding="utf-8")
    monkeypatch.setattr(loadscript, "SCRIPTS", tmp_path)

    module = loadscript.load_script("my-script.py", "my_script_under_test")

    assert module.ORIGIN == module.Point(0)
    assert sys.modules.pop("my_script_under_test") is module


def test_a_file_that_is_not_python_cannot_be_loaded_as_a_module(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "notes.txt").write_text("not a module", encoding="utf-8")
    monkeypatch.setattr(loadscript, "SCRIPTS", tmp_path)

    with pytest.raises(ImportError, match="notes.txt cannot be loaded as a module"):
        loadscript.load_script("notes.txt", "notes_under_test")

    assert "notes_under_test" not in sys.modules


def test_the_scripts_that_other_scripts_load_by_name_can_be_loaded() -> None:
    module = loadscript.load_script("run-local.py", "run_local_under_test")

    try:
        assert callable(module.load_settings)
    finally:
        del sys.modules["run_local_under_test"]
