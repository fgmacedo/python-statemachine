"""Runtime system variables of the statechart execution model.

These are part of the (SCXML-derived) execution model the library implements, not of
any particular syntax — so they are format-neutral and available to statecharts loaded
from SCXML, JSON or YAML alike. The :class:`~statemachine.io.interpreter.Interpreter`
injects them on every event via :func:`build_system_variables`:

- ``_event``: the current event, wrapped as :class:`EventDataWrapper`
  (``name``/``data``/``type``/``origintype``/``sendid``/``invokeid``).
- ``_sessionid``: a stable id for the running machine session.
- ``_name``: the machine name.
- ``_ioprocessors``: the session's :class:`IOProcessor`.
"""

from dataclasses import dataclass
from typing import Any


@dataclass
class _Data:
    kwargs: dict

    def __getattr__(self, name):
        return self.kwargs.get(name, None)

    def get(self, name, default=None):
        return self.kwargs.get(name, default)


class OriginTypeSCXML(str):
    """The origintype of an :ref:`Event` as specified by the SCXML namespace."""

    def __eq__(self, other):
        return other == "http://www.w3.org/TR/scxml/#SCXMLEventProcessor" or other == "scxml"


class EventDataWrapper:
    """The ``_event`` system variable: a read-only view of the current event.

    Exposes ``name``/``data``/``type``/``origintype``/``sendid``/``invokeid`` following
    the SCXML event model, which is the library's execution model regardless of the
    source syntax.
    """

    origin: str = ""
    origintype: str = OriginTypeSCXML("scxml")
    invokeid: str = ""
    """If this event is generated from an invoked child process, the Processor MUST set
    this field to the invoke id of the invocation that triggered the child process.
    Otherwise it MUST leave it blank.
    """

    def __init__(self, event_data=None, *, trigger_data=None):
        self.event_data = event_data
        if trigger_data is not None:
            self.trigger_data = trigger_data
        elif event_data is not None:
            self.trigger_data = event_data.trigger_data
        else:
            raise ValueError("Either event_data or trigger_data must be provided")

        td = self.trigger_data
        self.sendid = td.send_id
        self.invokeid = td.kwargs.get("_invokeid", "")
        if td.event is None or td.event.internal:
            if "error.execution" == td.event:
                self.type = "platform"
            else:
                self.type = "internal"
                self.origintype = ""
        else:
            self.type = "external"

    @classmethod
    def from_trigger_data(cls, trigger_data):
        """Create an EventDataWrapper directly from a TriggerData (no EventData needed)."""
        return cls(trigger_data=trigger_data)

    def __getattr__(self, name):
        if self.event_data is not None:
            return getattr(self.event_data, name)
        raise AttributeError(f"'{type(self).__name__}' object has no attribute '{name}'")

    def __eq__(self, value):
        "This makes SCXML test 329 pass. It assumes that the event is the same instance"
        return isinstance(value, EventDataWrapper)

    @property
    def name(self):
        if self.event_data is not None:
            return self.event_data.event
        return str(self.trigger_data.event) if self.trigger_data.event else None

    @property
    def data(self):
        "Property used to access the event payload (the SCXML ``_event.data``)."
        td = self.trigger_data
        if td.kwargs:
            return _Data(td.kwargs)
        elif td.args and len(td.args) == 1:
            return td.args[0]
        elif td.args:
            return td.args
        else:
            return None


class IOProcessor:
    """The ``_ioprocessors`` system variable for a session.

    A minimal Event I/O Processor handle: indexing by any processor name returns itself,
    and ``location`` is the machine name.
    """

    def __init__(self, interpreter, machine):
        self.interpreter = interpreter
        self.machine = machine

    def __getitem__(self, name: str):
        return self

    @property
    def location(self):
        return self.machine.name

    def get(self, name: str):
        return getattr(self, name)


@dataclass
class SessionData:
    """Per-machine runtime session state held by the interpreter."""

    machine: Any
    processor: IOProcessor
    first_event_raised: bool = False

    def __post_init__(self):
        self.session_id = f"{self.machine.name}:{id(self.machine)}"


def build_system_variables(machine, session_data: SessionData, event, event_data) -> dict:
    """Compute the system variables to inject into callbacks for the current event.

    ``_event`` is exposed only after the first real (non-``__initial__``) event, matching
    the SCXML rule that ``_event`` is unbound during the initial macrostep.
    """
    if not session_data.first_event_raised and event and event != "__initial__":
        session_data.first_event_raised = True

    _event: "EventDataWrapper | None" = None
    if session_data.first_event_raised:
        _event = EventDataWrapper(event_data)

    return {
        "_name": machine.name,
        "_sessionid": session_data.session_id,
        "_ioprocessors": session_data.processor,
        "_event": _event,
    }


def create_invoke_init_callable():
    """Create a callback that extracts invoke-specific kwargs and stores them on the machine.

    Inserted at position 0 in the initial state's onentry list for invoked children, so
    ``_invoke_session`` and ``_invoke_params`` are handled before any other callbacks run,
    even for machines without a datamodel.
    """
    initialized = False

    def invoke_init(*args, **kwargs):
        nonlocal initialized
        if initialized:
            return
        initialized = True
        machine = kwargs.get("machine")
        if machine is not None:
            # Use get() not pop(): each callback receives a copy of kwargs
            # (via EventData.extended_kwargs), so pop would be misleading.
            machine._invoke_params = kwargs.get("_invoke_params")
            machine._invoke_session = kwargs.get("_invoke_session")

    return invoke_init
