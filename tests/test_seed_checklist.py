"""Offline tests for scripts/seed-checklist.py: the table ends up matching checklist.json, and a rerun writes nothing."""

from __future__ import annotations

import importlib.util
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any, NamedTuple

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))

import checklistlib  # noqa: E402
import schemalib  # noqa: E402

_spec = importlib.util.spec_from_file_location("seed_checklist", SCRIPTS / "seed-checklist.py")
seed = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = seed  # a dataclass resolves its string annotations through sys.modules
_spec.loader.exec_module(seed)

ENTITY_SET = "vz_checklistitems"


class Write(NamedTuple):
    method: str
    path: str
    body: dict[str, Any]
    headers: dict[str, str]


class FakeDataverse:
    """The vz_checklistitem table in memory. Like Dataverse, it hands multi-line text back with CRLF line breaks
    and has no way to delete: a DELETE from the script would fail the test."""

    def __init__(self, *, account: str = "admin@example.test", table_exists: bool = True,
                 drop_writes: bool = False) -> None:
        self.base_url = "https://example.crm.dynamics.test"
        self.account = account
        self.table_exists = table_exists
        self.drop_writes = drop_writes
        self.rows: dict[str, dict[str, Any]] = {}
        self.writes: list[Write] = []

    def whoami(self) -> dict[str, Any]:
        return {"UserId": "user-1"}

    def get(self, path: str, params: dict[str, Any] | None = None, *, missing_ok: bool = False) -> dict[str, Any] | None:
        if path == "EntityDefinitions(LogicalName='vz_checklistitem')":
            return {"EntitySetName": ENTITY_SET} if self.table_exists else None
        if path == "systemusers(user-1)":
            return {"domainname": self.account, "internalemailaddress": self.account}
        raise AssertionError(f"unexpected GET {path}")

    def list(self, path: str, params: dict[str, Any] | None = None) -> Iterator[dict[str, Any]]:
        assert path == ENTITY_SET
        return iter([dict(row) for row in self.rows.values()])

    def request(self, method: str, path: str, *, body: dict[str, Any] | None = None,
                headers: dict[str, str] | None = None) -> None:
        assert method in ("POST", "PATCH"), f"{method} {path}: this script never deletes"
        self.writes.append(Write(method, path, body or {}, headers or {}))
        if self.drop_writes:
            return
        stored = dict(body or {})
        if "vz_definition" in stored:
            stored["vz_definition"] = stored["vz_definition"].replace("\r\n", "\n").replace("\n", "\r\n")
        if method == "POST":
            assert path == ENTITY_SET
            self.add(stored)
        else:
            self.rows[path.removeprefix(f"{ENTITY_SET}(").removesuffix(")")].update(stored)

    def add(self, row: dict[str, Any]) -> str:
        row_id = f"row-{len(self.rows) + 1}"
        self.rows[row_id] = {seed.ID_COLUMN: row_id, **row}
        return row_id

    def reset_affinity(self) -> None:
        pass

    def row(self, key: str) -> dict[str, Any]:
        return next(row for row in self.rows.values() if row["vz_key"] == key)


@pytest.fixture
def wanted() -> list[dict[str, Any]]:
    schema = schemalib.load_schema()
    return checklistlib.seed_rows(checklistlib.load_checklist(schema=schema), schema)


def quiet(_line: str) -> None:
    pass


def filled(wanted: list[dict[str, Any]]) -> FakeDataverse:
    dv = FakeDataverse()
    seed.sync(dv, wanted, apply=True, log=quiet)
    dv.writes.clear()
    return dv


def test_an_empty_table_is_filled_and_a_second_run_writes_nothing(wanted: list[dict[str, Any]]) -> None:
    dv = FakeDataverse()
    plan = seed.sync(dv, wanted, apply=True, log=quiet)
    assert plan.in_sync and plan.unchanged == len(wanted)
    assert [write.method for write in dv.writes] == ["POST"] * len(wanted)
    dv.writes.clear()
    again = seed.sync(dv, wanted, apply=True, log=quiet)
    assert again.unchanged == len(wanted)
    assert dv.writes == []


def test_only_the_columns_that_differ_are_updated(wanted: list[dict[str, Any]]) -> None:
    dv = filled(wanted)
    first = wanted[0]
    dv.row(first["vz_key"]).update(vz_name="An old label", vz_sortorder=9999)
    seed.sync(dv, wanted, apply=True, log=quiet)
    assert len(dv.writes) == 1
    write = dv.writes[0]
    assert write.method == "PATCH" and write.headers == {"If-Match": "*"}
    assert write.body == {"vz_name": first["vz_name"], "vz_sortorder": first["vz_sortorder"]}


def test_line_endings_alone_are_not_a_difference(wanted: list[dict[str, Any]]) -> None:
    multi_line = [dict(wanted[0], vz_definition="first line\nsecond line")]
    dv = filled(multi_line)
    assert dv.row(multi_line[0]["vz_key"])["vz_definition"] == "first line\r\nsecond line"
    assert seed.sync(dv, multi_line, apply=True, log=quiet).in_sync
    assert dv.writes == []


def test_status_reports_a_difference_without_writing(wanted: list[dict[str, Any]]) -> None:
    dv = filled(wanted)
    dv.row(wanted[0]["vz_key"])["vz_name"] = "Drifted"
    lines: list[str] = []
    plan = seed.sync(dv, wanted, apply=False, log=lines.append)
    assert not plan.in_sync
    assert dv.writes == []
    assert any("update" in line and wanted[0]["vz_key"] in line for line in lines)


def test_a_row_the_file_does_not_hold_is_reported_and_left_alone(wanted: list[dict[str, Any]]) -> None:
    dv = filled(wanted)
    dv.add({"vz_key": "Retired_Item", "vz_name": "Retired"})
    lines: list[str] = []
    plan = seed.sync(dv, wanted, apply=True, log=lines.append)
    assert plan.extra == ["Retired_Item"] and plan.in_sync
    assert dv.writes == []
    assert any("Retired_Item" in line for line in lines)


def test_duplicate_rows_stop_the_run_before_any_write(wanted: list[dict[str, Any]]) -> None:
    dv = filled(wanted)
    dv.add(dict(dv.row(wanted[0]["vz_key"])))
    with pytest.raises(seed.SeedError, match="more than one row"):
        seed.sync(dv, wanted, apply=True, log=quiet)
    assert dv.writes == []


def test_a_missing_table_is_named_with_the_command_that_creates_it(wanted: list[dict[str, Any]]) -> None:
    with pytest.raises(seed.SeedError, match="provision-dataverse"):
        seed.sync(FakeDataverse(table_exists=False), wanted, apply=False, log=quiet)


def test_a_write_that_does_not_take_effect_is_an_error(wanted: list[dict[str, Any]]) -> None:
    with pytest.raises(seed.SeedError, match="still differs"):
        seed.sync(FakeDataverse(drop_writes=True), wanted, apply=True, log=quiet)


def test_only_the_account_named_in_env_may_write() -> None:
    dv = FakeDataverse(account="Admin@Example.test")
    assert seed.check_account(dv, "admin@example.test") == "Admin@Example.test"
    assert seed.check_account(dv, None) == "Admin@Example.test"
    with pytest.raises(seed.SeedError, match="signed in as Admin@Example.test"):
        seed.check_account(dv, "someone.else@example.test")


def test_without_a_flag_nothing_is_sent(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
                                        wanted: list[dict[str, Any]]) -> None:
    def forbidden(*_args: Any, **_kwargs: Any) -> None:
        raise AssertionError("the offline run must not connect to Dataverse")

    monkeypatch.setattr(seed, "Dataverse", forbidden)
    assert seed.main([]) == 0
    assert f"{len(wanted)} rows" in capsys.readouterr().out
