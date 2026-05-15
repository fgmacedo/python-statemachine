from statemachine import State
from statemachine import StateChart


class CampaignMachineWithValues(StateChart):
    "A workflow machine"

    draft = State(initial=True, value=1)
    producing = State("Being produced", value=2)
    closed = State(value=3, final=True)

    add_job = draft.to(draft) | producing.to(producing)
    produce = draft.to(producing)
    deliver = producing.to(closed)
