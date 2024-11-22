import pickle
from enum import Enum
from enum import auto

from statemachine import StateMachine
from statemachine.states import States


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


class TestPickleSerialization:
    def test_pickle(self):
        sm = GameStateMachine()
        sm.play()
        assert sm.current_state == GameStateMachine.GAME_PLAYING

        serialized = pickle.dumps(sm)
        sm2 = pickle.loads(serialized)
        assert sm2.current_state == GameStateMachine.GAME_PLAYING
