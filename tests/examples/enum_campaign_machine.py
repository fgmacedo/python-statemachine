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
        use_enum_instance=True,
    )

    add_job = states.DRAFT.to(states.DRAFT) | states.PRODUCING.to(states.PRODUCING)
    produce = states.DRAFT.to(states.PRODUCING)
    deliver = states.PRODUCING.to(states.CLOSED)


# %%
# Asserting campaign machine declaration

assert CampaignMachine.DRAFT.initial
assert not CampaignMachine.DRAFT.final

assert not CampaignMachine.PRODUCING.initial
assert not CampaignMachine.PRODUCING.final

assert not CampaignMachine.CLOSED.initial
assert CampaignMachine.CLOSED.final


# %%
# Testing our campaign machine

sm = CampaignMachine()
res = sm.send("produce")

assert sm.DRAFT.is_active is False
assert sm.PRODUCING.is_active is True
assert sm.CLOSED.is_active is False
assert sm.PRODUCING in sm.configuration
assert CampaignStatus.PRODUCING in sm.configuration_values
