"""Run the Azure CLI against this project's subscription, as this project's account, and nothing else.

    python scripts/az.py provider show --namespace Microsoft.Web -o table

The machine's default subscription is not the project's, so every call gets --subscription from .env
(AZURE_SUBSCRIPTION_ID). A call runs only when the CLI is signed in to TENANT_ID as AZURE_ACCOUNT. Commands that
change the CLI's own sign-in state (login, logout, account set) are refused.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import auth  # noqa: E402

BUNDLED_PYTHON = Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Microsoft SDKs" / "Azure" / "CLI2" / "python.exe"
REFUSED = (("login",), ("logout",), ("account", "set"), ("account", "clear"))


class AzError(RuntimeError):
    """A refusal or failure worth one clear line."""


def az_command() -> list[str]:
    """The CLI through its bundled Python when present, which keeps cmd.exe from re-parsing arguments."""
    if BUNDLED_PYTHON.exists():
        return [str(BUNDLED_PYTHON), "-IBm", "azure.cli"]
    found = shutil.which("az")
    if not found:
        raise AzError("the Azure CLI is not installed")
    return [found]


def check_signed_in(account: Mapping[str, Any], tenant: str, expected: str | None) -> str:
    user = str((account.get("user") or {}).get("name") or "an unknown account")
    if account.get("tenantId") != tenant:
        raise AzError(f"the Azure CLI is signed in as {user}, which is not in the project tenant. "
                      f"Run: az login --tenant {tenant}")
    if expected and user.lower() != expected.lower():
        raise AzError(f"the Azure CLI is signed in as {user}, but AZURE_ACCOUNT expects {expected}")
    return user


def run(args: Sequence[str], env: Mapping[str, str], runner: Callable[..., Any] = subprocess.run) -> int:
    words = tuple(arg for arg in args if not arg.startswith("-"))
    if any(words[:len(refused)] == refused for refused in REFUSED):
        raise AzError(f"'az {' '.join(words[:2])}' changes the CLI's own state and is not allowed here")
    if any(arg in ("--subscription", "-s") or arg.startswith("--subscription=") for arg in args):
        raise AzError("do not pass --subscription; it is added from .env")
    subscription, tenant = env.get("AZURE_SUBSCRIPTION_ID", ""), env.get("TENANT_ID", "")
    if not subscription or not tenant:
        raise AzError("AZURE_SUBSCRIPTION_ID and TENANT_ID must be set in .env")

    base = az_command()
    shown = runner([*base, "account", "show", "--subscription", subscription, "-o", "json", "--only-show-errors"],
                   capture_output=True, text=True, check=False)
    if shown.returncode != 0:
        raise AzError(f"the Azure CLI cannot see the project subscription. Sign in with: az login --tenant {tenant}")
    account = json.loads(shown.stdout)
    user = check_signed_in(account, tenant, env.get("AZURE_ACCOUNT") or None)
    print(f"az: {user}, subscription {account.get('name')}", file=sys.stderr)
    return runner([*base, *args, "--subscription", subscription, "--only-show-errors"], check=False).returncode


def main(argv: Sequence[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args:
        print(__doc__)
        return 2
    try:
        auth.load_env()
        return run(args, os.environ)
    except AzError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
