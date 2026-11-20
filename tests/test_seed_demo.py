"""Offline tests for scripts/seed-demo.py: the demo contracts are written the way the analysis flow writes them, in an order
that keeps a half-finished run visible, and a rerun writes nothing."""

from __future__ import annotations

import importlib.util
import itertools
import json
import re
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any, NamedTuple

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))

import checklistlib  # noqa: E402
import schemalib  # noqa: E402

_spec = importlib.util.spec_from_file_location("seed_demo", SCRIPTS / "seed-demo.py")
seed = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = seed  # a dataclass resolves its string annotations through sys.modules
_spec.loader.exec_module(seed)

RUN_LOCAL = seed.load_run_local()
NOW = "2026-10-22T20:00:00Z"
ACCOUNT = "admin@example.test"
DEMO = ("bluepine-sow.pdf", "bluepine-amendment.pdf", "tessera-dua.pdf")


class Reply(NamedTuple):
    headers: dict[str, str]


class FakeDataverse:
    """The three tables in memory. Deleting a contract takes its findings with it, as in Dataverse."""

    def __init__(self, keys: list[str], *, account: str = ACCOUNT, drop_finish: bool = False) -> None:
        self.base_url = "https://example.crm.dynamics.test"
        self.account = account
        self.drop_finish = drop_finish
        self.items = {f"item-{index}": key for index, key in enumerate(keys)}
        self.contracts: dict[str, dict[str, Any]] = {}
        self.findings: list[dict[str, Any]] = []
        self.uploads: dict[str, tuple[str, bytes]] = {}
        self.created_as: dict[str, int] = {}
        self.writes: list[tuple[str, str]] = []  # what was done, to which contract id
        self.reads = 0
        self._ids = itertools.count(1)

    def whoami(self) -> dict[str, Any]:
        return {"UserId": "user-1"}

    def get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        assert path == "systemusers(user-1)"
        return {"domainname": self.account}

    def list(self, path: str, params: dict[str, Any] | None = None) -> Iterator[dict[str, Any]]:
        self.reads += 1
        if path == seed.CHECKLIST:
            return iter([{"vz_checklistitemid": item, "vz_key": key} for item, key in self.items.items()])
        if path == seed.FINDINGS:
            return iter([dict(row) for row in self.findings])
        assert path == seed.CONTRACTS
        return iter([dict(row) for row in self.contracts.values()])

    def request(self, method: str, path: str, *, body: dict[str, Any] | None = None,
                headers: dict[str, str] | None = None) -> Reply | None:
        body = body or {}
        if method == "POST" and path == seed.CONTRACTS:
            row_id = self.add_contract(body["vz_name"], body["vz_status"])
            self.created_as[row_id] = body["vz_status"]
            self.writes.append(("create", row_id))
            return Reply({"OData-EntityId": f"https://example.test/api/data/v9.2/{seed.CONTRACTS}({row_id})"})
        if method == "POST" and path == seed.FINDINGS:
            contract = re.fullmatch(rf"{seed.CONTRACTS}\((.+)\)", body["vz_contract@odata.bind"]).group(1)
            key = re.fullmatch(rf"{seed.CHECKLIST}\(vz_key='(\w+)'\)", body["vz_checklistitem@odata.bind"]).group(1)
            self.add_finding(contract, key, **{name: value for name, value in body.items() if "@" not in name})
            self.writes.append(("finding", contract))
            return None
        row_id = re.fullmatch(rf"{seed.CONTRACTS}\((.+)\)", path).group(1)
        if method == "DELETE":
            del self.contracts[row_id]
            self.findings = [row for row in self.findings if row["_vz_contract_value"] != row_id]
            self.writes.append(("delete", row_id))
        elif method == "PATCH":
            assert headers == {"If-Match": "*"}
            if not self.drop_finish:
                self.contracts[row_id].update(body)
            self.writes.append(("finish", row_id))
        else:
            raise AssertionError(f"unexpected {method} {path}")
        return None

    def upload_file(self, row: str, column: str, file_name: str, content: bytes) -> None:
        row_id = re.fullmatch(rf"{seed.CONTRACTS}\((.+)\)", row).group(1)
        assert column == "vz_document"
        self.contracts[row_id]["vz_document_name"] = file_name
        self.uploads[row_id] = (file_name, content)
        self.writes.append(("upload", row_id))

    def reset_affinity(self) -> None:
        pass

    # --- set-up and inspection, which are not writes by the script -----------------------------------------------

    def add_contract(self, name: str, status: int, *, document: bool = False, findings: list[str] | None = None,
                     sharepoint_item: str | None = None) -> str:
        row_id = f"contract-{next(self._ids)}"
        self.contracts[row_id] = {"vz_contractid": row_id, "vz_name": name, "vz_status": status,
                                  "vz_document_name": name if document else None, "vz_sharepointitemid": sharepoint_item}
        for key in findings or []:
            self.add_finding(row_id, key)
        return row_id

    def add_finding(self, contract: str, key: str, **columns: Any) -> None:
        item = next(item for item, known in self.items.items() if known == key)
        self.findings.append({"_vz_contract_value": contract, "_vz_checklistitem_value": item, **columns})

    def ids(self, name: str) -> list[str]:
        return [row_id for row_id, row in self.contracts.items() if row["vz_name"] == name]

    def count(self, row_id: str) -> int:
        return sum(row["_vz_contract_value"] == row_id for row in self.findings)

    def steps(self, row_id: str) -> list[str]:
        return [what for what, target in self.writes if target == row_id]


def quiet(_line: str) -> None:
    pass


def make_pdf(path: Path, text: str) -> Path:
    canvas = pytest.importorskip("reportlab.pdfgen.canvas")
    pytest.importorskip("pypdf")
    page = canvas.Canvas(str(path))
    page.drawString(72, 720, text)
    page.save()
    return path


def saved_result(keys: list[str], document_type: str = "SOW") -> dict[str, Any]:
    findings = []
    for index, key in enumerate(keys):
        found = index % 4 != 3
        findings.append({
            "key": key, "presence": "Found" if found else "Not Found", "value": f"value {index}",
            "judgment": "Permitted" if found else "Not Addressed", "conditions": "", "clause": f"clause {index}",
            "page": index + 1 if found else None,
            "sourceRegions": [{"page": 1, "polygon": [0, 0, 1, 0, 1, 1, 0, 1]}] if found else [], "confidence": 0.9})
    contract = {"vendor": "Acme Data, Inc.", "vizientEntity": "Vizient, Inc.", "documentType": document_type,
                "contractIdentifier": "AC-1", "effectiveDate": "2025-01-15", "expirationDate": "2028-01-14",
                "hasParentReference": True, "foundCount": 15, "totalCount": 20, "completeness": 75.0}
    return {"contract": contract, "findings": findings, "raw": {"fields": {"a": "b"}}}


@pytest.fixture(scope="module")
def schema() -> dict[str, Any]:
    return schemalib.load_schema()


@pytest.fixture(scope="module")
def rules(schema: dict[str, Any]) -> Any:
    return seed.rules_from(schema)


@pytest.fixture(scope="module")
def keys(schema: dict[str, Any]) -> list[str]:
    return [item["key"] for item in checklistlib.analyzer_items(checklistlib.load_checklist(schema=schema))]


@pytest.fixture(autouse=True)
def cached_run_local(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(seed, "load_run_local", lambda: RUN_LOCAL)


def write_samples(directory: Path, keys: list[str], marker: str = "SYNTHETIC SAMPLE - TEST") -> Path:
    (directory / "results").mkdir(parents=True, exist_ok=True)
    for stem in seed.DEMO_CONTRACTS:
        make_pdf(directory / f"{stem}.pdf", f"{marker} {stem}")
        (directory / "results" / f"{stem}.json").write_text(json.dumps(saved_result(keys)), encoding="utf-8")
    return directory


@pytest.fixture(scope="module")
def sample_dir(tmp_path_factory: pytest.TempPathFactory, keys: list[str]) -> Path:
    return write_samples(tmp_path_factory.mktemp("samples"), keys)


@pytest.fixture(scope="module")
def samples(sample_dir: Path, keys: list[str], rules: Any) -> list[Any]:
    return seed.load_samples(sample_dir, keys, rules, NOW)


def sync(dv: FakeDataverse, samples: list[Any], rules: Any, **kwargs: Any) -> list[Any]:
    return seed.sync(dv, samples, rules, log=quiet, **kwargs)


# --- the rows ----------------------------------------------------------------------------------------------------------

def test_a_contract_is_mapped_the_way_the_analysis_flow_writes_it(samples: list[Any], rules: Any, keys: list[str]) -> None:
    sow = samples[0]
    assert [sample.name for sample in samples] == list(DEMO)
    assert sow.created == {"vz_name": "bluepine-sow.pdf", "vz_status": rules.status["Received"]}
    assert sow.finished | {"vz_processedon": None} == {
        "vz_vendor": "Acme Data, Inc.", "vz_viziententity": "Vizient, Inc.", "vz_contractidentifier": "AC-1",
        "vz_documenttype": rules.kinds["SOW"], "vz_effectivedate": "2025-01-15", "vz_expirationdate": "2028-01-14",
        "vz_hasparentreference": True, "vz_foundcount": 15, "vz_totalcount": 20, "vz_completeness": 75.0,
        "vz_processedon": None, "vz_rawresult": '{"fields":{"a":"b"}}', "vz_status": rules.status["Ready for Review"]}
    assert sow.finished["vz_processedon"] == NOW
    found, not_found = sow.findings[keys[0]], sow.findings[keys[3]]
    assert found["vz_name"] == f"bluepine-sow.pdf - {keys[0]}"
    assert found["vz_checklistitem@odata.bind"] == f"vz_checklistitems(vz_key='{keys[0]}')"
    assert (found["vz_presence"], found["vz_aijudgment"], found["vz_page"]) == (
        rules.presence["Found"], rules.judgment["Permitted"], 1)
    assert found["vz_sourceregions"] == '[{"page":1,"polygon":[0,0,1,0,1,1,0,1]}]'
    assert (not_found["vz_presence"], not_found["vz_aijudgment"], not_found["vz_page"], not_found["vz_sourceregions"]) == (
        rules.presence["Not Found"], rules.judgment["Not Addressed"], None, "[]")


def test_values_a_column_would_reject_are_cleaned_as_the_flow_cleans_them(keys: list[str], rules: Any) -> None:
    saved = saved_result(keys)
    saved["contract"].update(documentType="Lease", effectiveDate="soon", vendor="x" * 999, hasParentReference="yes")
    saved["findings"][0].update(judgment="", presence="Maybe")
    saved["raw"] = {"text": "y" * rules.raw_limit}
    sample = seed.build_sample("odd.pdf", b"%PDF-", saved, keys, rules, NOW)
    assert sample.finished["vz_documenttype"] == rules.kinds["Other"]
    assert sample.finished["vz_effectivedate"] is None
    assert len(sample.finished["vz_vendor"]) == rules.text_length["vz_vendor"]
    assert sample.finished["vz_hasparentreference"] is False
    assert sample.finished["vz_rawresult"] is None
    assert sample.findings[keys[0]]["vz_aijudgment"] is None
    assert sample.findings[keys[0]]["vz_presence"] == rules.presence["Unclear"]


@pytest.mark.parametrize(("change", "message"), [
    (lambda saved: saved["findings"].pop(), "lacks"),
    (lambda saved: saved["findings"].append({"key": "Surprise"}), "unknown Surprise"),
    (lambda saved: saved["findings"].append(dict(saved["findings"][0])), "twice"),
    (lambda saved: saved.pop("raw"), "must hold contract, findings and raw"),
])
def test_a_result_that_does_not_cover_the_checklist_is_refused(keys: list[str], rules: Any, change: Any, message: str) -> None:
    saved = saved_result(keys)
    change(saved)
    with pytest.raises(seed.SeedError, match=message):
        seed.build_sample("odd.pdf", b"%PDF-", saved, keys, rules, NOW)


def test_a_pdf_without_the_synthetic_marker_is_refused(tmp_path: Path, keys: list[str], rules: Any) -> None:
    write_samples(tmp_path, keys, marker="an ordinary agreement")
    with pytest.raises(seed.SeedError, match="not marked 'SYNTHETIC SAMPLE'"):
        seed.load_samples(tmp_path, keys, rules, NOW)


def test_a_missing_saved_result_says_how_to_make_it(tmp_path: Path, keys: list[str], rules: Any) -> None:
    write_samples(tmp_path, keys)
    (tmp_path / "results" / "tessera-dua.json").unlink()
    with pytest.raises(seed.SeedError, match=r"run-local\.py samples/tessera-dua\.pdf"):
        seed.load_samples(tmp_path, keys, rules, NOW)


# --- Dataverse ---------------------------------------------------------------------------------------------------------

def test_an_empty_environment_is_filled_and_a_second_run_writes_nothing(samples: list[Any], rules: Any,
                                                                         keys: list[str]) -> None:
    dv = FakeDataverse(keys)
    steps = sync(dv, samples, rules, apply=True)
    assert [step.action for step in steps] == ["keep"] * 3
    created = [dv.contracts[row_id]["vz_name"] for what, row_id in dv.writes if what == "create"]
    assert created == ["tessera-dua.pdf", "bluepine-amendment.pdf", "bluepine-sow.pdf"]
    for sample in samples:
        (row_id,) = dv.ids(sample.name)
        assert dv.steps(row_id) == ["create", "upload"] + ["finding"] * len(keys) + ["finish"]
        assert dv.created_as[row_id] == rules.status["Received"]
        assert dv.contracts[row_id]["vz_status"] == rules.status["Ready for Review"]
        assert dv.uploads[row_id] == (sample.name, sample.pdf)
    dv.writes.clear()
    assert [step.action for step in sync(dv, samples, rules, apply=True)] == ["keep"] * 3
    assert dv.writes == []


def test_status_reads_and_writes_nothing(samples: list[Any], rules: Any, keys: list[str]) -> None:
    dv = FakeDataverse(keys)
    assert [step.action for step in sync(dv, samples, rules, apply=False)] == ["create"] * 3
    assert dv.writes == [] and dv.contracts == {}


def test_a_half_written_contract_is_finished_not_duplicated(samples: list[Any], rules: Any, keys: list[str]) -> None:
    dv = FakeDataverse(keys)
    started = dv.add_contract("tessera-dua.pdf", rules.status["Received"], document=True, findings=keys[:5])
    steps = sync(dv, samples, rules, apply=True)
    assert [step.action for step in steps] == ["keep"] * 3
    assert dv.ids("tessera-dua.pdf") == [started]
    assert dv.steps(started) == ["finding"] * (len(keys) - 5) + ["finish"]
    assert dv.count(started) == len(keys)
    assert dv.contracts[started]["vz_status"] == rules.status["Ready for Review"]


def test_a_contract_in_another_state_is_left_alone_until_reset(samples: list[Any], rules: Any, keys: list[str]) -> None:
    dv = FakeDataverse(keys)
    failed = dv.add_contract("tessera-dua.pdf", rules.status["Failed"])
    steps = sync(dv, samples, rules, apply=True)
    assert [step.action for step in steps] == ["keep", "keep", "blocked"]
    assert "Failed; no document" in steps[2].note and "--reset" in steps[2].note
    assert dv.steps(failed) == [] and dv.ids("tessera-dua.pdf") == [failed]

    steps = sync(dv, samples, rules, apply=True, reset=True)
    assert [step.action for step in steps] == ["keep"] * 3
    assert failed not in dv.contracts and len(dv.ids("tessera-dua.pdf")) == 1
    assert all(dv.count(row_id) == len(keys) for name in DEMO for row_id in dv.ids(name))


def test_contracts_that_came_through_sharepoint_are_never_touched(samples: list[Any], rules: Any, keys: list[str]) -> None:
    dv = FakeDataverse(keys)
    live = dv.add_contract("bluepine-sow.pdf", rules.status["Extracting"], document=True, sharepoint_item="7")
    sync(dv, samples, rules, apply=True)
    assert len(dv.ids("bluepine-sow.pdf")) == 2 and dv.steps(live) == []
    sync(dv, samples, rules, apply=True, reset=True)
    assert len(dv.ids("bluepine-sow.pdf")) == 2 and "delete" not in dv.steps(live)
    assert dv.contracts[live]["vz_status"] == rules.status["Extracting"]


def test_a_reset_replaces_every_copy_but_a_plain_run_refuses_duplicates(samples: list[Any], rules: Any,
                                                                         keys: list[str]) -> None:
    dv = FakeDataverse(keys)
    old = [dv.add_contract("bluepine-sow.pdf", rules.status["Approved"]) for _ in range(2)]
    with pytest.raises(seed.SeedError, match="2 contracts named bluepine-sow.pdf"):
        sync(dv, samples, rules, apply=True)
    assert dv.writes == []
    sync(dv, samples, rules, apply=True, reset=True)
    assert not set(old) & set(dv.contracts) and len(dv.ids("bluepine-sow.pdf")) == 1


def test_a_missing_checklist_row_stops_before_any_write(samples: list[Any], rules: Any, keys: list[str]) -> None:
    dv = FakeDataverse(keys[:-1])
    with pytest.raises(seed.SeedError, match=rf"no row for {keys[-1]}.*seed-checklist\.py"):
        sync(dv, samples, rules, apply=True)
    assert dv.writes == []


def test_a_write_that_does_not_land_is_reported(samples: list[Any], rules: Any, keys: list[str]) -> None:
    with pytest.raises(seed.SeedError, match="still differ from the saved results"):
        sync(FakeDataverse(keys, drop_finish=True), samples, rules, apply=True)


# --- the command line --------------------------------------------------------------------------------------------------

def test_an_offline_run_sends_nothing(monkeypatch: pytest.MonkeyPatch, sample_dir: Path,
                                      capsys: pytest.CaptureFixture[str]) -> None:
    def refuse(*_args: Any, **_kwargs: Any) -> None:
        raise AssertionError("an offline run must not connect to Dataverse")

    monkeypatch.setattr(seed, "DEFAULT_SAMPLES", sample_dir)
    monkeypatch.setattr(seed, "Dataverse", refuse)
    assert seed.main([]) == 0
    assert "Nothing was sent" in capsys.readouterr().out


def test_the_wrong_account_stops_the_run_before_it_reads_anything(monkeypatch: pytest.MonkeyPatch, sample_dir: Path,
                                                                   keys: list[str],
                                                                   capsys: pytest.CaptureFixture[str]) -> None:
    dv = FakeDataverse(keys, account="someone@example.test")
    monkeypatch.setattr(seed, "DEFAULT_SAMPLES", sample_dir)
    monkeypatch.setattr(seed, "Dataverse", lambda _skill: dv)
    monkeypatch.setenv("AZURE_ACCOUNT", ACCOUNT)
    assert seed.main(["--apply"]) == 1
    assert f"AZURE_ACCOUNT expects {ACCOUNT}" in capsys.readouterr().out
    assert dv.reads == 0 and dv.writes == []


def test_main_reports_whether_the_demo_data_is_in_place(monkeypatch: pytest.MonkeyPatch, sample_dir: Path,
                                                         keys: list[str], capsys: pytest.CaptureFixture[str]) -> None:
    dv = FakeDataverse(keys)
    monkeypatch.setattr(seed, "DEFAULT_SAMPLES", sample_dir)
    monkeypatch.setattr(seed, "Dataverse", lambda _skill: dv)
    monkeypatch.setenv("AZURE_ACCOUNT", ACCOUNT)
    assert seed.main(["--status"]) == 1 and dv.writes == []
    assert seed.main(["--apply"]) == 0
    assert seed.main(["--status"]) == 0
    assert "3 in place" in capsys.readouterr().out
