"""Offline tests for scripts/az.py: a recording runner stands in for the Azure CLI."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import az  # noqa: E402

ENV = {"AZURE_SUBSCRIPTION_ID": "sub-1", "TENANT_ID": "tenant-1", "AZURE_ACCOUNT": "admin@demo.onmicrosoft.com"}


class Runner:
    def __init__(self, user: str = "Admin@demo.onmicrosoft.com", tenant: str = "tenant-1", signed_in: bool = True) -> None:
        self.calls: list[list[str]] = []
        self.account = {"name": "IT", "tenantId": tenant, "user": {"name": user}}
        self.signed_in = signed_in

    def __call__(self, command: list[str], **_kwargs: Any) -> Any:
        self.calls.append(command)
        if command[1:3] == ["account", "show"]:
            return SimpleNamespace(returncode=0 if self.signed_in else 1, stdout=json.dumps(self.account))
        return SimpleNamespace(returncode=0, stdout="")


@pytest.fixture(autouse=True)
def plain_az(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(az, "az_command", lambda: ["az"])


def test_a_call_is_pinned_to_the_project_subscription_after_the_identity_check() -> None:
    runner = Runner()
    assert az.run(["provider", "show", "--namespace", "Microsoft.Web"], ENV, runner) == 0
    assert runner.calls == [
        ["az", "account", "show", "--subscription", "sub-1", "-o", "json", "--only-show-errors"],
        ["az", "provider", "show", "--namespace", "Microsoft.Web", "--subscription", "sub-1", "--only-show-errors"]]


@pytest.mark.parametrize(("runner", "message"), [
    (Runner(tenant="corp-tenant"), "not in the project tenant"),
    (Runner(user="someone@microsoft.com"), "AZURE_ACCOUNT expects"),
    (Runner(signed_in=False), "cannot see the project subscription"),
])
def test_a_wrong_or_missing_sign_in_runs_nothing_else(runner: Runner, message: str) -> None:
    with pytest.raises(az.AzError, match=message):
        az.run(["group", "list"], ENV, runner)
    assert len(runner.calls) == 1


@pytest.mark.parametrize("args", [
    ["account", "set", "--subscription", "x"], ["login"], ["logout"],
    ["group", "list", "--subscription", "other"], ["group", "list", "-s", "other"]])
def test_commands_that_change_the_cli_or_pick_another_subscription_are_refused(args: list[str]) -> None:
    runner = Runner()
    with pytest.raises(az.AzError):
        az.run(args, ENV, runner)
    assert runner.calls == []
