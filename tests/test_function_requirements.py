"""function/requirements.txt: every direct dependency of the deployed Function is pinned to one version, each pin lies inside the range that
requirements-tools.txt lets the tests run against, and the platform's own worker package is not listed."""

from __future__ import annotations

from pathlib import Path

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name
from packaging.version import Version

ROOT = Path(__file__).resolve().parent.parent
DEPLOYED_FILE = ROOT / "function" / "requirements.txt"


def read(path: Path) -> dict[str, Requirement]:
    lines = (line.split("#", 1)[0].strip() for line in path.read_text(encoding="utf-8").splitlines())
    requirements = [Requirement(line) for line in lines if line and not line.startswith("-")]
    return {canonicalize_name(requirement.name): requirement for requirement in requirements}


def pinned(requirement: Requirement) -> Version:
    """The version of a requirement that says `==` and nothing else."""
    pins = list(requirement.specifier)
    assert len(pins) == 1 and pins[0].operator == "==" and "*" not in pins[0].version, f"{requirement} is not pinned to one exact version"
    return Version(pins[0].version)


def test_every_direct_dependency_is_pinned_to_one_exact_version() -> None:
    deployed = read(DEPLOYED_FILE)

    assert deployed
    for requirement in deployed.values():
        pinned(requirement)


def test_each_pin_is_inside_the_range_the_tests_run_against() -> None:
    ranges = read(ROOT / "requirements-tools.txt")

    for name, requirement in read(DEPLOYED_FILE).items():
        assert name in ranges, f"{name} is deployed, but requirements-tools.txt does not install it for the tests"
        assert pinned(requirement) in ranges[name].specifier, f"{requirement} is outside {name}{ranges[name].specifier}"


def test_the_platforms_python_worker_is_not_listed_and_the_warning_stays() -> None:
    assert "azure-functions-worker" not in read(DEPLOYED_FILE)
    assert DEPLOYED_FILE.read_text(encoding="utf-8").startswith("# DO NOT include azure-functions-worker in this file")
