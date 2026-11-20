from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))
_spec = importlib.util.spec_from_file_location("provision_qa", SCRIPTS / "provision-qa.py")
provision_qa = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = provision_qa
_spec.loader.exec_module(provision_qa)


def test_search_region_is_left_to_the_template_default_when_not_configured() -> None:
    expected = ("--parameters", "functionPrincipalId=fn", "deployerPrincipalId=me")
    assert provision_qa.deployment_parameters("fn", "me", None) == expected
    assert provision_qa.deployment_parameters("fn", "me", "") == expected


def test_a_configured_search_region_is_passed_to_the_template() -> None:
    assert provision_qa.deployment_parameters("fn", "me", "westus3") == (
        "--parameters", "functionPrincipalId=fn", "deployerPrincipalId=me", "searchLocation=westus3")
