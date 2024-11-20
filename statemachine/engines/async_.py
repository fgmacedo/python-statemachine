from typing import TYPE_CHECKING

from ..event_data import EventData
from ..event_data import TriggerData
from ..exceptions import InvalidDefinition
from ..exceptions import TransitionNotAllowed
from ..i18n import _
from .base import BaseEngine

if TYPE_CHECKING:
    from ..statemachine import StateMachine
    from ..transition import Transition


class AsyncEngine(BaseEngine):
    def __init__(self, sm: "StateMachine", rtc: bool = True):
        if not rtc:
            raise InvalidDefinition(_("Only RTC is supported on async engine"))
        super().__init__(sm=sm, rtc=rtc)

    async def activate_initial_state(self):
        """
        Activate the initial state.

        Called automatically on state machine creation from sync code, but in
        async code, the user must call this method explicitly.

        Given how async works on python, there's no built-in way to activate the initial state that
        may depend on async code from the StateMachine.__init__ method.
        """
        return await self.processing_loop()

    async def processing_loop(self):
        """Process event triggers.

        The simplest implementation is the non-RTC (synchronous),
        where the trigger will be run immediately and the result collected as the return.

        .. note::

            While processing the trigger, if others events are generated, they
            will also be processed immediately, so a "nested" behavior happens.

        If the machine is on ``rtc`` model (queued), the event is put on a queue, and only the
        first event will have the result collected.

        .. note::
            While processing the queue items, if others events are generated, they
            will be processed sequentially (and not nested).

        """
        # We make sure that only the first event enters the processing critical section,
        # next events will only be put on the queue and processed by the same loop.
        if not self._processing.acquire(blocking=False):
            return None

        # We will collect the first result as the processing result to keep backwards compatibility
        # so we need to use a sentinel object instead of `None` because the first result may
        # be also `None`, and on this case the `first_result` may be overridden by another result.
        first_result = self._sentinel
        try:
            # Execute the triggers in the queue in FIFO order until the queue is empty
            while self._external_queue:
                trigger_data = self._external_queue.popleft()
                try:
                    result = await self._trigger(trigger_data)
                    if first_result is self._sentinel:
                        first_result = result
                except Exception:
                    # Whe clear the queue as we don't have an expected behavior
                    # and cannot keep processing
                    self._external_queue.clear()
                    raise
        finally:
            self._processing.release()
        return first_result if first_result is not self._sentinel else None

    async def _trigger(self, trigger_data: TriggerData):
        executed = False
        if trigger_data.event == "__initial__":
            transition = self._initial_transition(trigger_data)
            await self._activate(trigger_data, transition)
            return self._sentinel

        state = self.sm.current_state
        for transition in state.transitions:
            if not transition.match(trigger_data.event):
                continue

            executed, result = await self._activate(trigger_data, transition)
            if not executed:
                continue
            break
        else:
            if not self.sm.allow_event_without_transition:
                raise TransitionNotAllowed(trigger_data.event, state)

        return result if executed else None

    async def _activate(self, trigger_data: TriggerData, transition: "Transition"):
        event_data = EventData(trigger_data=trigger_data, transition=transition)
        args, kwargs = event_data.args, event_data.extended_kwargs

        await self.sm._callbacks.async_call(transition.validators.key, *args, **kwargs)
        if not await self.sm._callbacks.async_all(transition.cond.key, *args, **kwargs):
            return False, None

        source = transition.source
        target = transition.target

        result = await self.sm._callbacks.async_call(transition.before.key, *args, **kwargs)
        if source is not None and not transition.internal:
            await self.sm._callbacks.async_call(source.exit.key, *args, **kwargs)

        result += await self.sm._callbacks.async_call(transition.on.key, *args, **kwargs)

        self.sm.current_state = target
        event_data.state = target
        kwargs["state"] = target

        if not transition.internal:
            await self.sm._callbacks.async_call(target.enter.key, *args, **kwargs)
        await self.sm._callbacks.async_call(transition.after.key, *args, **kwargs)

        if len(result) == 0:
            result = None
        elif len(result) == 1:
            result = result[0]

        return True, result
