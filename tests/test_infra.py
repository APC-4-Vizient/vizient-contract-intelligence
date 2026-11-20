"""Offline checks on the Bicep templates and how azd feeds them.

azd substitutes `${NAME}` in infra/main.parameters.json from the azd environment, which holds text, so a parameter
filled that way has to be a string (or an array or object, which azd parses from JSON). A bool or int parameter would
fail in ARM the first time someone sets the value.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import az  # noqa: E402

PARAMETERS = ROOT / "infra" / "main.parameters.json"
MAIN = ROOT / "infra" / "main.bicep"
RUNBOOK = ROOT / "docs" / "deployment-runbook.md"
# Signs that the Bicep module registry could not be reached, as opposed to a template that does not compile.
UNREACHABLE = ("error occurred while sending the request", "no such host", "name or service not known",
               "timed out", "unable to connect", "connection refused", "ssl")


def declared_parameters(bicep: str) -> dict[str, str]:
    """Parameter name -> declared type, for the `param name type` lines of a Bicep file."""
    return dict(re.findall(r"^param\s+(\w+)\s+([\w\[\]?]+)", bicep, flags=re.MULTILINE))


def is_text_type(kind: str) -> bool:
    """True for the types azd can fill from an environment value: text, or JSON it parses into an array or object."""
    return kind.rstrip("?") in {"string", "array", "object"} or kind.rstrip("?").endswith("[]")


def azd_variables(parameters: dict) -> dict[str, list[str]]:
    """Parameter name -> the azd environment variables its value is built from."""
    found = {}
    for name, entry in parameters["parameters"].items():
        value = entry.get("value")
        found[name] = re.findall(r"\$\{(\w+)\}", value) if isinstance(value, str) else []
    return found


def test_every_parameters_file_entry_is_a_declared_parameter() -> None:
    declared = declared_parameters(MAIN.read_text(encoding="utf-8"))
    entries = json.loads(PARAMETERS.read_text(encoding="utf-8"))["parameters"]
    assert set(entries) <= set(declared), f"main.bicep does not declare: {sorted(set(entries) - set(declared))}"


def test_parameters_filled_from_azd_are_text_typed() -> None:
    declared = declared_parameters(MAIN.read_text(encoding="utf-8"))
    parameters = json.loads(PARAMETERS.read_text(encoding="utf-8"))
    wrong = {name: declared[name] for name, variables in azd_variables(parameters).items()
             if variables and not is_text_type(declared[name])}
    assert not wrong, f"azd passes environment values as text, so these must be string, array or object: {wrong}"


def test_every_azd_variable_is_documented_in_the_deployment_runbook() -> None:
    runbook = RUNBOOK.read_text(encoding="utf-8")
    parameters = json.loads(PARAMETERS.read_text(encoding="utf-8"))
    missing = sorted({variable for variables in azd_variables(parameters).values() for variable in variables
                      if f"`{variable}`" not in runbook})
    assert not missing, f"add these azd values to the table in section 3.2 of docs/deployment-runbook.md: {missing}"


def test_templates_compile() -> None:
    try:
        az_command = az.az_command()
        installed = subprocess.run([*az_command, "bicep", "version"], capture_output=True, check=False, timeout=90)
    except (az.AzError, subprocess.TimeoutExpired):
        pytest.skip("the Azure CLI or its Bicep tool is not available")
    if installed.returncode != 0:
        pytest.skip("the Bicep tool is not installed")
    result = subprocess.run([*az_command, "bicep", "build", "--file", str(MAIN), "--stdout"],
                            capture_output=True, text=True, check=False, timeout=300)
    if result.returncode != 0 and "restore" in result.stderr.lower() \
            and any(phrase in result.stderr.lower() for phrase in UNREACHABLE):
        pytest.skip("the Bicep module registry is not reachable")
    assert result.returncode == 0, result.stderr[-2000:]
