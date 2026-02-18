"""SCXML-specific invoke adapter.

Resolves ``src``, ``srcexpr``, and ``content`` attributes from SCXML
``<invoke>`` elements into a child StateChart class, then delegates to
:class:`StateChartInvoker` for execution.

Also absorbs SCXML-specific invoke concerns (autoforward, namelist/params
evaluation, finalize blocks) that do not belong in the core invoke module.
"""

import logging
import time
from typing import TYPE_CHECKING
from typing import Any
from typing import List

from ...invoke import InvokeContext
from ...invoke import StateChartInvoker

if TYPE_CHECKING:
    from ...statemachine import StateChart

logger = logging.getLogger(__name__)


class _TriggerDataAdapter:
    """Adapts a TriggerData to look like EventData for EventDataWrapper."""

    def __init__(self, trigger_data: Any):
        self.trigger_data = trigger_data

    def __getattr__(self, name: str) -> Any:
        return getattr(self.trigger_data, name)


class SCXMLInvoker(StateChartInvoker):
    """Resolves SCXML src/srcexpr/content to a child StateChart class.

    Unlike the base :class:`StateChartInvoker` which receives a concrete
    class, this adapter defers class resolution until ``run()`` is called,
    because ``srcexpr`` may reference datamodel variables that are only
    available at runtime.

    Also handles SCXML-specific concerns:
    - ``autoforward``: forward parent events to child
    - ``namelist``/``params``: evaluate and pass to child at spawn time
    - ``finalize``: execute finalize block on events from child
    """

    def __init__(
        self,
        src: "str | None" = None,
        srcexpr: "str | None" = None,
        content: "str | None" = None,
        base_dir: Any = None,
        autoforward: bool = False,
        namelist: "str | None" = None,
        params: "List[Any] | None" = None,
        finalize: Any = None,
    ):
        # Don't call super().__init__() — we don't have the class yet
        self._src = src
        self._srcexpr = srcexpr
        self._content = content
        self._base_dir = base_dir
        self._child_class: "type[StateChart] | None" = None  # type: ignore[assignment]
        self._child_sm: "StateChart | None" = None

        # SCXML-specific fields
        self.autoforward = autoforward
        self.namelist = namelist
        self.params = params or []
        self.finalize = finalize

    def run(self, ctx: InvokeContext) -> Any:
        child_class = self._resolve_child_class(ctx)
        if child_class is None:
            raise RuntimeError(
                f"Could not resolve child class for invoke {ctx.invokeid} "
                f"(src={self._src}, srcexpr={self._srcexpr}, content={self._content})"
            )
        self._child_class = child_class

        # Evaluate namelist/params and merge into ctx.params
        resolved_params = self._evaluate_params(ctx)
        ctx.params.update(resolved_params)

        # Create child with _defer_start=True (engine not started yet)
        child_sm = self._create_child(ctx)
        self._child_sm = child_sm

        # Three-phase activation (SCXML spec):
        # 1. Enter initial configuration — runs datamodel onentry actions,
        #    creating model variables like Var1.
        child_sm._engine.enter_initial_configuration()
        # 2. Apply namelist/param data — overrides datamodel defaults with
        #    values from the parent.
        self._apply_params(child_sm, ctx.params)
        # 3. Start processing loop — evaluates eventless transitions with
        #    correct param values.
        child_sm._processing_loop()

        # Poll until child terminates or parent cancels
        while not child_sm.is_terminated and not ctx.cancelled:
            time.sleep(0.01)

        return None

    def on_event(self, event: str, **data):
        """Forward events to child if autoforward is enabled."""
        if self.autoforward and self._child_sm is not None:
            self._child_sm.send(event, **data)

    def on_finalize(self, trigger_data: Any):
        """Execute SCXML finalize block."""
        if self.finalize is None:
            return
        try:
            from .actions import EventDataWrapper

            _event = EventDataWrapper(_TriggerDataAdapter(trigger_data))
            parent_sm = trigger_data.machine
            self.finalize(
                machine=parent_sm,
                model=parent_sm.model,
                event_data=trigger_data,
                _event=_event,
            )
        except Exception:
            logger.exception("Error in finalize for SCXMLInvoker")

    def _evaluate_params(self, ctx: InvokeContext) -> "dict[str, Any]":
        """Evaluate namelist and param expressions in the parent's context."""
        params: dict[str, Any] = {}
        parent_sm = ctx._parent_sm

        if self.namelist:
            for name in self.namelist.strip().split():
                if not hasattr(parent_sm.model, name):
                    raise NameError(f"Namelist variable '{name}' not found on parent model")
                params[name] = getattr(parent_sm.model, name)

        for param in self.params:
            if param.expr is not None:
                from .actions import _eval

                try:
                    kwargs = {"machine": parent_sm, "model": parent_sm.model}
                    kwargs.update(
                        {
                            k: v
                            for k, v in parent_sm.model.__dict__.items()
                            if k not in {"_sessionid", "_ioprocessors", "_name", "_event"}
                        }
                    )
                    params[param.name] = _eval(param.expr, **kwargs)
                except Exception:
                    logger.exception("Error evaluating param %s", param.name)

        return params

    def _resolve_child_class(self, ctx: InvokeContext) -> "type[StateChart] | None":
        """Resolve src/srcexpr/content into a StateChart class."""
        from .processor import SCXMLProcessor

        if self._content:
            processor = SCXMLProcessor()
            processor.parse_scxml(f"invoke_{ctx.invokeid}", self._content)
            return next(iter(processor.scs.values()), None)

        src = self._resolve_src(ctx)
        if src:
            from pathlib import Path
            from urllib.parse import urlparse

            parsed = urlparse(src)
            if parsed.scheme == "file" or not parsed.scheme:
                path = Path(parsed.path) if parsed.scheme == "file" else Path(src)
                if not path.is_absolute() and self._base_dir is not None:
                    path = self._base_dir / path
                processor = SCXMLProcessor()
                processor.parse_scxml_file(path)
                return next(iter(processor.scs.values()), None)
            else:
                logger.warning("Unsupported invoke src scheme: %s", parsed.scheme)

        return None

    def _resolve_src(self, ctx: InvokeContext) -> "str | None":
        """Resolve src or srcexpr to a string."""
        if self._src:
            return self._src
        if self._srcexpr:
            parent_sm = getattr(ctx, "_parent_sm", None)
            if parent_sm is not None:
                from .actions import _eval

                return str(_eval(self._srcexpr, machine=parent_sm, model=parent_sm.model))
        return None

    def _create_child(self, ctx: InvokeContext) -> "StateChart":
        """Override to use SCXMLProcessor.start() for SCXML-parsed children."""

        child_class = self._child_class
        assert child_class is not None

        # Check if this was parsed via SCXMLProcessor (needs special start)
        if self._content or self._src or self._srcexpr:
            return self._create_scxml_child(ctx)

        # For directly provided classes, use the parent's implementation
        return super()._create_child(ctx)

    def _create_scxml_child(self, ctx: InvokeContext) -> "StateChart":
        """Create a child SM from SCXML-parsed class with deferred start.

        Uses ``_start=False`` so that the caller can apply namelist/param
        data before the engine starts.
        """
        from ...invoke import _ParentBridge
        from .processor import SCXMLProcessor

        bridge = _ParentBridge(ctx)

        # Re-parse via processor to get proper SCXML wiring
        processor = SCXMLProcessor()
        if self._content:
            processor.parse_scxml(f"invoke_{ctx.invokeid}", self._content)
        else:
            src = self._resolve_src(ctx)
            if src:
                from pathlib import Path
                from urllib.parse import urlparse

                parsed = urlparse(src)
                path = Path(parsed.path) if parsed.scheme == "file" else Path(src)
                if not path.is_absolute() and self._base_dir is not None:
                    path = self._base_dir / path
                processor.parse_scxml_file(path)

        child_sm = processor.start(listeners=[bridge], _start=False)

        from ...invoke import InvokeSession

        child_sm._invoke_session = InvokeSession(  # type: ignore[attr-defined]
            parent_sm=ctx._parent_sm,
            invokeid=ctx.invokeid,
        )

        # Copy base_dir for nested invocations
        if self._base_dir is not None:
            child_sm._scxml_base_dir = self._base_dir  # type: ignore[attr-defined]

        return child_sm  # type: ignore[no-any-return]
