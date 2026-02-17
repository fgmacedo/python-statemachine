"""SCXML-specific invoke adapter.

Resolves ``src``, ``srcexpr``, and ``content`` attributes from SCXML
``<invoke>`` elements into a child StateChart class, then delegates to
:class:`StateChartInvoker` for execution.
"""

import logging
import time
from typing import TYPE_CHECKING
from typing import Any

from ...invoke import InvokeContext
from ...invoke import StateChartInvoker

if TYPE_CHECKING:
    from ...statemachine import StateChart

logger = logging.getLogger(__name__)


class SCXMLInvoker(StateChartInvoker):
    """Resolves SCXML src/srcexpr/content to a child StateChart class.

    Unlike the base :class:`StateChartInvoker` which receives a concrete
    class, this adapter defers class resolution until ``run()`` is called,
    because ``srcexpr`` may reference datamodel variables that are only
    available at runtime.
    """

    def __init__(
        self,
        src: "str | None" = None,
        srcexpr: "str | None" = None,
        content: "str | None" = None,
        base_dir: Any = None,
    ):
        # Don't call super().__init__() — we don't have the class yet
        self._src = src
        self._srcexpr = srcexpr
        self._content = content
        self._base_dir = base_dir
        self._child_class: "type[StateChart] | None" = None  # type: ignore[assignment]
        self._child_sm: "StateChart | None" = None

    def run(self, ctx: InvokeContext) -> Any:
        child_class = self._resolve_child_class(ctx)
        if child_class is None:
            raise RuntimeError(
                f"Could not resolve child class for invoke {ctx.invokeid} "
                f"(src={self._src}, srcexpr={self._srcexpr}, content={self._content})"
            )
        self._child_class = child_class

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

        Uses ``_defer_start=True`` so that the caller can apply namelist/param
        data before the engine starts.  The caller is responsible for calling
        ``child_sm._engine.start()`` after applying params.
        """
        from ...invoke import _cleanup_class_attrs
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

        child_cls = next(iter(processor.scs.values()))
        child_cls._parent_sm = ctx._parent_sm  # type: ignore[attr-defined]
        child_cls._invokeid = ctx.invokeid  # type: ignore[attr-defined]
        child_cls._defer_start = True  # type: ignore[attr-defined]

        try:
            child_sm = processor.start(listeners=[bridge])
        finally:
            _cleanup_class_attrs(child_cls)

        child_sm._parent_sm = ctx._parent_sm  # type: ignore[attr-defined]
        child_sm._invokeid = ctx.invokeid  # type: ignore[attr-defined]

        # Copy base_dir for nested invocations
        if self._base_dir is not None:
            child_sm._scxml_base_dir = self._base_dir  # type: ignore[attr-defined]

        return child_sm  # type: ignore[no-any-return]
