from inspect import BoundArguments
from inspect import FullArgSpec
from inspect import Signature
from inspect import getfullargspec
from typing import Any
from typing import Callable


class SignatureAdapter(Signature):
    method: Callable[..., Any]
    spec: FullArgSpec

    @classmethod
    def wrap(cls, obj):
        """Build a wrapper that adapts the received arguments to the inner method signature"""

        # spec is a named tuple ArgSpec(args, varargs, keywords, defaults)
        # args is a list of the argument names (it may contain nested lists)
        # varargs and keywords are the names of the * and ** arguments or None
        # defaults is a tuple of default argument values or None if there are no default arguments
        spec = getfullargspec(obj)
        sig = cls.from_callable(obj)
        sig.method = obj
        sig.spec = spec
        sig.__name__ = obj.__name__

        return sig

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        keywords = self.spec.varkw
        expected_args = list(self.spec.args)
        expected_kwargs = self.spec.defaults or ()

        # discard "self" argument for bounded methods
        if (
            hasattr(self.method, "__self__")
            and expected_args
            and expected_args[0] == "self"
        ):
            expected_args = expected_args[1:]

        if self.spec.varargs is not None:
            filtered_args = args
        else:
            filtered_args = tuple(
                kwargs.get(k, (args[idx] if idx < len(args) else None))
                for idx, k in enumerate(expected_args)
            )

        if keywords is not None:
            filtered_kwargs = kwargs
        else:
            filtered_kwargs = {k: v for k, v in kwargs.items() if k in expected_kwargs}

        return self.method(*filtered_args, **filtered_kwargs)

    def bind_expected(
        self, *args: Any, **kwargs: Any
    ) -> BoundArguments:  # pragma: no cover
        return BoundArguments(self, {})  # type: ignore [arg-type]
