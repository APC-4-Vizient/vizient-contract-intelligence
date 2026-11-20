"""Offline tests for eval/generate_contracts.py: the synthetic data-license contracts and their gold labels."""

from __future__ import annotations

import hashlib
import io
import json
import re
import sys
from pathlib import Path
from typing import Any

import pytest
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "eval"))

import checklistlib  # noqa: E402
import generate_contracts as gen  # noqa: E402

FOOTER = "SYNTHETIC SAMPLE - FICTIONAL PARTIES - NOT A REAL AGREEMENT"
JUDGMENTS = {"Permitted", "Prohibited", "Conditional", "Not Addressed"}
PAGE_TARGETS = {"bluepine-sow": (12, 16), "bluepine-amendment": (3, 4), "tessera-dua": (10, 14)}
MIN_QUOTED_PAGES = {"bluepine-sow": 5, "bluepine-amendment": 2, "tessera-dua": 5}

P, X, C, N = "Permitted", "Prohibited", "Conditional", "Not Addressed"
PROFILES = {
    "bluepine-sow": {
        "Right_InternalAnalytics": P, "Right_AIML": X, "Right_ProductDevelopment": C, "Right_BAARequired": N,
        "Right_Retention": C, "Right_AffiliateSharing": N, "Right_ThirdPartySharing": X, "Right_DataLinking": C,
        "Right_DeIdentification": N, "Right_Destruction": C, "Right_Geographic": N},
    "bluepine-amendment": {
        "Right_InternalAnalytics": N, "Right_AIML": N, "Right_ProductDevelopment": N, "Right_BAARequired": N,
        "Right_Retention": N, "Right_AffiliateSharing": N, "Right_ThirdPartySharing": N, "Right_DataLinking": N,
        "Right_DeIdentification": N, "Right_Destruction": N, "Right_Geographic": N},
    "tessera-dua": {
        "Right_InternalAnalytics": P, "Right_AIML": C, "Right_ProductDevelopment": N, "Right_BAARequired": C,
        "Right_Retention": C, "Right_AffiliateSharing": C, "Right_ThirdPartySharing": X, "Right_DataLinking": X,
        "Right_DeIdentification": P, "Right_Destruction": C, "Right_Geographic": X},
}
DETAILS = {
    "bluepine-sow": {
        "Vendor": "Bluepine Health Data, Inc.", "VizientEntity": "Vizient, Inc.", "DocumentType": "SOW",
        "ContractIdentifier": "Statement of Work No. BP-2025-0417", "EffectiveDate": "2025-01-15",
        "ExpirationDate": "2028-01-14",
        "RenewalTermination": "Client may terminate at the end of any Annual License Period on at least 60 days' "
                              "written notice; no refund of fees paid; no automatic renewal",
        "Signatories": "Maren Okafor (President, Data and Analytics, 01/22/2025); Tobias Lindqvist (Vice President "
                       "and General Manager, 01/21/2025)",
        "ParentAgreementReference": "Master Data License Agreement No. 70418822 dated March 3, 2021"},
    "bluepine-amendment": {
        "Vendor": "Bluepine Health Data, Inc.", "VizientEntity": "Vizient, Inc.", "DocumentType": "Amendment",
        "ContractIdentifier": "Amendment No. 1 to Statement of Work No. BP-2025-0417", "EffectiveDate": "2025-09-02",
        "ExpirationDate": "2029-01-14", "RenewalTermination": "",
        "Signatories": "Maren Okafor (President, Data and Analytics, 09/09/2025); Priya Raman (Senior Director, "
                       "Product and Strategy, 09/08/2025)",
        "ParentAgreementReference": "Statement of Work No. BP-2025-0417 dated January 15, 2025"},
    "tessera-dua": {
        "Vendor": "Tessera Clinical Research Analytics, LLC", "VizientEntity": "Meridian Care Analytics, LLC",
        "DocumentType": "DUA", "ContractIdentifier": "Data Use Agreement No. TCR-DUA-2025-118",
        "EffectiveDate": "2025-04-01", "ExpirationDate": "2027-03-31",
        "RenewalTermination": "Renews automatically for successive one-year terms unless either party gives at least "
                              "90 days' written notice of non-renewal; either party may terminate for uncured "
                              "material breach after 30 days' notice; Client may terminate for convenience on 30 "
                              "days' notice",
        "Signatories": "Dr. Helena Voss (Chief Executive Officer, 04/03/2025); Marcus Adeyemi (Chief Data Officer, "
                       "04/02/2025)",
        "ParentAgreementReference": ""},
}

# SHA-256 of the lowercase real names and identifiers that must never appear in this synthetic data. They are kept
# hashed so that no file in the repo contains them.
BANNED_SHA256 = frozenset({
    "02a6efa44deef545bc56c1aae1e1d9feb53d505bb269a2abd6efe8d8f4e237f2",
    "2ca0970cb08b1ace04bf9f72c3ab9ad832b8750b02e706f75ec5d195908cbd32",
    "49fa327f2b30ae3be09640afde107af469303fd5275b47e67a72a593febe8811",
    "75688a3511c38dc1c838cf4a6c4dececa3dd882d474a018234eb9e14f7af9b82",
    "a23c496e57d452880a6d657e2148ee02d543778f52d1525ad5300932df369eb2",
    "b37a2ca110a8b21f8daad71762272b3c211764ec272e3d48b5983a47334d1c70",
    "b736100361ded8976e400f768df86e0b8a384ddaed59f07da9b4dbe9f56fa91b",
    "cadbae40d44d1de60b731a8754935c7656a1dc5931b239a146d7f8e357d39f17",
    "e4737dbe1ba9b078b6760b0f36c36c1e7233ae83317fe8e5b3241ee30609fa0e",
    "fe58d52a54087d971aafb84ebce57662bc31f728bc10078ecbb7d822e184ab6d",
})


@pytest.fixture(scope="module")
def specs() -> dict[str, dict[str, Any]]:
    return {spec["id"]: spec for spec in gen.load_specs()}


@pytest.fixture(scope="module")
def contracts() -> dict[str, gen.Contract]:
    return {contract.id: contract for contract in gen.render_all()}


@pytest.fixture(scope="module")
def texts(contracts: dict[str, gen.Contract]) -> dict[str, tuple[str, ...]]:
    """Text of each page, extracted here with pypdf and not taken from the generator."""
    return {cid: tuple(" ".join((page.extract_text() or "").split()) for page in PdfReader(io.BytesIO(c.pdf)).pages)
            for cid, c in contracts.items()}


def leaked(text: str, banned: frozenset[str] = BANNED_SHA256) -> list[str]:
    words = set(re.findall(r"[a-z0-9]+", text.lower()))
    return sorted(word for word in words if hashlib.sha256(word.encode()).hexdigest() in banned)


def test_each_spec_covers_exactly_the_analyzer_keys(specs: dict[str, dict[str, Any]]) -> None:
    data = checklistlib.load_checklist()
    details = {item["key"] for item in checklistlib.detail_items(data)}
    rights = {item["key"] for item in checklistlib.right_items(data)}
    assert (len(details), len(rights)) == (9, 11)
    assert set(specs) == set(PAGE_TARGETS)
    for cid, spec in specs.items():
        assert set(spec["details"]) == details, cid
        assert set(spec["rights"]) == rights, cid
        assert {judgment for judgment, _ in spec["rights"].values()} <= JUDGMENTS, cid
        assert spec["rights"]["Right_BAARequired"][0] in {C, N}, cid


def test_pdfs_render_with_page_counts_inside_the_targets(contracts: dict[str, gen.Contract], tmp_path: Path) -> None:
    pdf_dir = tmp_path / "pdf"
    gen.write_outputs(list(contracts.values()), pdf_dir, tmp_path / "gold")
    assert sorted(path.name for path in pdf_dir.iterdir()) == sorted(f"{cid}.pdf" for cid in PAGE_TARGETS)
    for cid, (low, high) in PAGE_TARGETS.items():
        count = len(PdfReader(pdf_dir / f"{cid}.pdf").pages)
        assert low <= count <= high, f"{cid} has {count} pages"
        assert count == contracts[cid].gold["_meta"]["pages"], cid


def test_not_addressed_rights_are_never_hinted_at(specs: dict[str, dict[str, Any]],
                                                  texts: dict[str, tuple[str, ...]]) -> None:
    for cid, spec in specs.items():
        assert spec["forbidden"], cid
        # An exemption may only cover a signer's job title, never a topic word.
        assert set(spec["exempt"]) <= {title.lower() for _, _, _, title, _ in spec["signers"]}, cid
        text = " ".join(texts[cid]).lower()
        for phrase in spec["exempt"]:
            text = text.replace(phrase, " ")
        assert [word for word in spec["forbidden"] if word in text] == [], cid


def test_gold_quotes_occur_once_on_the_recorded_page(contracts: dict[str, gen.Contract],
                                                     texts: dict[str, tuple[str, ...]]) -> None:
    for cid, contract in contracts.items():
        pages, quoted_pages = texts[cid], set()
        document = " ".join(pages)
        for key, entry in contract.gold.items():
            if key == "_meta":
                continue
            where = f"{cid} {key}"
            if entry.get("judgment") == N or entry.get("value") == "":
                assert set(entry) <= {"judgment", "value"}, where
                continue
            assert set(entry) - {"judgment", "value"} == {"page", "quote"}, where
            quote = entry["quote"]
            assert len(quote) <= (300 if "value" in entry else 400), where
            assert len(re.findall(f"(?={re.escape(quote)})", document)) == 1, where
            assert quote in pages[entry["page"] - 1], where
            quoted_pages.add(entry["page"])
        assert len(quoted_pages) >= MIN_QUOTED_PAGES[cid], f"{cid} quotes sit on pages {sorted(quoted_pages)}"


def test_rendering_twice_gives_identical_pdfs_and_gold(contracts: dict[str, gen.Contract]) -> None:
    again = {contract.id: contract for contract in gen.render_all()}
    assert again.keys() == contracts.keys()
    for cid, contract in contracts.items():
        assert again[cid].pdf == contract.pdf, cid
        assert gen.gold_text(again[cid].gold) == gen.gold_text(contract.gold), cid


def test_committed_gold_files_match_a_fresh_render(contracts: dict[str, gen.Contract]) -> None:
    assert gen.stale_gold(list(contracts.values()), gen.DEFAULT_GOLD_DIR) == []
    assert sorted(path.stem for path in gen.DEFAULT_GOLD_DIR.glob("*.json")) == sorted(contracts)


def test_no_real_names_or_values_appear_in_generated_text_or_source_files(
        contracts: dict[str, gen.Contract], texts: dict[str, tuple[str, ...]]) -> None:
    assert leaked("Alpha-BETA gamma", frozenset({hashlib.sha256(b"beta").hexdigest()})) == ["beta"]
    found = {f"{cid} pdf": " ".join(pages) for cid, pages in texts.items()}
    found.update({f"{cid} gold": gen.gold_text(contract.gold) for cid, contract in contracts.items()})
    sources = [*(ROOT / "eval").glob("*.py"), *(ROOT / "eval" / "gold").glob("*.json"), Path(__file__)]
    found.update({path.name: path.read_text(encoding="utf-8") for path in sources})
    assert {name: words for name, text in found.items() if (words := leaked(text))} == {}


def test_gold_matches_the_spec_table(specs: dict[str, dict[str, Any]], contracts: dict[str, gen.Contract]) -> None:
    for cid, contract in contracts.items():
        gold = contract.gold
        assert (len(PROFILES[cid]), len(DETAILS[cid])) == (11, 9), cid
        assert {key: gold[key]["judgment"] for key in PROFILES[cid]} == PROFILES[cid], cid
        assert {key: gold[key]["value"] for key in DETAILS[cid]} == DETAILS[cid], cid
        assert specs[cid]["blocks"][0] == ("title", gold["DocumentType"]["quote"]), cid
        assert gold["Signatories"]["quote"] == specs[cid]["signers"][0][2], cid


def test_every_page_has_header_footer_and_plain_ascii_text(specs: dict[str, dict[str, Any]],
                                                           texts: dict[str, tuple[str, ...]]) -> None:
    for cid, pages in texts.items():
        for number, text in enumerate(pages, 1):
            where = f"{cid} page {number}"
            assert text.startswith(specs[cid]["header_title"]), where
            assert f"Page {number} of {len(pages)}" in text, where
            assert FOOTER in text, where
            assert text.isascii(), where


def test_cli_writes_outputs_and_check_reports_drift_without_writing(tmp_path: Path,
                                                                    capsys: pytest.CaptureFixture[str]) -> None:
    pdf_dir, gold_dir = tmp_path / "pdf", tmp_path / "gold"
    args = ["--pdf-dir", str(pdf_dir), "--gold-dir", str(gold_dir)]

    assert gen.main(["--check", *args]) == 1
    assert not pdf_dir.exists() and not gold_dir.exists()

    assert gen.main(args) == 0
    assert sorted(path.name for path in pdf_dir.iterdir()) == sorted(f"{cid}.pdf" for cid in PAGE_TARGETS)
    assert sorted(path.name for path in gold_dir.iterdir()) == sorted(f"{cid}.json" for cid in PAGE_TARGETS)
    assert gen.main(["--check", *args]) == 0

    target = gold_dir / "tessera-dua.json"
    tampered = target.read_bytes().replace(b'"Permitted"', b'"Prohibited"', 1)
    target.write_bytes(tampered)
    capsys.readouterr()
    assert gen.main(["--check", *args]) == 1
    assert target.read_bytes() == tampered
    assert [line.split()[0] for line in capsys.readouterr().out.splitlines() if "STALE" in line] == ["tessera-dua"]


def test_gold_files_are_ascii_two_space_json_in_checklist_order(contracts: dict[str, gen.Contract]) -> None:
    order = [item["key"] for item in checklistlib.analyzer_items(checklistlib.load_checklist())]
    for cid, contract in contracts.items():
        raw = (gen.DEFAULT_GOLD_DIR / f"{cid}.json").read_bytes()
        assert raw.isascii() and raw.endswith(b"\n"), cid
        gold = json.loads(raw)
        assert list(gold) == ["_meta", *order], cid
        assert raw.decode().replace("\r\n", "\n") == json.dumps(gold, indent=2) + "\n", cid
        assert gold["_meta"] == {"id": cid, "pdf": f"{cid}.pdf", "synthetic": True, "pages": len(contract.pages),
                                 "generator": "eval/generate_contracts.py"}, cid


def test_locate_names_the_contract_and_key_for_missing_or_ambiguous_quotes() -> None:
    pages = ("alpha beta gamma", "delta alpha beta")
    assert (gen.locate("demo", "Key", "gamma", pages), gen.locate("demo", "Key", "delta", pages)) == (1, 2)
    with pytest.raises(gen.SpecError, match="demo: Key: quote not found"):
        gen.locate("demo", "Key", "omega", pages)
    with pytest.raises(gen.SpecError, match="demo: Key: quote occurs 2 times"):
        gen.locate("demo", "Key", "alpha beta", pages)
