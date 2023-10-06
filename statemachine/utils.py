def qualname(cls):
    """
    Returns a fully qualified name of the class, to avoid name collisions.
    """
    return ".".join([cls.__module__, cls.__name__])


def ensure_iterable(obj):
    if isinstance(obj, str):
        return [obj]
    try:
        return iter(obj)
    except TypeError:
        return [obj]
