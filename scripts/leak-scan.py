"""Check that the files about to be committed carry none of this project's identifiers.

The identifiers come from .env, and from the azd environment under .azure/: ids, the sign-in account, and the hosts of the
Power Platform and SharePoint addresses. The report names the setting that matched and where, never the value itself.

    python scripts/leak-scan.py              # the files git would commit: tracked, plus untracked and not ignored
    python scripts/leak-scan.py PATH [...]   # the named files or folders instead

Exit code 0 when clean, 1 when something matched, 2 when the scan could not run. Office files (.xlsx, .docx, .pptx) are read part
by part because they are zip packages of XML, and a .zip is read member by member (the solution export); other binary files are
listed, not read.
"""

from __future__ import annotations

import argparse
import io
import re
import subprocess
import sys
import zipfile
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent

GUID = re.compile(r"^[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}$", re.IGNORECASE)
HEX32 = re.compile(r"^[0-9a-f]{32}$", re.IGNORECASE)
EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
SETTING = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*?)\s*$")

MIN_TERM = 6
# On these domains the first label is the organization or tenant name, which identifies it as well as an id does.
# Azure resource addresses are not hidden: the docs name them on purpose.
TENANT_DOMAINS = ("dynamics.com", "sharepoint.com", "onmicrosoft.com")
# Microsoft's own client id for the Dataverse MCP server; it is public, and .env.example carries it as the default.
PUBLIC_SETTINGS = ("MCP_CLIENT_ID",)
MAX_BYTES = 5_000_000
OFFICE_SUFFIXES = (".xlsx", ".docx", ".pptx")
PACKAGE_SUFFIXES = OFFICE_SUFFIXES + (".zip",)


class ScanError(Exception):
    pass


def read_settings(path: Path) -> dict[str, str]:
    settings: dict[str, str] = {}
    if path.is_file():
        for line in path.read_text(encoding="utf-8-sig").splitlines():
            match = SETTING.match(line)
            if match:
                settings[match.group(1)] = match.group(2).strip("\"'")
    return settings


def identifiers(settings: dict[str, str]) -> dict[str, str]:
    """Each identifier worth hiding, lower-cased, mapped to the setting it came from."""
    found: dict[str, str] = {}

    def add(term: str, label: str) -> None:
        if len(term) >= MIN_TERM:
            found.setdefault(term.lower(), label)

    for key, value in settings.items():
        if key in PUBLIC_SETTINGS:
            continue
        if GUID.match(value) or HEX32.match(value):
            add(value, key)
            add(value.replace("-", ""), key)
        elif EMAIL.match(value):
            domain = value.split("@", 1)[1]
            add(value, key)
            add(domain, f"{key} domain")
            if domain.lower().endswith(TENANT_DOMAINS):
                add(domain.split(".")[0], f"{key} domain")
        elif re.match(r"^https?://", value, re.IGNORECASE):
            host = (urlparse(value).hostname or "").lower()
            if host.endswith(TENANT_DOMAINS):
                add(host, f"{key} host")
                add(host.split(".")[0], f"{key} host")
    return found


def project_identifiers(root: Path) -> dict[str, str]:
    found = identifiers(read_settings(root / ".env"))
    for azd_env in sorted((root / ".azure").glob("*/.env")):
        for term, label in identifiers(read_settings(azd_env)).items():
            found.setdefault(term, f"{label} (azd)")
    return found


def candidate_files(root: Path, paths: list[str]) -> list[Path]:
    if paths:
        files: list[Path] = []
        for raw in paths:
            path = Path(raw)
            files.extend(sorted(item for item in path.rglob("*") if item.is_file()) if path.is_dir() else [path])
        return files
    result = subprocess.run(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        cwd=root, capture_output=True, check=False,
    )
    if result.returncode != 0:
        raise ScanError("this is not a git repository; name the files or folders to check")
    return [root / name for name in result.stdout.decode("utf-8").split("\0") if name]


def matches(text: str, terms: dict[str, str]) -> list[tuple[int, str]]:
    """The line number and setting of every identifier found in the text, once each."""
    return sorted({
        (number, label)
        for number, line in enumerate(text.lower().splitlines(), 1)
        for term, label in terms.items()
        if term in line
    })


def hidden(name: str, terms: dict[str, str]) -> str:
    """The name with every identifier replaced by the setting it came from, longest first."""
    for term, label in sorted(terms.items(), key=lambda item: -len(item[0])):
        name = re.sub(re.escape(term), f"<{label}>", name, flags=re.IGNORECASE)
    return name


def shown(root: Path, path: Path) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve())).replace("\\", "/")
    except ValueError:
        return str(path)


def office_parts(data: bytes, any_text: bool = False) -> list[tuple[str, str]]:
    """The name and text of each XML part in an Office file, which is a zip package. For a plain zip (any_text), every
    member that is text and not too large: a solution export holds JSON and JavaScript as well as XML."""
    with zipfile.ZipFile(io.BytesIO(data)) as package:
        parts = []
        for item in package.infolist():
            if item.is_dir() or item.file_size > MAX_BYTES:
                continue
            body = package.read(item)
            if any_text and b"\0" in body[:8192]:
                continue
            if any_text or item.filename.endswith((".xml", ".rels")):
                parts.append((item.filename, body.decode("utf-8", errors="replace")))
        return parts


def scan(root: Path, files: list[Path], terms: dict[str, str]) -> tuple[list[str], list[str], int]:
    """Returns the problems found, the files skipped as binary, and how many files were read."""
    problems: list[str] = []
    binary: list[str] = []
    read = 0
    for path in files:
        if not path.is_file():
            continue
        plain = shown(root, path)
        name = hidden(plain, terms)
        if name != plain:
            problems.append(f"{name}  (file name)")
        data = path.read_bytes()
        if path.suffix.lower() in PACKAGE_SUFFIXES and zipfile.is_zipfile(io.BytesIO(data)):
            read += 1
            for part, text in office_parts(data, any_text=path.suffix.lower() == ".zip"):
                for label in sorted({label for _, label in matches(text, terms)}):
                    problems.append(f"{name}!{part}  {label}")
            continue
        if b"\0" in data[:8192] or len(data) > MAX_BYTES:
            binary.append(name)
            continue
        read += 1
        for number, label in matches(data.decode("utf-8", errors="replace"), terms):
            problems.append(f"{name}:{number}  {label}")
    return problems, binary, read


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("paths", nargs="*", help="files or folders to check instead of what git would commit")
    args = parser.parse_args(argv)
    try:
        terms = project_identifiers(ROOT)
        if not terms:
            raise ScanError("no identifiers to look for: .env is missing or holds no ids, accounts or addresses")
        files = candidate_files(ROOT, args.paths)
    except ScanError as error:
        print(f"ERROR: {error}", flush=True)
        return 2
    problems, binary, read = scan(ROOT, files, terms)
    if binary:
        print(f"Not read ({len(binary)} binary or very large): {', '.join(binary[:8])}{' ...' if len(binary) > 8 else ''}")
    if problems:
        print(f"FOUND project identifiers in {len(problems)} place(s); the matching setting is named, not its value:")
        for problem in problems:
            print(f"  {problem}")
        return 1
    print(f"CLEAN: {read} files read against {len(terms)} identifiers from .env and the azd environment.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
