from collections import deque
from copy import deepcopy
from functools import partial
from typing import TYPE_CHECKING
from typing import Any
from typing import Dict

from statemachine.graph import iterate_states_and_transitions
from statemachine.utils import run_async_from_sync

from .callbacks import CallbackMetaList
from .callbacks import CallbacksExecutor
from .callbacks import CallbacksRegistry
from .dispatcher import ObjectConfig
from .dispatcher import resolver_factory
from .event import Event
from .event_data import EventData
from .event_data import TriggerData
from .exceptions import InvalidDefinition
from .exceptions import InvalidStateValue
from .exceptions import TransitionNotAllowed
from .factory import StateMachineMetaclass
from .i18n import _
from .model import Model
from .transition import Transition

if TYPE_CHECKING:
    from .state import State


class StateMachine(metaclass=StateMachineMetaclass):
    """

    Args:
        model: An optional external object to store state. See :ref:`domain models`.

        state_field (str): The model's field which stores the current state.
            Default: ``state``.

        start_value: An optional start state value if there's no current state assigned
            on the :ref:`domain models`. Default: ``None``.

        rtc (bool): Controls the :ref:`processing model`. Defaults to ``True``
            that corresponds to a **run-to-completion** (RTC) model.

        allow_event_without_transition: If ``False`` when an event does not result in a transition,
            an exception ``TransitionNotAllowed`` will be raised.
            If ``True`` the state machine allows triggering events that may not lead to a state
            :ref:`transition`, including tolerance to unknown :ref:`event` triggers.
            Default: ``False``.

    """

    TransitionNotAllowed = TransitionNotAllowed
    """Shortcut for easy exception handling.

    Example::

        try:
            sm.send("an-inexistent-event")
        except sm.TransitionNotAllowed:
            pass
    """

    def __init__(
        self,
        model: Any = None,
        state_field: str = "state",
        start_value: Any = None,
        rtc: bool = True,
        allow_event_without_transition: bool = False,
    ):
        self.model = model if model else Model()
        self.state_field = state_field
        self.start_value = start_value
        self.allow_event_without_transition = allow_event_without_transition
        self.__initialized = False
        self.__rtc = rtc
        self.__processing: bool = False
        self._external_queue: deque = deque()
        self._callbacks_registry = CallbacksRegistry()
        self._states_for_instance: Dict[State, State] = {}
        self._observers: Dict[Any, Any] = {}

        if self._abstract:
            raise InvalidDefinition(_("There are no states or transitions."))

        self._register_callbacks()

        # Activate the initial state, this only works if the outer scope is sync code.
        # for async code, the user should manually call `await sm.activate_initial_state()`
        # after state machine creation.
        run_async_from_sync(self.activate_initial_state())

    def __init_subclass__(cls, strict_states: bool = False):
        cls._strict_states = strict_states
        super().__init_subclass__()

    if TYPE_CHECKING:
        """Makes mypy happy with dynamic created attributes"""

        def __getattr__(self, attribute: str) -> Any: ...

    def __repr__(self):
        current_state_id = self.current_state.id if self.current_state_value else None
        return (
            f"{type(self).__name__}(model={self.model!r}, state_field={self.state_field!r}, "
            f"current_state={current_state_id!r})"
        )

    def __deepcopy__(self, memo):
        deepcopy_method = self.__deepcopy__
        self.__deepcopy__ = None
        try:
            cp = deepcopy(self, memo)
        finally:
            self.__deepcopy__ = deepcopy_method
            cp.__deepcopy__ = deepcopy_method
        cp._callbacks_registry.clear()
        cp._register_callbacks()
        cp.add_observer(*cp._observers.keys())
        return cp

    def _get_initial_state(self):
        current_state_value = self.start_value if self.start_value else self.initial_state.value
        try:
            return self.states_map[current_state_value]
        except KeyError as err:
            raise InvalidStateValue(current_state_value) from err

    async def activate_initial_state(self):
        """
        Activate the initial state.

        Called automatically on state machine creation from sync code, but in
        async code, the user must call this method explicitly.

        Given how async works on python, there's no built-in way to activate the initial state that
        may depend on async code from the StateMachine.__init__ method.

        We do a `_ensure_is_initialized()` check before each event, but to check the current state
        just before the state machine is created, the user must await the activation of the initial
        state explicitly.
        """
        if self.__initialized:
            return
        self.__initialized = True
        if self.current_state_value is None:
            # send an one-time event `__initial__` to enter the current state.
            # current_state = self.current_state
            initial_transition = Transition(None, self._get_initial_state(), event="__initial__")
            initial_transition.before.clear()
            initial_transition.on.clear()
            initial_transition.after.clear()

            event_data = EventData(
                trigger_data=TriggerData(
                    machine=self,
                    event=initial_transition.event,
                ),
                transition=initial_transition,
            )
            await self._activate(event_data)

    async def _ensure_is_initialized(self):
        await self.activate_initial_state()

    def _register_callbacks(self):
        self._add_observer(
            (
                ObjectConfig.from_obj(self, skip_attrs=self._protected_attrs),
                ObjectConfig.from_obj(self.model, skip_attrs={self.state_field}),
            )
        )

        check_callbacks = self._callbacks_registry.check
        for visited in iterate_states_and_transitions(self.states):
            try:
                visited._check_callbacks(check_callbacks)
            except Exception as err:
                raise InvalidDefinition(
                    f"Error on {visited!s} when resolving callbacks: {err}"
                ) from err

    def _add_observer(self, observers):
        register = partial(self._callbacks_registry.register, resolver=resolver_factory(observers))
        for visited in iterate_states_and_transitions(self.states):
            visited._add_observer(register)

        return self

    def add_observer(self, *observers):
        """Add an observer.

        Observers are a way to generically add behavior to a :ref:`StateMachine` without changing
        its internal implementation.

        .. seealso::

            :ref:`observers`.
        """
        self._observers.update({o: None for o in observers})
        return self._add_observer(tuple(ObjectConfig.from_obj(o) for o in observers))

    def _repr_html_(self):
        return f'<div class="statemachine">{self._repr_svg_()}</div>'

    def _repr_svg_(self):
        return self._graph().create_svg().decode()

    def _graph(self):
        from .contrib.diagram import DotGraphMachine

        return DotGraphMachine(self).get_graph()

    @property
    def current_state_value(self):
        """Get/Set the current :ref:`state` value.

        This is a low level API, that can be used to assign any valid state value
        completely bypassing all the hooks and validations.
        """
        return getattr(self.model, self.state_field, None)

    @current_state_value.setter
    def current_state_value(self, value):
        if value not in self.states_map:
            raise InvalidStateValue(value)
        setattr(self.model, self.state_field, value)

    @property
    def current_state(self) -> "State":
        """Get/Set the current :ref:`state`.

        This is a low level API, that can be to assign any valid state
        completely bypassing all the hooks and validations.
        """

        try:
            state: State = self.states_map[self.current_state_value].for_instance(
                machine=self,
                cache=self._states_for_instance,
            )
            return state
        except KeyError as err:
            if self.current_state_value is None:
                raise InvalidStateValue(
                    self.current_state_value,
                    _(
                        "There's no current state set. In async code, "
                        "did you activate the initial state? "
                        "(e.g., `await sm.activate_initial_state()`)"
                    ),
                ) from err
            raise InvalidStateValue(self.current_state_value) from err

    @current_state.setter
    def current_state(self, value):
        self.current_state_value = value.value

    @property
    def events(self):
        return self.__class__.events

    @property
    def allowed_events(self):
        """List of the current allowed events."""
        return [getattr(self, event) for event in self.current_state.transitions.unique_events]

    async def _process(self, trigger):
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
        if not self.__rtc:
            # The machine is in "synchronous" mode
            return await trigger()

        # The machine is in "queued" mode
        # Add the trigger to queue and start processing in a loop.
        self._external_queue.append(trigger)

        # We make sure that only the first event enters the processing critical section,
        # next events will only be put on the queue and processed by the same loop.
        if self.__processing:
            return

        return await self._processing_loop()

    async def _processing_loop(self):
        """Execute the triggers in the queue in order until the queue is empty"""
        self.__processing = True

        # We will collect the first result as the processing result to keep backwards compatibility
        # so we need to use a sentinel object instead of `None` because the first result may
        # be also `None`, and on this case the `first_result` may be overridden by another result.
        sentinel = object()
        first_result = sentinel
        try:
            while self._external_queue:
                trigger = self._external_queue.popleft()
                try:
                    result = await trigger()
                    if first_result is sentinel:
                        first_result = result
                except Exception:
                    # Whe clear the queue as we don't have an expected behavior
                    # and cannot keep processing
                    self._external_queue.clear()
                    raise
        finally:
            self.__processing = False
        return first_result if first_result is not sentinel else None

    async def _activate(self, event_data: EventData):
        transition = event_data.transition
        source = event_data.state
        target = transition.target

        result = await self._callbacks(transition.before).call(
            *event_data.args, **event_data.extended_kwargs
        )
        if source is not None and not transition.internal:
            await self._callbacks(source.exit).call(*event_data.args, **event_data.extended_kwargs)

        result += await self._callbacks(transition.on).call(
            *event_data.args, **event_data.extended_kwargs
        )

        self.current_state = target
        event_data.state = target

        if not transition.internal:
            await self._callbacks(target.enter).call(
                *event_data.args, **event_data.extended_kwargs
            )
        await self._callbacks(transition.after).call(
            *event_data.args, **event_data.extended_kwargs
        )

        if len(result) == 0:
            result = None
        elif len(result) == 1:
            result = result[0]

        return result

    def send(self, event: str, *args, **kwargs):
        """Send an :ref:`Event` to the state machine.

        This is a thin wrapper around :meth:`async_send` to allow synchronous
        code to send events.

        .. seealso::

            See: :ref:`triggering events`.

        """
        return run_async_from_sync(self.async_send(event, *args, **kwargs))

    async def async_send(self, event: str, *args, **kwargs):
        """Send an :ref:`Event` to the state machine.

        .. seealso::

            See: :ref:`triggering events`.

        """
        event_instance: Event = Event(event)
        return await event_instance.trigger(self, *args, **kwargs)

    def _callbacks(self, meta_list: CallbackMetaList) -> CallbacksExecutor:
        return self._callbacks_registry[meta_list]
