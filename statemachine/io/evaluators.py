"""Evaluation strategies for statechart datamodel expressions and scripts.

An :class:`Evaluator` turns the raw expression/script strings carried by the
neutral IR (:mod:`statemachine.io.model`) into callables, deciding *how* they are
evaluated:

- :class:`RestrictedEvaluator` (secure default): compiles expressions with the
  AST-whitelist evaluator (:func:`statemachine.spec_parser.parse_expr`), which
  cannot reach builtins, dunder attributes, or arbitrary calls. ``<script>`` and
  raw-Python evaluation are rejected because they are arbitrary code.
- :class:`PythonEvaluator` (opt-in, ``trusted=True``): preserves the legacy
  behavior of evaluating expressions and scripts as arbitrary Python via
  ``eval``/``exec``.

The restricted evaluator validates the *structure* of an expression at compile
time (a violation raises :class:`~statemachine.exceptions.InvalidDefinition`),
but name resolution and value computation still happen at call time, so runtime
errors (``NameError``, ``TypeError``) keep flowing to ``error.execution`` as
before.

This module is format-neutral: it is shared by the SCXML, JSON and YAML readers.
See the :mod:`statemachine.io.scxml` package docstring and the GHSA-v4jc-pm6r-3vj8
advisory for the rationale.
"""

import ast
import html
import re
from collections.abc import Callable
from inspect import isawaitable
from typing import Any
from typing import Protocol

from ..dispatcher import callable_method
from ..event import _event_data_kwargs
from ..exceptions import InvalidDefinition
from ..spec_parser import InState
from ..spec_parser import parse_expr

#: Attributes that must never be exposed to or overwritten by datamodel
#: expressions (engine internals and SCXML system variables).
protected_attrs = _event_data_kwargs | {"_sessionid", "_ioprocessors", "_name", "_event"}


_COND_REPLACEMENTS = {
    "true": "True",
    "false": "False",
    "null": "None",
    "===": "==",
    "!==": "!=",
    "&&": "and",
    "||": "or",
}
_COND_PATTERN = re.compile(r"\b(?:true|false|null)\b|===|!==|&&|\|\|")


def normalize_cond(cond: str) -> str:
    """Normalize a JavaScript-like condition to Python syntax.

    Decodes XML entities (e.g. ``&lt;``) and maps ``true``/``false``/``null`` and
    the ``===``/``!==``/``&&``/``||`` operators to their Python equivalents. This
    is primarily an SCXML (ECMAScript datamodel) concern; for Python-style
    expressions (JSON/YAML) it is effectively a no-op.
    """
    cond = html.unescape(cond)
    return _COND_PATTERN.sub(lambda match: _COND_REPLACEMENTS[match.group(0)], cond)


def _resolvable_model_attr(name: str, model) -> bool:
    """The secure boundary for resolving a bare name off the model.

    Engine-protected names (``machine``, ``event``, system variables, …) and any
    private/dunder name (leading underscore) never resolve off the model, mirroring the
    dotted-access guard in :func:`statemachine.spec_parser.build_attribute`. System
    variables stay reachable because they are provided via the call kwargs, which are
    consulted before this. This keeps a semi-trusted document from reading the model's
    internals (``_secret``) or walking the object graph (``__class__``).
    """
    return name not in protected_attrs and not name.startswith("_") and hasattr(model, name)


def variable_hook(name: str) -> Callable:
    """Resolve a datamodel name at call time.

    Looks the name up in the call kwargs first (engine-provided variables such as
    ``_event``, ``_name``, ``machine``), then falls back to a (non-protected, non-private)
    attribute of ``machine.model``. Mirrors the namespace built by :func:`_eval`.
    """

    def resolver(*args, **kwargs):
        if name in kwargs:
            return kwargs[name]
        model = kwargs["machine"].model
        if _resolvable_model_attr(name, model):
            return getattr(model, name)
        raise NameError(f"name '{name}' is not defined")

    resolver.__name__ = name
    return resolver


def cond_variable_hook(name: str) -> Callable:
    """Resolve a name inside a guard, following the Python guard dialect.

    Same lookup as :func:`variable_hook`, but a referenced **method** is *called*
    (with dependency injection), while a property or plain attribute is *read*.
    This keeps native ``cond``/``unless`` at parity with class-defined guards (see
    ``docs/guards.md``): a name can be a property, an attribute or a method.
    """

    def resolver(*args, **kwargs):
        if name in kwargs:
            return kwargs[name]
        model = kwargs["machine"].model
        if _resolvable_model_attr(name, model):
            value = getattr(model, name)
            if callable(value):
                return callable_method(value)(*args, **kwargs)
            return value
        raise NameError(f"name '{name}' is not defined")

    resolver.__name__ = name
    return resolver


def _eval(expr: str, **kwargs) -> Any:
    """Evaluate an expression as arbitrary Python (``trusted=True`` path only).

    .. warning::

        Calls the built-in :func:`eval` with no sandboxing. Only reachable when
        the document is loaded with ``trusted=True``.
    """
    if "machine" in kwargs:
        kwargs.update(
            **{
                k: v
                for k, v in kwargs["machine"].model.__dict__.items()
                if k not in protected_attrs
            }
        )
        kwargs["In"] = InState(kwargs["machine"])
    return eval(expr, {}, kwargs)


class Evaluator(Protocol):
    """Port: turns expression/script strings into callables.

    This is the contract consumers (the processors, action compilers) depend on. They
    never name a concrete implementation; wiring goes through :func:`evaluator_for`.
    """

    def compile_value(self, expr: str) -> Callable:  # pragma: no cover - structural Protocol
        """Compile a value expression (``<assign>``, ``<send>``, ``<data>``, ...)."""
        ...

    def compile_bool(self, expr: str) -> Callable:  # pragma: no cover - structural Protocol
        """Compile a boolean guard expression (``cond``)."""
        ...

    def compile_script(self, content: str) -> Callable:  # pragma: no cover - structural Protocol
        """Compile a ``<script>`` body into a callable side effect."""
        ...

    def eval_literal(self, content: str) -> Any:  # pragma: no cover - structural Protocol
        """Evaluate inline ``<content>`` as a literal, falling back to the raw string."""
        ...


class RestrictedEvaluator:
    """Secure default: AST-whitelist evaluation, no ``eval``/``exec``.

    ``<script>`` and any expression outside the supported subset (method calls,
    dunder attribute access, lambdas, comprehensions, ...) are rejected at
    compile time with :class:`~statemachine.exceptions.InvalidDefinition`.
    """

    def compile_value(self, expr: str) -> Callable:
        return self._compile(expr, variable_hook)

    def compile_bool(self, expr: str) -> Callable:
        # Guards resolve names with the Python dialect (methods are called); the
        # result is coerced to bool, awaiting it first when a coroutine (an async
        # guard method) flows through, so the async engine works too.
        value_fn = self._compile(normalize_cond(expr), cond_variable_hook)

        def cond(*args, **kwargs):
            result = value_fn(*args, **kwargs)
            if isawaitable(result):

                async def _coerce():
                    return bool(await result)

                return _coerce()
            return bool(result)

        return cond

    def compile_script(self, content: str) -> Callable:
        raise InvalidDefinition(
            "<script> executes arbitrary code and is disabled by default. Pass "
            "trusted=True to enable it, and only for trusted sources."
        )

    def eval_literal(self, content: str) -> Any:
        try:
            return ast.literal_eval(content)
        except (ValueError, SyntaxError):
            return content

    @staticmethod
    def _compile(expr: str, hook: Callable) -> Callable:
        try:
            return parse_expr(expr, hook)
        except (ValueError, SyntaxError) as exc:
            raise InvalidDefinition(
                f"Expression {expr!r} is not allowed by the restricted "
                f"datamodel ({exc}). Pass trusted=True to evaluate it as "
                f"Python, and only for trusted sources."
            ) from exc


class PythonEvaluator:
    """Opt-in (``trusted=True``): evaluate expressions and scripts as Python.

    Preserves the legacy ``eval``/``exec`` behavior, including error timing
    (syntax/name errors surface at call time and become ``error.execution``).
    """

    def compile_value(self, expr: str) -> Callable:
        def value(*args, **kwargs):
            return _eval(expr, **kwargs)

        return value

    def compile_bool(self, expr: str) -> Callable:
        # Intentionally uses ``eval`` (not ``parse_expr``): the whole point of the
        # trusted evaluator is to accept guards the restricted AST whitelist rejects —
        # method/function calls, builtins, etc. (e.g. SCXML conformance conds like
        # ``_event.data.get('x') == 1`` or ``hasattr(_event, 'name')``). Routing this
        # through ``parse_expr`` would make trusted mode no more capable than the
        # restricted one for guards and would break those documents.
        normalized = normalize_cond(expr)

        def cond(*args, **kwargs):
            return _eval(normalized, **kwargs)

        return cond

    def compile_script(self, content: str) -> Callable:
        def script(*args, **kwargs):
            machine = kwargs["machine"]
            local_vars = {**machine.model.__dict__}
            exec(content, {}, local_vars)
            for var_name, value in local_vars.items():
                setattr(machine.model, var_name, value)

        return script

    def eval_literal(self, content: str) -> Any:
        try:
            return eval(content, {}, {})
        except (NameError, SyntaxError, TypeError):
            return content


def evaluator_for(trusted: bool = False) -> Evaluator:
    """Return the evaluation strategy for the given trust level (the wiring point).

    This is the single place that maps the public ``trusted`` flag to a concrete
    adapter, so no other module needs to import :class:`RestrictedEvaluator` or
    :class:`PythonEvaluator`. The default (``trusted=False``) is the secure restricted
    evaluator, so callers that omit the argument get the safe behaviour.
    """
    return PythonEvaluator() if trusted else RestrictedEvaluator()
