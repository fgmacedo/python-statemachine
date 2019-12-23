# coding: utf-8
import warnings

_REGISTRY = {}
_initialized = False


def _qualname(cls):
    """
    Returns a fully qualified name of the class, to avoid name collisions.
    """
    return u'.'.join([cls.__module__, cls.__name__])


def register(cls):
    _REGISTRY[_qualname(cls)] = cls
    _REGISTRY[cls.__name__] = cls
    return cls


def get_machine_cls(name):
    init_registry()
    if '.' not in name:
        warnings.warn(
            """Use fully qualified names (<module>.<class>) for state machine mixins.""",
            DeprecationWarning
        )
    return _REGISTRY[name]


def init_registry():
    global _initialized
    if not _initialized:
        load_modules(['statemachine', 'statemachines'])
        _initialized = True


def _has_django():
    try:
        import django  # noqa
        return True
    except ImportError:
        # Not a django project
        pass
    return False


def _autodiscover_modules(module_name):  # pragma: no cover
    "Django 1.6 compat to provide `autodiscover_modules`"
    from django.conf import settings
    from django.utils.importlib import import_module

    for app in settings.INSTALLED_APPS:
        # Attempt to import the app's `module_name`.
        try:
            import_module('{app}.{module}'.format(app=app, module=module_name))
        except Exception:
            pass


def load_modules(modules=None):
    if not _has_django():
        return
    try:  # pragma: no cover
        from django.utils.module_loading import autodiscover_modules
    except ImportError:  # pragma: no cover
        autodiscover_modules = _autodiscover_modules

    for module in modules:
        autodiscover_modules(module)
