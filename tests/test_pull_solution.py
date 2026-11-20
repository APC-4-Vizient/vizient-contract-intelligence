"""Offline test for scripts/pull-solution.py: the files that hold environment variable values never stay in the unpacked solution."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))

_spec = importlib.util.spec_from_file_location("pull_solution", SCRIPTS / "pull-solution.py")
pull = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = pull
_spec.loader.exec_module(pull)


def test_only_the_environment_variable_value_files_are_removed(tmp_path: Path) -> None:
    kept = [tmp_path / "Other" / "Solution.xml",
            tmp_path / "environmentvariabledefinitions" / "vz_FunctionKey" / "environmentvariabledefinition.xml",
            tmp_path / "Workflows" / "VizientContractAnalysis.json"]
    values = [tmp_path / "environmentvariabledefinitions" / "vz_FunctionKey" / "environmentvariablevalues.json",
              tmp_path / "environmentvariabledefinitions" / "vz_SharePointSiteUrl" / "environmentvariablevalues.json"]
    for path in (*kept, *values):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{}", encoding="utf-8")

    assert pull.strip_environment_values(tmp_path) == 2
    assert not any(path.exists() for path in values)
    assert all(path.exists() for path in kept)
    assert pull.strip_environment_values(tmp_path) == 0


def test_the_solution_zip_loses_only_the_value_entries() -> None:
    import io
    import zipfile

    names = {"solution.xml": b"<x/>", "Workflows/a.json": b"{}",
             "environmentvariabledefinitions/vz_FunctionKey/environmentvariabledefinition.xml": b"<d/>",
             "environmentvariabledefinitions/vz_FunctionKey/environmentvariablevalues.json": b"secret-key",
             "environmentvariabledefinitions/vz_SharePointSiteUrl/environmentvariablevalues.json": b"https://x"}
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as z:
        for name, body in names.items():
            z.writestr(name, body)

    clean, removed = pull.strip_zip_values(buffer.getvalue())
    out = zipfile.ZipFile(io.BytesIO(clean))
    assert removed == 2
    assert sorted(out.namelist()) == sorted(n for n in names if not n.endswith("environmentvariablevalues.json"))
    assert all(out.read(n) == names[n] for n in out.namelist())
    assert b"secret-key" not in clean
