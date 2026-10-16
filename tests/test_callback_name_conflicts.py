"""A method name bound both by an event convention and by a state convention (refs #587)."""

import copy
import pickle
import warnings

import pytest
from statemachine.event import Event
from statemachine.exceptions import InvalidDefinition

from statemachine import State
from statemachine import StateChart


def build_init_collision(**attrs):
    class Chart(StateChart):
        a = State(initial=True)

        class x(State.Compound):
            x1 = State()
            done = State(final=True)
            finish = x1.to(done)

        init_x = a.to(x)
        vars().update(attrs)

    return Chart


def on_init_x(self):
    pass


class TestInitConvention:
    def test_method_on_the_class_is_rejected(self):
        with pytest.raises(InvalidDefinition, match="on_init_x"):
            build_init_collision(on_init_x=on_init_x)

    def test_event_with_explicit_id_is_rejected(self):
        with pytest.raises(InvalidDefinition, match="on_init_x"):

            class Chart(StateChart):
                a = State(initial=True)

                class x(State.Compound):
                    x1 = State()
                    done = State(final=True)
                    finish = x1.to(done)

                start = Event(a.to(x), id="init_x")

                def on_init_x(self):
                    pass

    def test_without_the_method_the_class_is_accepted(self):
        sm = build_init_collision()()

        sm.send("init_x")

        assert "x1" in sm.configuration_values

    def test_listener_is_rejected_on_construction(self):
        class Listener:
            def on_init_x(self):
                pass

        with pytest.raises(InvalidDefinition, match="on_init_x"):
            build_init_collision()(listeners=[Listener()])

    def test_listener_is_rejected_on_add_listener(self):
        class Listener:
            def on_init_x(self):
                pass

        sm = build_init_collision()()

        with pytest.raises(InvalidDefinition, match="on_init_x"):
            sm.add_listener(Listener())

    def test_model_is_rejected(self):
        class Model:
            state = None

            def on_init_x(self):
                pass

        with pytest.raises(InvalidDefinition, match="on_init_x"):
            build_init_collision()(model=Model())

    def test_opt_out_binds_the_method_to_both(self):
        calls = []

        Chart = build_init_collision(
            validate_callback_name_conflicts=False,
            on_init_x=lambda self, event: calls.append(str(event)),
        )
        sm = Chart()

        sm.send("init_x")

        assert calls == ["init_x", "init_x"]

    def test_opt_out_accepts_listeners(self):
        class Listener:
            def on_init_x(self):
                pass

        Chart = build_init_collision(validate_callback_name_conflicts=False)

        Chart(listeners=[Listener()]).add_listener(Listener())


def build_state_collision(prefix, **attrs):
    class Chart(StateChart):
        a = State(initial=True)
        x = State()
        back = x.to(a)
        vars()[f"{prefix}_x"] = a.to(x)
        vars().update(attrs)

    return Chart


@pytest.mark.parametrize("prefix", ["enter", "exit", "invoke"])
class TestExistingStateConventions:
    def test_method_on_the_class_is_deprecated(self, prefix):
        with pytest.warns(DeprecationWarning, match=f"on_{prefix}_x"):
            build_state_collision(prefix, **{f"on_{prefix}_x": lambda self: None})

    def test_listener_is_deprecated(self, prefix):
        Listener = type("Listener", (), {f"on_{prefix}_x": lambda self: None})
        Chart = build_state_collision(prefix)

        with pytest.warns(DeprecationWarning, match=f"on_{prefix}_x"):
            Chart(listeners=[Listener()])

    def test_class_is_warned_once_not_per_instance(self, prefix):
        with pytest.warns(DeprecationWarning, match=f"on_{prefix}_x"):
            Chart = build_state_collision(prefix, **{f"on_{prefix}_x": lambda self: None})

        with warnings.catch_warnings():
            warnings.simplefilter("error")
            Chart()
            Chart()

    def test_opt_out_is_silent(self, prefix):
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            build_state_collision(
                prefix,
                validate_callback_name_conflicts=False,
                **{f"on_{prefix}_x": lambda self: None},
            )()


class TestNestedStateBody:
    def test_init_method_in_the_compound_body_is_rejected(self):
        with pytest.raises(InvalidDefinition, match="on_init_x"):

            class Chart(StateChart):
                a = State(initial=True)

                class x(State.Compound):
                    x1 = State()
                    done = State(final=True)
                    finish = x1.to(done)

                    def on_init_x(self):
                        pass

                init_x = a.to(x)

    def test_enter_method_in_the_compound_body_is_deprecated(self):
        with pytest.warns(DeprecationWarning, match="on_enter_x1"):

            class Chart(StateChart):
                a = State(initial=True)

                class x(State.Compound):
                    x1 = State()
                    done = State(final=True)
                    finish = x1.to(done)

                    def on_enter_x1(self):
                        pass

                enter_x1 = a.to(x.x1)


class EnterListener:
    def on_enter_x(self):
        pass


class RestorableChart(StateChart):
    a = State(initial=True)
    x = State()
    back = x.to(a)
    enter_x = a.to(x)


class TestRestoredMachine:
    @pytest.mark.parametrize("restore", [copy.deepcopy, lambda sm: pickle.loads(pickle.dumps(sm))])
    def test_is_not_warned_again(self, restore):
        with pytest.warns(DeprecationWarning, match="on_enter_x"):
            sm = RestorableChart(listeners=[EnterListener()])

        with warnings.catch_warnings():
            warnings.simplefilter("error")
            restored = restore(sm)

        assert [type(listener) for listener in restored.active_listeners] == [EnterListener]


class TestRejectedListener:
    def test_is_not_attached(self):
        class Listener:
            def on_init_x(self):
                pass

        sm = build_init_collision()()

        with pytest.raises(InvalidDefinition):
            sm.add_listener(Listener())

        assert sm.active_listeners == []
