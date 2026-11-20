"""Offline tests for scripts/leak-scan.py: project identifiers are found wherever they hide, and a report never repeats one."""

from __future__ import annotations

import importlib.util
import sys
import zipfile
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"

_spec = importlib.util.spec_from_file_location("leak_scan", SCRIPTS / "leak-scan.py")
leak = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = leak
_spec.loader.exec_module(leak)

TENANT = "11111111-2222-3333-4444-555555555555"
ORG_HOST = "orgabc123456.crm.dynamics.com"
ACCOUNT = "admin@Contosolab123.onmicrosoft.com"


@pytest.fixture
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    (tmp_path / ".env").write_text(
        "\n".join([
            f"TENANT_ID={TENANT}",
            f'DATAVERSE_URL="https://{ORG_HOST}/"',
            "SHAREPOINT_SITE_URL=https://othertenant9.sharepoint.com/sites/x",
            "CU_ENDPOINT=https://aif-demo-abc123.services.ai.azure.com/",
            f"AZURE_ACCOUNT={ACCOUNT}",
            "MCP_CLIENT_ID=aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
            "SOLUTION_NAME=VizientContractPOC",
            "AZURE_LOCATION=eastus2",
            "CONNECTION_NAME=0123456789abcdef0123456789abcdef",
        ]),
        encoding="utf-8",
    )
    monkeypatch.setattr(leak, "ROOT", tmp_path)
    return tmp_path


def test_only_ids_accounts_and_tenant_addresses_are_identifiers(project: Path) -> None:
    found = leak.project_identifiers(project)

    assert found[TENANT] == "TENANT_ID"
    assert found[TENANT.replace("-", "")] == "TENANT_ID"
    assert found[ORG_HOST] == "DATAVERSE_URL host"
    assert found["orgabc123456"] == "DATAVERSE_URL host"
    assert found["othertenant9.sharepoint.com"] == "SHAREPOINT_SITE_URL host"
    assert found["othertenant9"] == "SHAREPOINT_SITE_URL host"
    assert found[ACCOUNT.lower()] == "AZURE_ACCOUNT"
    assert found["contosolab123"] == "AZURE_ACCOUNT domain"
    assert found["0123456789abcdef0123456789abcdef"] == "CONNECTION_NAME"
    assert not {"vizientcontractpoc", "eastus2", "aif-demo-abc123.services.ai.azure.com", "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"} & set(found)


def test_a_report_names_the_setting_and_the_line_but_never_the_value(project: Path, capsys: pytest.CaptureFixture[str]) -> None:
    docs = project / "docs"
    docs.mkdir()
    (docs / "notes.md").write_text(f"clean line\nthe tenant is {TENANT.upper()} here\nand {ORG_HOST}\n", encoding="utf-8")

    code = leak.main([str(docs)])

    out = capsys.readouterr().out
    assert code == 1
    assert "docs/notes.md:2  TENANT_ID" in out
    assert "docs/notes.md:3  DATAVERSE_URL host" in out
    assert TENANT not in out.lower() and "orgabc123456" not in out.lower()


def test_a_folder_without_identifiers_is_clean(project: Path, capsys: pytest.CaptureFixture[str]) -> None:
    docs = project / "docs"
    docs.mkdir()
    (docs / "notes.md").write_text("Solution VizientContractPOC lives in eastus2.\n", encoding="utf-8")

    assert leak.main([str(docs)]) == 0
    assert capsys.readouterr().out.startswith("CLEAN: 1 files read")


def test_binary_files_are_listed_not_read(project: Path, capsys: pytest.CaptureFixture[str]) -> None:
    (project / "app.bin").write_bytes(b"\0\0" + TENANT.encode())

    assert leak.main([str(project / "app.bin")]) == 0
    assert "Not read (1 binary or very large): app.bin" in capsys.readouterr().out


def office_file(path: Path, parts: dict[str, str]) -> Path:
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as package:
        for part, text in parts.items():
            package.writestr(part, text)
    return path


def test_office_files_are_read_part_by_part(project: Path, capsys: pytest.CaptureFixture[str]) -> None:
    book = office_file(project / "sizing.xlsx", {"xl/sharedStrings.xml": f"<sst><si><t>{TENANT}</t></si></sst>", "docProps/core.xml": "<cp/>"})

    assert leak.main([str(book)]) == 1
    out = capsys.readouterr().out
    assert "sizing.xlsx!xl/sharedStrings.xml  TENANT_ID" in out
    assert TENANT not in out
    assert "Not read" not in out


def test_a_clean_office_file_counts_as_read(project: Path, capsys: pytest.CaptureFixture[str]) -> None:
    book = office_file(project / "sizing.xlsx", {"xl/sharedStrings.xml": "<sst><si><t>nothing here</t></si></sst>"})

    assert leak.main([str(book)]) == 0
    assert capsys.readouterr().out.startswith("CLEAN: 1 files read")


def test_a_plain_zip_is_read_member_by_member_whatever_the_member_type(project: Path, capsys: pytest.CaptureFixture[str]) -> None:
    export = office_file(project / "solution.zip", {"customizations.xml": "<x/>", "Workflows/a.json": f'{{"site": "{ORG_HOST}"}}'})
    with zipfile.ZipFile(export, "a") as package:
        package.writestr("CanvasApps/app.bin", b"\0\1\2" + TENANT.encode())

    assert leak.main([str(export)]) == 1
    out = capsys.readouterr().out
    assert "solution.zip!Workflows/a.json  DATAVERSE_URL" in out
    assert "app.bin" not in out and ORG_HOST not in out


def test_a_file_name_can_carry_an_identifier(project: Path, capsys: pytest.CaptureFixture[str]) -> None:
    (project / f"export-{TENANT}.txt").write_text("nothing here\n", encoding="utf-8")

    assert leak.main([str(project / f"export-{TENANT}.txt")]) == 1
    out = capsys.readouterr().out
    assert "export-<TENANT_ID>.txt  (file name)" in out
    assert TENANT not in out


def test_the_azd_environment_contributes_its_ids(project: Path) -> None:
    azd = project / ".azure" / "dev"
    azd.mkdir(parents=True)
    (azd / ".env").write_text(
        "AZURE_PRINCIPAL_ID=99999999-8888-7777-6666-555555555555\nSERVICE_API_URI=https://func-api-demo.azurewebsites.net\n",
        encoding="utf-8",
    )

    found = leak.project_identifiers(project)

    assert found["99999999-8888-7777-6666-555555555555"] == "AZURE_PRINCIPAL_ID (azd)"
    assert "func-api-demo.azurewebsites.net" not in found


def test_it_stops_when_there_is_nothing_to_look_for(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr(leak, "ROOT", tmp_path)

    assert leak.main([str(tmp_path)]) == 2
    assert "no identifiers to look for" in capsys.readouterr().out
