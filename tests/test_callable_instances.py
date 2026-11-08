from functools import partial
from inspect import Parameter
from inspect import Signature

import pytest
from statemachine.callbacks import CallbackGroup
from statemachine.callbacks import CallbackSpec
from statemachine.dispatcher import callable_method
from statemachine.engines.async_ import AsyncEngine
from statemachine.exceptions import TransitionNotAllowed
from statemachine.signature import SignatureAdapter

from statemachine import State
from statemachine import StateChart


class Guard:
    __slots__ = ("calls", "allowed")

    def __init__(self, allowed=True):
        self.calls = []
        self.allowed = allowed

    def __call__(self, machine, event, *, amount=0):
        self.calls.append((machine, event, amount))
        return self.allowed and amount > 0


@pytest.mark.parametrize("reference", ["direct", "named", "partial"])
async def test_callable_guard_injects_arguments_and_preserves_instance(sm_runner, reference):
    guard = Guard()
    callback = partial(guard, amount=7) if reference == "partial" else guard

    class Machine(StateChart):
        allow_event_without_transition = False
        catch_errors_as_events = False
        a = State(initial=True)
        b = State(final=True)
        condition = callback
        go = a.to(b, cond="condition" if reference == "named" else callback)

    machine = await sm_runner.start(Machine)
    guard.allowed = False
    with pytest.raises(TransitionNotAllowed):
        await sm_runner.send(machine, "go", amount=4, ignored="value")
    assert "a" in machine.configuration_values
    guard.allowed = True
    await sm_runner.send(machine, "go", amount=4, ignored="value")
    assert "b" in machine.configuration_values
    assert guard.calls == [(machine, "go", 4), (machine, "go", 4)]


async def test_callable_guards_do_not_share_instance_state(sm_runner):
    first = Guard(allowed=False)
    second = Guard()

    class Machine(StateChart):
        allow_event_without_transition = False
        catch_errors_as_events = False
        a = State(initial=True)
        b = State(final=True)
        go = a.to(b, cond=[first, second])

    machine = await sm_runner.start(Machine)
    with pytest.raises(TransitionNotAllowed):
        await sm_runner.send(machine, "go", amount=1)
    assert len(first.calls) == 1
    assert second.calls == []
    first.allowed = True
    await sm_runner.send(machine, "go", amount=2)
    assert first.calls[-1] == second.calls[-1] == (machine, "go", 2)
    assert "b" in machine.configuration_values


@pytest.mark.parametrize("form", ["direct", "partial", "nested_partial"])
async def test_async_callable_guard_selects_async_engine_and_awaits_result(form):
    calls = []

    class AsyncGuard:
        __slots__ = ()

        async def __call__(self, machine, *, allowed=False):
            calls.append((self, machine, allowed))
            return allowed

    guard = AsyncGuard()
    callback = partial(guard, allowed=False) if form != "direct" else guard
    if form == "nested_partial":
        callback.description = "preserve the nested partial"
        callback = partial(callback)

    class Machine(StateChart):
        allow_event_without_transition = False
        catch_errors_as_events = False
        a = State(initial=True)
        b = State(final=True)
        go = a.to(b, cond=callback)

    machine = Machine()
    assert isinstance(machine._engine, AsyncEngine)
    await machine.activate_initial_state()
    with pytest.raises(TransitionNotAllowed):
        await machine.go(allowed=False)
    assert "a" in machine.configuration_values
    await machine.go(allowed=True)
    assert "b" in machine.configuration_values
    assert calls == [(guard, machine, False), (guard, machine, True)]


def test_callable_signature_does_not_mutate_user_object():
    class Callable:
        def __call__(self, value):
            return value

    target = Callable()
    original_attributes = vars(target).copy()
    spec = CallbackSpec(target, group=CallbackGroup.COND)
    assert spec.func is target
    adapted = callable_method(target)
    assert adapted(value=3, ignored=True) == 3
    assert adapted(value=5, ignored=False) == 5
    assert vars(target) == original_attributes


def test_unhashable_callables_keep_distinct_explicit_signatures():
    class Callable:
        __hash__ = None

        def __init__(self, name):
            self.__signature__ = Signature([Parameter(name, Parameter.KEYWORD_ONLY)])

        def __call__(self, **kwargs):
            return kwargs

    first = Callable("left")
    second = Callable("right")
    first_adapted = callable_method(first)
    second_adapted = callable_method(second)
    for left, right in [(1, 2), (3, 4)]:
        assert first_adapted(left=left, right=right) == {"left": left}
        assert second_adapted(left=left, right=right) == {"right": right}


def test_partial_callable_preserves_bound_positional_arguments():
    class Callable:
        def __call__(self, prefix, value):
            return prefix, value

    target = Callable()
    wrapped = callable_method(partial(target, "bound"))
    assert wrapped(value=7, unrelated=True) == ("bound", 7)
    assert wrapped(value=9, unrelated=False) == ("bound", 9)


def test_callable_and_bound_call_method_have_equivalent_signatures():
    target = Guard()
    assert SignatureAdapter.from_callable(target) == SignatureAdapter.from_callable(
        target.__call__
    )


async def test_unhashable_guard_with_relocated_nested_callbacks(sm_runner):
    entered = []

    class UnhashableGuard:
        __hash__ = None

        def __call__(self, allowed):
            return allowed

    guard = UnhashableGuard()

    class Machine(StateChart):
        catch_errors_as_events = False

        class regions(State.Parallel):
            class left(State.Compound):
                start = State(initial=True)
                done = State(final=True)
                go = start.to(done, cond=guard)

                @done.enter
                def record(self):
                    entered.append("left")

            class right(State.Compound):
                waiting = State(initial=True)
                finished = State(final=True)
                go = waiting.to(finished)

                @finished.enter
                def record(self):
                    entered.append("right")

    machine = await sm_runner.start(Machine)
    await sm_runner.send(machine, "go", allowed=True)
    assert sorted(entered) == ["left", "right"]
    assert vars(guard) == {}


async def test_zero_argument_guard_and_callable_action(sm_runner):
    calls = []

    class Allowed:
        __slots__ = ()

        def __call__(self):
            return True

    class Record:
        __slots__ = ()

        def __call__(self, machine, event):
            calls.append((machine, event))

    class Machine(StateChart):
        catch_errors_as_events = False
        a = State(initial=True)
        b = State(final=True)
        go = a.to(b, cond=Allowed(), on=Record())

    machine = await sm_runner.start(Machine)
    await sm_runner.send(machine, "go")
    assert "b" in machine.configuration_values
    assert calls == [(machine, "go")]


def test_partial_callable_preserves_explicit_signature():
    class Callable:
        __signature__ = Signature(
            [
                Parameter("prefix", Parameter.POSITIONAL_OR_KEYWORD),
                Parameter("value", Parameter.KEYWORD_ONLY),
            ]
        )

        def __call__(self, *args, **kwargs):
            return args, kwargs

    target = Callable()
    wrapped = callable_method(partial(target, "bound"))
    assert wrapped(value=7, unrelated=True) == (("bound",), {"value": 7})
    assert wrapped(value=9, unrelated=False) == (("bound",), {"value": 9})
    assert not hasattr(target.__signature__, "is_coroutine")


def test_callable_without_explicit_signature_uses_call_method():
    class Callable:
        __signature__ = None

        def __call__(self, value):
            return value

    wrapped = callable_method(Callable())
    assert wrapped(value=7, ignored=True) == 7
