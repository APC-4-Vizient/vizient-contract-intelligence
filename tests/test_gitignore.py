"""The .gitignore guard on eval/gold.

Gold labels quote a contract verbatim, so only the synthetic sets may be committed. These tests ask git itself, so they
skip when git is missing or the checkout is not a work tree (an unpacked archive, for example).
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "eval"))

import generate_contracts as gen  # noqa: E402


def git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=False, timeout=60)


@pytest.fixture(scope="module", autouse=True)
def inside_a_work_tree() -> None:
    if shutil.which("git") is None:
        pytest.skip("git is not installed")
    probe = git("rev-parse", "--is-inside-work-tree")
    if probe.returncode != 0 or probe.stdout.strip() != "true":
        pytest.skip("this checkout is not a git work tree")


def is_ignored(path: str) -> bool:
    """Whether the rules ignore the path. --no-index applies them to a file git already tracks as well."""
    result = git("check-ignore", "--no-index", "--quiet", "--", path)
    assert result.returncode in (0, 1), result.stderr
    return result.returncode == 0


def test_a_gold_file_that_is_not_a_synthetic_set_is_ignored() -> None:
    assert is_ignored("eval/gold/some-real-contract.json")


def test_every_synthetic_gold_file_can_still_be_committed() -> None:
    ids = [spec["id"] for spec in gen.load_specs()]
    assert ids
    blocked = [cid for cid in ids if is_ignored(f"eval/gold/{cid}.json")]
    assert not blocked, f"add an '!eval/gold/<id>.json' line to .gitignore for: {blocked}"


def test_only_the_solution_export_zip_can_be_committed() -> None:
    assert not is_ignored("dataverse/VizientContractPOC_unmanaged.zip")
    assert is_ignored("dataverse/Other_unmanaged.zip")
    assert is_ignored("anything.zip")
    assert is_ignored("dataverse/solution/environmentvariabledefinitions/vz_FunctionKey/environmentvariablevalues.json")
