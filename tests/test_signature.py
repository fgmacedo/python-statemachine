import inspect
from functools import partial

import pytest
from statemachine.dispatcher import callable_method
from statemachine.signature import SignatureAdapter


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


def named_and_kwargs(source, **kwargs):
    return source, kwargs


class TestCachedBindExpected:
    """Tests that exercise the cache fast-path by calling the same
    wrapped function twice with the same argument shape."""

    def setup_method(self):
        SignatureAdapter.from_callable.clear_cache()

    def test_named_param_not_leaked_into_kwargs(self):
        """Named params should not appear in the **kwargs dict on cache hit."""
        wrapped = callable_method(named_and_kwargs)

        # 1st call: cache miss -> _full_bind
        result1 = wrapped(source="A", target="B", event="go")
        assert result1 == ("A", {"target": "B", "event": "go"})

        # 2nd call: cache hit -> _fast_bind
        result2 = wrapped(source="X", target="Y", event="stop")
        assert result2 == ("X", {"target": "Y", "event": "stop"})

    def test_kwargs_only_receives_unmatched_keys_with_positional(self):
        """When mixing positional and keyword args with **kwargs."""
        wrapped = callable_method(named_and_kwargs)

        result1 = wrapped("A", target="B")
        assert result1 == ("A", {"target": "B"})

        result2 = wrapped("X", target="Y")
        assert result2 == ("X", {"target": "Y"})

    def test_var_positional_collected_as_tuple(self):
        """VAR_POSITIONAL (*args) must be collected into a tuple on cache hit."""

        def fn(*args, **kwargs):
            return args, kwargs

        wrapped = callable_method(fn)

        result1 = wrapped(1, 2, 3, key="val")
        assert result1 == ((1, 2, 3), {"key": "val"})

        result2 = wrapped(4, 5, key="other")
        assert result2 == ((4, 5), {"key": "other"})

    def test_keyword_only_after_var_positional(self):
        """KEYWORD_ONLY params after *args must be extracted from kwargs on cache hit."""

        def fn(*args, event, **kwargs):
            return args, event, kwargs

        wrapped = callable_method(fn)

        result1 = wrapped(100, event="ev1", source="s0")
        assert result1 == ((100,), "ev1", {"source": "s0"})

        result2 = wrapped(200, event="ev2", source="s1")
        assert result2 == ((200,), "ev2", {"source": "s1"})

    def test_positional_or_keyword_prefers_kwargs_over_positional(self):
        """When a POSITIONAL_OR_KEYWORD param is in both args and kwargs, kwargs wins."""

        def fn(event, source, target):
            return event, source, target

        wrapped = callable_method(fn)

        # 1st call: positional arg provided but 'event' also in kwargs -> kwargs wins
        result1 = wrapped("discarded_content", event="ev1", source="s0", target="t0")
        assert result1 == ("ev1", "s0", "t0")

        # 2nd call: cache hit, same behavior expected
        result2 = wrapped("other_content", event="ev2", source="s1", target="t1")
        assert result2 == ("ev2", "s1", "t1")

    def test_empty_var_positional(self):
        """Empty *args is handled correctly on cache hit."""

        def fn(*args, **kwargs):
            return args, kwargs

        wrapped = callable_method(fn)

        # 1st call with args
        result1 = wrapped(1, key="val")
        assert result1 == ((1,), {"key": "val"})

        # 2nd call: only kwargs, no positional args — different cache key (len=0)
        result2 = wrapped(key="val2")
        assert result2 == ((), {"key": "val2"})

        # 3rd call: hits cache for len=0
        result3 = wrapped(key="val3")
        assert result3 == ((), {"key": "val3"})

    def test_named_params_before_var_positional(self):
        """Named params before *args are filled correctly on cache hit."""

        def fn(a, b, *args, **kwargs):
            return a, b, args, kwargs

        wrapped = callable_method(fn)

        result1 = wrapped(1, 2, 3, 4, key="val")
        assert result1 == (1, 2, (3, 4), {"key": "val"})

        result2 = wrapped(10, 20, 30, key="val2")
        assert result2 == (10, 20, (30,), {"key": "val2"})

    def test_kwargs_wins_with_var_positional_present(self):
        """POSITIONAL_OR_KEYWORD before *args prefers kwargs when name matches."""

        def fn(event, *args, **kwargs):
            return event, args, kwargs

        wrapped = callable_method(fn)

        # 1st call: 'event' in both positional and kwargs — kwargs wins
        result1 = wrapped("discarded", "extra", event="ev1", key="a")
        assert result1 == ("ev1", ("extra",), {"key": "a"})

        # 2nd call: cache hit, same behavior
        result2 = wrapped("other", "more", event="ev2", key="b")
        assert result2 == ("ev2", ("more",), {"key": "b"})
