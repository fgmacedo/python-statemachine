"""
Enum campaign machine
=====================

A :ref:`StateChart` that demonstrates declaring :ref:`States from Enum types` as source for
``States`` definition.

"""

from enum import Enum

from statemachine.states import States

from statemachine import StateChart


class CampaignStatus(Enum):
    DRAFT = 1
    PRODUCING = 2
    CLOSED = 3


class CampaignMachine(StateChart):
    "A workflow machine"

    states = States.from_enum(
        CampaignStatus,
        initial=CampaignStatus.DRAFT,
        final=CampaignStatus.CLOSED,
    )

    add_job = states.DRAFT.to(states.DRAFT) | states.PRODUCING.to(states.PRODUCING)
    produce = states.DRAFT.to(states.PRODUCING)
    deliver = states.PRODUCING.to(states.CLOSED)


# %%
# Asserting campaign machine declaration

assert CampaignMachine.states.DRAFT.initial
assert not CampaignMachine.states.DRAFT.final

assert not CampaignMachine.states.PRODUCING.initial
assert not CampaignMachine.states.PRODUCING.final

assert not CampaignMachine.states.CLOSED.initial
assert CampaignMachine.states.CLOSED.final


# %%
# Testing our campaign machine

sm = CampaignMachine()
res = sm.send("produce")

assert CampaignStatus.DRAFT not in sm.configuration_values
assert CampaignStatus.PRODUCING in sm.configuration_values
assert CampaignStatus.CLOSED not in sm.configuration_values
assert CampaignStatus.PRODUCING in sm.configuration_values
