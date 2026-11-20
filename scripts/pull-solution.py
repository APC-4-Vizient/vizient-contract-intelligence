"""Export the VizientContractPOC solution from Dataverse and unpack it into dataverse/solution/.

The unpacked files are the reviewable, diffable record of every Power Platform object in the solution.
The export goes through the Web API with this project's own sign-in, and the unpack is offline, so this
never touches the pac CLI's global auth profile.

    python scripts/pull-solution.py

dataverse/solution/ is generated: refresh it with this script and do not edit it by hand.
dataverse/<solution>_unmanaged.zip is the same export as a file that Power Apps can import (Solutions > Import), with the
Code App package inside. The files that hold the current value of an environment variable are removed from both the
unpacked folder and the zip. One of those values is the Function key, and the others are tenant-specific, so they must
never reach git.
"""

from __future__ import annotations

import io
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

import schemalib
from dvweb import Dataverse

TARGET = schemalib.ROOT / "dataverse" / "solution"
VALUE_FILE = "environmentvariablevalues.json"


def strip_environment_values(folder: Path) -> int:
    """Delete every environment variable value file under folder and return how many there were."""
    found = [path for path in folder.rglob(VALUE_FILE) if path.is_file()]
    for path in found:
        path.unlink()
    return len(found)


def strip_zip_values(data: bytes) -> tuple[bytes, int]:
    """The solution zip without its environment variable value entries, and how many were removed."""
    source = zipfile.ZipFile(io.BytesIO(data))
    out = io.BytesIO()
    removed = 0
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as target:
        for item in source.infolist():
            if item.filename.rsplit("/", 1)[-1] == VALUE_FILE:
                removed += 1
                continue
            target.writestr(item, source.read(item))
    return out.getvalue(), removed


def main() -> int:
    pac = shutil.which("pac")
    if not pac:
        print("pac CLI not found. Install it with: dotnet tool install --global Microsoft.PowerApps.CLI.Tool")
        print("(unpack is offline; no pac sign-in is needed)")
        return 1

    name = schemalib.load_schema()["solution"]
    data = Dataverse("dv-solution", solution=name).export_solution(name)
    TARGET.mkdir(parents=True, exist_ok=True)
    clean, dropped = strip_zip_values(data)
    zip_path = TARGET.parent / f"{name}_unmanaged.zip"
    zip_path.write_bytes(clean)
    print(f"Wrote {zip_path.relative_to(schemalib.ROOT)} ({len(clean):,} bytes, {dropped} environment variable value entr{'y' if dropped == 1 else 'ies'} removed)")
    with tempfile.TemporaryDirectory(prefix="vz-solution-", ignore_cleanup_errors=True) as scratch:
        archive = Path(scratch) / f"{name}.zip"
        archive.write_bytes(data)
        print(f"Exported {name}: {len(data):,} bytes")
        result = subprocess.run(
            [pac, "solution", "unpack", "--zipfile", str(archive), "--folder", str(TARGET),
             "--packagetype", "Unmanaged", "--allowWrite", "true", "--allowDelete", "true", "--clobber", "true"],
            capture_output=True, text=True)
    if result.returncode != 0:
        print(result.stdout)
        print(result.stderr, file=sys.stderr)
        print("pac solution unpack failed.")
        return 1

    stripped = strip_environment_values(TARGET)
    files = [p for p in TARGET.rglob("*") if p.is_file()]
    entities = sorted(p.name for p in (TARGET / "Entities").iterdir()) if (TARGET / "Entities").is_dir() else []
    print(f"Unpacked {len(files)} files into {TARGET.relative_to(schemalib.ROOT)}")
    if stripped:
        print(f"Removed {stripped} environment variable value file(s); they stay in Dataverse and out of git")
    print(f"Tables: {', '.join(entities) or 'none'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
