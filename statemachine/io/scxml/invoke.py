"""SCXML-specific invoke handler.

Implements the IInvoke protocol by resolving child SCXML content (inline or
via src/srcexpr), evaluating params/namelist in the parent context, and managing
the child machine lifecycle including ``#_parent`` routing, autoforward, and
finalize.
"""

import asyncio
import logging
from collections.abc import Callable
from inspect import isawaitable
from pathlib import Path
from typing import Any

from ...invoke import IInvoke
from ...invoke import InvokeContext
from .actions import ExecuteBlock
from .actions import _eval
from .schema import InvokeDefinition

logger = logging.getLogger(__name__)

_VALID_INVOKE_TYPES = {
    None,
    "scxml",
    "http://www.w3.org/TR/scxml",
    "http://www.w3.org/TR/scxml/",
    "http://www.w3.org/TR/scxml/#SCXMLEventProcessor",
}


class SCXMLInvoker:
    """SCXML-specific invoke handler implementing the IInvoke protocol.

    Resolves the child SCXML from inline content, src file, or srcexpr,
    evaluates params/namelist, and manages the child machine lifecycle.
    """

    def __init__(
        self,
        definition: InvokeDefinition,
        base_dir: str,
        register_child: "Callable[[str, str], type]",
    ):
        self._definition = definition
        self._register_child = register_child
        self._child: Any = None
        self._base_dir: str = base_dir

        # Duck-typed attributes for InvokeManager
        self.invoke_id: "str | None" = definition.id
        self.idlocation: "str | None" = definition.idlocation
        self.autoforward: bool = definition.autoforward

        # Pre-compile finalize block
        self._finalize_block: "ExecuteBlock | None" = None
        if definition.finalize and not definition.finalize.is_empty:
            self._finalize_block = ExecuteBlock(definition.finalize)

    def run(self, ctx: InvokeContext) -> Any:
        """Create and run the child state machine."""
        machine = ctx.machine

        # Store invokeid in idlocation if specified
        if self.idlocation:
            setattr(machine.model, self.idlocation, ctx.invokeid)

        # Resolve invoke type
        invoke_type = self._definition.type
        if self._definition.typeexpr:
            invoke_type = _eval(self._definition.typeexpr, machine=machine)

        if invoke_type not in _VALID_INVOKE_TYPES:
            raise ValueError(
                f"Unsupported invoke type: {invoke_type}. Supported types: {_VALID_INVOKE_TYPES}"
            )

        # Resolve child SCXML content
        scxml_content = self._resolve_content(machine)
        if scxml_content is None:
            raise ValueError("No content resolved for <invoke>")

        # Evaluate params and namelist
        invoke_params = self._evaluate_params(machine)

        # Parse and create the child machine
        child_cls = self._create_child_class(scxml_content, ctx.invokeid)

        # _invoke_session and _invoke_params are passed as kwargs so that the
        # invoke_init callback (inserted at position 0 in the initial state's onentry
        # by the processor) can pop them and store them on the machine instance.
        #
        # The _ChildRefSetter listener captures ``self._child`` during the first
        # state entry, before the processing loop blocks.  This is necessary
        # because the child's ``__init__`` may block for an extended time when
        # there are delayed events, and ``on_event()`` needs access to the child
        # to forward events from the parent session.
        session = _InvokeSession(parent=machine, invokeid=ctx.invokeid)
        ref_setter = _ChildRefSetter(self)
        self._child = child_cls(
            _invoke_params=invoke_params,
            _invoke_session=session,
            listeners=[ref_setter],
        )

        return None

    def on_cancel(self):
        """Cancel the child machine and all its invocations."""
        from ...invoke import _stop_child_machine

        _stop_child_machine(self._child)
        self._child = None

    def on_event(self, event_name: str, **data):
        """Forward an event to the child machine (autoforward)."""
        if self._child is not None and not self._child.is_terminated:
            try:
                self._child.send(event_name, **data)
            except Exception:
                logger.debug("Error forwarding event %s to child", event_name, exc_info=True)

    def on_finalize(self, trigger_data):
        """Execute the finalize block before the parent processes the event."""
        if self._finalize_block is not None:
            machine = trigger_data.machine
            kwargs = {
                "machine": machine,
                "model": machine.model,
            }
            # Inject SCXML context variables
            from .actions import EventDataWrapper

            kwargs.update(
                {k: v for k, v in machine.model.__dict__.items() if not k.startswith("_")}
            )
            # Build EventDataWrapper from trigger_data's kwargs
            kwargs["_event"] = EventDataWrapper.from_trigger_data(trigger_data)
            self._finalize_block(**kwargs)

    def _resolve_content(self, machine) -> "str | None":
        """Resolve the child SCXML content from content/src/srcexpr."""
        defn = self._definition

        if defn.content:
            # Content could be an expr to evaluate or inline SCXML
            if defn.content.lstrip().startswith("<"):
                return defn.content
            # It's an expression — evaluate it
            result = _eval(defn.content, machine=machine)
            if isinstance(result, str):
                return result
            return str(result)

        if defn.srcexpr:
            src = _eval(defn.srcexpr, machine=machine)
        elif defn.src:
            src = defn.src
        else:
            return None

        # Handle file: URIs and relative paths
        if src.startswith("file:"):
            path = Path(src.removeprefix("file:"))
        else:
            path = Path(src)

        # Resolve relative to the base directory of the parent SCXML file
        if not path.is_absolute():
            path = Path(self._base_dir) / path

        return path.read_text()

    def _evaluate_params(self, machine) -> dict:
        """Evaluate params and namelist into a dict of values."""
        defn = self._definition
        result = {}

        # Evaluate namelist
        if defn.namelist:
            for name in defn.namelist.strip().split():
                if hasattr(machine.model, name):
                    result[name] = getattr(machine.model, name)

        # Evaluate param elements
        for param in defn.params:
            if param.expr is not None:
                result[param.name] = _eval(param.expr, machine=machine)
            elif param.location is not None:
                result[param.name] = _eval(param.location, machine=machine)

        return result

    def _create_child_class(self, scxml_content: str, invokeid: str):
        """Parse the child SCXML and create a machine class."""
        child_name = f"invoke_{invokeid}"
        return self._register_child(scxml_content, child_name)


class _ChildRefSetter:
    """Listener that captures the child machine reference during initialization.

    The child's ``__init__`` blocks inside the processing loop (e.g. when there
    are delayed events).  By using this listener, ``SCXMLInvoker._child`` is set
    during the first state entry — *before* the processing loop starts spinning —
    so that ``on_event()`` can forward events to the child immediately.
    """

    def __init__(self, invoker: "SCXMLInvoker"):
        self._invoker = invoker

    def on_enter_state(self, machine=None, **kwargs):
        if self._invoker._child is None and machine is not None:
            self._invoker._child = machine


class _InvokeSession:
    """Holds the reference to the parent machine for ``#_parent`` routing."""

    def __init__(self, parent, invokeid: str):
        self.parent = parent
        self.invokeid = invokeid

    def send_to_parent(self, event: str, **data):
        """Send an event to the parent machine's external queue."""
        result = self.parent.send(event, _invokeid=self.invokeid, **data)
        if isawaitable(result):
            asyncio.ensure_future(result)


# Verify protocol compliance at import time
assert isinstance(SCXMLInvoker.__new__(SCXMLInvoker), IInvoke)
