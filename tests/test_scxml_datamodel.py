"""Unit tests for the SCXML datamodel evaluation strategies."""

import pytest
from statemachine.exceptions import InvalidDefinition
from statemachine.io.evaluators import PythonEvaluator
from statemachine.io.evaluators import RestrictedEvaluator
from statemachine.io.evaluators import _eval
from statemachine.io.evaluators import evaluator_for
from statemachine.io.evaluators import normalize_cond
from statemachine.io.evaluators import variable_hook


class TestEvaluatorFor:
    """The single wiring point that maps the trusted flag to a concrete strategy."""

    def test_default_is_restricted(self):
        assert isinstance(evaluator_for(), RestrictedEvaluator)

    def test_false_is_restricted(self):
        assert isinstance(evaluator_for(False), RestrictedEvaluator)

    def test_true_is_python(self):
        assert isinstance(evaluator_for(True), PythonEvaluator)


class _State:
    def __init__(self, id):
        self.id = id


class _Model:
    pass


class _Machine:
    def __init__(self, configuration=(), **attrs):
        self.model = _Model()
        for key, value in attrs.items():
            setattr(self.model, key, value)
        self.configuration = list(configuration)


class TestNormalizeCond:
    def test_javascript_literals_and_operators(self):
        assert normalize_cond("true && false || null") == "True and False or None"
        assert normalize_cond("a === b") == "a == b"
        assert normalize_cond("a !== b") == "a != b"

    def test_unescapes_xml_entities(self):
        assert normalize_cond("a &lt; b") == "a < b"


class TestVariableHook:
    def test_kwargs_take_precedence(self):
        resolver = variable_hook("_event")
        assert resolver(machine=_Machine(), _event="evt") == "evt"

    def test_falls_back_to_model_attribute(self):
        resolver = variable_hook("x")
        assert resolver(machine=_Machine(x=42)) == 42

    def test_protected_attribute_is_not_resolved_from_model(self):
        machine = _Machine()
        machine.model._name = "secret"  # protected
        resolver = variable_hook("_name")
        with pytest.raises(NameError):
            resolver(machine=machine)

    def test_unknown_name_raises(self):
        with pytest.raises(NameError):
            variable_hook("missing")(machine=_Machine())


class TestRestrictedEvaluator:
    def setup_method(self):
        self.evaluator = RestrictedEvaluator()

    def test_value_arithmetic(self):
        fn = self.evaluator.compile_value("x + 1")
        assert fn(machine=_Machine(x=4)) == 5

    def test_value_collection_and_subscript(self):
        assert self.evaluator.compile_value("[1, 2, 3]")(machine=_Machine()) == [1, 2, 3]
        fn = self.evaluator.compile_value("items[1]")
        assert fn(machine=_Machine(items=["a", "b"])) == "b"

    def test_value_attribute_read(self):
        nested = _Model()
        nested.value = 99
        fn = self.evaluator.compile_value("obj.value")
        assert fn(machine=_Machine(obj=nested)) == 99

    def test_bool_returns_bool_and_normalizes(self):
        fn = self.evaluator.compile_bool("x &gt; 2 &amp;&amp; true")
        assert fn(machine=_Machine(x=4)) is True
        assert fn(machine=_Machine(x=1)) is False

    def test_bool_in_predicate(self):
        fn = self.evaluator.compile_bool("In('s1')")
        assert fn(machine=_Machine(configuration=[_State("s1")])) is True
        assert fn(machine=_Machine(configuration=[_State("s2")])) is False

    @pytest.mark.parametrize(
        "expr",
        [
            "__import__('os')",
            "[].__class__",
            "obj.method()",
            "lambda: 1",
        ],
    )
    def test_value_escape_raises_invalid_definition(self, expr):
        with pytest.raises(InvalidDefinition, match="not allowed by the restricted"):
            self.evaluator.compile_value(expr)

    def test_script_is_rejected(self):
        with pytest.raises(InvalidDefinition, match="<script>"):
            self.evaluator.compile_script("x = 1")

    def test_runtime_name_error_is_not_swallowed(self):
        fn = self.evaluator.compile_value("missing + 1")  # compiles fine
        with pytest.raises(NameError):
            fn(machine=_Machine())

    def test_eval_literal_parses_value(self):
        assert self.evaluator.eval_literal("[1, 2]") == [1, 2]

    def test_eval_literal_falls_back_to_raw_string(self):
        # Not a literal; ast.literal_eval raises -> raw string.
        assert self.evaluator.eval_literal("not_a_literal") == "not_a_literal"


class TestPythonEvaluator:
    def setup_method(self):
        self.evaluator = PythonEvaluator()

    def test_value_evaluates_arbitrary_python(self):
        # Dunder access works in the trusted path (proves it is unrestricted).
        assert self.evaluator.compile_value("[].__class__")(machine=_Machine()) is list

    def test_value_uses_model_namespace(self):
        fn = self.evaluator.compile_value("x * 2")
        assert fn(machine=_Machine(x=21)) == 42

    def test_bool_normalizes_and_evaluates(self):
        fn = self.evaluator.compile_bool("x &gt; 0 || false")
        assert bool(fn(machine=_Machine(x=5))) is True

    def test_script_executes_and_writes_back_to_model(self):
        machine = _Machine(counter=0)
        self.evaluator.compile_script("counter = counter + 5")(machine=machine)
        assert machine.model.counter == 5

    def test_eval_literal_parses_value(self):
        assert self.evaluator.eval_literal("[1, 2]") == [1, 2]

    def test_eval_literal_falls_back_to_raw_string(self):
        # `unknown_name` is not a literal; eval raises NameError -> raw string.
        assert self.evaluator.eval_literal("unknown_name") == "unknown_name"


class TestEvalHelper:
    def test_eval_without_machine_skips_namespace_injection(self):
        # Covers the branch where no `machine` is present in kwargs.
        assert _eval("1 + 1") == 2
