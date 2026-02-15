from typing import List
from typing import Optional

from .utils import qualname

try:
    from django.utils.module_loading import autodiscover_modules
except ImportError:  # pragma: no cover
    # Not a django project
    def autodiscover_modules(module_name: str):
        pass


_REGISTRY = {}
_initialized = False


def register(cls):
    _REGISTRY[qualname(cls)] = cls
    return cls


def get_machine_cls(name):
    init_registry()
    return _REGISTRY[name]


def init_registry():
    global _initialized
    if not _initialized:
        load_modules(["statemachine", "statemachines"])
        _initialized = True


def load_modules(modules: Optional[List[str]] = None) -> None:
    for module in modules or []:
        autodiscover_modules(module)
