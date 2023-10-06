import itertools
from functools import partial
from inspect import BoundArguments
from inspect import Parameter
from inspect import Signature
from types import MethodType
from typing import Any


def _make_key(method):
    method = method.func if isinstance(method, partial) else method
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
    @classmethod
    def wrap(cls, method):
        """Build a wrapper that adapts the received arguments to the inner ``method`` signature"""

        sig = cls.from_callable(method)
        sig_bind_expected = sig.bind_expected

        metadata_to_copy = method.func if isinstance(method, partial) else method

        def method_wrapper(*args: Any, **kwargs: Any) -> Any:
            ba = sig_bind_expected(*args, **kwargs)
            return method(*ba.args, **ba.kwargs)

        method_wrapper.__name__ = metadata_to_copy.__name__

        return method_wrapper

    @classmethod
    @signature_cache
    def from_callable(cls, method):
        if hasattr(method, "__signature__"):
            sig = method.__signature__
            return SignatureAdapter(
                sig.parameters.values(),
                return_annotation=sig.return_annotation,
            )
        return super().from_callable(method)

    def bind_expected(self, *args: Any, **kwargs: Any) -> BoundArguments:  # noqa: C901
        """Get a BoundArguments object, that maps the passed `args`
        and `kwargs` to the function's signature.  It avoids to raise `TypeError`
        trying to fill all the required arguments and ignoring the unknown ones.

        Adapted from the internal `inspect.Signature._bind`.
        """
        arguments = {}

        parameters = iter(self.parameters.values())
        arg_vals = iter(args)
        parameters_ex: Any = ()
        kwargs_param = None

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
                                "{arg!r} parameter is positional only, "
                                "but was passed as a keyword"
                            )
                            msg = msg.format(arg=param.name)
                            raise TypeError(msg) from None
                        parameters_ex = (param,)
                        break
                    elif (
                        param.kind == Parameter.VAR_KEYWORD
                        or param.default is not Parameter.empty
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
                        break

                    if param.name in kwargs and param.kind != Parameter.POSITIONAL_ONLY:
                        arguments[param.name] = kwargs.pop(param.name)
                    else:
                        arguments[param.name] = arg_val

        # Now, we iterate through the remaining parameters to process
        # keyword arguments
        for param in itertools.chain(parameters_ex, parameters):
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
                arguments[param_name] = arg_val  #

        if kwargs:
            if kwargs_param is not None:
                # Process our '**kwargs'-like parameter
                arguments[kwargs_param.name] = kwargs  # type: ignore [assignment]
            else:
                # 'ignoring we got an unexpected keyword argument'
                pass

        return BoundArguments(self, arguments)  # type: ignore [arg-type]
