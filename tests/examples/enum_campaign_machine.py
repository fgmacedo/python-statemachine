"""
Enum campaign machine
=====================

A StateMachine that demonstrates using an Enum as source for `States` declaration.

.. note::

    Given that you assign the response of ``States.from_enum`` to a class level
    variable on your ``StateMachine`` you're good to go, you can use any name.
    The variable will be inspected by the metaclass and the ``State`` instances
    assigned to the state machine.

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

    _ = States.from_enum(
        CampaignStatus, initial=CampaignStatus.draft, final=CampaignStatus.closed
    )

    add_job = _.draft.to(_.draft) | _.producing.to(_.producing)
    produce = _.draft.to(_.producing)
    deliver = _.producing.to(_.closed)


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
assert sm.current_state_value == CampaignStatus.producing.value
