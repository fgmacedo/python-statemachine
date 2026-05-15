from statemachine import State
from statemachine import StateChart


class CampaignMachineWithValidator(StateChart):
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
