"""
Enum campaign machine
=====================

A :ref:`StateMachine` that demonstrates declaring :ref:`States from Enum types` as source for
``States`` definition.

"""

from enum import Enum

from statemachine import StateMachine
from statemachine.states import States


class CampaignStatus(Enum):
    draft = 1
    producing = 2
    closed = 3


class CampaignMachine(StateMachine):
    "A workflow machine"

    states = States.from_enum(
        CampaignStatus, initial=CampaignStatus.draft, final=CampaignStatus.closed
    )

    add_job = states.draft.to(states.draft) | states.producing.to(states.producing)
    produce = states.draft.to(states.producing)
    deliver = states.producing.to(states.closed)


# %%
# Asserting campaign machine declaration

assert CampaignMachine.draft.initial
assert not CampaignMachine.draft.final

assert not CampaignMachine.producing.initial
assert not CampaignMachine.producing.final

assert not CampaignMachine.closed.initial
assert CampaignMachine.closed.final


# %%
# Testing our campaign machine

sm = CampaignMachine()
res = sm.send("produce")

assert sm.draft.is_active is False
assert sm.producing.is_active is True
assert sm.closed.is_active is False
assert sm.current_state == sm.producing
assert sm.current_state_value == CampaignStatus.producing
