from unittest import mock

import pytest

from statemachine import State
from statemachine import StateMachine
from statemachine.callbacks import CallbackGroup
from statemachine.callbacks import CallbackSpec
from statemachine.callbacks import CallbackSpecList
from statemachine.callbacks import CallbacksRegistry
from statemachine.dispatcher import resolver_factory_from_objects
from statemachine.exceptions import InvalidDefinition


@pytest.fixture()
def ObjectWithCallbacks():
    class ObjectWithCallbacks:
        def __init__(self):
            super().__init__()
            self.name = "statemachine"
            self.callbacks = CallbackSpecList().add(
                ["life_meaning", "name", "a_method"],
                group=CallbackGroup.ON,
            )
            self.can_be_called = self.callbacks.grouper(CallbackGroup.ON)
            self.registry = CallbacksRegistry()
            resolver_factory_from_objects(self).resolve(self.callbacks, registry=self.registry)

        @property
        def life_meaning(self):
            return 42

        def a_method(self, *args, **kwargs):
            return args, kwargs

    return ObjectWithCallbacks


class TestCallbacksMachinery:
    def test_callback_meta_is_hashable(self):
        wrapper = CallbackSpec("something", group=CallbackGroup.ON)
        set().add(wrapper)

    def test_can_add_callback_that_is_a_string(self):
        specs = CallbackSpecList()
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

        specs.add("my_method", group=CallbackGroup.ON).add("other_method", group=CallbackGroup.ON)
        specs.add("last_one", group=CallbackGroup.ON)

        resolver_factory_from_objects(obj).resolve(specs, registry)

        registry[CallbackGroup.ON.build_key(specs)].call(1, 2, 3, a="x", b="y")

        assert func.call_args_list == [
            mock.call("my_method", 1, 2, 3, a="x", b="y"),
            mock.call("other_method", 1, 2, 3, a="x", b="y"),
            mock.call("last_one", 1, 2, 3, a="x", b="y"),
        ]

    def test_callbacks_are_iterable(self):
        specs = CallbackSpecList()

        specs.add("my_method", 1).add("other_method", 1)
        specs.add("last_one", 1)

        assert [c.func for c in specs] == ["my_method", "other_method", "last_one"]

    def test_add_many_callbacks_at_once(self):
        specs = CallbackSpecList()
        method_names = ["my_method", "other_method", "last_one"]

        specs.add(method_names, group=CallbackGroup.ON)

        assert [c.func for c in specs] == method_names

    @pytest.mark.parametrize("is_convention", [False, True])
    def test_raise_error_if_didnt_found_attr(self, is_convention):
        specs = CallbackSpecList()
        registry = CallbacksRegistry()

        specs.add(
            "this_does_no_exist",
            group=CallbackGroup.ON,
            is_convention=is_convention,
        )
        resolver_factory_from_objects(self).resolve(specs, registry=registry)

        if is_convention:
            registry.check(specs)
        else:
            with pytest.raises(InvalidDefinition):
                registry.check(specs)

    def test_collect_results(self):
        specs = CallbackSpecList()
        registry = CallbacksRegistry()

        def func1():
            return 10

        def func2():
            return ("a", True)

        def func3():
            return {"key": "value"}

        specs.add([func1, func2, func3], group=CallbackGroup.ON)
        resolver_factory_from_objects(object()).resolve(specs, registry=registry)

        results = registry[CallbackGroup.ON.build_key(specs)].call(1, 2, 3, a="x", b="y")

        assert results == [
            10,
            ("a", True),
            {"key": "value"},
        ]

    def test_callbacks_values_resolution(self, ObjectWithCallbacks):
        x = ObjectWithCallbacks()
        assert x.registry[CallbackGroup.ON.build_key(x.callbacks)].call(xablau=True) == [
            42,
            "statemachine",
            ((), {"xablau": True}),
        ]


class TestCallbacksAsDecorator:
    def test_decorate_unbounded_function(self, ObjectWithCallbacks):
        x = ObjectWithCallbacks()

        @x.can_be_called
        def hero_lowercase(hero):
            return hero.lower()

        @x.can_be_called
        def race_uppercase(race):
            return race.upper()

        resolver_factory_from_objects(x).resolve(x.callbacks, registry=x.registry)

        assert x.registry[CallbackGroup.ON.build_key(x.callbacks)].call(
            hero="Gandalf", race="Maia"
        ) == [
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
            call_to_adventure = State(final=True)
            refusal_of_call = State(final=True)

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


class TestIssue406:
    """
    A StateMachine that exercises the example given on issue
    #[406](https://github.com/fgmacedo/python-statemachine/issues/406).

    In this example, the event callback must be registered only once.
    """

    def test_issue_406(self, mocker):
        mock = mocker.Mock()

        class ExampleStateMachine(StateMachine, strict_states=False):
            created = State(initial=True)
            inited = State(final=True)

            initialize = created.to(inited)

            @initialize.before
            def before_initialize(self):
                mock("before init")

            @initialize.on
            def on_initialize(self):
                mock("on init")

        sm = ExampleStateMachine()
        sm.initialize()

        assert mock.call_args_list == [
            mocker.call("before init"),
            mocker.call("on init"),
        ]


class TestIssue417:
    """
    A StateMachine that exercises the example given on issue
    #[417](https://github.com/fgmacedo/python-statemachine/issues/417).
    """

    @pytest.fixture()
    def mock_calls(self, mocker):
        return mocker.Mock()

    @pytest.fixture()
    def model_class(self):
        class Model:
            def __init__(self, counter: int = 0):
                self.state = None
                self.counter = counter

            def can_be_started_on_model(self) -> bool:
                return self.counter > 0

            @property
            def can_be_started_as_property_on_model(self) -> bool:
                return self.counter > 1

            @property
            def can_be_started_as_property_str_on_model(self) -> bool:
                return self.counter > 2

        return Model

    @pytest.fixture()
    def sm_class(self, model_class, mock_calls):
        class ExampleStateMachine(StateMachine):
            created = State(initial=True)
            started = State(final=True)

            def can_be_started(self) -> bool:
                return self.counter > 0

            @property
            def can_be_started_as_property(self) -> bool:
                return self.counter > 1

            @property
            def can_be_started_as_property_str(self) -> bool:
                return self.counter > 2

            start = created.to(
                started,
                cond=[
                    can_be_started,
                    can_be_started_as_property,
                    "can_be_started_as_property_str",
                    model_class.can_be_started_on_model,
                    model_class.can_be_started_as_property_on_model,
                    "can_be_started_as_property_str_on_model",
                ],
            )

            def __init__(self, model=None, counter: int = 0):
                self.counter = counter
                super().__init__(model=model)

            def on_start(self):
                mock_calls("started")

        return ExampleStateMachine

    def test_issue_417_cannot_start(self, model_class, sm_class, mock_calls):
        model = model_class(0)
        sm = sm_class(model, 0)
        with pytest.raises(sm.TransitionNotAllowed, match="Can't start when in Created"):
            sm.start()

        mock_calls.assert_not_called()

    def test_issue_417_can_start(self, model_class, sm_class, mock_calls, mocker):
        model = model_class(3)
        sm = sm_class(model, 3)
        sm.start()

        assert mock_calls.call_args_list == [
            mocker.call("started"),
        ]

    def test_raise_exception_if_property_is_not_found(self):
        class StrangeObject:
            @property
            def this_cannot_resolve(self) -> bool:
                return True

        class ExampleStateMachine(StateMachine):
            created = State(initial=True)
            started = State(final=True)
            start = created.to(started, cond=[StrangeObject.this_cannot_resolve])

        with pytest.raises(
            InvalidDefinition,
            match="Error on transition start from Created to Started when resolving callbacks",
        ):
            ExampleStateMachine()
