# coding: utf-8
import warnings

from .utils import qualname


_REGISTRY = {}
_initialized = False


def register(cls):
    _REGISTRY[qualname(cls)] = cls
    _REGISTRY[cls.__name__] = cls
    return cls


def get_machine_cls(name):
    init_registry()
    if "." not in name:
        warnings.warn(
            """Use fully qualified names (<module>.<class>) for state machine mixins.""",
            DeprecationWarning,
        )
    return _REGISTRY[name]


def init_registry():
    global _initialized
    if not _initialized:
        load_modules(["statemachine", "statemachines"])
        _initialized = True


def _has_django():
    try:
        import django  # noqa

        return True
    except ImportError:
        # Not a django project
        pass
    return False


def load_modules(modules=None):
    if not _has_django():
        return
    from django.utils.module_loading import autodiscover_modules

    for module in modules:
        autodiscover_modules(module)
