"""scripts/check.py runs every offline check, keeps going after a failure, and says what is missing instead of crashing."""

from __future__ import annotations

import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import check  # noqa: E402


class Recorder:
    """Stands in for subprocess.run: records each command, fails the ones that contain a given word, and can touch a file as a command runs."""

    def __init__(self, fail: str = "", on_run: Callable[[list[str]], None] | None = None) -> None:
        self.calls: list[list[str]] = []
        self.fail = fail
        self.on_run = on_run

    def __call__(self, command: list[str], cwd: Path) -> subprocess.CompletedProcess[bytes]:
        self.calls.append(command)
        if self.on_run is not None:
            self.on_run(command)
        return subprocess.CompletedProcess(command, 1 if self.fail and self.fail in command else 0)


@pytest.fixture
def project(tmp_path: Path) -> Path:
    """A project with the app's packages installed and a 3D page, and no .env."""
    (tmp_path / "contract-review" / "node_modules").mkdir(parents=True)
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "architecture-3d.html").write_bytes(b"page")
    return tmp_path


def test_it_plans_the_python_checks_then_the_app_checks() -> None:
    assert [step.name for step in check.plan()] == [
        "Python lint", "Python types", "Python tests", "App lint", "App types", "App tests", "App build", "3D page", "Leak scan"]
    assert [step.name for step in check.plan(app=False)] == ["Python lint", "Python types", "Python tests", "Leak scan"]
    assert {step.group for step in check.plan(python=False) if step.name != "Leak scan"} == {"app"}


def test_the_python_checks_cover_the_same_folders_the_configuration_names() -> None:
    lint = next(step for step in check.plan() if step.name == "Python lint")
    assert set(lint.command[-5:]) == {"scripts", "function", "analyzer", "eval", "tests"}


def test_it_keeps_going_after_a_failure_and_exits_1(project: Path, capsys: pytest.CaptureFixture[str]) -> None:
    recorder = Recorder(fail="mypy")
    assert check.main([], runner=recorder, root=project) == 1
    assert len(recorder.calls) == len(check.plan(root=project)) - 1  # every step but the leak scan, which has no .env to read
    output = capsys.readouterr().out
    assert "1 failed: Python types" in output and "Python tests" in output


def test_it_exits_0_when_everything_passes(project: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert check.main([], runner=Recorder(), root=project) == 0
    assert "All checks passed." in capsys.readouterr().out


def test_it_says_what_to_install_before_the_app_checks_instead_of_crashing(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    recorder = Recorder()
    assert check.main(["--app"], runner=recorder, root=tmp_path) == 1
    assert recorder.calls == []
    assert "Run `npm ci` in contract-review/ first." in capsys.readouterr().out


def test_the_leak_scan_runs_only_when_there_is_an_env_file(project: Path) -> None:
    without = Recorder()
    check.main(["--python"], runner=without, root=project)
    assert not any(command[-1].endswith("leak-scan.py") for command in without.calls)
    (project / ".env").write_text("TENANT_ID=\n", encoding="utf-8")
    with_env = Recorder()
    check.main(["--python"], runner=with_env, root=project)
    assert any(command[-1].endswith("leak-scan.py") for command in with_env.calls)


def test_a_rebuild_that_changes_the_3d_page_fails_the_step(project: Path) -> None:
    page = project / "docs" / "architecture-3d.html"

    def rebuild(command: list[str]) -> None:
        if command[-1] == "build:standalone":
            page.write_bytes(b"a different page")

    outcomes = [check.run_step(step, Recorder(on_run=rebuild)) for step in check.plan(python=False, root=project)]
    outcome = next(item for item in outcomes if item.step.name == "3D page")
    assert outcome.status == "failed" and "architecture-3d.html changed" in outcome.detail


def test_a_rebuild_that_leaves_the_3d_page_alone_passes(project: Path) -> None:
    step = next(item for item in check.plan(python=False, root=project) if item.name == "3D page")
    assert check.run_step(step, Recorder()).status == "passed"


def test_a_dry_run_runs_nothing(project: Path, capsys: pytest.CaptureFixture[str]) -> None:
    recorder = Recorder()
    assert check.main(["--dry-run"], runner=recorder, root=project) == 0
    assert recorder.calls == []
    assert "build:standalone" in capsys.readouterr().out
