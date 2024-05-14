import asyncio


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
    try:
        loop = asyncio.get_running_loop()
        return asyncio.ensure_future(coroutine)
    except RuntimeError:
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(coroutine)
