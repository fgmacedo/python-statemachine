# coding: utf-8

_REGISTRY = {}
_initialized = False


def register(cls):
    _REGISTRY[cls.__name__] = cls
    return cls


def get_machine_cls(name):
    init_registry()
    return _REGISTRY[name]


def init_registry():
    global _initialized
    if not _initialized:
        load_modules(['statemachine', 'statemachines'])
        _initialized = True


def load_modules(modules=None):
    try:
        import django  # noqa
    except ImportError:
        # Not a django project
        return
    try:  # pragma: no cover
        from django.utils.module_loading import autodiscover_modules
    except ImportError:  # pragma: no cover
        # Django 1.6 compat to provide `autodiscover_modules`
        def autodiscover_modules(module_name):
            from django.conf import settings
            from django.utils.importlib import import_module

            for app in settings.INSTALLED_APPS:
                # Attempt to import the app's `module_name`.
                try:
                    import_module('{app}.{module}'.format(app=app, module=module_name))
                except Exception:
                    pass

        for module in modules:
            autodiscover_modules(module)
