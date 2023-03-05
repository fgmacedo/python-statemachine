import importlib
from pathlib import Path


def import_module_by_path(src_file: Path):
    module_name = str(src_file).replace("/", ".")
    try:
        return importlib.import_module(module_name)
    except ModuleNotFoundError:
        return
