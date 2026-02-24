import pytest
from statemachine.callbacks import CallbacksRegistry
from statemachine.dispatcher import resolver_factory_from_objects
from statemachine.transition import Transition
from statemachine.transition_list import TransitionList

from statemachine import State


def test_transition_list_or_operator():
    s1 = State("s1", initial=True)
    s2 = State("s2")
    s3 = State("s3")
    s4 = State("s4", final=True)

    t12 = s1.to(s2)
    t23 = s2.to(s3)
    t34 = s3.to(s4)

    cycle = t12 | t23 | t34

    assert [(t.source.name, t.target.name) for t in t12] == [("s1", "s2")]
    assert [(t.source.name, t.target.name) for t in t23] == [("s2", "s3")]
    assert [(t.source.name, t.target.name) for t in t34] == [("s3", "s4")]
    assert [(t.source.name, t.target.name) for t in cycle] == [
        ("s1", "s2"),
        ("s2", "s3"),
        ("s3", "s4"),
    ]


class TestDecorators:
    @pytest.mark.parametrize(
        ("callback_name", "list_attr_name", "expected_value"),
        [
            ("before", None, 42),
            ("after", None, 42),
            ("on", None, 42),
            ("validators", None, 42),
            ("cond", None, True),
            ("unless", "cond", False),
        ],
    )
    def test_should_assign_callback_to_transitions(
        self, callback_name, list_attr_name, expected_value
    ):
        registry = CallbacksRegistry()

        if list_attr_name is None:
            list_attr_name = callback_name

        s1 = State("s1", initial=True)
        transition_list = s1.to.itself()
        decorator = getattr(transition_list, callback_name)

        @decorator
        def my_callback():
            return 42

        transition = s1.transitions[0]
        specs_grouper = getattr(transition, list_attr_name)

        resolver_factory_from_objects(object()).resolve(transition._specs, registry=registry)

        assert registry[specs_grouper.key].call() == [expected_value]


def test_has_eventless_transition():
    """TransitionList.has_eventless_transition returns True for eventless transitions."""
    s1 = State("s1", initial=True)
    s2 = State("s2")
    t = Transition(s1, s2)
    tl = TransitionList([t])
    assert tl.has_eventless_transition is True


def test_has_no_eventless_transition():
    """TransitionList.has_eventless_transition returns False when all have events."""
    s1 = State("s1", initial=True)
    s2 = State("s2")
    t = Transition(s1, s2, event="go")
    tl = TransitionList([t])
    assert tl.has_eventless_transition is False


def test_transition_list_call_with_callable():
    """Calling a TransitionList with a single callable registers it as an on callback."""
    s1 = State("s1", initial=True)
    s2 = State("s2", final=True)
    tl = s1.to(s2)

    def my_callback(): ...  # No-op: used only to test callback registration

    result = tl(my_callback)
    assert result is my_callback


def test_transition_list_call_with_non_callable_raises():
    """Calling a TransitionList with a non-callable raises TypeError."""
    s1 = State("s1", initial=True)
    s2 = State("s2", final=True)
    tl = s1.to(s2)

    with pytest.raises(TypeError, match="only supports the decorator syntax"):
        tl("not_a_callable", "extra_arg")
