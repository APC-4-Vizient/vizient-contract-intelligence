"""Generate synthetic third-party data-license contracts (PDF) and their gold labels (JSON).

    python eval/generate_contracts.py            write samples/<id>.pdf and eval/gold/<id>.json
    python eval/generate_contracts.py --check    exit 1 if a gold file differs from a fresh render; writes nothing

The contracts are fictional test data for the Content Understanding analyzer and double as demo documents. Each
contract_*.py module holds one contract's text and gold facts as plain data (SPEC). Gold pages are never typed: every
gold quote is located in the text pypdf extracts from the rendered PDF and must occur exactly once there. Rendering is
deterministic (reportlab invariant mode), so repeated runs give byte-identical PDFs and identical gold files.

SPEC keys:
  id, header_title   file stem and the short title printed in every page header
  blocks             the document in order: ("title"|"subtitle"|"h1"|"h2"|"p", text), ("c", number, caption, text),
                     ("d", number, term, text), ("s", label, text), ("break",), ("signatures",)
  signers            (role, entity, name, title, date) for each signature block, in order
  details            Contract Detail key -> (value, quote); both empty when the contract states nothing
  rights             Data Right key -> (judgment, quote); the quote is empty for Not Addressed
  forbidden, exempt  words the text must never contain, and phrases removed before that check
"""

from __future__ import annotations

import argparse
import importlib
import io
import json
import re
import sys
from bisect import bisect_right
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape

from pypdf import PdfReader
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas
from reportlab.platypus import Flowable, KeepTogether, PageBreak, Paragraph, SimpleDocTemplate

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path[:0] = [str(HERE), str(ROOT / "scripts")]

import checklistlib  # noqa: E402

MODULES = ("contract_bluepine_sow", "contract_bluepine_amendment", "contract_tessera_dua")
GENERATOR = "eval/generate_contracts.py"
FOOTER_NOTE = "SYNTHETIC SAMPLE - FICTIONAL PARTIES - NOT A REAL AGREEMENT"
DEFAULT_PDF_DIR = ROOT / "samples"
DEFAULT_GOLD_DIR = ROOT / "eval" / "gold"
QUOTE_LIMITS = {"Contract Detail": 300, "Data Right": 400}
NOT_ADDRESSED = "Not Addressed"
SIGNATURE_LINE = "By: " + "_" * 30
BLOCK_KINDS = {"title", "subtitle", "h1", "h2", "p", "c", "d", "s", "break", "signatures"}


class SpecError(ValueError):
    """A contract SPEC is inconsistent with the checklist or with its own rendered text."""


@dataclass(frozen=True)
class Contract:
    id: str
    pdf: bytes
    pages: tuple[str, ...]  # whitespace-normalised text of each page
    gold: dict[str, Any]


def _style(name: str, **overrides: Any) -> ParagraphStyle:
    base: dict[str, Any] = {"fontName": "Times-Roman", "fontSize": 10.5, "leading": 14, "spaceAfter": 7,
                            "alignment": TA_LEFT}
    return ParagraphStyle(name, **{**base, **overrides})


BOLD = "Times-Bold"
STYLES = {
    "title": _style("title", fontName=BOLD, fontSize=15, leading=19, spaceAfter=4),
    "subtitle": _style("subtitle", fontName=BOLD, fontSize=11.5, leading=15, spaceAfter=14),
    "h1": _style("h1", fontName=BOLD, fontSize=11, leading=14, spaceBefore=12, spaceAfter=6, keepWithNext=1),
    "h2": _style("h2", fontName=BOLD, spaceBefore=6, spaceAfter=5, keepWithNext=1),
    "p": _style("p"),
    "c": _style("c"),
    "d": _style("d"),
    "s": _style("s", leftIndent=24, spaceAfter=5),
    "sigparty": _style("sigparty", fontName=BOLD, spaceBefore=18, spaceAfter=10),
    "sigby": _style("sigby", spaceAfter=6),
    "sigline": _style("sigline", spaceAfter=5),
}


def normalise(text: str) -> str:
    return " ".join(text.split())


def load_specs() -> list[dict[str, Any]]:
    return [importlib.import_module(name).SPEC for name in MODULES]


# --- SPEC validation ---------------------------------------------------------------------------------------------

def signatories_value(signers: list[tuple[str, ...]]) -> str:
    return "; ".join(f"{name} ({title}, {signed})" for _, _, name, title, signed in signers)


def _strings(obj: Any) -> Iterator[str]:
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for key, value in obj.items():
            yield from _strings(key)
            yield from _strings(value)
    elif isinstance(obj, (list, tuple)):
        for value in obj:
            yield from _strings(value)


def _detail_problem(item: dict[str, Any], value: str, quote: str) -> str:
    if item["group"] != "Contract Detail":
        return "is a data right, not a contract detail"
    if item["type"] == "date" and value:
        try:
            date.fromisoformat(value)
        except ValueError:
            return f"value {value!r} is not an ISO date"
    if item.get("enum") and value not in item["enum"]:
        return f"value {value!r} is not one of {item['enum']}"
    if bool(value) != bool(quote):
        return "needs both a value and a quote, or neither"
    return ""


def _right_problem(data: dict[str, Any], item: dict[str, Any], judgment: str, quote: str) -> str:
    if item["group"] != "Data Right":
        return "is a contract detail, not a data right"
    if judgment not in checklistlib.judgments_for(data, item):
        return f"judgment {judgment!r} is not allowed for this item"
    if (judgment == NOT_ADDRESSED) == bool(quote):
        return "needs a quote unless the judgment is Not Addressed, which carries none"
    return ""


def validate_spec(spec: dict[str, Any], data: dict[str, Any]) -> None:
    """Raise SpecError naming the contract and key for the first inconsistency in a SPEC."""
    cid = spec["id"]
    items = {item["key"]: item for item in checklistlib.analyzer_items(data)}
    details, rights = spec["details"], spec["rights"]
    given = [*details, *rights]
    if sorted(given) != sorted(items):
        raise SpecError(f"{cid}: SPEC keys differ from the checklist analyzer keys; "
                        f"missing {sorted(set(items) - set(given))}, unexpected {sorted(set(given) - set(items))}")
    for key, (first, quote) in {**details, **rights}.items():
        item = items[key]
        problem = (_detail_problem(item, first, quote) if key in details
                   else _right_problem(data, item, first, quote))
        if not problem and quote != normalise(quote):
            problem = "quote must use single spaces and no leading or trailing space"
        if not problem and len(quote) > QUOTE_LIMITS[item["group"]]:
            problem = f"quote is {len(quote)} characters; the limit is {QUOTE_LIMITS[item['group']]}"
        if problem:
            raise SpecError(f"{cid}: {key}: {problem}")
    unknown = {block[0] for block in spec["blocks"]} - BLOCK_KINDS
    if unknown:
        raise SpecError(f"{cid}: unknown block kinds {sorted(unknown)}")
    if details["Signatories"][0] != signatories_value(spec["signers"]):
        raise SpecError(f"{cid}: Signatories: value does not match the signature blocks")
    wrong = [text for text in _strings(spec) if not text.isascii()]
    if wrong:
        raise SpecError(f"{cid}: only ASCII is allowed, found {wrong[0]!r}")


# --- text blocks -------------------------------------------------------------------------------------------------

def signer_lines(args: tuple[str, ...] | list[str]) -> list[str]:
    role, entity, name, title, signed = args
    return [f"{role.upper()}: {entity}", SIGNATURE_LINE, f"Name: {name}", f"Title: {title}", f"Date: {signed}"]


def expand_blocks(spec: dict[str, Any]) -> list[tuple[str, ...]]:
    blocks: list[tuple[str, ...]] = []
    for block in spec["blocks"]:
        blocks += [("signer", *signer) for signer in spec["signers"]] if block[0] == "signatures" else [block]
    return blocks


def parts(block: tuple[str, ...]) -> tuple[str, str]:
    """The bold lead-in and the text of a block. The PDF and the quote search both use these."""
    kind, *args = block
    match kind:
        case "c":
            number, caption, text = args
            return (f"{number} {caption}." if caption else number), text
        case "d":
            number, term, text = args
            return number, f'"{term}" {text}'
        case "s":
            label, text = args
            return "", f"{label} {text}"
        case "signer":
            return "", " ".join(signer_lines(args))
        case "break":
            return "", ""
        case _:
            return "", args[0]


def block_text(block: tuple[str, ...]) -> str:
    return normalise(" ".join(parts(block)))


def quotes(spec: dict[str, Any]) -> Iterator[tuple[str, str]]:
    for key, (_, quote) in {**spec["details"], **spec["rights"]}.items():
        if quote:
            yield key, quote


def protected_blocks(spec: dict[str, Any], blocks: list[tuple[str, ...]]) -> set[int]:
    """Indexes of the blocks that contain a gold quote. Each is kept on one page so a quote never splits."""
    texts = [block_text(block) for block in blocks]
    protected: set[int] = set()
    for key, quote in quotes(spec):
        holders = [index for index, text in enumerate(texts) if quote in text]
        if not holders:
            raise SpecError(f"{spec['id']}: {key}: the quote is not inside one paragraph of the text: {quote!r}")
        protected.update(holders)
    return protected


def make_flowables(block: tuple[str, ...]) -> list[Flowable]:
    kind = block[0]
    if kind == "break":
        return [PageBreak()]
    if kind == "signer":
        names = ["sigparty", "sigby", "sigline", "sigline", "sigline"]
        return [Paragraph(escape(line), STYLES[name]) for line, name in zip(signer_lines(block[1:]), names)]
    lead, text = parts(block)
    return [Paragraph((f"<b>{escape(lead)}</b> " if lead else "") + escape(text), STYLES[kind])]


def build_story(spec: dict[str, Any]) -> list[Flowable]:
    """Flowables for the document. A heading joins the group of the block after it, because reportlab's own
    keepWithNext does not reach into a KeepTogether and would leave the heading alone at the foot of a page."""
    blocks = expand_blocks(spec)
    protected = protected_blocks(spec, blocks)
    story: list[Flowable] = []
    headings: list[Flowable] = []
    for index, block in enumerate(blocks):
        group = make_flowables(block)
        if block[0] in ("h1", "h2"):
            headings += group
            continue
        group, headings = headings + group, []
        if index in protected or len(group) > 1:
            story.append(KeepTogether(group))
        else:
            story += group
    return story + headings


# --- rendering ---------------------------------------------------------------------------------------------------

class _NumberedCanvas(canvas.Canvas):
    """Adds "Page N of M" and the synthetic-sample note once the page count is known.

    They are drawn last, so they are also the last text of each page when the PDF is extracted.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._saved_pages: list[dict[str, Any]] = []

    def showPage(self) -> None:
        self._saved_pages.append(dict(self.__dict__))
        self._startPage()

    def save(self) -> None:
        total = len(self._saved_pages)
        for state in self._saved_pages:
            self.__dict__.update(state)
            self._draw_footer(total)
            super().showPage()
        super().save()

    def _draw_footer(self, total: int) -> None:
        width = letter[0]
        self.saveState()
        self.setFont("Times-Roman", 8.5)
        self.setLineWidth(0.5)
        self.line(inch, 0.8 * inch, width - inch, 0.8 * inch)
        self.drawString(inch, 0.6 * inch, f"Page {self._pageNumber} of {total}")
        self.drawRightString(width - inch, 0.6 * inch, FOOTER_NOTE)
        self.restoreState()


def _header_drawer(title: str) -> Any:
    def draw(page: canvas.Canvas, _doc: Any) -> None:
        width, height = letter
        page.saveState()
        page.setFont("Times-Roman", 9)
        page.setLineWidth(0.5)
        page.drawString(inch, height - 0.6 * inch, title)
        page.line(inch, height - 0.68 * inch, width - inch, height - 0.68 * inch)
        page.restoreState()

    return draw


def render_pdf(spec: dict[str, Any]) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, leftMargin=inch, rightMargin=inch, topMargin=inch,
                            bottomMargin=inch, invariant=1, title=spec["header_title"],
                            author="Synthetic sample generator", subject=FOOTER_NOTE, creator=GENERATOR)
    header = _header_drawer(spec["header_title"])
    doc.build(build_story(spec), onFirstPage=header, onLaterPages=header, canvasmaker=_NumberedCanvas)
    return buffer.getvalue()


# --- gold --------------------------------------------------------------------------------------------------------

def extract_pages(pdf: bytes) -> tuple[str, ...]:
    return tuple(normalise(page.extract_text() or "") for page in PdfReader(io.BytesIO(pdf)).pages)


def locate(cid: str, key: str, quote: str, pages: tuple[str, ...]) -> int:
    """The 1-based page of the quote's first character; the quote must occur exactly once in the document."""
    needle = normalise(quote)
    hits = [match.start() for match in re.finditer(f"(?={re.escape(needle)})", " ".join(pages))]
    if not hits:
        raise SpecError(f"{cid}: {key}: quote not found in the rendered text: {quote!r}")
    if len(hits) > 1:
        raise SpecError(f"{cid}: {key}: quote occurs {len(hits)} times, so its page is ambiguous: {quote!r}")
    starts, offset = [], 0
    for text in pages:
        starts.append(offset)
        offset += len(text) + 1
    return bisect_right(starts, hits[0])


def build_gold(spec: dict[str, Any], data: dict[str, Any], pages: tuple[str, ...]) -> dict[str, Any]:
    gold: dict[str, Any] = {"_meta": {"id": spec["id"], "pdf": f"{spec['id']}.pdf", "synthetic": True,
                                      "pages": len(pages), "generator": GENERATOR}}
    for item in checklistlib.analyzer_items(data):
        key = item["key"]
        if key in spec["details"]:
            first, quote = spec["details"][key]
            entry: dict[str, Any] = {"value": first}
        else:
            first, quote = spec["rights"][key]
            entry = {"judgment": first}
        if quote:
            entry["page"] = locate(spec["id"], key, quote, pages)
            entry["quote"] = quote
        gold[key] = entry
    return gold


def forbidden_hits(spec: dict[str, Any], text: str) -> list[str]:
    """The forbidden words found in text, ignoring case and the exempt phrases."""
    lowered = normalise(text).lower()
    for phrase in spec.get("exempt", ()):
        lowered = lowered.replace(phrase, " ")
    return [word for word in spec["forbidden"] if word in lowered]


def render_contract(spec: dict[str, Any], data: dict[str, Any] | None = None) -> Contract:
    data = data or checklistlib.load_checklist()
    validate_spec(spec, data)
    pdf = render_pdf(spec)
    pages = extract_pages(pdf)
    hits = forbidden_hits(spec, " ".join(pages))
    if hits:
        raise SpecError(f"{spec['id']}: the rendered text contains forbidden words {hits}")
    return Contract(spec["id"], pdf, pages, build_gold(spec, data, pages))


def render_all(specs: list[dict[str, Any]] | None = None) -> list[Contract]:
    data = checklistlib.load_checklist()
    return [render_contract(spec, data) for spec in (specs or load_specs())]


def gold_text(gold: dict[str, Any]) -> str:
    return json.dumps(gold, indent=2, ensure_ascii=True) + "\n"


def quoted_count(gold: dict[str, Any]) -> int:
    return sum("quote" in entry for key, entry in gold.items() if key != "_meta")


# --- files and CLI -----------------------------------------------------------------------------------------------

def write_outputs(contracts: list[Contract], pdf_dir: Path, gold_dir: Path) -> None:
    pdf_dir.mkdir(parents=True, exist_ok=True)
    gold_dir.mkdir(parents=True, exist_ok=True)
    for contract in contracts:
        (pdf_dir / f"{contract.id}.pdf").write_bytes(contract.pdf)
        (gold_dir / f"{contract.id}.json").write_text(gold_text(contract.gold), encoding="utf-8", newline="\r\n")


def stale_gold(contracts: list[Contract], gold_dir: Path) -> list[str]:
    """Ids whose gold file is missing or differs from a fresh render. Only reads."""
    stale = []
    for contract in contracts:
        path = gold_dir / f"{contract.id}.json"
        if not path.exists() or path.read_text(encoding="utf-8") != gold_text(contract.gold):
            stale.append(contract.id)
    return stale


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate synthetic contract PDFs and their gold labels.")
    parser.add_argument("--pdf-dir", type=Path, default=DEFAULT_PDF_DIR, help="where the PDFs go (default samples)")
    parser.add_argument("--gold-dir", type=Path, default=DEFAULT_GOLD_DIR, help="where the gold JSON goes")
    parser.add_argument("--check", action="store_true",
                        help="render in memory and exit 1 if a gold file differs; nothing is written")
    args = parser.parse_args(argv)

    try:
        contracts = render_all()
    except SpecError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    stale = stale_gold(contracts, args.gold_dir) if args.check else []
    if not args.check:
        write_outputs(contracts, args.pdf_dir, args.gold_dir)
    for contract in contracts:
        state = ("  STALE" if contract.id in stale else "  current") if args.check else ""
        print(f"{contract.id:<20} {contract.gold['_meta']['pages']:>2} pages  "
              f"{quoted_count(contract.gold):>2} gold items with a quote{state}")
    if stale:
        print("Run: python eval/generate_contracts.py")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
