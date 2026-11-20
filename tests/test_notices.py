"""The third-party notices list every package the Code App is built from, under a license the project has accepted, and the 3D page prints
the notices for the packages it contains.

Regenerate them with `python scripts/gen-notices.py` after any change to the app's dependencies.
"""

from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "contract-review"
PAGE = ROOT / "docs" / "architecture-3d.html"

_spec = importlib.util.spec_from_file_location("gen_notices", ROOT / "scripts" / "gen-notices.py")
assert _spec is not None and _spec.loader is not None
notices = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = notices
_spec.loader.exec_module(notices)

# A license outside this list is not wrong, but it is a decision: someone should read it before it ships.
ACCEPTED = {"MIT", "Apache-2.0", "0BSD", "ISC", "BSD-2-Clause", "BSD-3-Clause", "Microsoft Software License Terms"}
REGENERATE = "Run `python scripts/gen-notices.py`."


def listed() -> dict[str, str]:
    """Package@version to license, from the rows of the table in THIRD-PARTY-NOTICES.md."""
    rows = re.findall(r"^\| (\S+) \| (\S+) \| ([^|]+?) \| .* \|$", (ROOT / "THIRD-PARTY-NOTICES.md").read_text(encoding="utf-8"), re.MULTILINE)
    return {f"{name}@{version}": license_ for name, version, license_ in rows if version[0].isdigit()}


# ---- the committed notices ---------------------------------------------------------------------------------------------

def test_the_notices_list_every_package_the_app_is_built_from() -> None:
    lock = json.loads((APP / "package-lock.json").read_text(encoding="utf-8"))
    wanted = {f"{name}@{version}" for name, version, _ in notices.production_packages(lock)}
    assert wanted == set(listed()), f"THIRD-PARTY-NOTICES.md and the lockfile disagree. {REGENERATE}"


def test_every_license_is_one_the_project_has_accepted() -> None:
    unexpected = {package: license_ for package, license_ in listed().items() if license_ not in ACCEPTED}
    assert not unexpected, f"read these licenses, then add them to ACCEPTED in this test if they are fine: {unexpected}"


def test_the_copy_in_the_app_package_and_the_data_file_agree_with_the_notices() -> None:
    text = (ROOT / "THIRD-PARTY-NOTICES.md").read_text(encoding="utf-8")
    assert (APP / "public" / "THIRD-PARTY-NOTICES.txt").read_text(encoding="utf-8") == text, REGENERATE
    data = json.loads((APP / "src" / "standalone" / "third-party.json").read_text(encoding="utf-8"))
    assert set(data["packages"]) == set(listed()), REGENERATE
    assert {entry["text"] for entry in data["packages"].values()} <= set(data["texts"]), REGENERATE


# ---- the 3D page -------------------------------------------------------------------------------------------------------

@pytest.fixture(scope="module")
def page() -> str:
    return PAGE.read_text(encoding="utf-8")


def notices_section(page: str) -> str:
    match = re.search(r'<details id="open-source-notices".*?</details>', page, re.DOTALL)
    assert match, "the 3D page has no open-source notices section: run `npm run build:standalone` in contract-review/"
    return match.group(0)


def test_the_page_prints_notices_for_the_libraries_it_contains(page: str) -> None:
    section = notices_section(page)
    info = re.search(r'<script type="application/json" id="build-info">(.*?)</script>', page, re.DOTALL)
    assert info, "the 3D page has no build-info block: run `npm run build:standalone` in contract-review/"
    built_with = json.loads(info.group(1))["packages"]
    for name in ("react", "react-dom", "three"):
        assert re.search(rf"<td>{re.escape(name)}</td><td>{re.escape(built_with[name])}</td>", section), f"{name} {built_with[name]} is bundled but not listed"
    assert section.count("Permission is hereby granted") == 1  # one MIT text, however many packages use it


def test_the_notices_in_the_page_name_only_packages_that_are_in_the_data_file(page: str) -> None:
    data = json.loads((APP / "src" / "standalone" / "third-party.json").read_text(encoding="utf-8"))
    rows = re.findall(r"<tr><td>([^<]+)</td><td>([^<]+)</td>", notices_section(page))
    assert rows and {f"{name}@{version}" for name, version in rows} <= set(data["packages"])


def test_the_notices_section_cannot_break_out_of_the_page(page: str) -> None:
    section = notices_section(page)
    assert "<script" not in section.lower() and "<!--" not in section


# ---- the generator -----------------------------------------------------------------------------------------------------

def make_project(tmp_path: Path, lock_packages: dict[str, Any], files: dict[str, str]) -> Path:
    app = tmp_path / "contract-review"
    app.mkdir(parents=True)
    (app / "package-lock.json").write_text(json.dumps({"packages": {"": {"name": "app"}, **lock_packages}}), encoding="utf-8")
    for relative, text in files.items():
        target = app / "node_modules" / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    return tmp_path


def mit(title: str = "MIT License", holder: str = "Copyright (c) 2020 Someone") -> str:
    return f"{title}\n\n{holder}\n\n" + notices.MIT.split("Copyright (c) the holders named in the table above\n\n", 1)[1]


def test_development_only_packages_are_left_out() -> None:
    lock = {
        "packages": {
            "": {},
            "node_modules/a": {"version": "1.0.0", "license": "MIT"},
            "node_modules/b": {"version": "2.0.0", "dev": True, "license": "MIT"},
            "node_modules/c": {"version": "3.0.0", "devOptional": True, "license": "MIT"},
            "node_modules/x/node_modules/d": {"version": "4.0.0", "license": "ISC"},
        }
    }
    assert notices.production_packages(lock) == [("a", "1.0.0", "MIT"), ("d", "4.0.0", "ISC")]


def test_the_same_license_with_a_different_title_is_one_text(tmp_path: Path) -> None:
    root = make_project(tmp_path, {"node_modules/a": {"version": "1.0.0", "license": "MIT"}, "node_modules/b": {"version": "1.0.0", "license": "MIT"}},
                        {"a/LICENSE": mit(), "b/LICENSE.md": mit(title="@scope/b", holder="Copyright (c) Microsoft Corporation")})
    packages, texts = notices.collect(root)
    assert len(texts) == 1 and {p.text_id for p in packages} == {"standard-mit"}
    assert [p.copyright for p in packages] == ["Copyright (c) 2020 Someone", "Copyright (c) Microsoft Corporation"]


def test_a_license_that_only_claims_to_be_mit_keeps_its_own_text(tmp_path: Path) -> None:
    root = make_project(tmp_path, {"node_modules/a": {"version": "1.0.0", "license": "MIT"}},
                        {"a/LICENSE": "MIT License\n\nCopyright (c) Someone\n\nYou may use this, but only on Tuesdays.\n"})
    _, texts = notices.collect(root)
    assert "standard-mit" not in texts and "Tuesdays" in next(iter(texts.values())).body


def test_a_package_with_no_license_file_gets_the_standard_text_and_no_invented_copyright(tmp_path: Path) -> None:
    root = make_project(tmp_path, {"node_modules/a": {"version": "1.0.0", "license": "MIT"}},
                        {"a/package.json": json.dumps({"author": "Ada Lovelace <ada@example.org> (https://example.org)"})})
    (package,), _ = notices.collect(root)
    assert package.text_id == "standard-mit" and package.copyright == "Not stated in the package (author: Ada Lovelace)"


def test_a_platform_build_of_a_package_uses_the_license_of_its_base_package(tmp_path: Path) -> None:
    root = make_project(
        tmp_path,
        {
            "node_modules/lib": {"version": "1.0.0", "license": "MIT"},
            "node_modules/lib-linux-arm64-gnu": {"version": "1.0.0", "license": "MIT", "optional": True},
        },
        {"lib/LICENSE": mit()},
    )
    packages, _ = notices.collect(root)
    assert [p.name for p in packages] == ["lib", "lib-linux-arm64-gnu"] and packages[1].copyright == packages[0].copyright


def test_a_license_with_no_text_anywhere_stops_the_run(tmp_path: Path) -> None:
    root = make_project(tmp_path, {"node_modules/a": {"version": "1.0.0", "license": "Custom-1.0"}}, {})
    with pytest.raises(SystemExit, match="No license text for a@1.0.0"):
        notices.collect(root)


def test_only_the_top_of_a_license_counts_as_the_holders_copyright() -> None:
    apache = "Apache License\nVersion 2.0\n\n" + "terms\n" * 20 + "Copyright [yyyy] [name of copyright owner]\n"
    assert notices.header_copyright(apache) == []
    assert notices.header_copyright("Copyright (c) A\nCopyright (c) A\n(c) B\n\nterms") == ["Copyright (c) A", "(c) B"]
    assert notices.without_holders("Copyright (c) A\nCopyright (c) B\n\nterms\n") == f"{notices.HOLDERS_NOTE}\n\nterms\n"
