def qualname(cls):
    """
    Returns a fully qualified name of the class, to avoid name collisions.
    """
    return ".".join([cls.__module__, cls.__name__])


def _is_string(obj):
    return isinstance(obj, (str, str))  # type(u""") is a small hack for Python2


def ensure_iterable(obj):
    if _is_string(obj):
        return [obj]
    try:
        return iter(obj)
    except TypeError:
        return [obj]
