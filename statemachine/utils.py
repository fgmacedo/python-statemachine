import asyncio

_cached_loop = None


def qualname(cls):
    """
    Returns a fully qualified name of the class, to avoid name collisions.
    """
    return ".".join([cls.__module__, cls.__name__])


def ensure_iterable(obj):
    """
    Returns an iterator if obj is not an instance of string or if it
    encounters type error, otherwise it returns a list.
    """
    if isinstance(obj, str):
        return [obj]
    try:
        return iter(obj)
    except TypeError:
        return [obj]


def run_async_from_sync(coroutine):
    """
    Run an async coroutine from a synchronous context.
    """
    global _cached_loop
    try:
        asyncio.get_running_loop()
        return asyncio.ensure_future(coroutine)
    except RuntimeError:
        if _cached_loop is None:
            _cached_loop = asyncio.new_event_loop()
        return _cached_loop.run_until_complete(coroutine)
