from dataclasses import dataclass
from dataclasses import field
from typing import TYPE_CHECKING
from typing import Any

if TYPE_CHECKING:
    from .state import State
    from .statemachine import StateMachine
    from .transition import Transition


@dataclass
class TriggerData:
    machine: "StateMachine"

    event: str
    """The Event that was triggered."""

    model: Any = field(init=False)
    """A reference to the underlying model that holds the current :ref:`State`."""

    args: tuple = field(default_factory=tuple)
    """All positional arguments provided on the :ref:`Event`."""

    kwargs: dict = field(default_factory=dict)
    """All keyword arguments provided on the :ref:`Event`."""

    def __post_init__(self):
        self.model = self.machine.model


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

    @property
    def machine(self):
        return self.trigger_data.machine

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
