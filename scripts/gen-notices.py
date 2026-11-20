"""Write the third-party notices for the Code App's production dependencies, from the lockfile and the installed packages.

    python scripts/gen-notices.py          # write the three files below
    python scripts/gen-notices.py --check  # exit 1 when any of them is out of date, and write nothing

  THIRD-PARTY-NOTICES.md                           what a reader of the repository sees
  contract-review/public/THIRD-PARTY-NOTICES.txt   the same text, shipped inside the Code App package
  contract-review/src/standalone/third-party.json  the data the 3D page build uses to print notices for the packages it bundles

The packages come from contract-review/package-lock.json (everything that is not development-only). The copyright lines and the license
texts come from the installed packages, so run `npm ci` in contract-review/ first. Run this again after any change to the app's
dependencies: tests/test_notices.py fails while the files are stale.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "contract-review"
MARKDOWN = ROOT / "THIRD-PARTY-NOTICES.md"
TEXT_COPY = APP / "public" / "THIRD-PARTY-NOTICES.txt"
DATA = APP / "src" / "standalone" / "third-party.json"

LICENSE_FILES = re.compile(r"^(licen[cs]e|copying)([-._].*)?$", re.IGNORECASE)
COPYRIGHT = re.compile(r"^\s*(?:copyright\b|\(c\)|\u00a9)", re.IGNORECASE)
PLATFORM_SUFFIX = re.compile(r"-(?:android|darwin|freebsd|linux|openharmony|win32)-.+$")
HEADER_LINES = 8  # copyright lines this far into a license are the holder's; later ones are boilerplate (the Apache appendix)
HOLDERS_NOTE = "Copyright (c) the holders named in the table above"

MIT = """MIT License

Copyright (c) the holders named in the table above

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
"""  # noqa: E501 (the standard text keeps its paragraphs on single lines)
STANDARD_TEXTS = {"MIT": MIT}


def collapse(text: str) -> str:
    """Letters and digits only, in lower case: two license texts that differ in quotes, spacing or line breaks compare equal."""
    return re.sub(r"[^a-z0-9]+", "", text.lower())


# What a package's own license file must contain before the standard text may stand in for it.
STANDARD_CORE = {spdx: collapse(text.split("Permission is hereby granted", 1)[1]) for spdx, text in STANDARD_TEXTS.items()}


@dataclass(frozen=True)
class Package:
    name: str
    version: str
    license: str
    copyright: str
    text_id: str


@dataclass(frozen=True)
class Text:
    label: str
    body: str


def production_packages(lock: dict[str, Any]) -> list[tuple[str, str, str]]:
    """(name, version, declared license) of every package that is not development-only, sorted by name."""
    found = {}
    for key, entry in lock["packages"].items():
        if not key or entry.get("dev") or entry.get("devOptional"):
            continue
        found[key.rsplit("node_modules/", 1)[-1]] = (entry["version"], entry.get("license", ""))
    return [(name, *found[name]) for name in sorted(found, key=str.lower)]


def find_license_file(package_dir: Path) -> Path | None:
    if not package_dir.is_dir():
        return None
    candidates = sorted(path for path in package_dir.iterdir() if path.is_file() and LICENSE_FILES.match(path.name))
    return candidates[0] if candidates else None


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace").replace("\r\n", "\n").replace("\r", "\n").lstrip("\ufeff")


def header_copyright(text: str) -> list[str]:
    """The copyright lines at the top of a license text."""
    lines = [line.strip() for line in text.split("\n")[:HEADER_LINES] if COPYRIGHT.match(line)]
    return list(dict.fromkeys(lines))


def without_holders(text: str) -> str:
    """The license text with the holder's own copyright line replaced, so one text can stand for every package that carries it."""
    lines = text.rstrip().split("\n")
    out: list[str] = []
    for index, line in enumerate(lines):
        if index < HEADER_LINES and COPYRIGHT.match(line):
            if not out or out[-1] != HOLDERS_NOTE:
                out.append(HOLDERS_NOTE)
            continue
        out.append(line.rstrip())
    return "\n".join(out) + "\n"


def label_for(declared: str, text: str) -> str:
    """An SPDX identifier as declared, or the title of the license text when the package only points at its LICENSE file."""
    if declared and " " not in declared:
        return declared
    title = next((line.strip() for line in text.split("\n") if line.strip()), declared or "Unknown")
    return title.title() if title.isupper() else title


def package_author(package_dir: Path) -> str:
    """The author's name from package.json, without an e-mail address or a link."""
    try:
        author = json.loads((package_dir / "package.json").read_text(encoding="utf-8")).get("author")
    except (OSError, ValueError):
        return ""
    name = str(author.get("name", "")) if isinstance(author, dict) else str(author or "")
    return re.sub(r"\s*[<(][^>)]*[>)]", "", name).strip()


def installed_dir(modules: Path, name: str) -> Path | None:
    for candidate in (modules / name, modules / PLATFORM_SUFFIX.sub("", name)):
        if candidate.is_dir():
            return candidate
    return None


def collect(root: Path = ROOT) -> tuple[list[Package], dict[str, Text]]:
    app = root / "contract-review"
    lock = json.loads((app / "package-lock.json").read_text(encoding="utf-8"))
    modules = app / "node_modules"
    packages: list[Package] = []
    texts: dict[str, Text] = {}
    for name, version, declared in production_packages(lock):
        package_dir = installed_dir(modules, name)
        license_file = find_license_file(package_dir) if package_dir else None
        raw = read_text(license_file) if license_file else ""
        if declared in STANDARD_TEXTS and (not raw or STANDARD_CORE[declared] in collapse(raw)):
            # The package's own file carries the standard grant (or it ships none): one canonical text serves all of them.
            label, body, text_id = declared, STANDARD_TEXTS[declared], f"standard-{declared.lower()}"
        elif raw:
            label = label_for(declared, raw)
            body = without_holders(raw)
            text_id = hashlib.sha256(re.sub(r"\s+", " ", f"{label}\n{body}").encode("utf-8")).hexdigest()[:8]
        else:
            raise SystemExit(f"No license text for {name}@{version} ({declared or 'no license declared'}). Run `npm ci` in contract-review/ first.")
        texts.setdefault(text_id, Text(label, body))
        holders = header_copyright(raw)
        if holders:
            copyright_line = "; ".join(holders)
        else:
            author = package_author(package_dir) if package_dir else ""
            copyright_line = f"Not stated in the package (author: {author})" if author else "Not stated in the package"
        packages.append(Package(name, version, declared if declared and " " not in declared else label, copyright_line, text_id))
    return packages, texts


def cell(text: str) -> str:
    return text.replace("|", "\\|")


def render_markdown(packages: list[Package], texts: dict[str, Text]) -> str:
    lines = [
        "# Third-party notices",
        "",
        "The Code App in `contract-review/` and the 3D page `docs/architecture-3d.html` are compiled from the JavaScript packages below, and each is",
        "used under its own license, reproduced after the table. This file is generated by `python scripts/gen-notices.py` from",
        "`contract-review/package-lock.json`; do not edit it by hand. A copy ships inside the Code App package, and the 3D page prints the notices for",
        "the packages it contains.",
        "",
        "Not covered here: the Python packages the scripts and the Function use are installed from PyPI when you deploy and are not redistributed in",
        "this repository; the Bicep adapted from an Azure sample carries its own license in `infra/LICENSE-functions-quickstart.txt`; and the packages",
        "that only build and test the app are not part of what is distributed.",
        "",
        f"## Packages ({len(packages)})",
        "",
        "| Package | Version | License | Copyright |",
        "|---|---|---|---|",
    ]
    lines += [f"| {cell(p.name)} | {p.version} | {cell(p.license)} | {cell(p.copyright)} |" for p in packages]
    lines += ["", "## License texts"]
    users: dict[str, list[str]] = defaultdict(list)
    for p in packages:
        users[p.text_id].append(p.name)
    for text_id, text in sorted(texts.items(), key=lambda item: (item[1].label.lower(), item[0])):
        names = users[text_id]
        applies = ", ".join(names) if len(names) <= 12 else f"the {len(names)} packages above whose license is {text.label}"
        lines += ["", f"### {text.label}", "", f"Applies to: {applies}", "", "~~~~text", text.body.rstrip("\n"), "~~~~"]
    return "\n".join(lines) + "\n"


def render_json(packages: list[Package], texts: dict[str, Text]) -> str:
    data = {
        "generatedBy": "python scripts/gen-notices.py",
        "packages": {f"{p.name}@{p.version}": {"license": p.license, "copyright": p.copyright, "text": p.text_id} for p in packages},
        "texts": {text_id: {"label": text.label, "text": text.body} for text_id, text in sorted(texts.items())},
    }
    return json.dumps(data, indent=1, sort_keys=True, ensure_ascii=False) + "\n"


def outputs(root: Path = ROOT) -> dict[Path, str]:
    packages, texts = collect(root)
    markdown = render_markdown(packages, texts)
    return {root / MARKDOWN.name: markdown, root / TEXT_COPY.relative_to(ROOT): markdown, root / DATA.relative_to(ROOT): render_json(packages, texts)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--check", action="store_true", help="exit 1 when a file is out of date, and write nothing")
    args = parser.parse_args(argv)
    wanted = outputs()
    stale = [path for path, text in wanted.items() if not path.exists() or path.read_text(encoding="utf-8") != text]
    if args.check:
        for path in stale:
            print(f"out of date: {path.relative_to(ROOT).as_posix()}")
        return 1 if stale else 0
    for path, text in wanted.items():
        if path in stale:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8", newline="\n")
            print(f"wrote {path.relative_to(ROOT).as_posix()}")
    if not stale:
        print("already up to date")
    return 0


if __name__ == "__main__":
    sys.exit(main())
