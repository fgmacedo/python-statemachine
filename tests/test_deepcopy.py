import logging
from copy import deepcopy

import pytest

from statemachine import State
from statemachine import StateMachine
from statemachine.exceptions import TransitionNotAllowed

logger = logging.getLogger(__name__)
DEBUG = logging.DEBUG


class MySM(StateMachine):
    draft = State("Draft", initial=True, value="draft")
    published = State("Published", value="published", final=True)

    publish = draft.to(published, cond="let_me_be_visible")

    def on_transition(self, event: str):
        logger.debug(f"{self.__class__.__name__} recorded {event} transition")

    def let_me_be_visible(self):
        logger.debug(f"{type(self).__name__} let_me_be_visible: True")
        return True


class MyModel:
    def __init__(self, name: str) -> None:
        self.name = name
        self.let_me_be_visible = False

    def __repr__(self) -> str:
        return f"{type(self).__name__}@{id(self)}({self.name!r})"

    def on_transition(self, event: str):
        logger.debug(f"{type(self).__name__}({self.name!r}) recorded {event} transition")

    @property
    def let_me_be_visible(self):
        logger.debug(
            f"{type(self).__name__}({self.name!r}) let_me_be_visible: {self._let_me_be_visible}"
        )
        return self._let_me_be_visible

    @let_me_be_visible.setter
    def let_me_be_visible(self, value):
        self._let_me_be_visible = value


def test_deepcopy():
    sm = MySM(MyModel("main_model"))

    sm2 = deepcopy(sm)

    with pytest.raises(TransitionNotAllowed):
        sm2.send("publish")


def test_deepcopy_with_observers(caplog):
    model1 = MyModel("main_model")

    sm1 = MySM(model1)

    observer_1 = MyModel("observer_1")
    observer_2 = MyModel("observer_2")
    sm1.add_observer(observer_1)
    sm1.add_observer(observer_2)

    sm2 = deepcopy(sm1)

    assert sm1.model is not sm2.model

    caplog.set_level(logging.DEBUG)

    def assertions(sm, _reference):
        caplog.clear()
        if not sm._observers:
            pytest.fail("did not found any observer")

        for observer in sm._observers:
            observer.let_me_be_visible = False

        with pytest.raises(TransitionNotAllowed):
            sm.send("publish")

        sm.model.let_me_be_visible = True

        for observer in sm._observers:
            with pytest.raises(TransitionNotAllowed):
                sm.send("publish")

            observer.let_me_be_visible = True

        sm.send("publish")

        assert caplog.record_tuples == [
            ("tests.test_deepcopy", DEBUG, "MySM let_me_be_visible: True"),
            ("tests.test_deepcopy", DEBUG, "MyModel('main_model') let_me_be_visible: False"),
            ("tests.test_deepcopy", DEBUG, "MySM let_me_be_visible: True"),
            ("tests.test_deepcopy", DEBUG, "MyModel('main_model') let_me_be_visible: True"),
            ("tests.test_deepcopy", DEBUG, "MyModel('observer_1') let_me_be_visible: False"),
            ("tests.test_deepcopy", DEBUG, "MySM let_me_be_visible: True"),
            ("tests.test_deepcopy", DEBUG, "MyModel('main_model') let_me_be_visible: True"),
            ("tests.test_deepcopy", DEBUG, "MyModel('observer_1') let_me_be_visible: True"),
            ("tests.test_deepcopy", DEBUG, "MyModel('observer_2') let_me_be_visible: False"),
            ("tests.test_deepcopy", DEBUG, "MySM let_me_be_visible: True"),
            ("tests.test_deepcopy", DEBUG, "MyModel('main_model') let_me_be_visible: True"),
            ("tests.test_deepcopy", DEBUG, "MyModel('observer_1') let_me_be_visible: True"),
            ("tests.test_deepcopy", DEBUG, "MyModel('observer_2') let_me_be_visible: True"),
            ("tests.test_deepcopy", DEBUG, "MySM recorded publish transition"),
            ("tests.test_deepcopy", DEBUG, "MyModel('main_model') recorded publish transition"),
            ("tests.test_deepcopy", DEBUG, "MyModel('observer_1') recorded publish transition"),
            ("tests.test_deepcopy", DEBUG, "MyModel('observer_2') recorded publish transition"),
        ]

    assertions(sm1, "original")
    assertions(sm2, "copy")
