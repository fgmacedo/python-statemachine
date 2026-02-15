"""Invoke support for SCXML child sessions.

This module implements the SCXML `<invoke>` mechanism: when a state is entered,
it can spawn a child state machine (session). When the state is exited, the
child is cancelled. Communication between parent and child uses the existing
thread-safe ``send()`` mechanism via ``PriorityQueue``.
"""

import logging
import threading
from dataclasses import dataclass
from dataclasses import field
from typing import TYPE_CHECKING
from typing import Any
from typing import Dict
from typing import List
from uuid import uuid4

if TYPE_CHECKING:
    from .engines.base import BaseEngine
    from .state import State
    from .statemachine import StateChart

logger = logging.getLogger(__name__)


@dataclass
class InvokeConfig:
    """Static configuration for an invocation, derived from SCXML or Python API."""

    invoke_type: "str | None" = None
    src: "str | None" = None
    srcexpr: "str | None" = None
    id: "str | None" = None
    idlocation: "str | None" = None
    autoforward: bool = False
    namelist: "str | None" = None
    params: "List[Any]" = field(default_factory=list)
    content: "str | None" = None
    finalize: Any = None
    child_class: "type[StateChart] | None" = None


@dataclass
class Invocation:
    """Runtime state of an active invocation."""

    invokeid: str
    config: InvokeConfig
    child_sm: "StateChart | None" = None
    thread: "threading.Thread | None" = None
    cancelled: bool = False
    state_id: str = ""


class ParentBridge:
    """Listener attached to a child state machine that intercepts ``#_parent`` sends.

    When the child's engine finishes (reaches a final state), this bridge sends
    ``done.invoke.<invokeid>`` to the parent.  It also intercepts events sent
    to ``#_parent`` and routes them to the parent's external queue.
    """

    def __init__(self, parent_sm: "StateChart", invokeid: str, invocation: "Invocation"):
        self._parent_sm = parent_sm
        self._invokeid = invokeid
        self._invocation = invocation


class InvokeManager:
    """Manages active invocations for an engine instance."""

    def __init__(self, engine: "BaseEngine"):
        self._engine = engine
        self._active: Dict[str, Invocation] = {}

    @property
    def sm(self) -> "StateChart":
        return self._engine.sm

    def _generate_invokeid(self, state: "State", config: InvokeConfig) -> str:
        if config.id:
            return config.id
        return f"{state.id}.{uuid4().hex[:8]}"

    def _set_idlocation(self, config: InvokeConfig, invokeid: str):
        if config.idlocation:
            setattr(self.sm.model, config.idlocation, invokeid)

    def spawn_sync(self, state: "State", config: InvokeConfig, trigger_data: Any):
        """Spawn a child session synchronously (in a daemon thread)."""
        invokeid = self._generate_invokeid(state, config)
        self._set_idlocation(config, invokeid)

        invocation = Invocation(
            invokeid=invokeid,
            config=config,
            state_id=state.id,
        )
        self._active[invokeid] = invocation

        child_sm = self._create_child(config, invokeid, invocation, trigger_data)
        if child_sm is None:
            del self._active[invokeid]
            return

        invocation.child_sm = child_sm

        def run_child():
            try:
                # The child was already started during creation (sync engine).
                # Wait for it to terminate by polling.
                import time

                while not child_sm.is_terminated and not invocation.cancelled:
                    time.sleep(0.01)

                if not invocation.cancelled:
                    logger.debug("Child %s terminated, sending done.invoke.%s", invokeid, invokeid)
                    self.sm.send(f"done.invoke.{invokeid}", invokeid=invokeid)
            except Exception:
                logger.exception("Error in child session %s", invokeid)

        thread = threading.Thread(target=run_child, daemon=True, name=f"invoke-{invokeid}")
        invocation.thread = thread
        thread.start()

    async def spawn_async(self, state: "State", config: InvokeConfig, trigger_data: Any):
        """Spawn a child session asynchronously."""
        import asyncio

        invokeid = self._generate_invokeid(state, config)
        self._set_idlocation(config, invokeid)

        invocation = Invocation(
            invokeid=invokeid,
            config=config,
            state_id=state.id,
        )
        self._active[invokeid] = invocation

        child_sm = self._create_child(config, invokeid, invocation, trigger_data)
        if child_sm is None:
            del self._active[invokeid]
            return

        invocation.child_sm = child_sm

        async def run_child():
            try:
                await child_sm.activate_initial_state()

                while not child_sm.is_terminated and not invocation.cancelled:
                    await asyncio.sleep(0.01)

                if not invocation.cancelled:
                    logger.debug("Child %s terminated, sending done.invoke.%s", invokeid, invokeid)
                    self.sm.send(f"done.invoke.{invokeid}", invokeid=invokeid)
            except Exception:
                logger.exception("Error in child session %s", invokeid)

        asyncio.ensure_future(run_child())

    def _create_child(
        self,
        config: InvokeConfig,
        invokeid: str,
        invocation: Invocation,
        trigger_data: Any,
    ) -> "StateChart | None":
        """Create and return a child StateChart instance."""
        from .io.scxml.processor import SCXMLProcessor

        bridge = ParentBridge(self.sm, invokeid, invocation)

        child_class = config.child_class
        child_sm: "StateChart | None" = None

        if child_class is not None:
            child_sm = child_class(listeners=[bridge])
        elif config.content:
            processor = SCXMLProcessor()
            processor.parse_scxml(f"invoke_{invokeid}", config.content)
            child_sm = processor.start(listeners=[bridge])
        elif config.src:
            from pathlib import Path
            from urllib.parse import urlparse

            parsed = urlparse(config.src)
            if parsed.scheme == "file" or not parsed.scheme:
                path = Path(parsed.path) if parsed.scheme == "file" else Path(config.src)
                processor = SCXMLProcessor()
                processor.parse_scxml_file(path)
                child_sm = processor.start(listeners=[bridge])

        if child_sm is None:
            logger.warning("Could not create child for invoke %s", invokeid)
            return None

        # Set parent references on child
        child_sm._parent_sm = self.sm  # type: ignore[attr-defined]
        child_sm._invokeid = invokeid  # type: ignore[attr-defined]

        # Apply initial data from namelist/params
        self._apply_initial_data(child_sm, config, trigger_data)

        return child_sm

    def _apply_initial_data(
        self,
        child_sm: "StateChart",
        config: InvokeConfig,
        trigger_data: Any,
    ):
        """Apply namelist and param data to the child's datamodel."""
        if config.namelist:
            for name in config.namelist.strip().split():
                if hasattr(self.sm.model, name):
                    value = getattr(self.sm.model, name)
                    if hasattr(child_sm.model, name):
                        setattr(child_sm.model, name, value)

        for param in config.params:
            if param.expr is not None:
                from .io.scxml.actions import _eval

                try:
                    kwargs = {"machine": self.sm, "model": self.sm.model}
                    kwargs.update(
                        {
                            k: v
                            for k, v in self.sm.model.__dict__.items()
                            if k not in {"_sessionid", "_ioprocessors", "_name", "_event"}
                        }
                    )
                    value = _eval(param.expr, **kwargs)
                    if hasattr(child_sm.model, param.name):
                        setattr(child_sm.model, param.name, value)
                except Exception:
                    logger.exception("Error evaluating param %s", param.name)

    def cancel_for_state(self, state: "State"):
        """Cancel all invocations associated with a state."""
        to_remove = [
            inv_id
            for inv_id, inv in self._active.items()
            if inv.state_id == state.id and not inv.cancelled
        ]
        for inv_id in to_remove:
            self._cancel(inv_id)

    def cancel_all(self):
        """Cancel all active invocations."""
        for inv_id in list(self._active.keys()):
            self._cancel(inv_id)

    def _cancel(self, invokeid: str):
        invocation = self._active.get(invokeid)
        if invocation is None or invocation.cancelled:
            return
        invocation.cancelled = True
        logger.debug("Cancelling invocation %s", invokeid)
        if invocation.child_sm is not None:
            invocation.child_sm._engine.running = False

    def get_invocation_by_id(self, invokeid: str) -> "Invocation | None":
        return self._active.get(invokeid)

    def active_for_state(self, state: "State") -> List[Invocation]:
        return [inv for inv in self._active.values() if inv.state_id == state.id]

    def apply_finalize(self, invocation: Invocation, trigger_data: Any):
        """Execute the finalize block for an invocation before the event is processed."""
        config = invocation.config
        if config.finalize is None:
            return
        try:
            config.finalize(machine=self.sm, model=self.sm.model, event_data=trigger_data)
        except Exception:
            logger.exception("Error in finalize for %s", invocation.invokeid)

    def forward_event(self, invocation: Invocation, event_name: str, trigger_data: Any):
        """Forward an event to a child session (autoforward)."""
        if invocation.child_sm is None or invocation.cancelled:
            return
        invocation.child_sm.send(event_name, **trigger_data.kwargs)

    def get_invocation_for_child(self, child_sm: "StateChart") -> "Invocation | None":
        """Find the invocation record for a given child state machine."""
        for inv in self._active.values():
            if inv.child_sm is child_sm:
                return inv
        return None

    def send_to_child(self, event_name: str, **kwargs):
        """Send an event to the first active child (for #_child target)."""
        for inv in self._active.values():
            if inv.child_sm is not None and not inv.cancelled:
                inv.child_sm.send(event_name, **kwargs)
                return
        logger.warning("No active child to send event %s", event_name)

    def send_to_invokeid(self, invokeid: str, event_name: str, **kwargs):
        """Send an event to a specific child by invokeid."""
        inv = self._active.get(invokeid)
        if inv and inv.child_sm and not inv.cancelled:
            inv.child_sm.send(event_name, **kwargs)
        else:
            logger.warning("No active child with invokeid %s", invokeid)
