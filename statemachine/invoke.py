"""Invoke support for StateCharts.

Invoke lets a state spawn external work (API calls, file I/O, child state machines)
when entered, and cancel it when exited. Invoke is modelled as a callback group
(``CallbackGroup.INVOKE``) so that convention naming (``on_invoke_<state>``),
decorators (``@state.invoke``), and inline callables all work out of the box.
"""

import asyncio
import logging
import threading
import uuid
from concurrent.futures import Future
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from dataclasses import field
from typing import TYPE_CHECKING
from typing import Any
from typing import Callable
from typing import Dict
from typing import List
from typing import Tuple
from typing import runtime_checkable

try:
    from typing import Protocol
except ImportError:  # pragma: no cover
    from typing_extensions import Protocol  # type: ignore[assignment]

if TYPE_CHECKING:
    from .callbacks import CallbackWrapper
    from .engines.base import BaseEngine
    from .state import State
    from .statemachine import StateChart

logger = logging.getLogger(__name__)


@runtime_checkable
class IInvoke(Protocol):
    """Protocol for advanced invoke handlers.

    Implement ``run(ctx)`` to execute work when a state is entered.
    Optionally implement ``on_cancel()`` for cleanup when the state is exited.
    """

    def run(self, ctx: "InvokeContext") -> Any: ...  # pragma: no branch


def _stop_child_machine(child: "StateChart | None") -> None:
    """Stop a child state machine and cancel all its invocations."""
    if child is None:
        return
    logger.debug("invoke: stopping child machine %s", type(child).__name__)
    try:
        child._engine.running = False
        child._engine._invoke_manager.cancel_all()
    except Exception:
        logger.debug("Error stopping child machine", exc_info=True)


class _InvokeCallableWrapper:
    """Wraps an IInvoke class/instance or StateChart class for the callback system.

    The callback resolution system expects plain callables or strings. This wrapper
    makes IInvoke classes, IInvoke instances, and StateChart classes look like regular
    callables while preserving the original object for the InvokeManager to detect.

    When ``_invoke_handler`` is a **class**, ``run()`` instantiates it on each call
    so that each StateChart instance gets its own handler — avoiding shared mutable
    state between machines.
    """

    def __init__(self, handler: Any):
        self._invoke_handler = handler
        self._is_class = isinstance(handler, type)
        self._instance: Any = None
        name = getattr(handler, "__name__", type(handler).__name__)
        self.__name__ = name
        self.__qualname__ = getattr(handler, "__qualname__", name)
        # The callback system inspects __code__ for caching (signature.py)
        self.__code__ = self.__call__.__code__

    def __call__(self, **kwargs):
        return self._invoke_handler

    def run(self, ctx: "InvokeContext") -> Any:
        """Create a fresh instance (if class) and delegate to its ``run()``."""
        handler = self._invoke_handler
        if self._is_class:
            handler = handler()
        self._instance = handler
        return handler.run(ctx)

    def on_cancel(self):
        """Delegate to the live instance's ``on_cancel()`` if available."""
        if self._instance is not None:
            target = self._instance
        elif self._is_class:
            return  # Handler hasn't been instantiated yet — nothing to cancel
        else:
            target = self._invoke_handler
        if hasattr(target, "on_cancel"):
            target.on_cancel()


def normalize_invoke_callbacks(invoke: Any) -> Any:
    """Wrap IInvoke instances and StateChart classes so the callback system can handle them.

    Plain callables and strings pass through unchanged.
    """
    if invoke is None:
        return None

    from .utils import ensure_iterable

    items = ensure_iterable(invoke)
    result = []
    for item in items:
        if _needs_wrapping(item):
            result.append(_InvokeCallableWrapper(item))
        else:
            result.append(item)
    return result


def _needs_wrapping(item: Any) -> bool:
    """Check if an item needs wrapping for the callback system."""
    if isinstance(item, str):
        return False
    if isinstance(item, _InvokeCallableWrapper):
        return False
    # IInvoke instance (already instantiated — kept for advanced use / SCXML adapter)
    if isinstance(item, IInvoke):
        return True
    if isinstance(item, type):
        from .statemachine import StateChart

        # StateChart subclass → child machine invoker
        if issubclass(item, StateChart):
            return True
    return False


@dataclass
class InvokeContext:
    """Context passed to invoke handlers."""

    invokeid: str
    """Unique identifier for this invocation."""

    state_id: str
    """The id of the state that triggered this invocation."""

    send: "Callable[..., None]"
    """``send(event, **data)`` — enqueue an event on the parent machine's external queue."""

    machine: "StateChart"
    """Reference to the parent state machine."""

    cancelled: threading.Event = field(default_factory=threading.Event)
    """Set when the owning state is exited; handlers should check this to stop early."""

    kwargs: dict = field(default_factory=dict)
    """Keyword arguments from the event that triggered the state entry."""


@dataclass
class Invocation:
    """Tracks a single active invocation."""

    invokeid: str
    state_id: str
    ctx: InvokeContext
    thread: "threading.Thread | None" = None
    task: "asyncio.Task[Any] | None" = None
    terminated: bool = False
    _handler: Any = None


class StateChartInvoker:
    """Wraps a :class:`StateChart` subclass as an :class:`IInvoke` handler.

    When ``run(ctx)`` is called, it instantiates and runs the child machine
    synchronously. The child machine's final result (if any) becomes the
    return value.
    """

    def __init__(self, child_class: "type[StateChart]"):
        self._child_class = child_class
        self._child: "StateChart | None" = None

    def run(self, _ctx: "InvokeContext") -> Any:
        self._child = self._child_class()
        # The child machine starts automatically in its constructor.
        # If it has final states, it will terminate on its own.
        return None

    def on_cancel(self):
        _stop_child_machine(self._child)
        self._child = None


class InvokeGroup:
    """Runs multiple callables concurrently and returns their results as a list.

    All callables are submitted to a :class:`~concurrent.futures.ThreadPoolExecutor`.
    The handler blocks until every callable completes, then returns a list of results
    in the same order as the input callables.

    If the owning state is exited before all callables finish, the remaining futures
    are cancelled.  If any callable raises, the remaining futures are cancelled and
    the exception propagates (which causes an ``error.execution`` event).
    """

    def __init__(self, callables: "List[Callable[..., Any]]"):
        self._callables = list(callables)
        self._futures: "List[Future[Any]]" = []
        self._executor: "ThreadPoolExecutor | None" = None

    def run(self, ctx: "InvokeContext") -> "List[Any]":
        results: "List[Any]" = [None] * len(self._callables)
        self._executor = ThreadPoolExecutor(max_workers=len(self._callables))
        try:
            self._futures = [self._executor.submit(fn) for fn in self._callables]
            for idx, future in enumerate(self._futures):
                # Poll so we can react to cancellation promptly.
                while not future.done():
                    if ctx.cancelled.is_set():
                        self._cancel_remaining()
                        return []
                    ctx.cancelled.wait(timeout=0.05)
                results[idx] = future.result()  # re-raises if the callable failed
        except Exception:
            self._cancel_remaining()
            raise
        finally:
            # Normal exit: all futures completed, safe to shutdown without waiting.
            self._executor.shutdown(wait=False)
        return results

    def on_cancel(self):
        # Called from the engine thread — must not block. Cancel pending futures
        # and signal shutdown; the invoke thread's run() will detect ctx.cancelled
        # and exit, then _cancel()'s thread.join() waits for the actual cleanup.
        self._cancel_remaining()
        if self._executor is not None:
            self._executor.shutdown(wait=False, cancel_futures=True)

    def _cancel_remaining(self):
        for future in self._futures:
            if not future.done():
                future.cancel()


def invoke_group(*callables: "Callable[..., Any]") -> InvokeGroup:
    """Group multiple callables into a single invoke that runs them concurrently.

    Returns an :class:`InvokeGroup` instance (implements :class:`IInvoke`).
    When all callables complete, a single ``done.invoke`` event is sent with
    ``data`` set to a list of results in the same order as the input callables.

    Example::

        loading = State(initial=True, invoke=invoke_group(fetch_users, fetch_config))

        def on_enter_ready(self, data=None, **kwargs):
            users, config = data
    """
    return InvokeGroup(list(callables))


class InvokeManager:
    """Manages the lifecycle of invoke handlers for a state machine engine.

    Tracks which states need invocation after entry, spawns handlers
    (in threads for sync, as tasks for async), and cancels them on exit.
    """

    def __init__(self, engine: "BaseEngine"):
        self._engine = engine
        self._active: Dict[str, Invocation] = {}
        self._pending: "List[Tuple[State, dict]]" = []

    @property
    def sm(self) -> "StateChart":
        return self._engine.sm

    # --- Engine hooks ---

    def mark_for_invoke(self, state: "State", event_kwargs: "dict | None" = None):
        """Called by ``_enter_states()`` after entering a state with invoke callbacks.

        Args:
            state: The state that was entered.
            event_kwargs: Keyword arguments from the event that triggered the
                state entry.  These are forwarded to invoke handlers via
                dependency injection (plain callables) and ``InvokeContext.kwargs``
                (IInvoke handlers).
        """
        self._pending.append((state, event_kwargs or {}))

    def cancel_for_state(self, state: "State"):
        """Called by ``_exit_states()`` before exiting a state."""
        logger.debug("invoke cancel_for_state: %s", state.id)
        for inv_id, inv in list(self._active.items()):
            if inv.state_id == state.id and not inv.ctx.cancelled.is_set():
                self._cancel(inv_id)
        self._pending = [(s, kw) for s, kw in self._pending if s.id != state.id]
        # Don't cleanup here — terminated invocations must stay in _active
        # so that handle_external_event can still run finalize blocks for
        # done.invoke events that are already queued.

    def cancel_all(self):
        """Cancel all active invocations."""
        logger.debug("invoke cancel_all: %d active", len(self._active))
        for inv_id in list(self._active.keys()):
            self._cancel(inv_id)
        self._cleanup_terminated()

    def _cleanup_terminated(self):
        """Remove invocations whose threads/tasks have actually finished.

        Only removes invocations that are both terminated AND cancelled.
        A terminated-but-not-cancelled invocation means the handler's ``run()``
        has returned but the owning state is still active — the invocation must
        stay in ``_active`` so that ``send_to_child()`` can still forward events
        to it (e.g. ``<send target="#_<invokeid>">``).
        """
        self._active = {
            inv_id: inv
            for inv_id, inv in self._active.items()
            if not inv.terminated or not inv.ctx.cancelled.is_set()
        }

    # --- Sync spawning ---

    def spawn_pending_sync(self):
        """Spawn invoke handlers for all states marked for invocation (sync engine)."""
        # Opportunistically clean up finished invocations before spawning new ones.
        self._cleanup_terminated()

        pending = sorted(self._pending, key=lambda p: p[0].document_order)
        self._pending.clear()
        for state, event_kwargs in pending:
            self.sm._callbacks.visit(
                state.invoke.key,
                self._spawn_one_sync,
                state=state,
                event_kwargs=event_kwargs,
            )

    def _spawn_one_sync(self, callback: "CallbackWrapper", **kwargs):
        state: "State" = kwargs["state"]
        event_kwargs: dict = kwargs.get("event_kwargs", {})

        # Use meta.func to find the original (unwrapped) handler; the callback
        # system wraps everything in a signature_adapter closure.
        handler = self._resolve_handler(callback.meta.func)
        ctx = self._make_context(state, event_kwargs, handler=handler)
        invocation = Invocation(invokeid=ctx.invokeid, state_id=state.id, ctx=ctx)

        invocation._handler = handler
        self._active[ctx.invokeid] = invocation
        logger.debug("invoke spawn sync: %s on state %s", ctx.invokeid, state.id)

        thread = threading.Thread(
            target=self._run_sync_handler,
            args=(callback, handler, ctx, invocation),
            daemon=True,
        )
        invocation.thread = thread
        thread.start()

    def _run_sync_handler(
        self,
        callback: "CallbackWrapper",
        handler: "Any | None",
        ctx: InvokeContext,
        invocation: Invocation,
    ):
        try:
            if handler is not None:
                result = handler.run(ctx)
            else:
                result = callback.call(ctx=ctx, machine=ctx.machine, **ctx.kwargs)
            if not ctx.cancelled.is_set():
                self.sm.send(
                    f"done.invoke.{ctx.invokeid}",
                    data=result,
                )
        except Exception as e:
            if not ctx.cancelled.is_set():
                # Intentionally using the external queue (no internal=True):
                # This handler runs in a background thread, outside the processing
                # loop. Using the internal queue would either contaminate an
                # unrelated macrostep in progress, or stall if no macrostep is
                # active (the internal queue is only drained within a macrostep).
                # This matches done.invoke, which also uses the external queue.
                self.sm.send("error.execution", error=e)
        finally:
            invocation.terminated = True
            logger.debug(
                "invoke %s: completed (cancelled=%s)", ctx.invokeid, ctx.cancelled.is_set()
            )

    # --- Async spawning ---

    async def spawn_pending_async(self):
        """Spawn invoke handlers for all states marked for invocation (async engine)."""
        # Opportunistically clean up finished invocations before spawning new ones.
        self._cleanup_terminated()

        pending = sorted(self._pending, key=lambda p: p[0].document_order)
        self._pending.clear()
        for state, event_kwargs in pending:
            await self.sm._callbacks.async_visit(
                state.invoke.key,
                self._spawn_one_async,
                state=state,
                event_kwargs=event_kwargs,
            )

    def _spawn_one_async(self, callback: "CallbackWrapper", **kwargs):
        state: "State" = kwargs["state"]
        event_kwargs: dict = kwargs.get("event_kwargs", {})

        handler = self._resolve_handler(callback.meta.func)
        ctx = self._make_context(state, event_kwargs, handler=handler)
        invocation = Invocation(invokeid=ctx.invokeid, state_id=state.id, ctx=ctx)

        invocation._handler = handler
        self._active[ctx.invokeid] = invocation
        logger.debug("invoke spawn async: %s on state %s", ctx.invokeid, state.id)

        loop = asyncio.get_running_loop()
        task = loop.create_task(self._run_async_handler(callback, handler, ctx, invocation))
        invocation.task = task

    async def _run_async_handler(
        self,
        callback: "CallbackWrapper",
        handler: "Any | None",
        ctx: InvokeContext,
        invocation: Invocation,
    ):
        try:
            loop = asyncio.get_running_loop()
            if handler is not None:
                # Run handler.run(ctx) in a thread executor so blocking I/O
                # doesn't freeze the event loop.
                result = await loop.run_in_executor(None, handler.run, ctx)
            else:
                result = await loop.run_in_executor(
                    None, lambda: callback.call(ctx=ctx, machine=ctx.machine, **ctx.kwargs)
                )
            if not ctx.cancelled.is_set():
                self.sm.send(
                    f"done.invoke.{ctx.invokeid}",
                    data=result,
                )
        except asyncio.CancelledError:
            # Intentionally swallowed: the owning state was exited, so this
            # invocation was cancelled — there is nothing to propagate.
            return
        except Exception as e:
            if not ctx.cancelled.is_set():
                # External queue — see comment in _run_sync_handler.
                self.sm.send("error.execution", error=e)
        finally:
            invocation.terminated = True
            logger.debug(
                "invoke %s: completed (cancelled=%s)", ctx.invokeid, ctx.cancelled.is_set()
            )

    # --- Cancel ---

    def _cancel(self, invokeid: str):
        invocation = self._active.get(invokeid)
        if not invocation or invocation.ctx.cancelled.is_set():
            return

        logger.debug("invoke cancel: %s", invokeid)
        # 1) Signal cancellation so the handler can check and stop early.
        invocation.ctx.cancelled.set()

        # 2) Notify the handler (may stop child SMs, cancel futures, etc.).
        handler = invocation._handler
        if handler is not None and hasattr(handler, "on_cancel"):
            try:
                handler.on_cancel()
            except Exception:
                logger.debug("Error in on_cancel for %s", invokeid, exc_info=True)

        # 3) Cancel the async task (raises CancelledError at next await).
        if invocation.task is not None and not invocation.task.done():
            invocation.task.cancel()

        # 4) Wait for the sync thread to actually finish (skip if we ARE
        #    that thread — e.g. done.invoke processed from within the handler).
        if (
            invocation.thread is not None
            and invocation.thread is not threading.current_thread()
            and invocation.thread.is_alive()
        ):
            invocation.thread.join(timeout=2.0)

    def send_to_child(self, invokeid: str, event: str, **data) -> bool:
        """Send an event to an invoked child session by its invokeid.

        Returns True if the event was forwarded, False if the invocation was
        not found or doesn't support event forwarding.
        """
        invocation = self._active.get(invokeid)
        if invocation is None:
            return False
        handler = invocation._handler
        if handler is not None and hasattr(handler, "on_event"):
            handler.on_event(event, **data)
            return True
        return False

    # --- Helpers ---

    def handle_external_event(self, trigger_data) -> None:
        """Run finalize blocks and autoforward for active invocations.

        Called by the engine before processing each external event.
        For each active invocation whose handler has ``on_finalize`` or
        ``on_event`` (autoforward), delegate accordingly.
        """
        event_name = str(trigger_data.event) if trigger_data.event else None
        if event_name is None:
            return

        # Tag done.invoke events with the invokeid
        if event_name.startswith("done.invoke."):
            invokeid = event_name[len("done.invoke.") :]
            trigger_data.kwargs.setdefault("_invokeid", invokeid)

        for inv in list(self._active.values()):
            handler = inv._handler
            if handler is None:
                continue

            # Check if event originates from this invocation
            is_from_child = trigger_data.kwargs.get(
                "_invokeid"
            ) == inv.invokeid or event_name.startswith(f"done.invoke.{inv.invokeid}")

            # Finalize: run the finalize block if the event came from this invocation.
            # Note: finalize must run even after the invocation terminates, because
            # child events may still be queued when the handler thread completes.
            if is_from_child and hasattr(handler, "on_finalize"):
                handler.on_finalize(trigger_data)

            # Autoforward: forward parent events to child (not events from child itself).
            # Only forward if the invocation is still running.
            if (
                not inv.terminated
                and not inv.ctx.cancelled.is_set()
                and not is_from_child
                and hasattr(handler, "autoforward")
                and handler.autoforward
                and hasattr(handler, "on_event")
            ):
                logger.debug("invoke autoforward: %s -> %s", event_name, inv.invokeid)
                handler.on_event(event_name, **trigger_data.kwargs)

    def _make_context(
        self, state: "State", event_kwargs: "dict | None" = None, handler: Any = None
    ) -> InvokeContext:
        # Use static invoke_id from handler if available (SCXML id= attribute)
        static_id = getattr(handler, "invoke_id", None) if handler else None
        invokeid = static_id or f"{state.id}.{uuid.uuid4().hex[:8]}"
        return InvokeContext(
            invokeid=invokeid,
            state_id=state.id,
            send=self.sm.send,
            machine=self.sm,
            kwargs=event_kwargs or {},
        )

    @staticmethod
    def _resolve_handler(underlying: Any) -> "Any | None":
        """Determine the handler type from the resolved callable."""
        from .statemachine import StateChart

        if isinstance(underlying, _InvokeCallableWrapper):
            inner = underlying._invoke_handler
            if isinstance(inner, type) and issubclass(inner, StateChart):
                return StateChartInvoker(inner)
            # Return the inner handler directly if it's an IInvoke instance
            # (e.g., SCXMLInvoker) so duck-typed attributes like invoke_id are accessible.
            # Exclude classes — @runtime_checkable matches classes that define run().
            if not isinstance(inner, type) and isinstance(inner, IInvoke):
                return inner
            return underlying
        if isinstance(underlying, IInvoke):
            return underlying
        if isinstance(underlying, type) and issubclass(underlying, StateChart):
            return StateChartInvoker(underlying)
        return None
