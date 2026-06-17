"""Format-neutral invoke handler.

Implements the engine's ``IInvoke`` protocol: resolves a child statechart (inline
content, ``src`` file, or ``srcexpr``), evaluates ``params``/``namelist`` in the parent
context, and manages the child machine lifecycle including ``#_parent`` routing,
autoforward and finalize.

The child is compiled via the ``register_child`` callback (which the interpreter wires to
its own format reader), so invoke is not tied to SCXML: a child may be authored in any
format the interpreter understands.
"""

import asyncio
import logging
from collections.abc import Callable
from inspect import isawaitable
from pathlib import Path
from typing import Any

from ..invoke import IInvoke
from ..invoke import InvokeContext
from .actions import ExecuteBlock
from .evaluators import Evaluator
from .model import InvokeDefinition
from .model import StateMachineDefinition
from .system_variables import EventDataWrapper

logger = logging.getLogger(__name__)

#: Invoke ``type`` values understood by the runtime (SCXML processor URLs + ``None``).
VALID_INVOKE_TYPES = {
    None,
    "scxml",
    "http://www.w3.org/TR/scxml",
    "http://www.w3.org/TR/scxml/",
    "http://www.w3.org/TR/scxml/#SCXMLEventProcessor",
}


class Invoker:
    """Invoke handler implementing the IInvoke protocol.

    Resolves the child statechart from inline content, a ``src`` file or ``srcexpr``,
    evaluates params/namelist, and manages the child machine lifecycle.
    """

    def __init__(
        self,
        definition: InvokeDefinition,
        base_dir: str,
        register_child: "Callable[[StateMachineDefinition | str, str], type]",
        evaluator: Evaluator,
    ):
        self._definition = definition
        self._register_child = register_child
        self._child: Any = None
        self._base_dir: str = base_dir
        self._evaluator: Evaluator = evaluator

        # Duck-typed attributes for InvokeManager
        self.invoke_id: "str | None" = definition.id
        self.idlocation: "str | None" = definition.idlocation
        self.autoforward: bool = definition.autoforward

        # Pre-compile finalize block
        self._finalize_block: "ExecuteBlock | None" = None
        if definition.finalize and not definition.finalize.is_empty:
            self._finalize_block = ExecuteBlock(definition.finalize, self._evaluator)

    def _eval(self, expr: str, machine) -> Any:
        return self._evaluator.compile_value(expr)(machine=machine)

    def run(self, ctx: InvokeContext) -> Any:
        """Create and run the child state machine."""
        machine = ctx.machine

        # Store invokeid in idlocation if specified
        if self.idlocation:
            setattr(machine.model, self.idlocation, ctx.invokeid)

        # Resolve invoke type
        invoke_type = self._definition.type
        if self._definition.typeexpr:
            invoke_type = self._eval(self._definition.typeexpr, machine=machine)

        if invoke_type not in VALID_INVOKE_TYPES:
            raise ValueError(
                f"Unsupported invoke type: {invoke_type}. Supported types: {VALID_INVOKE_TYPES}"
            )

        # Resolve child statechart content
        child_content = self._resolve_content(machine)
        if child_content is None:
            raise ValueError("No content resolved for <invoke>")

        # Evaluate params and namelist
        invoke_params = self._evaluate_params(machine)

        # Parse and create the child machine
        child_cls = self._create_child_class(child_content, ctx.invokeid)

        # _invoke_session and _invoke_params are passed as kwargs so that the
        # invoke_init callback (inserted at position 0 in the initial state's onentry
        # by the interpreter) can pop them and store them on the machine instance.
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
        from ..invoke import _stop_child_machine

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
            kwargs.update(
                {k: v for k, v in machine.model.__dict__.items() if not k.startswith("_")}
            )
            kwargs["_event"] = EventDataWrapper.from_trigger_data(trigger_data)
            self._finalize_block(**kwargs)

    def _resolve_content(self, machine):
        """Resolve the child statechart content from content/src/srcexpr.

        Returns either a source string (file text / inline document text) that the reader
        will parse, or an already-parsed definition (native inline child), which the
        interpreter registers directly.
        """
        defn = self._definition

        if defn.content is not None:
            content = defn.content
            if not isinstance(content, str):
                # Native inline child: an already-parsed StateMachineDefinition.
                return content
            if self._is_inline_document(content):
                return content
            # It's an expression — evaluate it
            result = self._eval(content, machine=machine)
            if isinstance(result, str):
                return result
            return str(result)

        if defn.srcexpr:
            src = self._eval(defn.srcexpr, machine=machine)
        elif defn.src:
            src = defn.src
        else:
            return None

        # Handle file: URIs and relative paths
        if src.startswith("file:"):
            path = Path(src.removeprefix("file:"))
        else:
            path = Path(src)

        # Resolve relative to the base directory of the parent document
        if not path.is_absolute():
            path = Path(self._base_dir) / path

        return path.read_text()

    @staticmethod
    def _is_inline_document(content: str) -> bool:
        """Whether ``content`` is an inline document (vs an expression to evaluate).

        The default heuristic recognizes inline XML (SCXML). Other formats may override.
        """
        return content.lstrip().startswith("<")

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
                result[param.name] = self._eval(param.expr, machine=machine)
            elif param.location is not None:
                result[param.name] = self._eval(param.location, machine=machine)

        return result

    def _create_child_class(self, content: "StateMachineDefinition | str", invokeid: str):
        """Compile the child statechart and create a machine class."""
        child_name = f"invoke_{invokeid}"
        return self._register_child(content, child_name)


class _ChildRefSetter:
    """Listener that captures the child machine reference during initialization.

    The child's ``__init__`` blocks inside the processing loop (e.g. when there
    are delayed events).  By using this listener, ``Invoker._child`` is set during
    the first state entry — *before* the processing loop starts spinning — so that
    ``on_event()`` can forward events to the child immediately.
    """

    def __init__(self, invoker: "Invoker"):
        self._invoker = invoker

    def on_enter_state(self, machine=None, **kwargs):
        if self._invoker._child is None and machine is not None:
            self._invoker._child = machine


class _InvokeSession:
    """Holds the reference to the parent machine for ``#_parent`` routing."""

    def __init__(self, parent, invokeid: str):
        self.parent = parent
        self.invokeid = invokeid
        self._pending_tasks: "set[asyncio.Future]" = set()
        """Strong refs to scheduled sends; the loop only holds weak refs to tasks."""

    def send_to_parent(self, event: str, **data):
        """Send an event to the parent machine's external queue."""
        result = self.parent.send(event, _invokeid=self.invokeid, **data)
        if isawaitable(result):
            task = asyncio.ensure_future(result)
            self._pending_tasks.add(task)
            task.add_done_callback(self._pending_tasks.discard)


# Verify protocol compliance at import time
assert isinstance(Invoker.__new__(Invoker), IInvoke)
