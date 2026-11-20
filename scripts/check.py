"""Run every offline check the repository has, in order, and say which ones failed.

    python scripts/check.py            # Python, then the Code App
    python scripts/check.py --python   # lint, types, and tests with coverage
    python scripts/check.py --app      # the Code App: lint, types, tests, build, and the 3D page
    python scripts/check.py --dry-run  # print the commands without running them

Every step runs even when an earlier one fails, so one pass shows everything that needs fixing. The exit code is 1 when any step failed.
No sign-in is needed. The leak scan runs only when a .env file exists, because it compares what Git would commit with the identifiers in it.
Install the Python tools with `python -m pip install -r requirements-dev.txt` and the app's packages with `npm ci` in contract-review/.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PYTHON_PATHS = ("scripts", "function", "analyzer", "eval", "tests")
Runner = Callable[..., "subprocess.CompletedProcess[bytes]"]


@dataclass(frozen=True)
class Step:
    name: str
    command: tuple[str, ...]
    cwd: Path
    group: str  # "python" or "app"
    needs: Path | None = None  # a path that must exist before the command can run
    hint: str = ""  # what to do when it does not
    skip_without: Path | None = None  # the step is skipped, not failed, when this does not exist
    watch: Path | None = None  # a file the command must leave exactly as it found it


@dataclass(frozen=True)
class Outcome:
    step: Step
    status: str  # "passed", "failed" or "skipped"
    detail: str
    seconds: float


def plan(*, python: bool = True, app: bool = True, root: Path = ROOT) -> list[Step]:
    """The steps to run, in order."""
    code_app = root / "contract-review"
    page = root / "docs" / "architecture-3d.html"
    install = "Run `npm ci` in contract-review/ first."
    py = sys.executable
    steps: list[Step] = []
    if python:
        steps += [
            Step("Python lint", (py, "-m", "ruff", "check", *PYTHON_PATHS), root, "python"),
            Step("Python types", (py, "-m", "mypy"), root, "python"),
            Step("Python tests", (py, "-m", "pytest", "-q", "--cov"), root, "python"),
        ]
    if app:
        needs = code_app / "node_modules"
        steps += [
            Step("App lint", ("npm", "run", "lint"), code_app, "app", needs, install),
            Step("App types", ("npx", "tsc", "-b"), code_app, "app", needs, install),
            Step("App tests", ("npm", "test"), code_app, "app", needs, install),
            Step("App build", ("npm", "run", "build"), code_app, "app", needs, install),
            Step("3D page", ("npm", "run", "build:standalone"), code_app, "app", needs, install, watch=page),
        ]
    if python or app:
        steps.append(Step("Leak scan", (py, "scripts/leak-scan.py"), root, "python", skip_without=root / ".env"))
    return steps


def describe(step: Step) -> str:
    return " ".join(step.command)


def resolve(command: Sequence[str]) -> list[str]:
    """npm and npx are .cmd files on Windows, which subprocess only finds by their full path."""
    return [shutil.which(command[0]) or command[0], *command[1:]]


def run_step(step: Step, runner: Runner = subprocess.run) -> Outcome:
    started = time.monotonic()

    def outcome(status: str, detail: str = "") -> Outcome:
        return Outcome(step, status, detail, time.monotonic() - started)

    if step.skip_without is not None and not step.skip_without.exists():
        return outcome("skipped", f"{step.skip_without.name} not found")
    if step.needs is not None and not step.needs.exists():
        return outcome("failed", step.hint)
    before = step.watch.read_bytes() if step.watch is not None and step.watch.exists() else None
    print(f"\n==> {step.name}: {describe(step)}", flush=True)
    completed = runner(resolve(step.command), cwd=step.cwd)
    if completed.returncode != 0:
        return outcome("failed", f"exit code {completed.returncode}")
    if step.watch is not None and (step.watch.read_bytes() if step.watch.exists() else None) != before:
        return outcome("failed", f"{step.watch.name} changed: commit the rebuilt file")
    return outcome("passed")


def summary(outcomes: Sequence[Outcome]) -> str:
    width = max(len(item.step.name) for item in outcomes)
    lines = [f"{item.step.name:<{width}}  {item.status:<8} {item.seconds:6.1f}s  {item.detail}".rstrip() for item in outcomes]
    failed = [item.step.name for item in outcomes if item.status == "failed"]
    lines.append("")
    lines.append(f"{len(failed)} failed: {', '.join(failed)}" if failed else "All checks passed.")
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None, runner: Runner = subprocess.run, root: Path = ROOT) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--python", action="store_true", help="only the Python checks")
    parser.add_argument("--app", action="store_true", help="only the Code App checks")
    parser.add_argument("--dry-run", action="store_true", help="print the commands without running them")
    args = parser.parse_args(argv)
    both = args.python == args.app
    steps = plan(python=args.python or both, app=args.app or both, root=root)
    if args.dry_run:
        for step in steps:
            print(f"{step.name}: {describe(step)}  (in {step.cwd.relative_to(root).as_posix() or '.'})")
        return 0
    outcomes = [run_step(step, runner) for step in steps]
    print("\n" + summary(outcomes))
    return 1 if any(item.status == "failed" for item in outcomes) else 0


if __name__ == "__main__":
    sys.exit(main())
