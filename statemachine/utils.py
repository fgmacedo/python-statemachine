import asyncio
import re
import threading
from typing import Any

_SEPARATOR_RE = re.compile(r"[_.]")

_cached_loop = threading.local()
"""Loop that will be used when the SM is running in a synchronous context. One loop per thread."""


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


def humanize_id(id: str) -> str:
    """Convert a machine identifier to a human-readable name.

    Splits on ``_`` and ``.`` separators and capitalizes the first word.

    >>> humanize_id("go")
    'Go'
    >>> humanize_id("done_state_parent")
    'Done state parent'
    >>> humanize_id("error.execution")
    'Error execution'
    """
    return _SEPARATOR_RE.sub(" ", id).strip().capitalize()


def run_async_from_sync(coroutine: "Any") -> "Any":
    """
    Compatibility layer to run an async coroutine from a synchronous context.
    """
    global _cached_loop
    try:
        asyncio.get_running_loop()
        return coroutine
    except RuntimeError:
        if not hasattr(_cached_loop, "loop"):
            _cached_loop.loop = asyncio.new_event_loop()
        return _cached_loop.loop.run_until_complete(coroutine)
