import logging
import pickle
from copy import deepcopy
from enum import Enum
from enum import auto

import pytest

from statemachine import State
from statemachine import StateMachine
from statemachine.exceptions import TransitionNotAllowed
from statemachine.states import States

logger = logging.getLogger(__name__)
DEBUG = logging.DEBUG


def copy_pickle(obj):
    return pickle.loads(pickle.dumps(obj))


@pytest.fixture(params=[deepcopy, copy_pickle], ids=["deepcopy", "pickle"])
def copy_method(request):
    return request.param


class GameStates(str, Enum):
    GAME_START = auto()
    GAME_PLAYING = auto()
    TURN_END = auto()
    GAME_END = auto()


class GameStateMachine(StateMachine):
    s = States.from_enum(GameStates, initial=GameStates.GAME_START)

    play = s.GAME_START.to(s.GAME_PLAYING)
    stop = s.GAME_PLAYING.to(s.TURN_END)
    end_game = s.TURN_END.to(s.GAME_END)

    @end_game.cond
    def game_is_over(self) -> bool:
        return True

    advance_round = end_game | s.TURN_END.to(s.GAME_END)


class MyStateMachine(StateMachine):
    created = State(initial=True)
    started = State()

    start = created.to(started)

    def __init__(self):
        super().__init__()
        self.custom = 1
        self.value = [1, 2, 3]


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


def test_copy(copy_method):
    sm = MySM(MyModel("main_model"))

    sm2 = copy_method(sm)

    with pytest.raises(TransitionNotAllowed):
        sm2.send("publish")


def test_copy_with_listeners(caplog, copy_method):
    model1 = MyModel("main_model")

    sm1 = MySM(model1)

    listener_1 = MyModel("observer_1")
    listener_2 = MyModel("observer_2")
    sm1.add_listener(listener_1)
    sm1.add_listener(listener_2)

    sm2 = copy_method(sm1)

    assert sm1.model is not sm2.model

    caplog.set_level(logging.DEBUG, logger="tests")

    def assertions(sm, _reference):
        caplog.clear()
        if not sm._listeners:
            pytest.fail("did not found any observer")

        for listener in sm._listeners:
            listener.let_me_be_visible = False

        with pytest.raises(TransitionNotAllowed):
            sm.send("publish")

        sm.model.let_me_be_visible = True

        for listener in sm._listeners:
            with pytest.raises(TransitionNotAllowed):
                sm.send("publish")

            listener.let_me_be_visible = True

        sm.send("publish")

        assert caplog.record_tuples == [
            ("tests.test_copy", DEBUG, "MySM let_me_be_visible: True"),
            ("tests.test_copy", DEBUG, "MyModel('main_model') let_me_be_visible: False"),
            ("tests.test_copy", DEBUG, "MySM let_me_be_visible: True"),
            ("tests.test_copy", DEBUG, "MyModel('main_model') let_me_be_visible: True"),
            ("tests.test_copy", DEBUG, "MyModel('observer_1') let_me_be_visible: False"),
            ("tests.test_copy", DEBUG, "MySM let_me_be_visible: True"),
            ("tests.test_copy", DEBUG, "MyModel('main_model') let_me_be_visible: True"),
            ("tests.test_copy", DEBUG, "MyModel('observer_1') let_me_be_visible: True"),
            ("tests.test_copy", DEBUG, "MyModel('observer_2') let_me_be_visible: False"),
            ("tests.test_copy", DEBUG, "MySM let_me_be_visible: True"),
            ("tests.test_copy", DEBUG, "MyModel('main_model') let_me_be_visible: True"),
            ("tests.test_copy", DEBUG, "MyModel('observer_1') let_me_be_visible: True"),
            ("tests.test_copy", DEBUG, "MyModel('observer_2') let_me_be_visible: True"),
            ("tests.test_copy", DEBUG, "MySM recorded publish transition"),
            ("tests.test_copy", DEBUG, "MyModel('main_model') recorded publish transition"),
            ("tests.test_copy", DEBUG, "MyModel('observer_1') recorded publish transition"),
            ("tests.test_copy", DEBUG, "MyModel('observer_2') recorded publish transition"),
        ]

    assertions(sm1, "original")
    assertions(sm2, "copy")


def test_copy_with_enum(copy_method):
    sm = GameStateMachine()
    sm.play()
    assert sm.current_state == GameStateMachine.GAME_PLAYING

    sm2 = copy_method(sm)
    assert sm2.current_state == GameStateMachine.GAME_PLAYING


def test_copy_with_custom_init_and_vars(copy_method):
    sm = MyStateMachine()
    sm.start()

    sm2 = copy_method(sm)
    assert sm2.custom == 1
    assert sm2.value == [1, 2, 3]
    assert sm2.current_state == MyStateMachine.started
