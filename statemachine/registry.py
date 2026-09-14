from typing import TYPE_CHECKING

from .utils import qualname

if TYPE_CHECKING:
    from .statemachine import StateMachine

try:
    from django.utils.module_loading import autodiscover_modules
except ImportError:  # pragma: no cover
    # Not a django project
    def autodiscover_modules(module_name: str):
        pass


_REGISTRY: "dict[str, type[StateMachine]]" = {}
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


def load_modules(modules: list[str] | None = None) -> None:
    for module in modules or []:
        autodiscover_modules(module)
