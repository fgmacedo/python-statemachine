"""Tests for the value-expression support added to ``spec_parser`` (the restricted
AST-whitelist evaluator used to avoid ``eval`` on SCXML datamodel expressions)."""

import pytest
from statemachine.spec_parser import parse_expr


def hook_from(values: dict):
    """Build a ``variable_hook`` that resolves names from a static dict."""

    def hook(name: str):
        def resolver(*args, **kwargs):
            try:
                return values[name]
            except KeyError as exc:
                raise NameError(name) from exc

        return resolver

    return hook


class _Obj:
    def __init__(self, **attrs):
        self.__dict__.update(attrs)

    def method(self):  # pragma: no cover - only referenced by a rejected expression
        return "called"


class TestValueExpressions:
    def test_constant(self):
        assert parse_expr("42", hook_from({}))() == 42

    def test_name_resolution(self):
        assert parse_expr("x", hook_from({"x": 7}))() == 7

    def test_arithmetic(self):
        hook = hook_from({"x": 4})
        assert parse_expr("x + 1", hook)() == 5
        assert parse_expr("x - 1", hook)() == 3
        assert parse_expr("x * 2", hook)() == 8
        assert parse_expr("x / 2", hook)() == 2
        assert parse_expr("x // 3", hook)() == 1
        assert parse_expr("x % 3", hook)() == 1
        assert parse_expr("x ** 2", hook)() == 16

    def test_unary_minus_and_plus(self):
        hook = hook_from({"x": 4})
        assert parse_expr("-x", hook)() == -4
        assert parse_expr("+x", hook)() == 4

    def test_list_tuple_set(self):
        hook = hook_from({"x": 2})
        assert parse_expr("[1, x, 3]", hook)() == [1, 2, 3]
        assert parse_expr("(1, x)", hook)() == (1, 2)
        assert parse_expr("{1, x, 3}", hook)() == {1, 2, 3}

    def test_dict(self):
        assert parse_expr("{'a': 1, 'b': 2}", hook_from({}))() == {"a": 1, "b": 2}

    def test_subscript(self):
        hook = hook_from({"arr": [10, 20, 30], "d": {"k": "v"}, "i": 1})
        assert parse_expr("arr[0]", hook)() == 10
        assert parse_expr("arr[i]", hook)() == 20
        assert parse_expr("d['k']", hook)() == "v"

    def test_attribute_read_allowed(self):
        hook = hook_from({"obj": _Obj(value=10)})
        assert parse_expr("obj.value", hook)() == 10

    def test_comparison_returns_bool(self):
        hook = hook_from({"x": 4})
        assert parse_expr("x > 2", hook)() is True
        assert parse_expr("x == 5", hook)() is False

    def test_boolean_short_circuit_returns_value(self):
        # BoolOp keeps Python short-circuit value semantics (not coerced to bool).
        hook = hook_from({"x": 0, "y": 9})
        assert parse_expr("x or y", hook)() == 9
        assert parse_expr("x and y", hook)() == 0

    def test_nested_expression(self):
        hook = hook_from({"items": [1, 2, 3], "factor": 10})
        assert parse_expr("items[2] * factor + 1", hook)() == 31


class TestRejectedExpressions:
    """Each of these must raise at parse/compile time (becomes InvalidDefinition)."""

    @pytest.mark.parametrize(
        "expr",
        [
            "__import__('os')",
            "().__class__",
            "x.__class__",
            "().__class__.__bases__",
            "obj.method()",
            "lambda: 1",
            "[i for i in x]",
            "(y := 1)",
            "{**d}",
            "a[1:2]",
            "x ^ y",
            "x | y",
        ],
    )
    def test_unsupported_structures_raise_value_error(self, expr):
        with pytest.raises(ValueError, match="Unsupported|not allowed"):
            parse_expr(expr, hook_from({"x": 1, "y": 2, "obj": _Obj(), "a": [1, 2], "d": {}}))

    def test_attribute_dunder_message(self):
        with pytest.raises(ValueError, match="Attribute access to '__class__' is not allowed"):
            parse_expr("x.__class__", hook_from({"x": 1}))

    def test_unknown_function_rejected(self):
        with pytest.raises(ValueError, match="Unsupported function"):
            parse_expr("open('f')", hook_from({}))

    def test_empty_expression_raises_syntax_error(self):
        with pytest.raises(SyntaxError):
            parse_expr("   ", hook_from({}))

    def test_statement_rejected_as_syntax_error(self):
        with pytest.raises(SyntaxError):
            parse_expr("import os", hook_from({}))


class TestRuntimeErrorsArePropagated:
    """Name/value errors surface at call time (so the engine can map them to
    error.execution), not at parse time."""

    def test_undefined_name_raises_at_runtime(self):
        fn = parse_expr("missing + 1", hook_from({}))  # compiles fine
        with pytest.raises(NameError):
            fn()

    def test_type_error_raises_at_runtime(self):
        fn = parse_expr("x + 1", hook_from({"x": "str"}))  # compiles fine
        with pytest.raises(TypeError):
            fn()
