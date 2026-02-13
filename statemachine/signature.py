from __future__ import annotations

from functools import partial
from inspect import BoundArguments
from inspect import Parameter
from inspect import Signature
from inspect import iscoroutinefunction
from itertools import chain
from types import MethodType
from typing import Any
from typing import FrozenSet
from typing import Optional
from typing import Tuple

BindCacheKey = Tuple[int, FrozenSet[str]]
BindTemplate = Tuple[Tuple[str, ...], Optional[str], Optional[str]]  # noqa: UP007


def _make_key(method):
    method = method.func if isinstance(method, partial) else method
    method = method.fget if isinstance(method, property) else method
    if isinstance(method, MethodType):
        return hash(
            (
                method.__qualname__,
                method.__self__.__class__.__name__,
                method.__code__.co_varnames,
            )
        )
    else:
        return hash((method.__qualname__, method.__code__.co_varnames))


def signature_cache(user_function):
    cache = {}
    cache_get = cache.get

    def cached_function(cls, method):
        key = _make_key(method)
        sig = cache_get(key)
        if sig is None:
            sig = user_function(cls, method)
            cache[key] = sig

        return sig

    cached_function.clear_cache = cache.clear
    cached_function.make_key = _make_key

    return cached_function


class SignatureAdapter(Signature):
    is_coroutine: bool = False
    _bind_cache: dict[BindCacheKey, BindTemplate]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._bind_cache = {}

    @classmethod
    @signature_cache
    def from_callable(cls, method):
        if hasattr(method, "__signature__"):
            sig = method.__signature__
            adapter = SignatureAdapter(
                sig.parameters.values(),
                return_annotation=sig.return_annotation,
            )
        else:
            adapter = super().from_callable(method)

        adapter.is_coroutine = iscoroutinefunction(method)
        return adapter

    def bind_expected(self, *args: Any, **kwargs: Any) -> BoundArguments:
        cache_key: BindCacheKey = (len(args), frozenset(kwargs.keys()))
        template = self._bind_cache.get(cache_key)

        if template is not None:
            return self._fast_bind(args, kwargs, template)

        result = self._full_bind(cache_key, *args, **kwargs)
        return result

    def _fast_bind(
        self,
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
        template: BindTemplate,
    ) -> BoundArguments:
        param_names, kwargs_param_name, var_positional_name = template
        arguments: dict[str, Any] = {}
        past_var_positional = False

        for i, name in enumerate(param_names):
            if name == var_positional_name:
                # Collect all remaining positional args into a tuple
                arguments[name] = args[i:]
                past_var_positional = True
            elif past_var_positional:
                # After *args, remaining params are keyword-only
                arguments[name] = kwargs.get(name)
            elif i < len(args):
                # Match _full_bind: if param is also in kwargs, kwargs wins
                # (POSITIONAL_OR_KEYWORD params prefer kwargs over positional args)
                if name in kwargs:
                    arguments[name] = kwargs[name]
                else:
                    arguments[name] = args[i]
            else:
                arguments[name] = kwargs.get(name)

        if kwargs_param_name is not None:
            matched = set(param_names)
            arguments[kwargs_param_name] = {k: v for k, v in kwargs.items() if k not in matched}

        return BoundArguments(self, arguments)  # type: ignore[arg-type]

    def _full_bind(  # noqa: C901
        self,
        cache_key: BindCacheKey,
        *args: Any,
        **kwargs: Any,
    ) -> BoundArguments:
        """Get a BoundArguments object, that maps the passed `args`
        and `kwargs` to the function's signature.  It avoids to raise `TypeError`
        trying to fill all the required arguments and ignoring the unknown ones.

        Adapted from the internal `inspect.Signature._bind`.
        """
        arguments: dict[str, Any] = {}
        param_names_used: list[str] = []

        parameters = iter(self.parameters.values())
        arg_vals = iter(args)
        parameters_ex: Any = ()
        kwargs_param = None
        kwargs_param_name: str | None = None
        var_positional_name: str | None = None

        while True:
            # Let's iterate through the positional arguments and corresponding
            # parameters
            try:
                arg_val = next(arg_vals)
            except StopIteration:
                # No more positional arguments
                try:
                    param = next(parameters)
                except StopIteration:
                    # No more parameters. That's it. Just need to check that
                    # we have no `kwargs` after this while loop
                    break
                else:
                    if param.kind == Parameter.VAR_POSITIONAL:
                        # That's OK, just empty *args.  Let's start parsing
                        # kwargs
                        break
                    elif param.name in kwargs:
                        if param.kind == Parameter.POSITIONAL_ONLY:
                            msg = (
                                "{arg!r} parameter is positional only, but was passed as a keyword"
                            )
                            msg = msg.format(arg=param.name)
                            raise TypeError(msg) from None
                        parameters_ex = (param,)
                        break
                    elif (
                        param.kind == Parameter.VAR_KEYWORD or param.default is not Parameter.empty
                    ):
                        # That's fine too - we have a default value for this
                        # parameter.  So, lets start parsing `kwargs`, starting
                        # with the current parameter
                        parameters_ex = (param,)
                        break
                    else:
                        # No default, not VAR_KEYWORD, not VAR_POSITIONAL,
                        # not in `kwargs`
                        parameters_ex = (param,)
                        break
            else:
                # We have a positional argument to process
                try:
                    param = next(parameters)
                except StopIteration:
                    # raise TypeError('too many positional arguments') from None
                    break
                else:
                    if param.kind == Parameter.VAR_KEYWORD:
                        # Memorize that we have a '**kwargs'-like parameter
                        kwargs_param = param
                        break

                    if param.kind == Parameter.KEYWORD_ONLY:
                        # Looks like we have no parameter for this positional
                        # argument
                        # 'too many positional arguments' forgiven
                        break

                    if param.kind == Parameter.VAR_POSITIONAL:
                        # We have an '*args'-like argument, let's fill it with
                        # all positional arguments we have left and move on to
                        # the next phase
                        values = [arg_val]
                        values.extend(arg_vals)
                        arguments[param.name] = tuple(values)
                        param_names_used.append(param.name)
                        var_positional_name = param.name
                        break

                    if param.name in kwargs and param.kind != Parameter.POSITIONAL_ONLY:
                        arguments[param.name] = kwargs.pop(param.name)
                    else:
                        arguments[param.name] = arg_val
                    param_names_used.append(param.name)

        # Now, we iterate through the remaining parameters to process
        # keyword arguments
        for param in chain(parameters_ex, parameters):
            if param.kind == Parameter.VAR_KEYWORD:
                # Memorize that we have a '**kwargs'-like parameter
                kwargs_param = param
                continue

            if param.kind == Parameter.VAR_POSITIONAL:
                # Named arguments don't refer to '*args'-like parameters.
                # We only arrive here if the positional arguments ended
                # before reaching the last parameter before *args.
                continue

            param_name = param.name
            try:
                arg_val = kwargs.pop(param_name)
            except KeyError:
                # We have no value for this parameter.  It's fine though,
                # if it has a default value, or it is an '*args'-like
                # parameter, left alone by the processing of positional
                # arguments.
                pass
            else:
                arguments[param_name] = arg_val
                param_names_used.append(param_name)

        if kwargs:
            if kwargs_param is not None:
                # Process our '**kwargs'-like parameter
                arguments[kwargs_param.name] = kwargs  # type: ignore[assignment]
                kwargs_param_name = kwargs_param.name
            else:
                # 'ignoring we got an unexpected keyword argument'
                pass

        template: BindTemplate = (tuple(param_names_used), kwargs_param_name, var_positional_name)
        self._bind_cache[cache_key] = template

        return BoundArguments(self, arguments)  # type: ignore[arg-type]
