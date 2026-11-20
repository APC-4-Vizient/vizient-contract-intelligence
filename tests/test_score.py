"""Tests for eval/score.py: the matching, the checks behind success criteria 2 to 6, and the command line."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / "eval"), str(ROOT / "scripts")]

import checklistlib  # noqa: E402
import score  # noqa: E402

GOLD_FILES = sorted((ROOT / "eval" / "gold").glob("*.json"))
REAL_ITEMS = checklistlib.analyzer_items(checklistlib.load_checklist())

ITEMS = [
    {"key": "Vendor", "group": "Contract Detail", "type": "string", "method": "extract"},
    {"key": "EffectiveDate", "group": "Contract Detail", "type": "date", "method": "extract"},
    {"key": "DocumentType", "group": "Contract Detail", "type": "string", "method": "classify",
     "enum": ["MSA", "SOW"]},
    {"key": "ParentAgreementReference", "group": "Contract Detail", "type": "string", "method": "extract"},
    {"key": "Right_AIML", "group": "Data Right"},
    {"key": "Right_Retention", "group": "Data Right"},
    {"key": "Right_Geographic", "group": "Data Right"},
]

GOLD = {
    "Vendor": {"value": "Bluepine Health Data, Inc.", "page": 1,
               "quote": 'Bluepine Health Data, Inc., a Delaware corporation ("Provider")'},
    "EffectiveDate": {"value": "2025-01-15", "page": 1, "quote": "entered into as of January 15, 2025"},
    "DocumentType": {"value": "SOW", "page": 1, "quote": "STATEMENT OF WORK NO. BP-2025-0417"},
    "ParentAgreementReference": {"value": ""},
    "Right_AIML": {"judgment": "Prohibited", "page": 4,
                   "quote": "Client shall not use the Licensed Data to train any machine learning model."},
    "Right_Retention": {"judgment": "Conditional", "page": 6, "alsoAcceptable": ["Permitted"],
                        "quote": "Client may keep one archival copy for audit purposes."},
    "Right_Geographic": {"judgment": "Not Addressed"},
}


def finding(key, presence="Found", *, value="", judgment="N/A", clause="", page=None):
    return {"key": key, "presence": presence, "value": value, "judgment": judgment, "clause": clause, "page": page}


def answer(gold, items):
    """The findings a flawless pipeline returns for this gold."""
    findings = {}
    for item in items:
        key, entry = item["key"], gold[item["key"]]
        right = item["group"] == "Data Right"
        silent = entry["judgment"] == "Not Addressed" if right else not entry["value"]
        findings[key] = finding(key, "Not Found" if silent else "Found", value="" if right else entry["value"],
                                judgment=entry["judgment"] if right else "N/A", clause=entry.get("quote", ""),
                                page=entry.get("page"))
    return findings


def scored(**changes):
    findings = answer(GOLD, ITEMS)
    for key, update in changes.items():
        findings[key] = {**findings[key], **update}
    return score.score_contract("t", GOLD, findings, ITEMS)


def missed(result):
    return {(miss.check, miss.key) for miss in result.misses}


def details(result, check):
    return [miss.detail for miss in result.misses if miss.check == check]


# --- matching ----------------------------------------------------------------------------------------------------

def test_the_string_ratio_is_the_indel_similarity():
    assert score.lcs_length("abcde", "ace") == 3
    assert score.lcs_length("", "abc") == 0
    assert score.ratio("abc", "abc") == 100
    assert score.ratio("abc", "xyz") == 0
    assert score.ratio("abcd", "abxd") == 75


def test_the_token_set_ratio_ignores_case_punctuation_and_order():
    assert score.token_set_ratio("Vizient, Inc.", "inc VIZIENT") == 100
    assert score.token_set_ratio("Master Agreement No. 5", "the Master Agreement No. 5 dated 2021") == 100
    assert score.token_set_ratio("Acme Analytics", "Bluepine Health Data, Inc.") < score.TEXT_THRESHOLD
    assert score.token_set_ratio("", "anything") == 0
    assert score.token_set_ratio("...", "anything") == 0


@pytest.mark.parametrize("key, value, matches", [
    ("Vendor", "Bluepine Health Data", True),
    ("Vendor", "BLUEPINE HEALTH DATA, INC", True),
    ("Vendor", "Acme Analytics Corp.", False),
    ("Vendor", "", False),
    ("EffectiveDate", "2025-01-15", True),
    ("EffectiveDate", "2025-01-16", False),
    ("EffectiveDate", "January 15, 2025", False),
    ("DocumentType", "sow", True),
    ("DocumentType", "MSA", False),
])
def test_details_match_by_kind(key, value, matches):
    assert (("detail", key) not in missed(scored(**{key: {"value": value}}))) is matches


def test_the_kind_of_a_field_comes_from_the_checklist():
    kinds = {item["key"]: score.kind_of(item) for item in REAL_ITEMS if item["group"] == "Contract Detail"}
    assert kinds["EffectiveDate"] == kinds["ExpirationDate"] == "date"
    assert kinds["DocumentType"] == "enum"
    assert kinds["Vendor"] == kinds["Signatories"] == "text"


# --- the checks --------------------------------------------------------------------------------------------------

def test_a_flawless_answer_has_no_misses():
    result = scored()
    assert result.misses == []
    assert result.totals == {"detail": 4, "right": 3, "prohibited": 1, "found": 5, "silent": 2, "highlight": 5}


def test_a_silent_detail_must_stay_empty():
    result = scored(ParentAgreementReference={"presence": "Found", "value": "Master Agreement No. 7",
                                              "clause": "Master Agreement No. 7", "page": 2})
    assert missed(result) == {("detail", "ParentAgreementReference"), ("silent", "ParentAgreementReference")}
    assert details(result, "detail") == ['expected nothing, got "Master Agreement No. 7"']


def test_rights_match_the_gold_judgment_or_an_accepted_alternative():
    assert missed(scored(Right_Retention={"judgment": "Permitted"})) == set()
    assert missed(scored(Right_AIML={"judgment": "prohibited"})) == set()
    assert missed(scored(Right_Retention={"judgment": "Prohibited"})) == {("right", "Right_Retention")}
    wrong = scored(Right_AIML={"judgment": "Conditional"})
    assert missed(wrong) == {("right", "Right_AIML")}
    assert details(wrong, "right") == ["expected Prohibited, got Conditional"]
    assert (wrong.totals["prohibited"], wrong.missed["prohibited"]) == (1, 1)


def test_found_where_the_contract_is_silent_is_counted():
    result = scored(Right_Geographic={"presence": "Found", "judgment": "Permitted", "clause": "Data may go abroad.",
                                       "page": 3})
    assert missed(result) == {("right", "Right_Geographic"), ("silent", "Right_Geographic")}


def test_an_unclear_answer_is_a_disagreement_but_not_a_found_assertion():
    result = scored(Right_Geographic={"presence": "Unclear", "judgment": "Permitted", "clause": "x", "page": 3})
    assert missed(result) == {("right", "Right_Geographic")}


@pytest.mark.parametrize("change", [{"clause": ""}, {"clause": "   "}, {"page": None}, {"page": 0}])
def test_a_found_item_needs_a_clause_and_a_page(change):
    assert ("found", "Vendor") in missed(scored(Vendor=change))


def test_the_evidence_proxy_wants_the_gold_page_and_the_gold_clause():
    assert missed(scored(Right_AIML={"clause": "shall not use the Licensed Data to train any machine learning"})) \
        == set()
    assert details(scored(Right_AIML={"page": 5}), "highlight") == ["page 5, gold page 4"]
    assert details(scored(Right_AIML={"clause": "The parties shall meet quarterly."}), "highlight") \
        == ["clause differs from the gold quote"]
    assert details(scored(Right_AIML={"page": 9, "clause": "Unrelated."}), "highlight") \
        == ["page 9, gold page 4; clause differs from the gold quote"]


def test_only_found_items_are_held_to_the_evidence_checks():
    result = scored(Vendor={"presence": "Unclear", "page": 9, "clause": ""})
    assert (result.totals["found"], result.totals["highlight"]) == (4, 4)
    assert result.misses == []


def test_a_finding_missing_from_the_payload_counts_as_nothing():
    findings = answer(GOLD, ITEMS)
    del findings["Vendor"], findings["Right_Geographic"]
    result = score.score_contract("t", GOLD, findings, ITEMS)
    assert missed(result) == {("detail", "Vendor"), ("right", "Right_Geographic")}
    assert details(result, "detail") == ['expected "Bluepine Health Data, Inc.", got nothing']


# --- the criteria ------------------------------------------------------------------------------------------------

def tallies(check, hits, total):
    result = score.Result("t")
    result.totals[check], result.missed[check] = total, total - hits
    return result


@pytest.mark.parametrize("index, hits, total, met", [
    (0, 90, 100, True), (0, 89, 100, False),
    (1, 85, 100, True), (1, 84, 100, False),
    (2, 19, 20, True), (2, 18, 20, False),
    (3, 43, 43, True), (3, 42, 43, False),
    (4, 7, 7, True), (4, 6, 7, False),
    (5, 90, 100, True), (5, 89, 100, False),
])
def test_the_criteria_apply_the_thresholds_of_the_brief(index, hits, total, met):
    assert score.criteria(tallies(score.CHECKS[index], hits, total))[index].met is met


def test_a_criterion_with_nothing_to_measure_has_no_verdict():
    rows = score.criteria(score.Result("t"))
    assert [row.met for row in rows] == [None] * 6
    assert rows[0].measured == "n/a" and rows[4].measured == "0 of 0"


def test_contracts_are_pooled_before_the_criteria_are_applied():
    first, second = tallies("detail", 9, 9), tallies("detail", 8, 9)
    total = score.combine([first, second])
    assert (total.totals["detail"], total.missed["detail"]) == (18, 1)


# --- the files and the command line ------------------------------------------------------------------------------

@pytest.mark.parametrize("path", GOLD_FILES, ids=lambda path: path.stem)
def test_every_gold_file_is_valid_and_a_flawless_answer_scores_perfectly(path):
    gold = score.load_gold(path, REAL_ITEMS)
    result = score.score_contract(path.stem, gold, answer(gold, REAL_ITEMS), REAL_ITEMS)
    assert result.misses == []
    assert result.totals["detail"] + result.totals["right"] == len(REAL_ITEMS)
    assert all(row.met is not False for row in score.criteria(result))


def real_gold():
    """A gold file for the real checklist: every right is Prohibited except Right_Geographic, on which it is silent."""
    gold = {"_meta": {"synthetic": True}}
    for item in REAL_ITEMS:
        key = item["key"]
        if key == "Right_Geographic":
            gold[key] = {"judgment": "Not Addressed"}
        elif item["group"] == "Data Right":
            gold[key] = {"judgment": "Prohibited", "page": 2, "quote": f"{key} is not allowed."}
        else:
            value = "2025-01-15" if item["type"] == "date" else item["enum"][0] if "enum" in item else f"{key} value"
            gold[key] = {"value": value, "page": 1, "quote": f"{key} appears here: {value}"}
    return gold


def payload(findings):
    return {"contract": {}, "findings": list(findings.values()), "raw": {}}


def put(directory, name, data):
    text = data if isinstance(data, str) else json.dumps(data)
    (directory / f"{name}.json").write_text(text, encoding="utf-8")


@pytest.fixture
def folders(tmp_path):
    gold_dir, results_dir = tmp_path / "gold", tmp_path / "results"
    gold_dir.mkdir()
    results_dir.mkdir()
    return gold_dir, results_dir


def run(folders, *extra):
    gold_dir, results_dir = folders
    return score.main([*extra, "--gold", str(gold_dir), "--results", str(results_dir)])


def test_a_gold_file_is_validated_strictly(folders):
    gold = real_gold()
    gold["Right_AIML"]["judgment"] = "Maybe"
    gold["Nonsense"] = {"value": "x"}
    del gold["Vendor"]
    put(folders[0], "bad", gold)
    with pytest.raises(score.ScoreError) as error:
        score.load_gold(folders[0] / "bad.json", REAL_ITEMS)
    message = str(error.value)
    assert "Nonsense: not a checklist item" in message
    assert "Vendor: missing" in message
    assert "Right_AIML: judgment must be one of" in message


def test_main_reports_a_passing_run(folders, capsys):
    gold = real_gold()
    put(folders[0], "alpha", gold)
    put(folders[1], "alpha", payload(answer(gold, REAL_ITEMS)))
    assert run(folders) == 0
    output = capsys.readouterr().out
    assert output.startswith("alpha: details 9/9  rights 11/11")
    assert output.count("PASS") == 6 and "FAIL" not in output and "Misses" not in output


def test_main_exits_1_and_lists_the_misses_when_a_criterion_fails(folders, capsys):
    gold, findings = real_gold(), answer(real_gold(), REAL_ITEMS)
    findings["Right_AIML"]["judgment"] = "Permitted"
    put(folders[0], "alpha", gold)
    put(folders[1], "alpha", payload(findings))
    assert run(folders) == 1
    output = capsys.readouterr().out
    assert "FAIL" in output and "Misses (1)" in output
    assert "Right_AIML" in output and "expected Prohibited, got Permitted" in output


def test_main_scores_only_the_named_contracts_and_notes_the_ones_without_a_result(folders, capsys):
    gold = real_gold()
    for name in ("alpha", "beta", "gamma"):
        put(folders[0], name, gold)
    for name in ("alpha", "beta"):
        put(folders[1], name, payload(answer(gold, REAL_ITEMS)))
    assert run(folders, "beta", "beta") == 0
    output = capsys.readouterr().out
    assert "beta:" in output and "alpha:" not in output and "Skipped" not in output
    assert run(folders) == 0
    output = capsys.readouterr().out
    assert "alpha:" in output and "beta:" in output
    assert "Skipped, no saved result yet: gamma" in output


def test_main_has_nothing_to_score_without_a_saved_result(folders, capsys):
    put(folders[0], "alpha", real_gold())
    assert run(folders) == 2
    assert "python scripts/run-local.py samples/alpha.pdf" in capsys.readouterr().err


@pytest.mark.parametrize("gold, result, message", [
    ("{not json", "{}", "gold file alpha.json is not valid JSON"),
    ("[]", "{}", "gold file alpha.json must hold a JSON object"),
    ('{"Vendor": {"value": "x"}}', "{}", "gold file alpha.json is not valid"),
    (None, '{"findings": "nope"}', "no findings list"),
    (None, '{"findings": [1]}', "no findings list"),
    (None, "not json", "result file alpha.json is not valid JSON"),
])
def test_main_rejects_files_it_cannot_score(folders, capsys, gold, result, message):
    put(folders[0], "alpha", real_gold() if gold is None else gold)
    put(folders[1], "alpha", result)
    assert run(folders) == 2
    assert message in capsys.readouterr().err


def test_main_rejects_a_missing_gold_file_and_a_bad_id(folders, capsys):
    assert run(folders, "alpha") == 2
    assert "cannot read the gold file alpha.json" in capsys.readouterr().err
    assert run(folders) == 2
    assert "there are no gold files" in capsys.readouterr().err
    with pytest.raises(SystemExit) as exit_info:
        run(folders, "../alpha")
    assert exit_info.value.code == 2


def test_main_writes_the_json_report(folders, tmp_path, capsys):
    gold = real_gold()
    put(folders[0], "alpha", gold)
    put(folders[1], "alpha", payload(answer(gold, REAL_ITEMS)))
    out = tmp_path / "report.json"
    assert run(folders, "--json", str(out)) == 0
    report = json.loads(out.read_text(encoding="utf-8"))
    assert [row["number"] for row in report["criteria"]] == [2, 3, 3, 4, 5, 6]
    assert report["contracts"]["alpha"]["misses"] == []
    capsys.readouterr()
    assert run(folders, "--json", str(tmp_path / "missing" / "report.json")) == 2
    assert "cannot write" in capsys.readouterr().err
