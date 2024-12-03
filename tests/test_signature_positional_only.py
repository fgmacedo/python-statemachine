import inspect

import pytest

from statemachine.dispatcher import callable_method


class TestSignatureAdapter:
    @pytest.mark.parametrize(
        ("args", "kwargs", "expected"),
        [
            ([], {}, TypeError),
            ([1, 2, 3], {}, TypeError),
            ([1, 2], {"kw_only_param": 42}, (1, 2, 42)),
            ([1], {"pos_or_kw_param": 21, "kw_only_param": 42}, (1, 21, 42)),
            (
                [],
                {"pos_only": 10, "pos_or_kw_param": 21, "kw_only_param": 42},
                TypeError,
            ),
        ],
    )
    def test_positional_only(self, args, kwargs, expected):
        def func(pos_only, /, pos_or_kw_param, *, kw_only_param):
            # https://peps.python.org/pep-0570/
            return pos_only, pos_or_kw_param, kw_only_param

        wrapped_func = callable_method(func)

        if inspect.isclass(expected) and issubclass(expected, Exception):
            with pytest.raises(expected):
                wrapped_func(*args, **kwargs)
        else:
            assert wrapped_func(*args, **kwargs) == expected
