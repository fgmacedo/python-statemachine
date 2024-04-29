from functools import partial
from unittest import mock

import pytest

from statemachine import State
from statemachine import StateMachine
from statemachine.callbacks import CallbackMeta
from statemachine.callbacks import CallbackMetaList
from statemachine.callbacks import CallbacksExecutor
from statemachine.callbacks import CallbacksRegistry
from statemachine.dispatcher import resolver_factory
from statemachine.exceptions import InvalidDefinition


@pytest.fixture()
def ObjectWithCallbacks():
    class ObjectWithCallbacks:
        def __init__(self):
            super().__init__()
            self.name = "statemachine"
            self.callbacks = CallbackMetaList().add(
                ["life_meaning", "name", "a_method"],
            )
            self.registry = CallbacksRegistry()
            self.executor = self.registry.register(self.callbacks, resolver=resolver_factory(self))

        @property
        def life_meaning(self):
            return 42

        def a_method(self, *args, **kwargs):
            return args, kwargs

    return ObjectWithCallbacks


class TestCallbacksMachinery:
    def test_can_add_callback(self):
        meta_list = CallbackMetaList()
        executor = CallbacksExecutor()

        func = mock.Mock()

        class MyObject:
            def do_something(self, *args, **kwargs):
                return func(*args, **kwargs)

        obj = MyObject()

        meta_list.add(obj.do_something)
        executor.add(meta_list, resolver_factory(obj))

        executor.call(1, 2, 3, a="x", b="y")

        func.assert_called_once_with(1, 2, 3, a="x", b="y")

    def test_callback_meta_is_hashable(self):
        wrapper = CallbackMeta("something")
        set().add(wrapper)

    def test_can_add_callback_that_is_a_string(self):
        callbacks = CallbackMetaList()
        func = mock.Mock()

        registry = CallbacksRegistry()

        class MyObject:
            def my_method(self, *args, **kwargs):
                return func("my_method", *args, **kwargs)

            def other_method(self, *args, **kwargs):
                return func("other_method", *args, **kwargs)

            def last_one(self, *args, **kwargs):
                return func("last_one", *args, **kwargs)

        obj = MyObject()

        callbacks.add("my_method").add("other_method")
        callbacks.add("last_one")

        registry.register(callbacks, resolver_factory(obj))

        registry[callbacks].call(1, 2, 3, a="x", b="y")

        assert func.call_args_list == [
            mock.call("my_method", 1, 2, 3, a="x", b="y"),
            mock.call("other_method", 1, 2, 3, a="x", b="y"),
            mock.call("last_one", 1, 2, 3, a="x", b="y"),
        ]

    def test_callbacks_are_iterable(self):
        callbacks = CallbackMetaList()

        callbacks.add("my_method").add("other_method")
        callbacks.add("last_one")

        assert [c.func for c in callbacks] == ["my_method", "other_method", "last_one"]

    def test_add_many_callbacks_at_once(self):
        callbacks = CallbackMetaList()
        method_names = ["my_method", "other_method", "last_one"]

        callbacks.add(method_names)

        assert [c.func for c in callbacks] == method_names

    @pytest.mark.parametrize("suppress_errors", [False, True])
    def test_raise_error_if_didnt_found_attr(self, suppress_errors):
        callbacks = CallbackMetaList()
        registry = CallbacksRegistry()

        register = partial(registry.register, resolver=resolver_factory(self))

        callbacks.add(
            "this_does_no_exist",
            suppress_errors=suppress_errors,
        )
        register(callbacks)

        if suppress_errors:
            registry.check(callbacks)
        else:
            with pytest.raises(InvalidDefinition):
                registry.check(callbacks)

    def test_collect_results(self):
        callbacks = CallbackMetaList()
        registry = CallbacksRegistry()

        def func1():
            return 10

        def func2():
            return ("a", True)

        def func3():
            return {"key": "value"}

        callbacks.add([func1, func2, func3])
        registry.register(callbacks, resolver_factory(object()))

        results = registry[callbacks].call(1, 2, 3, a="x", b="y")

        assert results == [
            10,
            ("a", True),
            {"key": "value"},
        ]

    def test_callbacks_values_resolution(self, ObjectWithCallbacks):
        x = ObjectWithCallbacks()
        assert x.executor.call(xablau=True) == [
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

        x.registry.register(x.callbacks, resolver=resolver_factory(x))

        assert x.executor.call(hero="Gandalf", race="Maia") == [
            42,
            "statemachine",
            ((), {"hero": "Gandalf", "race": "Maia"}),
            "gandalf",
            "MAIA",
        ]

        assert race_uppercase("Hobbit") == "HOBBIT"

    def test_decorate_unbounded_machine_methods(self):
        class MiniHeroJourneyMachine(StateMachine, strict_states=False):
            ordinary_world = State(initial=True)
            call_to_adventure = State()
            refusal_of_call = State()

            adventure_called = ordinary_world.to(call_to_adventure)

            def __init__(self, *args, **kwargs):
                self.spy = mock.Mock(side_effect=lambda *x: x)
                super().__init__(*args, **kwargs)

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
        sm.adventure_called(request="The darkness is coming")
        assert sm.spy.call_args_list == [
            mock.call("enter_ordinary_world"),
            mock.call("call_to_adventure", "The darkness is coming"),
        ]

        sm = MiniHeroJourneyMachine()
        sm.refuse_call(reason="Not prepared yet")
        assert sm.spy.call_args_list == [
            mock.call("enter_ordinary_world"),
            mock.call("refuse_call", "Not prepared yet"),
        ]
