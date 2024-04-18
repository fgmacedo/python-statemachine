from copy import deepcopy

import pytest

from statemachine import State
from statemachine import StateMachine
from statemachine.exceptions import TransitionNotAllowed


class MySM(StateMachine):
    draft = State("Draft", initial=True, value="draft")
    published = State("Published", value="published")

    publish = draft.to(published, cond="let_me_be_visible")


class MyModel:
    def __init__(self, name: str) -> None:
        self.name = name
        self.let_me_be_visible = False

    def __repr__(self) -> str:
        return f"{type(self).__name__}@{id(self)}({self.name!r})"


def test_deepcopy():
    sm = MySM(MyModel("main_model"))

    sm2 = deepcopy(sm)

    with pytest.raises(TransitionNotAllowed):
        sm2.send("publish")


def test_deepcopy_with_observers():
    model1 = MyModel("main_model")

    sm1 = MySM(model1)

    observer_1 = MyModel("observer_1")
    observer_2 = MyModel("observer_2")
    sm1.add_observer(observer_1)
    sm1.add_observer(observer_2)

    sm2 = deepcopy(sm1)

    assert sm1.model is not sm2.model

    def assertions(sm):
        if not sm._observers:
            pytest.fail("did not found any observer")

        for observer in sm._observers:
            observer.let_me_be_visible = False

        with pytest.raises(TransitionNotAllowed):
            sm.send("publish")

        sm.model.let_me_be_visible = True

        with pytest.raises(TransitionNotAllowed):
            sm.send("publish")

        for observer in sm._observers:
            observer.let_me_be_visible = True

        sm.send("publish")

    assertions(sm1)
    assertions(sm2)
