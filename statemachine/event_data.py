from dataclasses import dataclass
from dataclasses import field
from time import time
from typing import TYPE_CHECKING
from typing import Any
from uuid import uuid4

if TYPE_CHECKING:
    from .event import Event
    from .state import State
    from .statemachine import StateMachine
    from .transition import Transition


@dataclass(order=True)
class TriggerData:
    machine: "StateMachine" = field(compare=False)

    event: "Event | None" = field(compare=False)
    """The Event that was triggered."""

    send_id: "str | None" = field(compare=False, default=None)
    """A string literal to be used as the id of this instance of :ref:`TriggerData`.

    Allow revoking a delayed :ref:`TriggerData` instance.
    """

    execution_time: float = field(default=0.0)
    """The time at which the :ref:`Event` should run."""

    model: Any = field(init=False, compare=False)
    """A reference to the underlying model that holds the current :ref:`State`."""

    args: tuple = field(default_factory=tuple, compare=False)
    """All positional arguments provided on the :ref:`Event`."""

    kwargs: dict = field(default_factory=dict, compare=False)
    """All keyword arguments provided on the :ref:`Event`."""

    def __post_init__(self):
        self.model = self.machine.model
        delay = self.event.delay if self.event and self.event.delay else 0
        self.execution_time = time() + (delay / 1000)
        if self.send_id is None:
            self.send_id = uuid4().hex


@dataclass
class EventData:
    trigger_data: TriggerData
    """The :ref:`TriggerData` of the :ref:`event`."""

    transition: "Transition"
    """The :ref:`Transition` instance that was activated by the :ref:`Event`."""

    state: "State" = field(init=False)
    """The current :ref:`State` of the :ref:`statemachine`."""

    source: "State" = field(init=False)
    """The :ref:`State` which :ref:`statemachine` was in when the Event started."""

    target: "State" = field(init=False)
    """The destination :ref:`State` of the :ref:`transition`."""

    result: "Any | None" = None

    executed: bool = False

    def __post_init__(self):
        self.state = self.transition.source
        self.source = self.transition.source
        self.target = self.transition.target
        self.machine = self.trigger_data.machine

    @property
    def event(self):
        return self.trigger_data.event

    @property
    def args(self):
        return self.trigger_data.args

    @property
    def extended_kwargs(self):
        kwargs = self.trigger_data.kwargs.copy()
        kwargs["event_data"] = self
        kwargs["machine"] = self.trigger_data.machine
        kwargs["event"] = self.trigger_data.event
        kwargs["model"] = self.trigger_data.model
        kwargs["transition"] = self.transition
        kwargs["state"] = self.state
        kwargs["source"] = self.source
        kwargs["target"] = self.target
        return kwargs
