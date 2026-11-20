"""Import a script whose file name has a hyphen, such as run-local.py: an import statement cannot name it."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

SCRIPTS = Path(__file__).resolve().parent


def load_script(file_name: str, module_name: str) -> ModuleType:
    """Run scripts/<file_name> as the module module_name and return it. A dataclass resolves its string annotations
    through sys.modules, so the module is registered there before its code runs."""
    spec = importlib.util.spec_from_file_location(module_name, SCRIPTS / file_name)
    if spec is None or spec.loader is None:
        raise ImportError(f"{file_name} cannot be loaded as a module")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module
