# coding: utf-8

_REGISTRY = {}


def register(cls):
    _REGISTRY[cls.__name__] = cls
    return cls


def get_machine_cls(name):
    return _REGISTRY[name]
