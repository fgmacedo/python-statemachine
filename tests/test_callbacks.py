# coding: utf-8
import mock
import pytest

from statemachine import State
from statemachine import StateMachine
from statemachine.callbacks import Callbacks
from statemachine.callbacks import CallbackWrapper
from statemachine.dispatcher import resolver_factory
from statemachine.exceptions import InvalidDefinition


@pytest.fixture
def ObjectWithCallbacks():
    class ObjectWithCallbacks(object):
        def __init__(self):
            super(ObjectWithCallbacks, self).__init__()
            self.name = "statemachine"
            self.callbacks = Callbacks(resolver=resolver_factory(self)).add(
                ["life_meaning", "name", "a_method"]
            )

        @property
        def life_meaning(self):
            return 42

        def a_method(self, *args, **kwargs):
            return args, kwargs

    return ObjectWithCallbacks


class TestCallbacksMachinery:
    def test_raises_exception_without_setup_phase(self):
        func = mock.Mock()

        callbacks = Callbacks()
        callbacks.add(func)

        with pytest.raises(InvalidDefinition):
            callbacks.call(1, 2, 3, a="x", b="y")

        func.assert_not_called()

    def test_can_add_callback(self):
        callbacks = Callbacks()
        func = mock.Mock()

        callbacks.add(func)
        callbacks.setup(lambda x: x)

        callbacks.call(1, 2, 3, a="x", b="y")

        func.assert_called_once_with(1, 2, 3, a="x", b="y")

    def test_callback_wrapper_is_hashable(self):
        wrapper = CallbackWrapper("something")
        set().add(wrapper)

    def test_can_add_callback_that_is_a_string(self):
        callbacks = Callbacks()
        func = mock.Mock()
        resolver = mock.Mock(return_value=func)

        callbacks.add("my_method").add("other_method")
        callbacks.add("last_one")
        callbacks.setup(resolver)

        callbacks.call(1, 2, 3, a="x", b="y")

        resolver.assert_has_calls(
            [
                mock.call("my_method"),
                mock.call("other_method"),
            ]
        )
        assert func.call_args_list == [
            mock.call(1, 2, 3, a="x", b="y"),
            mock.call(1, 2, 3, a="x", b="y"),
            mock.call(1, 2, 3, a="x", b="y"),
        ]

    def test_callbacks_are_iterable(self):
        callbacks = Callbacks()

        callbacks.add("my_method").add("other_method")
        callbacks.add("last_one")

        assert [c.func for c in callbacks] == ["my_method", "other_method", "last_one"]

    def test_add_many_callbacks_at_once(self):
        callbacks = Callbacks()
        method_names = ["my_method", "other_method", "last_one"]

        callbacks.add(method_names)

        assert [c.func for c in callbacks] == method_names

    @pytest.mark.parametrize("suppress_errors", [False, True])
    def test_raise_error_if_didnt_found_attr(self, suppress_errors):
        callbacks = Callbacks(resolver_factory(object()))

        if suppress_errors:
            callbacks.add("this_does_no_exist", suppress_errors=suppress_errors)
        else:
            with pytest.raises(InvalidDefinition):
                callbacks.add("this_does_no_exist", suppress_errors=suppress_errors)

    def test_collect_results(self):
        callbacks = Callbacks()
        func1 = mock.Mock(return_value=10)
        func2 = mock.Mock(return_value=("a", True))
        func3 = mock.Mock(return_value={"key": "value"})

        callbacks.add([func1, func2, func3])
        callbacks.setup(lambda x: x)

        results = callbacks.call(1, 2, 3, a="x", b="y")

        assert results == [
            10,
            ("a", True),
            {"key": "value"},
        ]

    def test_callbacks_values_resolution(self, ObjectWithCallbacks):
        x = ObjectWithCallbacks()
        assert x.callbacks.call(xablau=True) == [
            42,
            "statemachine",
            ((), {"xablau": True}),
        ]


class TestCallbacksAsDecorator:
    def test_decorate_unbounded_function(self, ObjectWithCallbacks):
        x = ObjectWithCallbacks()

        @x.callbacks
        def hero_lowercase(hero):
            return hero.lower()

        @x.callbacks
        def race_uppercase(race):
            return race.upper()

        assert x.callbacks.call(hero="Gandalf", race="Maia") == [
            42,
            "statemachine",
            ((), {"hero": "Gandalf", "race": "Maia"}),
            "gandalf",
            "MAIA",
        ]

        assert race_uppercase("Hobbit") == "HOBBIT"

    def test_decorate_unbounded_machine_methods(self):
        class MiniHeroJourneyMachine(StateMachine):

            ordinary_world = State("Ordinary World", initial=True)
            call_to_adventure = State("Call to Adventure")
            refusal_of_call = State("Refusal of the Call")

            adventure_called = ordinary_world.to(call_to_adventure)

            def __init__(self, *args, **kwargs):
                self.spy = mock.Mock(side_effect=lambda *x: x)
                super(MiniHeroJourneyMachine, self).__init__(*args, **kwargs)

            @ordinary_world.enter
            def enter_ordinary_world(self):
                """This is the hero's life before they begin their journey. It is their "normal"
                world, where they are comfortable and familiar.
                """
                self.spy("enter_ordinary_world")

            @call_to_adventure.enter
            def enter_call_to_adventure(self, request):
                """Something happens that forces the hero to leave their ordinary world and embark
                on a journey. This might be a direct call, like a prophecy or a request for help,
                or it might be a more subtle nudge, like a feeling of restlessness or a sense of
                something missing in their life."""
                self.spy("call_to_adventure", request)

            @ordinary_world.to(refusal_of_call)
            def refuse_call(self, reason):
                self.spy("refuse_call", reason)

        sm = MiniHeroJourneyMachine()
        sm.adventure_called(request="The darkness is comming")
        assert sm.spy.call_args_list == [
            mock.call("enter_ordinary_world"),
            mock.call("call_to_adventure", "The darkness is comming"),
        ]

        sm = MiniHeroJourneyMachine()
        sm.refuse_call(reason="Not prepared yet")
        assert sm.spy.call_args_list == [
            mock.call("enter_ordinary_world"),
            mock.call("refuse_call", "Not prepared yet"),
        ]
