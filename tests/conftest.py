import sys
from datetime import datetime
from typing import List

import pytest

collect_ignore_glob: List[str] = []

# We support Python 3.8+ positional only syntax
if sys.version_info[:2] < (3, 8):  # noqa: UP036
    collect_ignore_glob.append("*_positional_only.py")


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

        def _get_engine(self, rtc: bool):
            return engine(self, rtc)

    return TrafficLightMachine


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
