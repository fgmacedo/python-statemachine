from unittest import mock

import pytest

from statemachine import State
from statemachine import StateMachine


@pytest.fixture()
def chained_after_sm_class():  # noqa: C901
    class ChainedSM(StateMachine):
        a = State(initial=True)
        b = State()
        c = State(final=True)

        t1 = a.to(b, after="t1") | b.to(c)

        def __init__(self, *args, **kwargs):
            self.spy = mock.Mock(side_effect=lambda x, **kwargs: x)
            super().__init__(*args, **kwargs)

        def before_t1(self, source: State, value: int = 0):
            return self.spy("before_t1", source=source.id, value=value)

        def on_t1(self, source: State, value: int = 0):
            return self.spy("on_t1", source=source.id, value=value)

        def after_t1(self, source: State, value: int = 0):
            return self.spy("after_t1", source=source.id, value=value)

        def on_enter_state(self, state: State, source: State, value: int = 0):
            return self.spy(
                "on_enter_state",
                state=state.id,
                source=getattr(source, "id", None),
                value=value,
            )

        def on_exit_state(self, state: State, source: State, value: int = 0):
            return self.spy("on_exit_state", state=state.id, source=source.id, value=value)

    return ChainedSM


@pytest.fixture()
def chained_on_sm_class():  # noqa: C901
    class ChainedSM(StateMachine):
        s1 = State(initial=True)
        s2 = State()
        s3 = State()
        s4 = State(final=True)

        t1 = s1.to(s2)
        t2a = s2.to(s2)
        t2b = s2.to(s3)
        t3 = s3.to(s4)

        def __init__(self, rtc=True):
            self.spy = mock.Mock()
            super().__init__(rtc=rtc)

        def on_t1(self):
            return [self.t2a(), self.t2b(), self.send("t3")]

        def on_enter_state(self, event: str, state: State, source: State):
            self.spy(
                "on_enter_state",
                event=event,
                state=state.id,
                source=getattr(source, "id", ""),
            )

        def on_exit_state(self, event: str, state: State, target: State):
            self.spy("on_exit_state", event=event, state=state.id, target=target.id)

        def on_transition(self, event: str, source: State, target: State):
            self.spy("on_transition", event=event, source=source.id, target=target.id)
            return event

        def after_transition(self, event: str, source: State, target: State):
            self.spy("after_transition", event=event, source=source.id, target=target.id)

    return ChainedSM


class TestChainedTransition:
    @pytest.mark.parametrize(
        ("rtc", "expected_calls"),
        [
            (
                False,
                [
                    mock.call("on_enter_state", state="a", source=None, value=0),
                    mock.call("before_t1", source="a", value=42),
                    mock.call("on_exit_state", state="a", source="a", value=42),
                    mock.call("on_t1", source="a", value=42),
                    mock.call("on_enter_state", state="b", source="a", value=42),
                    mock.call("before_t1", source="b", value=42),
                    mock.call("on_exit_state", state="b", source="b", value=42),
                    mock.call("on_t1", source="b", value=42),
                    mock.call("on_enter_state", state="c", source="b", value=42),
                    mock.call("after_t1", source="b", value=42),
                    mock.call("after_t1", source="a", value=42),
                ],
            ),
            (
                True,
                [
                    mock.call("on_enter_state", state="a", source=None, value=0),
                    mock.call("before_t1", source="a", value=42),
                    mock.call("on_exit_state", state="a", source="a", value=42),
                    mock.call("on_t1", source="a", value=42),
                    mock.call("on_enter_state", state="b", source="a", value=42),
                    mock.call("after_t1", source="a", value=42),
                    mock.call("before_t1", source="b", value=42),
                    mock.call("on_exit_state", state="b", source="b", value=42),
                    mock.call("on_t1", source="b", value=42),
                    mock.call("on_enter_state", state="c", source="b", value=42),
                    mock.call("after_t1", source="b", value=42),
                ],
            ),
        ],
    )
    def test_should_allow_chaining_transitions_using_actions(
        self, chained_after_sm_class, rtc, expected_calls
    ):
        sm = chained_after_sm_class(rtc=rtc)
        sm.t1(value=42)

        assert sm.c.is_active

        assert sm.spy.call_args_list == expected_calls

    @pytest.mark.parametrize("rtc", [False, True])
    async def test_should_preserve_event_order(self, chained_on_sm_class, rtc):
        sm = chained_on_sm_class(rtc=rtc)

        result = await sm.send("t1")

        assert result == ["t1", [mock.ANY, mock.ANY, mock.ANY]]
        assert sm.spy.call_args_list == [
            mock.call("on_enter_state", event="__initial__", state="s1", source=""),
            mock.call("on_exit_state", event="t1", state="s1", target="s2"),
            mock.call("on_transition", event="t1", source="s1", target="s2"),
            mock.call("on_enter_state", event="t1", state="s2", source="s1"),
            mock.call("after_transition", event="t1", source="s1", target="s2"),
            mock.call("on_exit_state", event="t2a", state="s2", target="s2"),
            mock.call("on_transition", event="t2a", source="s2", target="s2"),
            mock.call("on_enter_state", event="t2a", state="s2", source="s2"),
            mock.call("after_transition", event="t2a", source="s2", target="s2"),
            mock.call("on_exit_state", event="t2b", state="s2", target="s3"),
            mock.call("on_transition", event="t2b", source="s2", target="s3"),
            mock.call("on_enter_state", event="t2b", state="s3", source="s2"),
            mock.call("after_transition", event="t2b", source="s2", target="s3"),
            mock.call("on_exit_state", event="t3", state="s3", target="s4"),
            mock.call("on_transition", event="t3", source="s3", target="s4"),
            mock.call("on_enter_state", event="t3", state="s4", source="s3"),
            mock.call("after_transition", event="t3", source="s3", target="s4"),
        ]
