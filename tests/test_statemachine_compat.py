"""Backward-compatibility tests for the StateMachine (v2) API.

These tests verify that ``StateMachine`` (which inherits from ``StateChart``
with different defaults) continues to work as expected.  Tests here exercise
behaviour that differs from ``StateChart`` defaults:

- ``allow_event_without_transition = False``  → ``TransitionNotAllowed``
- ``enable_self_transition_entries = False``
- ``atomic_configuration_update = True``
- ``catch_errors_as_events = False``  → exceptions propagate directly
- ``current_state`` deprecated property
"""

import warnings

import pytest

from statemachine import State
from statemachine import StateMachine
from statemachine import exceptions

# ---------------------------------------------------------------------------
# Flag defaults
# ---------------------------------------------------------------------------


class TestStateMachineDefaults:
    """Verify the four class-level flag defaults on StateMachine."""

    def test_allow_event_without_transition(self):
        assert StateMachine.allow_event_without_transition is False

    def test_enable_self_transition_entries(self):
        assert StateMachine.enable_self_transition_entries is False

    def test_atomic_configuration_update(self):
        assert StateMachine.atomic_configuration_update is True

    def test_catch_errors_as_events(self):
        assert StateMachine.catch_errors_as_events is False


# ---------------------------------------------------------------------------
# Smoke test
# ---------------------------------------------------------------------------


class TestStateMachineSmoke:
    """StateMachine as a subclass works for basic operations."""

    def test_create_send_and_check_state(self):
        class TrafficLight(StateMachine):
            green = State(initial=True)
            yellow = State()
            red = State()

            cycle = green.to(yellow) | yellow.to(red) | red.to(green)

        sm = TrafficLight()
        assert sm.green.is_active

        sm.send("cycle")
        assert sm.yellow.is_active

        sm.send("cycle")
        assert sm.red.is_active

    def test_final_state_terminates(self):
        class Simple(StateMachine):
            s1 = State(initial=True)
            s2 = State(final=True)

            go = s1.to(s2)

        sm = Simple()
        sm.send("go")
        assert sm.is_terminated


# ---------------------------------------------------------------------------
# TransitionNotAllowed (allow_event_without_transition = False)
# ---------------------------------------------------------------------------


class TestTransitionNotAllowed:
    """StateMachine raises TransitionNotAllowed for invalid events."""

    @pytest.fixture()
    def sm(self):
        class Workflow(StateMachine):
            draft = State(initial=True)
            published = State(final=True)

            publish = draft.to(published)

        return Workflow()

    def test_invalid_event_raises(self, sm):
        with pytest.raises(exceptions.TransitionNotAllowed):
            sm.send("nonexistent")

    def test_event_not_available_in_current_state(self, sm):
        sm.send("publish")
        with pytest.raises(exceptions.TransitionNotAllowed):
            sm.send("publish")

    def test_condition_blocks_transition(self):
        class Gated(StateMachine):
            s1 = State(initial=True)
            s2 = State(final=True)

            go = s1.to(s2, cond="allowed")

            allowed: bool = False

        sm = Gated()
        with pytest.raises(sm.TransitionNotAllowed):
            sm.go()

    def test_multiple_destinations_all_blocked(self):
        def never(event_data):
            return False

        class Multi(StateMachine):
            requested = State(initial=True)
            accepted = State(final=True)
            rejected = State(final=True)

            validate = requested.to(accepted, cond=never) | requested.to(
                rejected, cond="also_never"
            )

            @property
            def also_never(self):
                return False

        sm = Multi()
        with pytest.raises(exceptions.TransitionNotAllowed):
            sm.validate()
        assert sm.requested.is_active

    def test_from_any_with_cond_blocked(self):
        class Account(StateMachine):
            active = State(initial=True)
            closed = State(final=True)

            close = closed.from_.any(cond="can_close")

            can_close: bool = False

        sm = Account()
        with pytest.raises(sm.TransitionNotAllowed):
            sm.close()

    def test_condition_algebra_any_false(self):
        class CondAlgebra(StateMachine):
            start = State(initial=True)
            end = State(final=True)

            submit = start.to(end, cond="used_money or used_credit")

            used_money: bool = False
            used_credit: bool = False

        sm = CondAlgebra()
        with pytest.raises(sm.TransitionNotAllowed):
            sm.submit()


# ---------------------------------------------------------------------------
# TransitionNotAllowed — async
# ---------------------------------------------------------------------------


class TestTransitionNotAllowedAsync:
    """TransitionNotAllowed in async machines."""

    @pytest.fixture()
    def async_sm_cls(self):
        class AsyncWorkflow(StateMachine):
            s1 = State(initial=True)
            s2 = State()
            s3 = State(final=True)

            go = s1.to(s2, cond="is_ready")
            finish = s2.to(s3)

            is_ready: bool = False

            async def on_go(self): ...

        return AsyncWorkflow

    async def test_async_transition_not_allowed(self, async_sm_cls):
        sm = async_sm_cls()
        await sm.activate_initial_state()
        with pytest.raises(sm.TransitionNotAllowed):
            await sm.send("go")

    def test_sync_context_transition_not_allowed(self, async_sm_cls):
        sm = async_sm_cls()
        with pytest.raises(sm.TransitionNotAllowed):
            sm.send("go")

    async def test_async_condition_blocks(self):
        class AsyncCond(StateMachine):
            s1 = State(initial=True)
            s2 = State(final=True)

            go = s1.to(s2, cond="check")

            async def check(self):
                return False

        sm = AsyncCond()
        await sm.activate_initial_state()
        with pytest.raises(sm.TransitionNotAllowed):
            await sm.go()


# ---------------------------------------------------------------------------
# catch_errors_as_events = False (exceptions propagate directly)
# ---------------------------------------------------------------------------


class TestErrorOnExecutionFalse:
    """With catch_errors_as_events=False, exceptions propagate without being caught."""

    def test_runtime_error_in_action_propagates(self):
        class SM(StateMachine):
            s1 = State(initial=True)
            s2 = State(final=True)

            go = s1.to(s2)

            def on_go(self):
                raise RuntimeError("boom")

        sm = SM()
        with pytest.raises(RuntimeError, match="boom"):
            sm.send("go")

    def test_runtime_error_in_after_propagates(self):
        class SM(StateMachine):
            s1 = State(initial=True)
            s2 = State(final=True)

            go = s1.to(s2)

            def after_go(self):
                raise RuntimeError("after boom")

        sm = SM()
        with pytest.raises(RuntimeError, match="after boom"):
            sm.send("go")

    @pytest.mark.timeout(5)
    async def test_async_runtime_error_in_after_propagates(self):
        class SM(StateMachine):
            s1 = State(initial=True)
            s2 = State(final=True)

            go = s1.to(s2)

            async def after_go(self, **kwargs):
                raise RuntimeError("async after boom")

        sm = SM()
        await sm.activate_initial_state()
        with pytest.raises(RuntimeError, match="async after boom"):
            await sm.send("go")


# ---------------------------------------------------------------------------
# enable_self_transition_entries = False
# ---------------------------------------------------------------------------


class TestSelfTransitionNoEntries:
    """With enable_self_transition_entries=False, internal self-transitions do NOT fire entry/exit.

    Note: ``enable_self_transition_entries`` only applies to *internal* self-transitions
    (``internal=True``). External self-transitions always fire entry/exit regardless.
    """

    def test_internal_self_transition_does_not_fire_enter_exit(self):
        log = []

        class SM(StateMachine):
            s1 = State(initial=True)

            loop = s1.to.itself(internal=True)

            def on_enter_s1(self):
                log.append("enter_s1")

            def on_exit_s1(self):
                log.append("exit_s1")

        sm = SM()
        log.clear()  # clear initial enter
        sm.send("loop")
        assert "enter_s1" not in log
        assert "exit_s1" not in log

    def test_external_self_transition_fires_enter_exit(self):
        """External self-transitions always fire, regardless of the flag."""
        log = []

        class SM(StateMachine):
            s1 = State(initial=True)

            loop = s1.to.itself()

            def on_enter_s1(self):
                log.append("enter_s1")

            def on_exit_s1(self):
                log.append("exit_s1")

        sm = SM()
        log.clear()
        sm.send("loop")
        assert "enter_s1" in log
        assert "exit_s1" in log


# ---------------------------------------------------------------------------
# current_state deprecated property
# ---------------------------------------------------------------------------


class TestCurrentStateDeprecated:
    """The current_state property emits DeprecationWarning but still works."""

    def test_current_state_returns_state(self):
        class SM(StateMachine):
            s1 = State(initial=True)
            s2 = State(final=True)

            go = s1.to(s2)

        sm = SM()
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            cs = sm.current_state
        assert cs == sm.s1

    def test_current_state_emits_warning(self):
        class SM(StateMachine):
            s1 = State(initial=True)
            s2 = State(final=True)

            go = s1.to(s2)

        sm = SM()
        with pytest.warns(DeprecationWarning, match="current_state"):
            _ = sm.current_state  # noqa: F841
