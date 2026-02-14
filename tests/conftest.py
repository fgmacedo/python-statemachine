from datetime import datetime

import pytest


def pytest_addoption(parser):
    parser.addoption(
        "--upd-fail",
        action="store_true",
        default=False,
        help="Update marks for failing tests",
    )
    parser.addoption(
        "--gen-diagram",
        action="store_true",
        default=False,
        help="Generate a diagram of the SCXML machine",
    )


@pytest.fixture()
def current_time():
    return datetime.now()


@pytest.fixture()
def campaign_machine():
    "Define a new class for each test"
    from statemachine import State
    from statemachine import StateMachine

    class CampaignMachine(StateMachine):
        "A workflow machine"

        draft = State(initial=True)
        producing = State("Being produced")
        closed = State(final=True)

        add_job = draft.to(draft) | producing.to(producing)
        produce = draft.to(producing)
        deliver = producing.to(closed)

    return CampaignMachine


@pytest.fixture()
def campaign_machine_with_validator():
    "Define a new class for each test"
    from statemachine import State
    from statemachine import StateMachine

    class CampaignMachine(StateMachine):
        "A workflow machine"

        draft = State(initial=True)
        producing = State("Being produced")
        closed = State(final=True)

        add_job = draft.to(draft) | producing.to(producing)
        produce = draft.to(producing, validators="can_produce")
        deliver = producing.to(closed)

        def can_produce(*args, **kwargs):
            if "goods" not in kwargs:
                raise LookupError("Goods not found.")

    return CampaignMachine


@pytest.fixture()
def campaign_machine_with_final_state():
    "Define a new class for each test"
    from statemachine import State
    from statemachine import StateMachine

    class CampaignMachine(StateMachine):
        "A workflow machine"

        draft = State(initial=True)
        producing = State("Being produced")
        closed = State(final=True)

        add_job = draft.to(draft) | producing.to(producing)
        produce = draft.to(producing)
        deliver = producing.to(closed)

    return CampaignMachine


@pytest.fixture()
def campaign_machine_with_values():
    "Define a new class for each test"
    from statemachine import State
    from statemachine import StateMachine

    class CampaignMachineWithKeys(StateMachine):
        "A workflow machine"

        draft = State(initial=True, value=1)
        producing = State("Being produced", value=2)
        closed = State(value=3, final=True)

        add_job = draft.to(draft) | producing.to(producing)
        produce = draft.to(producing)
        deliver = producing.to(closed)

    return CampaignMachineWithKeys


@pytest.fixture()
def traffic_light_machine():
    from tests.examples.traffic_light_machine import TrafficLightMachine

    return TrafficLightMachine


@pytest.fixture()
def OrderControl():
    from tests.examples.order_control_machine import OrderControl

    return OrderControl


@pytest.fixture()
def AllActionsMachine():
    from tests.examples.all_actions_machine import AllActionsMachine

    return AllActionsMachine


@pytest.fixture()
def classic_traffic_light_machine(engine):
    from statemachine import State
    from statemachine import StateMachine

    class TrafficLightMachine(StateMachine):
        green = State(initial=True)
        yellow = State()
        red = State()

        slowdown = green.to(yellow)
        stop = yellow.to(red)
        go = red.to(green)

        def _get_engine(self):
            return engine(self)

    return TrafficLightMachine


@pytest.fixture()
def classic_traffic_light_machine_allow_event(classic_traffic_light_machine):
    class TrafficLightMachineAllowingEventWithoutTransition(classic_traffic_light_machine):
        allow_event_without_transition = True

    return TrafficLightMachineAllowingEventWithoutTransition


@pytest.fixture()
def reverse_traffic_light_machine():
    from statemachine import State
    from statemachine import StateMachine

    class ReverseTrafficLightMachine(StateMachine):
        "A traffic light machine"

        green = State(initial=True)
        yellow = State()
        red = State()

        stop = red.from_(yellow, green, red)
        cycle = green.from_(red) | yellow.from_(green) | red.from_(yellow) | red.from_.itself()

    return ReverseTrafficLightMachine


@pytest.fixture()
def approval_machine(current_time):  # noqa: C901
    from statemachine import State
    from statemachine import StateMachine

    class ApprovalMachine(StateMachine):
        "A workflow machine"

        requested = State(initial=True)
        accepted = State()
        rejected = State()

        completed = State(final=True)

        validate = requested.to(accepted, cond="is_ok") | requested.to(rejected)

        @validate
        def do_validate(self, *args, **kwargs):
            if self.model.is_ok():
                self.model.accepted_at = current_time
                return self.model
            else:
                self.model.rejected_at = current_time
                return self.model

        @accepted.to(completed)
        def complete(self):
            self.model.completed_at = current_time

        @requested.to(requested)
        def update(self, **kwargs):
            for k, v in kwargs.items():
                setattr(self.model, k, v)
            return self.model

        @rejected.to(requested)
        def retry(self):
            self.model.rejected_at = None
            return self.model

    return ApprovalMachine


@pytest.fixture(params=["sync", "async"])
def engine(request):
    from statemachine.engines.async_ import AsyncEngine
    from statemachine.engines.sync import SyncEngine

    if request.param == "sync":
        return SyncEngine
    else:
        return AsyncEngine


class _AsyncListener:
    """No-op async listener that triggers AsyncEngine selection."""

    async def on_enter_state(
        self, **kwargs
    ): ...  # No-op: presence of async callback triggers AsyncEngine selection


class SMRunner:
    """Helper for running state machine tests on both sync and async engines.

    Usage in tests::

        async def test_something(self, sm_runner):
            sm = await sm_runner.start(MyStateChart)
            await sm_runner.send(sm, "some_event")
            assert "expected_state" in sm.configuration_values
    """

    def __init__(self, is_async: bool):
        self.is_async = is_async

    async def start(self, cls, **kwargs):
        """Create and activate a state machine instance."""
        from inspect import isawaitable

        if self.is_async:
            listeners = list(kwargs.pop("listeners", []))
            listeners.append(_AsyncListener())
            sm = cls(listeners=listeners, **kwargs)
            result = sm.activate_initial_state()
            if isawaitable(result):
                await result
        else:
            sm = cls(**kwargs)
        return sm

    async def send(self, sm, event, **kwargs):
        """Send an event to the state machine."""
        from inspect import isawaitable

        result = sm.send(event, **kwargs)
        if isawaitable(result):
            return await result
        return result

    async def processing_loop(self, sm):
        """Run the processing loop (for delayed event tests)."""
        from inspect import isawaitable

        result = sm._processing_loop()
        if isawaitable(result):
            return await result
        return result


@pytest.fixture(params=["sync", "async"])
def sm_runner(request):
    """Fixture that runs tests on both sync and async engines."""
    return SMRunner(is_async=request.param == "async")
