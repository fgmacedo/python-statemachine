import inspect
from functools import partial

import pytest

from statemachine.dispatcher import callable_method


def single_positional_param(a):
    return a


def single_default_keyword_param(a=42):
    return a


def args_param(*args):
    return args


def kwargs_param(**kwargs):
    return kwargs


def args_and_kwargs_param(*args, **kwargs):
    return args, kwargs


def positional_optional_catchall(a, b="ham", *args):
    return a, b, args


def ignored_param(a, b, *, c, d=10):
    return a, b, c, d


def positional_and_kw_arguments(source, target, event):
    return source, target, event


def default_kw_arguments(source: str = "A", target: str = "B", event: str = "go"):
    return source, target, event


class MyObject:
    def __init__(self, value=42):
        self.value = value

    def method_no_argument(self):
        return self.value


class TestSignatureAdapter:
    @pytest.mark.parametrize(
        ("func", "args", "kwargs", "expected"),
        [
            (single_positional_param, [10], {}, 10),
            (single_positional_param, [], {"a": 10}, 10),
            pytest.param(single_positional_param, [], {}, TypeError),
            (single_default_keyword_param, [10], {}, 10),
            (single_default_keyword_param, [], {"a": 10}, 10),
            pytest.param(single_default_keyword_param, [], {}, 42),
            (MyObject().method_no_argument, [], {}, 42),
            (MyObject().method_no_argument, ["ignored"], {"x": True}, 42),
            (MyObject.method_no_argument, [MyObject()], {"x": True}, 42),
            pytest.param(MyObject.method_no_argument, [], {}, TypeError),
            (args_param, [], {}, ()),
            (args_param, [42], {}, (42,)),
            (args_param, [1, 1, 2, 3, 5, 8, 13], {}, (1, 1, 2, 3, 5, 8, 13)),
            (
                args_param,
                [1, 1, 2, 3, 5, 8, 13],
                {"x": True, "other": 42},
                (1, 1, 2, 3, 5, 8, 13),
            ),
            (kwargs_param, [], {}, {}),
            (kwargs_param, [1], {}, {}),
            (kwargs_param, [1, 3, 5, 8, "x", True], {}, {}),
            (kwargs_param, [], {"x": True}, {"x": True}),
            (kwargs_param, [], {"x": True, "n": 42}, {"x": True, "n": 42}),
            (
                kwargs_param,
                [10, "x", False],
                {"x": True, "n": 42},
                {"x": True, "n": 42},
            ),
            (args_and_kwargs_param, [], {}, ((), {})),
            (args_and_kwargs_param, [1], {}, ((1,), {})),
            (
                args_and_kwargs_param,
                [1, 3, 5, False, "n"],
                {"x": True, "n": 42},
                ((1, 3, 5, False, "n"), {"x": True, "n": 42}),
            ),
            (positional_optional_catchall, [], {}, TypeError),
            (positional_optional_catchall, [42], {}, (42, "ham", ())),
            pytest.param(
                positional_optional_catchall,
                [True],
                {"b": "spam"},
                (True, "spam", ()),
            ),
            pytest.param(
                positional_optional_catchall,
                ["a", "b"],
                {"b": "spam"},
                ("a", "spam", ()),
            ),
            (
                positional_optional_catchall,
                ["a", "b", "c"],
                {"b": "spam"},
                ("a", "spam", ("c",)),
            ),
            (
                positional_optional_catchall,
                ["a", "b", "c", False, 10],
                {"other": 42},
                ("a", "b", ("c", False, 10)),
            ),
            (ignored_param, [], {}, TypeError),
            (ignored_param, [1, 2, 3], {}, TypeError),
            pytest.param(
                ignored_param,
                [1, 2],
                {"c": 42},
                (1, 2, 42, 10),
            ),
            pytest.param(
                ignored_param,
                [1, 2],
                {"c": 42, "d": 21},
                (1, 2, 42, 21),
            ),
            pytest.param(positional_and_kw_arguments, [], {}, TypeError),
            (positional_and_kw_arguments, [1, 2, 3], {}, (1, 2, 3)),
            (positional_and_kw_arguments, [1, 2], {"event": "foo"}, (1, 2, "foo")),
            (
                positional_and_kw_arguments,
                [],
                {"source": "A", "target": "B", "event": "foo"},
                ("A", "B", "foo"),
            ),
            pytest.param(default_kw_arguments, [], {}, ("A", "B", "go")),
            (default_kw_arguments, [1, 2, 3], {}, (1, 2, 3)),
            (default_kw_arguments, [1, 2], {"event": "wait"}, (1, 2, "wait")),
        ],
    )
    def test_wrap_fn_single_positional_parameter(self, func, args, kwargs, expected):
        wrapped_func = callable_method(func)
        assert wrapped_func.__name__ == func.__name__

        if inspect.isclass(expected) and issubclass(expected, Exception):
            with pytest.raises(expected):
                wrapped_func(*args, **kwargs)
        else:
            assert wrapped_func(*args, **kwargs) == expected

    def test_support_for_partial(self):
        part = partial(positional_and_kw_arguments, event="activated")
        wrapped_func = callable_method(part)

        assert wrapped_func("A", "B") == ("A", "B", "activated")
        assert wrapped_func.__name__ == positional_and_kw_arguments.__name__
