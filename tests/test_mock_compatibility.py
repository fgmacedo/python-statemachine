from statemachine import State
from statemachine import StateMachine


def test_minimal(mocker):
    class Observer:
        def on_enter_state(self, event, model, source, target, state): ...

    obs = Observer()
    on_enter_state = mocker.spy(obs, "on_enter_state")

    class Machine(StateMachine):
        a = State("Init", initial=True)
        b = State("Fin")

        cycle = a.to(b) | b.to(a)

    state = Machine().add_listener(obs)
    assert state.a.is_active

    state.cycle()

    assert state.b.is_active
    on_enter_state.assert_called_once()
