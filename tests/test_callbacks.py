# coding: utf-8
"""
TODO: on_enter_state()  (genérico)
TODO: on_exit_state()  (genérico)
TODO: on_enter_<state>()
TODO: on_exit_<state>()
TODO: before_transition() (genérico)
TODO: after_transition() (genérico)
TODO: before_<transition>()
TODO: after_<transition>()
"""

import pytest
import mock
from statemachine.callbacks import Callbacks, ensure_callable, resolver_factory
from statemachine.exceptions import InvalidDefinition


class Person(object):
    def __init__(self, first_name, last_name):
        self.first_name = first_name
        self.last_name = last_name

    def get_full_name(self):
        return "{} {}".format(self.first_name, self.last_name)


class TestCallbacksMachinery:
    def test_raises_exception_without_setup_phase(self):
        func = mock.Mock()

        callbacks = Callbacks()
        callbacks.add(func)

        with pytest.raises(InvalidDefinition):
            callbacks(1, 2, 3, a="x", b="y")

        func.assert_not_called()

    def test_can_add_callback(self):
        callbacks = Callbacks()
        func = mock.Mock()

        callbacks.add(func)
        callbacks.setup(lambda x: x)

        callbacks(1, 2, 3, a="x", b="y")

        func.assert_called_once_with(1, 2, 3, a="x", b="y")

    def test_can_add_callback_that_is_a_string(self):
        callbacks = Callbacks()
        func = mock.Mock()
        resolver = mock.Mock(return_value=func)

        callbacks.add("my_method").add("other_method")
        callbacks.add("last_one")
        callbacks.setup(resolver)

        callbacks(1, 2, 3, a="x", b="y")

        resolver.assert_has_calls(
            [mock.call("my_method"), mock.call("other_method"), ]
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
        callbacks = Callbacks()

        resolver = resolver_factory(object())
        if suppress_errors:
            callbacks.add("this_does_no_exist", resolver, suppress_errors=suppress_errors)
        else:
            with pytest.raises(InvalidDefinition):
                callbacks.add("this_does_no_exist", resolver, suppress_errors=suppress_errors)

    def test_collect_results(self):
        callbacks = Callbacks()
        func1 = mock.Mock(return_value=10)
        func2 = mock.Mock(return_value=("a", True))
        func3 = mock.Mock(return_value={"key": "value"})

        callbacks.add([func1, func2, func3])
        callbacks.setup(lambda x: x)

        results = callbacks(1, 2, 3, a="x", b="y")

        assert results == [
            10,
            ("a", True),
            {"key": "value"},
        ]


class TestEnsureCallable:
    @pytest.fixture(
        params=[
            pytest.param([], id="no-args"),
            pytest.param([24, True, "Go!"], id="with-args"),
        ]
    )
    def args(self, request):
        return request.param

    @pytest.fixture(
        params=[
            pytest.param(dict(), id="no-kwargs"),
            pytest.param(dict(a="x", b="y"), id="with-kwargs"),
        ]
    )
    def kwargs(self, request):
        return request.param

    def test_return_same_object_if_already_a_callable(self):
        model = Person("Frodo", "Bolseiro")
        expected = model.get_full_name
        actual = ensure_callable(expected)
        assert actual.__name__ == expected.__name__
        assert actual.__doc__ == expected.__doc__

    def test_retrieve_a_method_from_its_name(self, args, kwargs):
        model = Person("Frodo", "Bolseiro")
        expected = model.get_full_name
        method = ensure_callable("get_full_name", model)

        assert method.__name__ == expected.__name__
        assert method.__doc__ == expected.__doc__
        assert method(*args, **kwargs) == "Frodo Bolseiro"

    def test_retrieve_a_callable_from_a_property_name(self, args, kwargs):
        model = Person("Frodo", "Bolseiro")
        method = ensure_callable("first_name", model)

        assert method(*args, **kwargs) == "Frodo"

    def test_retrieve_callable_from_a_property_name_that_should_keep_reference(
        self, args, kwargs
    ):
        model = Person("Frodo", "Bolseiro")
        method = ensure_callable("first_name", model)

        model.first_name = "Bilbo"

        assert method(*args, **kwargs) == "Bilbo"
