"""Timeout helper for state invocations.

Provides a ``timeout()`` function that returns an :class:`~statemachine.invoke.IInvoke`
handler. When a state is entered, the handler waits for the given duration; if the state
is not exited before the timer expires, an event is sent to the machine.

Example::

    from statemachine.contrib.timeout import timeout

    class MyMachine(StateChart):
        waiting = State(initial=True, invoke=timeout(5, on="expired"))
        timed_out = State(final=True)
        expired = waiting.to(timed_out)
"""

from typing import TYPE_CHECKING
from typing import Any

if TYPE_CHECKING:
    from statemachine.invoke import InvokeContext


class _Timeout:
    """IInvoke handler that waits for a duration and optionally sends an event."""

    def __init__(self, duration: float, on: "str | None" = None):
        self.duration = duration
        self.on = on

    def run(self, ctx: "InvokeContext") -> Any:
        """Wait for the timeout duration, then optionally send an event.

        If the owning state is exited before the timer expires (``ctx.cancelled``
        is set), the handler returns immediately without sending anything.
        """
        fired = not ctx.cancelled.wait(timeout=self.duration)
        if not fired:
            # State was exited before the timeout — nothing to do.
            return None
        if self.on is not None:
            ctx.send(self.on)
        return None

    def __repr__(self) -> str:
        args = f"{self.duration}"
        if self.on is not None:
            args += f", on={self.on!r}"
        return f"timeout({args})"


def timeout(duration: float, *, on: "str | None" = None) -> _Timeout:
    """Create a timeout invoke handler.

    Args:
        duration: Time in seconds to wait before firing.
        on: Event name to send when the timeout expires. If ``None``, the
            standard ``done.invoke.<state>`` event fires via invoke completion.

    Returns:
        An :class:`~statemachine.invoke.IInvoke`-compatible handler.

    Raises:
        ValueError: If *duration* is not positive.
    """
    if duration <= 0:
        raise ValueError(f"timeout duration must be positive, got {duration}")
    return _Timeout(duration=duration, on=on)
