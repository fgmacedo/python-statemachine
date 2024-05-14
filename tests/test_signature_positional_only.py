import inspect

import pytest

from statemachine.signature import SignatureAdapter


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
    async def test_positional_ony(self, args, kwargs, expected):
        def func(pos_only, /, pos_or_kw_param, *, kw_only_param):
            # https://peps.python.org/pep-0570/
            return pos_only, pos_or_kw_param, kw_only_param

        wrapped_func = SignatureAdapter.wrap(func)

        if inspect.isclass(expected) and issubclass(expected, Exception):
            with pytest.raises(expected):
                await wrapped_func(*args, **kwargs)
        else:
            assert await wrapped_func(*args, **kwargs) == expected
