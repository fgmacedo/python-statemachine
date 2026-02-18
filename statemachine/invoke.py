"""Invoke support for state machine child sessions.

This module implements the invoke mechanism: when a state is entered, it can
spawn a child session (StateChart, function, or custom handler). When the
state is exited, the child is cancelled.

The architecture is based on a Protocol pattern:

- **Invoker** — Protocol that any handler must satisfy (just ``run(ctx)``).
- **InvokeContext** — Context provided to handlers with params, send callback, etc.
- **InvokeConfig** — Static configuration for an invocation.
- **Invocation** — Runtime state of an active invocation.
- **InvokeManager** — Manages lifecycle, delegates to handlers.
- **StateChartInvoker** — Adapter that wraps a StateChart class as an Invoker.

Users can use any callable or class with a ``run()`` method::

    def fetch_user(ctx):
        return requests.get(f"/users/{ctx.params['id']}").json()

    class MyHandler:
        def run(self, ctx):
            return do_work(ctx.params)

        def on_cancel(self):
            ...  # optional cleanup

    class MyMachine(StateChart):
        s1 = State(invoke=fetch_user)
        s2 = State(invoke=MyHandler)
        s3 = State(invoke=ChildChart)
"""

import asyncio
import inspect
import logging
import threading
import time
from dataclasses import dataclass
from dataclasses import field
from typing import TYPE_CHECKING
from typing import Any
from typing import Callable
from typing import Dict
from typing import List
from typing import runtime_checkable
from uuid import uuid4

from .orderedset import OrderedSet

try:
    from typing import Protocol
except ImportError:
    from typing_extensions import Protocol  # type: ignore[assignment]

if TYPE_CHECKING:
    from .engines.base import BaseEngine
    from .state import State
    from .statemachine import StateChart

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Protocol & Context
# ---------------------------------------------------------------------------


@runtime_checkable
class Invoker(Protocol):
    """Protocol for invoke handlers. Implement ``run()`` to define the logic."""

    def run(self, ctx: "InvokeContext") -> Any: ...


@dataclass
class InvokeContext:
    """Context provided to an Invoker.run() call."""

    invokeid: str
    params: "dict[str, Any]"
    send: "Callable[..., None]"
    """``send(event, **data)`` — sends an event to the parent machine."""
    cancelled: bool = False
    _parent_sm: "Any" = field(default=None, repr=False)


# ---------------------------------------------------------------------------
# Configuration & Runtime
# ---------------------------------------------------------------------------


@dataclass
class InvokeSession:
    """Tracks the parent session relationship for a child StateChart.

    Attached to child StateMachines as ``_invoke_session`` so the engine
    can route events back to the parent without ad-hoc ``setattr`` hacks.
    """

    parent_sm: "StateChart"
    invokeid: str


@dataclass
class InvokeConfig:
    """Static configuration for an invocation."""

    handler: Any = None
    """Callable, Invoker instance/class, or type[StateChart]."""

    id: "str | None" = None
    idlocation: "str | None" = None
    autoforward: bool = False
    namelist: "str | None" = None
    params: "List[Any]" = field(default_factory=list)
    finalize: Any = None


@dataclass
class Invocation:
    """Runtime state of an active invocation."""

    invokeid: str
    config: InvokeConfig
    handler: Any = None
    ctx: "InvokeContext | None" = None
    child_sm: "StateChart | None" = None
    thread: "threading.Thread | None" = None
    terminated: bool = False
    state_id: str = ""
    trigger_data: Any = None


# ---------------------------------------------------------------------------
# StateChartInvoker — adapter for StateChart classes
# ---------------------------------------------------------------------------


class StateChartInvoker:
    """Adapter: wraps a StateChart class as an Invoker.

    Handles the two-phase activation pattern required by SCXML:
    1. Enter initial configuration (runs datamodel entry actions)
    2. Apply invoke params (namelist/param from parent)
    3. Start processing loop
    """

    def __init__(self, child_class: "type[StateChart]"):
        self._child_class = child_class
        self._child_sm: "StateChart | None" = None

    def run(self, ctx: InvokeContext) -> Any:
        child_sm = self._create_child(ctx)
        self._child_sm = child_sm

        # Two-phase activation
        child_sm._engine.enter_initial_configuration()
        self._apply_params(child_sm, ctx.params)
        child_sm._processing_loop()

        # Poll until child terminates or parent cancels
        while not child_sm.is_terminated and not ctx.cancelled:
            time.sleep(0.01)

        return None

    def on_cancel(self):
        if self._child_sm is not None:
            self._child_sm._engine.running = False

    def on_event(self, event: str, **data):
        if self._child_sm is not None:
            self._child_sm.send(event, **data)

    @property
    def child_sm(self) -> "StateChart | None":
        return self._child_sm

    def _create_child(self, ctx: InvokeContext) -> "StateChart":
        """Create and return a child StateChart instance with deferred start."""
        child_class = self._child_class
        bridge = _ParentBridge(ctx)

        child_sm = child_class(listeners=[bridge], _start=False)

        child_sm._invoke_session = InvokeSession(  # type: ignore[attr-defined]
            parent_sm=ctx._parent_sm,
            invokeid=ctx.invokeid,
        )

        return child_sm

    @staticmethod
    def _apply_params(child_sm: "StateChart", params: "dict[str, Any]"):
        """Apply resolved params to the child's datamodel."""
        for name, value in params.items():
            if hasattr(child_sm.model, name):
                setattr(child_sm.model, name, value)


class _ParentBridge:
    """Listener attached to a child SM. Placeholder for future extensions."""

    def __init__(self, ctx: InvokeContext):
        self._ctx = ctx


# ---------------------------------------------------------------------------
# InvokeManager
# ---------------------------------------------------------------------------


class _TriggerDataAdapter:
    """Adapts a TriggerData to look like EventData for EventDataWrapper."""

    def __init__(self, trigger_data: Any):
        self.trigger_data = trigger_data

    def __getattr__(self, name: str) -> Any:
        return getattr(self.trigger_data, name)


class InvokeManager:
    """Manages active invocations for an engine instance.

    Also acts as the invoke handler: the engine calls hook methods
    (``on_state_entered``, ``on_state_exiting``, ``spawn_pending_sync``, etc.)
    instead of containing inline invoke logic.
    """

    def __init__(self, engine: "BaseEngine"):
        self._engine = engine
        self._active: Dict[str, Invocation] = {}
        self._states_to_invoke: "OrderedSet[State]" = OrderedSet()

    @property
    def sm(self) -> "StateChart":
        return self._engine.sm

    # --- Engine hooks ---

    def on_state_entered(self, state: "State") -> None:
        """Track a state with invocations for post-macrostep spawning."""
        if getattr(state, "invocations", None):
            self._states_to_invoke.add(state)

    def on_state_exiting(self, state: "State") -> None:
        """Cancel invocations and remove from pending spawn set."""
        if getattr(state, "invocations", None):
            self.cancel_for_state(state)
        self._states_to_invoke.discard(state)

    def spawn_pending_sync(self, trigger_data: Any) -> None:
        """Spawn invocations for states entered during this macrostep (sync)."""
        for state in sorted(self._states_to_invoke, key=lambda s: s.document_order):
            for config in state.invocations:
                self.spawn_sync(state, config, trigger_data)
        self._states_to_invoke.clear()

    async def spawn_pending_async(self, trigger_data: Any) -> None:
        """Spawn invocations for states entered during this macrostep (async)."""
        for state in sorted(self._states_to_invoke, key=lambda s: s.document_order):
            for config in state.invocations:
                await self.spawn_async(state, config, trigger_data)
        self._states_to_invoke.clear()

    def handle_external_event(self, trigger_data: Any) -> bool:
        """Process invoke-related aspects of an external event.

        Handles forward_target (returns ``True`` if the event was consumed),
        and applies finalize/autoforward as side-effects.

        Returns:
            ``True`` if the event was forwarded to another session and should
            not be processed further; ``False`` otherwise.
        """
        # Forward delayed cross-session events to their target
        if "_forward_target" in trigger_data.kwargs:
            self._forward_to_target(trigger_data)
            return True

        # Handle invoke finalize and autoforward
        for state in self.sm.configuration:
            for inv in self.active_for_state(state):
                if trigger_data.invokeid and inv.invokeid == trigger_data.invokeid:
                    self.apply_finalize(inv, trigger_data)
                if inv.config.autoforward and trigger_data.event:
                    self.forward_event(inv, str(trigger_data.event), trigger_data)

        return False

    def on_terminate(self) -> None:
        """Cancel all active invocations on machine termination."""
        self.cancel_all()

    def _forward_to_target(self, trigger_data: Any) -> None:
        """Forward an event to a cross-session target instead of processing it.

        Called when ``trigger_data.kwargs['_forward_target']`` is set.
        This supports delayed cross-session sends.
        """
        target = trigger_data.kwargs.pop("_forward_target")
        event_name = str(trigger_data.event)
        kwargs = trigger_data.kwargs
        if target in ("#_parent", "parent"):
            session = getattr(self.sm, "_invoke_session", None)
            if session is not None:
                session.parent_sm.send(
                    event_name,
                    *trigger_data.args,
                    invokeid=session.invokeid,
                    **kwargs,
                )
            else:
                self.sm.send("error.communication", internal=True)
        elif target == "#_child":
            self.send_to_child(event_name, **kwargs)
        else:
            logger.warning("Unknown forward_target: %s", target)

    # --- ID generation ---

    def _generate_invokeid(self, state: "State", config: InvokeConfig) -> str:
        if config.id:
            return config.id
        return f"{state.id}.{uuid4().hex[:8]}"

    def _set_idlocation(self, config: InvokeConfig, invokeid: str):
        if config.idlocation:
            setattr(self.sm.model, config.idlocation, invokeid)

    # --- Param evaluation ---

    def _evaluate_params(self, config: InvokeConfig, trigger_data: Any) -> "dict[str, Any]":
        """Evaluate namelist and param expressions in the parent's context."""
        params: dict[str, Any] = {}

        if config.namelist:
            for name in config.namelist.strip().split():
                if not hasattr(self.sm.model, name):
                    raise NameError(f"Namelist variable '{name}' not found on parent model")
                params[name] = getattr(self.sm.model, name)

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
                    params[param.name] = _eval(param.expr, **kwargs)
                except Exception:
                    logger.exception("Error evaluating param %s", param.name)

        return params

    # --- Handler resolution ---

    def _resolve_handler(self, handler: Any) -> Any:
        """Resolve a handler into an instance with a run() method or a callable."""
        if isinstance(handler, type):
            # It's a class — instantiate it
            return handler()
        return handler

    def _make_parent_send(self, invokeid: str) -> "Callable[..., None]":
        """Create a send callback that routes events to the parent machine."""

        def parent_send(event: str, **data):
            self.sm.send(event, invokeid=invokeid, **data)

        return parent_send

    # --- Spawn (sync) ---

    def spawn_sync(self, state: "State", config: InvokeConfig, trigger_data: Any):
        """Spawn a child session synchronously (in a daemon thread)."""
        invokeid = self._generate_invokeid(state, config)
        self._set_idlocation(config, invokeid)

        try:
            params = self._evaluate_params(config, trigger_data)
        except Exception as e:
            # SCXML spec: error in arg evaluation cancels the invocation
            logger.debug("Error evaluating invoke params for %s: %s", invokeid, e)
            self.sm.send("error.execution", error=e, internal=True)
            return
        ctx = InvokeContext(
            invokeid=invokeid,
            params=params,
            send=self._make_parent_send(invokeid),
            _parent_sm=self.sm,
        )

        handler = self._resolve_handler(config.handler)

        invocation = Invocation(
            invokeid=invokeid,
            config=config,
            handler=handler,
            ctx=ctx,
            state_id=state.id,
            trigger_data=trigger_data,
        )
        self._active[invokeid] = invocation

        # For StateChartInvoker, we need the child_sm reference after run starts
        thread = threading.Thread(
            target=self._run_session,
            args=(handler, ctx, invokeid, invocation),
            daemon=True,
            name=f"invoke-{invokeid}",
        )
        invocation.thread = thread
        thread.start()

    def _run_session(
        self, handler: Any, ctx: InvokeContext, invokeid: str, invocation: Invocation
    ):
        """Run a handler session in a thread."""
        try:
            if hasattr(handler, "run"):
                result = handler.run(ctx)
            else:
                result = handler(ctx)

            # Track child_sm if handler is a StateChartInvoker
            if hasattr(handler, "child_sm"):
                invocation.child_sm = handler.child_sm

            if not ctx.cancelled:
                logger.debug("Handler %s completed, sending done.invoke.%s", invokeid, invokeid)
                done_kwargs: dict[str, Any] = {"invokeid": invokeid}
                if result is not None:
                    if isinstance(result, dict):
                        done_kwargs.update(result)
                    else:
                        done_kwargs["data"] = result
                self._send_done_invoke(invokeid, done_kwargs)
        except Exception as e:
            if not ctx.cancelled:
                logger.exception("Error in handler session %s", invokeid)
                self.sm.send("error.execution", error=e, internal=True)
        finally:
            invocation.terminated = True

    def _send_done_invoke(self, invokeid: str, done_kwargs: "dict[str, Any]") -> Any:
        """Send done.invoke event using the dot-notation event name.

        Per SCXML spec, the event is ``done.invoke.<invokeid>``.  For Python API
        transitions like ``done_invoke_<state>``, prefix matching ensures the
        transition fires correctly (``done.invoke.active`` matches
        ``done.invoke.active.abc123``).

        Returns the result of ``sm.send()`` (may be a coroutine in async mode).
        """
        return self.sm.send(f"done.invoke.{invokeid}", **done_kwargs)

    # --- Spawn (async) ---

    async def spawn_async(self, state: "State", config: InvokeConfig, trigger_data: Any):
        """Spawn a child session asynchronously."""
        invokeid = self._generate_invokeid(state, config)
        self._set_idlocation(config, invokeid)

        try:
            params = self._evaluate_params(config, trigger_data)
        except Exception as e:
            logger.debug("Error evaluating invoke params for %s: %s", invokeid, e)
            self.sm.send("error.execution", error=e, internal=True)
            return
        ctx = InvokeContext(
            invokeid=invokeid,
            params=params,
            send=self._make_parent_send(invokeid),
            _parent_sm=self.sm,
        )

        handler = self._resolve_handler(config.handler)

        invocation = Invocation(
            invokeid=invokeid,
            config=config,
            handler=handler,
            ctx=ctx,
            state_id=state.id,
            trigger_data=trigger_data,
        )
        self._active[invokeid] = invocation

        # Determine if the handler is async
        run_fn = getattr(handler, "run", handler)
        if asyncio.iscoroutinefunction(run_fn):
            asyncio.ensure_future(self._run_async_session(handler, ctx, invokeid, invocation))
        else:
            # Sync handlers (callables, StateChartInvoker, classes with run()) run in
            # a thread to avoid blocking the event loop.  Completion is handled back
            # on the event loop so sm.send() works correctly.
            asyncio.ensure_future(self._run_in_thread(handler, ctx, invokeid, invocation))

    async def _run_in_thread(
        self, handler: Any, ctx: InvokeContext, invokeid: str, invocation: Invocation
    ):
        """Run a sync handler in a thread executor, handle completion on the event loop."""
        loop = asyncio.get_running_loop()
        try:
            if hasattr(handler, "run"):
                result = await loop.run_in_executor(None, handler.run, ctx)
            else:
                result = await loop.run_in_executor(None, handler, ctx)

            if hasattr(handler, "child_sm"):
                invocation.child_sm = handler.child_sm

            if not ctx.cancelled:
                logger.debug("Handler %s completed, sending done.invoke.%s", invokeid, invokeid)
                done_kwargs: dict[str, Any] = {"invokeid": invokeid}
                if result is not None:
                    if isinstance(result, dict):
                        done_kwargs.update(result)
                    else:
                        done_kwargs["data"] = result
                send_result = self._send_done_invoke(invokeid, done_kwargs)
                if inspect.isawaitable(send_result):
                    await send_result
        except Exception as e:
            if not ctx.cancelled:
                logger.exception("Error in handler session %s", invokeid)
                err_result = self.sm.send("error.execution", error=e, internal=True)
                if inspect.isawaitable(err_result):
                    await err_result
        finally:
            invocation.terminated = True

    async def _run_async_session(
        self, handler: Any, ctx: InvokeContext, invokeid: str, invocation: Invocation
    ):
        """Run an async handler session as an asyncio task."""
        try:
            if hasattr(handler, "run"):
                result = await handler.run(ctx)
            else:
                result = await handler(ctx)

            if hasattr(handler, "child_sm"):
                invocation.child_sm = handler.child_sm

            if not ctx.cancelled:
                logger.debug("Handler %s completed, sending done.invoke.%s", invokeid, invokeid)
                done_kwargs: dict[str, Any] = {"invokeid": invokeid}
                if result is not None:
                    if isinstance(result, dict):
                        done_kwargs.update(result)
                    else:
                        done_kwargs["data"] = result
                send_result = self._send_done_invoke(invokeid, done_kwargs)
                if inspect.isawaitable(send_result):
                    await send_result
        except Exception as e:
            if not ctx.cancelled:
                logger.exception("Error in async handler session %s", invokeid)
                err_result = self.sm.send("error.execution", error=e, internal=True)
                if inspect.isawaitable(err_result):
                    await err_result
        finally:
            invocation.terminated = True

    # --- Cancel ---

    def cancel_for_state(self, state: "State"):
        """Cancel all invocations associated with a state."""
        to_cancel = [
            inv_id
            for inv_id, inv in self._active.items()
            if inv.state_id == state.id and not inv.terminated
        ]
        for inv_id in to_cancel:
            self._cancel(inv_id)

    def cancel_all(self):
        """Cancel all active invocations."""
        for inv_id in list(self._active.keys()):
            self._cancel(inv_id)

    def _cancel(self, invokeid: str):
        invocation = self._active.get(invokeid)
        if invocation is None or invocation.terminated:
            return
        logger.debug("Cancelling invocation %s", invokeid)

        ctx = invocation.ctx
        if ctx is not None:
            ctx.cancelled = True

        handler = invocation.handler
        if handler is not None and hasattr(handler, "on_cancel"):
            try:
                handler.on_cancel()
            except Exception:
                logger.exception("Error in on_cancel for %s", invokeid)

        # Fallback: stop child SM directly if handler didn't handle it
        if invocation.child_sm is not None:
            invocation.child_sm._engine.running = False

    # --- Query ---

    def get_invocation_by_id(self, invokeid: str) -> "Invocation | None":
        return self._active.get(invokeid)

    def active_for_state(self, state: "State") -> List[Invocation]:
        return [inv for inv in self._active.values() if inv.state_id == state.id]

    def get_invocation_for_child(self, child_sm: "StateChart") -> "Invocation | None":
        for inv in self._active.values():
            if inv.child_sm is child_sm:
                return inv
        return None

    # --- Finalize & Autoforward ---

    def apply_finalize(self, invocation: Invocation, trigger_data: Any):
        """Execute the finalize block for an invocation before the event is processed."""
        config = invocation.config
        if config.finalize is None:
            return
        try:
            from .io.scxml.actions import EventDataWrapper

            _event = EventDataWrapper(_TriggerDataAdapter(trigger_data))
            config.finalize(
                machine=self.sm, model=self.sm.model, event_data=trigger_data, _event=_event
            )
        except Exception:
            logger.exception("Error in finalize for %s", invocation.invokeid)

    def forward_event(self, invocation: Invocation, event_name: str, trigger_data: Any):
        """Forward an event to a child session (autoforward)."""
        handler = invocation.handler
        if handler is not None and hasattr(handler, "on_event"):
            try:
                handler.on_event(event_name, **trigger_data.kwargs)
            except Exception:
                logger.exception("Error forwarding event to %s", invocation.invokeid)
        else:
            child_sm = invocation.child_sm or getattr(handler, "_child_sm", None)
            if child_sm is not None and not invocation.terminated:
                child_sm.send(event_name, **trigger_data.kwargs)

    # --- Cross-session sends ---

    def send_to_child(self, event_name: str, **kwargs):
        """Send an event to the first active child (for #_child target)."""
        for inv in self._active.values():
            if inv.terminated:
                continue
            child_sm = inv.child_sm or getattr(inv.handler, "_child_sm", None)
            if child_sm is not None:
                child_sm.send(event_name, **kwargs)
                return
        logger.warning("No active child to send event %s", event_name)

    def send_to_invokeid(self, invokeid: str, event_name: str, **kwargs):
        """Send an event to a specific child by invokeid."""
        inv = self._active.get(invokeid)
        if inv and not inv.terminated:
            # Check handler's child_sm first (may be set during run() before
            # invocation.child_sm is populated)
            child_sm = inv.child_sm
            if child_sm is None and inv.handler is not None:
                child_sm = getattr(inv.handler, "_child_sm", None)
            if child_sm is not None:
                child_sm.send(event_name, **kwargs)
                return
        logger.warning("No active child with invokeid %s", invokeid)
