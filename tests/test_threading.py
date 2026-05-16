import threading
import time
from collections import Counter

import pytest
from statemachine.state import State
from statemachine.statemachine import StateChart


def test_machine_should_allow_multi_thread_event_changes():
    """
    Test for https://github.com/fgmacedo/python-statemachine/issues/443
    """

    class CampaignMachine(StateChart):
        "A workflow machine"

        draft = State(initial=True)
        producing = State()
        closed = State(final=True)
        add_job = draft.to(producing) | producing.to(closed)

    machine = CampaignMachine()

    def off_thread_change_state():
        time.sleep(0.01)
        machine.add_job()

    thread = threading.Thread(target=off_thread_change_state)
    thread.start()
    thread.join()
    assert machine.current_state_value == "producing"


def test_regression_443():
    """
    Test for https://github.com/fgmacedo/python-statemachine/issues/443
    """
    total_iterations = 4
    send_at_iteration = 3  # 0-indexed: send before the 4th sample

    class TrafficLightMachine(StateChart):
        "A traffic light machine"

        green = State(initial=True)
        yellow = State()
        red = State()

        cycle = green.to(yellow) | yellow.to(red) | red.to(green)

    class Controller:
        def __init__(self):
            self.statuses_history = []
            self.fsm = TrafficLightMachine()
            # set up thread
            self.thread = threading.Thread(target=self.recv_cmds)
            self.thread.start()

        def recv_cmds(self):
            """Pretend we receive a command triggering a state change."""
            for i in range(total_iterations):
                if i == send_at_iteration:
                    self.fsm.cycle()
                self.statuses_history.append(self.fsm.current_state_value)

    c1 = Controller()
    c2 = Controller()
    c1.thread.join()
    c2.thread.join()
    assert c1.statuses_history == ["green", "green", "green", "yellow"]
    assert c2.statuses_history == ["green", "green", "green", "yellow"]


def test_regression_443_with_modifications():
    """
    Test for https://github.com/fgmacedo/python-statemachine/issues/443
    """
    total_iterations = 4
    send_at_iteration = 3  # 0-indexed: send before the 4th sample

    class TrafficLightMachine(StateChart):
        "A traffic light machine"

        green = State(initial=True)
        yellow = State()
        red = State()

        cycle = green.to(yellow) | yellow.to(red) | red.to(green)

        def __init__(self, name):
            self.name = name
            self.statuses_history = []
            super().__init__()

        def beat(self):
            for i in range(total_iterations):
                if i == send_at_iteration:
                    self.cycle()
                self.statuses_history.append(f"{self.name}.{self.current_state_value}")

    class Controller:
        def __init__(self, name):
            self.fsm = TrafficLightMachine(name)
            # set up thread
            self.thread = threading.Thread(target=self.fsm.beat)
            self.thread.start()

    c1 = Controller("c1")
    c2 = Controller("c2")
    c3 = Controller("c3")
    c1.thread.join()
    c2.thread.join()
    c3.thread.join()

    assert c1.fsm.statuses_history == ["c1.green", "c1.green", "c1.green", "c1.yellow"]
    assert c2.fsm.statuses_history == ["c2.green", "c2.green", "c2.green", "c2.yellow"]
    assert c3.fsm.statuses_history == ["c3.green", "c3.green", "c3.green", "c3.yellow"]


class TestThreadSafety:
    """Stress tests for concurrent access to a single state machine instance.

    These tests exercise real contention: multiple threads sending events to the
    same SM simultaneously, synchronized via barriers to maximize overlap.
    """

    @pytest.fixture()
    def cycling_machine(self):
        class CyclingMachine(StateChart):
            s1 = State(initial=True)
            s2 = State()
            s3 = State()
            cycle = s1.to(s2) | s2.to(s3) | s3.to(s1)

        return CyclingMachine()

    @pytest.fixture()
    def parallel_machine(self):
        class TwoRegions(StateChart):
            class both(State.Parallel):
                class left(State.Compound):
                    l1 = State(initial=True)
                    l2 = State()
                    tick_l = l1.to(l2) | l2.to(l1)

                class right(State.Compound):
                    r1 = State(initial=True)
                    r2 = State()
                    tick_r = r1.to(r2) | r2.to(r1)

        return TwoRegions()

    @pytest.mark.parametrize("num_threads", [4, 8])
    def test_concurrent_sends_no_lost_events(self, cycling_machine, num_threads):
        """All events sent concurrently must be processed — none lost."""
        events_per_thread = 300
        total_events = num_threads * events_per_thread
        barrier = threading.Barrier(num_threads)
        errors = []

        def sender():
            try:
                barrier.wait(timeout=5)
                for _ in range(events_per_thread):
                    cycling_machine.send("cycle")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=sender) for _ in range(num_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        assert not errors, f"Thread errors: {errors}"

        # The machine cycles s1→s2→s3→s1. After N total cycle events starting
        # from s1, the state is determined by (N % 3).
        expected_states = {0: "s1", 1: "s2", 2: "s3"}
        expected = expected_states[total_events % 3]
        assert cycling_machine.current_state_value == expected

    def test_concurrent_sends_state_consistency(self, cycling_machine):
        """State must always be one of the valid states, never corrupted."""
        valid_values = {"s1", "s2", "s3"}
        num_threads = 6
        events_per_thread = 500
        barrier = threading.Barrier(num_threads + 1)  # +1 for observer
        stop_event = threading.Event()
        observed_values = []
        errors = []

        def sender():
            try:
                barrier.wait(timeout=5)
                for _ in range(events_per_thread):
                    cycling_machine.send("cycle")
            except Exception as e:
                errors.append(e)

        def observer():
            barrier.wait(timeout=5)
            while not stop_event.is_set():
                val = cycling_machine.current_state_value
                observed_values.append(val)

        threads = [threading.Thread(target=sender) for _ in range(num_threads)]
        obs_thread = threading.Thread(target=observer)

        for t in threads:
            t.start()
        obs_thread.start()

        for t in threads:
            t.join(timeout=30)

        stop_event.set()
        obs_thread.join(timeout=5)

        assert not errors, f"Thread errors: {errors}"
        # None may appear transiently during configuration updates — that's expected.
        invalid = [v for v in observed_values if v not in valid_values and v is not None]
        assert not invalid, f"Observed invalid state values: {set(invalid)}"
        assert len(observed_values) > 100, "Observer didn't collect enough samples"

    def test_concurrent_sends_with_callbacks(self):
        """Callbacks must execute exactly once per transition under contention."""
        call_log = []
        lock = threading.Lock()

        class CallbackMachine(StateChart):
            s1 = State(initial=True)
            s2 = State()
            go = s1.to(s2) | s2.to(s1)

            def on_enter_s2(self):
                with lock:
                    call_log.append("enter_s2")

            def on_enter_s1(self):
                with lock:
                    call_log.append("enter_s1")

        sm = CallbackMachine()
        num_threads = 4
        events_per_thread = 200
        total_events = num_threads * events_per_thread
        barrier = threading.Barrier(num_threads)
        errors = []

        def sender():
            try:
                barrier.wait(timeout=5)
                for _ in range(events_per_thread):
                    sm.send("go")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=sender) for _ in range(num_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        assert not errors, f"Thread errors: {errors}"

        # Each transition fires exactly one on_enter callback.
        # +1 because initial activation also fires on_enter_s1.
        counts = Counter(call_log)
        total_callbacks = counts["enter_s1"] + counts["enter_s2"]
        assert total_callbacks == total_events + 1

    def test_concurrent_send_and_read_configuration(self, cycling_machine):
        """Reading configuration while events are being processed must not raise."""
        num_senders = 4
        events_per_sender = 300
        barrier = threading.Barrier(num_senders + 1)
        stop_event = threading.Event()
        errors = []

        def sender():
            try:
                barrier.wait(timeout=5)
                for _ in range(events_per_sender):
                    cycling_machine.send("cycle")
            except Exception as e:
                errors.append(e)

        def reader():
            barrier.wait(timeout=5)
            while not stop_event.is_set():
                try:
                    _ = cycling_machine.configuration
                    _ = cycling_machine.current_state_value
                    _ = list(cycling_machine.configuration)
                except Exception as e:
                    errors.append(e)

        threads = [threading.Thread(target=sender) for _ in range(num_senders)]
        reader_thread = threading.Thread(target=reader)

        for t in threads:
            t.start()
        reader_thread.start()

        for t in threads:
            t.join(timeout=30)
        stop_event.set()
        reader_thread.join(timeout=5)

        assert not errors, f"Thread errors: {errors}"

    def test_concurrent_parallel_region_send_and_read(self, parallel_machine):
        """Reading configuration while parallel-region events mutate it must not raise.

        Regresses an in-place mutation of the model's ``OrderedSet`` during
        ``Configuration.add()`` / ``discard()``: a concurrent reader iterating
        ``.configuration`` could crash with
        ``RuntimeError: Set changed size during iteration`` or briefly observe
        a stale cached set missing the newly entered state.
        """
        num_senders = 4
        events_per_sender = 400
        barrier = threading.Barrier(num_senders + 1)
        stop_event = threading.Event()
        errors = []

        def sender(event_name):
            try:
                barrier.wait(timeout=5)
                for _ in range(events_per_sender):
                    parallel_machine.send(event_name)
            except Exception as e:
                errors.append(e)

        def reader():
            barrier.wait(timeout=5)
            while not stop_event.is_set():
                try:
                    # Force resolution + iteration each loop.
                    _ = list(parallel_machine.configuration)
                    _ = [s.id for s in parallel_machine.configuration]
                except Exception as e:
                    errors.append(e)

        senders = []
        # Alternate tick_l / tick_r across threads so both regions mutate concurrently.
        for i in range(num_senders):
            event = "tick_l" if i % 2 == 0 else "tick_r"
            senders.append(threading.Thread(target=sender, args=(event,)))
        reader_thread = threading.Thread(target=reader)

        for t in senders:
            t.start()
        reader_thread.start()

        for t in senders:
            t.join(timeout=30)
        stop_event.set()
        reader_thread.join(timeout=5)

        assert not errors, f"Thread errors: {errors}"

    def test_add_discard_produce_fresh_orderedset(self, parallel_machine):
        """``add`` / ``discard`` must produce a fresh ``OrderedSet`` ref each call.

        Pins the copy-on-write contract independently of timing: otherwise a
        reader holding the prior ref could observe mid-mutation.
        """
        snapshot = parallel_machine._config.values
        parallel_machine.send("tick_l")
        assert parallel_machine._config.values is not snapshot


async def test_regression_443_with_modifications_for_async_engine():
    """
    Test for https://github.com/fgmacedo/python-statemachine/issues/443
    """
    total_iterations = 4
    send_at_iteration = 3  # 0-indexed: send before the 4th sample

    class TrafficLightMachine(StateChart):
        "A traffic light machine"

        green = State(initial=True)
        yellow = State()
        red = State()

        cycle = green.to(yellow) | yellow.to(red) | red.to(green)

        async def on_cycle(self):
            return "caution"

        def __init__(self, name):
            self.name = name
            self.statuses_history = []
            super().__init__()

        def beat(self):
            for i in range(total_iterations):
                if i == send_at_iteration:
                    self.cycle()
                self.statuses_history.append(f"{self.name}.{self.current_state_value}")

    class Controller:
        def __init__(self, name):
            self.fsm = TrafficLightMachine(name)

        async def start(self):
            # set up thread
            await self.fsm.activate_initial_state()
            self.thread = threading.Thread(target=self.fsm.beat)
            self.thread.start()

    c1 = Controller("c1")
    c2 = Controller("c2")
    c3 = Controller("c3")
    await c1.start()
    await c2.start()
    await c3.start()
    c1.thread.join()
    c2.thread.join()
    c3.thread.join()

    assert c1.fsm.statuses_history == ["c1.green", "c1.green", "c1.green", "c1.yellow"]
    assert c2.fsm.statuses_history == ["c2.green", "c2.green", "c2.green", "c2.yellow"]
    assert c3.fsm.statuses_history == ["c3.green", "c3.green", "c3.green", "c3.yellow"]
