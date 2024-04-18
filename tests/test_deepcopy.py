from copy import deepcopy

import pytest

from statemachine import State
from statemachine import StateMachine
from statemachine.exceptions import TransitionNotAllowed


def test_deepcopy():
    class MySM(StateMachine):
        draft = State("Draft", initial=True, value="draft")
        published = State("Published", value="published")

        publish = draft.to(published, cond="let_me_be_visible")

    class MyModel:
        let_me_be_visible = False

    sm = MySM(MyModel())

    sm2 = deepcopy(sm)

    with pytest.raises(TransitionNotAllowed):
        sm2.send("publish")
