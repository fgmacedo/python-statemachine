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


# ---------------------------------------------------------------------------
# Configuration & Runtime
# ---------------------------------------------------------------------------


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

        # Set class-level attrs temporarily for __init__
        child_class._parent_sm = ctx._parent_sm  # type: ignore[attr-defined]
        child_class._invokeid = ctx.invokeid  # type: ignore[attr-defined]
        child_class._defer_start = True  # type: ignore[attr-defined]
        try:
            child_sm = child_class(listeners=[bridge])
        finally:
            _cleanup_class_attrs(child_class)

        # Ensure instance-level parent references
        child_sm._parent_sm = ctx._parent_sm  # type: ignore[attr-defined]
        child_sm._invokeid = ctx.invokeid  # type: ignore[attr-defined]

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


def _cleanup_class_attrs(cls: type):
    for attr in ("_parent_sm", "_invokeid", "_defer_start"):
        if hasattr(cls, attr):
            delattr(cls, attr)


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
    """Manages active invocations for an engine instance."""

    def __init__(self, engine: "BaseEngine"):
        self._engine = engine
        self._active: Dict[str, Invocation] = {}

    @property
    def sm(self) -> "StateChart":
        return self._engine.sm

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
        )
        # Attach parent SM reference for StateChartInvoker (not part of public API)
        ctx._parent_sm = self.sm  # type: ignore[attr-defined]

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
        import asyncio

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
        )
        ctx._parent_sm = self.sm  # type: ignore[attr-defined]

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
        import asyncio

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
