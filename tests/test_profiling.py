import weakref

import pytest

from statemachine import HistoryState
from statemachine import State
from statemachine import StateChart

# ---------------------------------------------------------------------------
# Machines under test
# ---------------------------------------------------------------------------


# 1. Flat machine with model, guards, and listener callbacks (v1-style)
class OrderControl(StateChart):
    allow_event_without_transition = False
    catch_errors_as_events = False

    waiting_for_payment = State(initial=True)
    processing = State()
    shipping = State()
    completed = State(final=True)

    add_to_order = waiting_for_payment.to(waiting_for_payment)
    receive_payment = waiting_for_payment.to(
        processing, cond="payments_enough"
    ) | waiting_for_payment.to(waiting_for_payment, unless="payments_enough")
    process_order = processing.to(shipping, cond="payment_received")
    ship_order = shipping.to(completed)


class Order:
    def __init__(self):
        self.order_total = 0
        self.payments = []
        self.payment_received = False
        self.state_machine = OrderControl(model=weakref.proxy(self))

    def payments_enough(self, amount):
        return sum(self.payments) + amount >= self.order_total

    def before_add_to_order(self, amount):
        self.order_total += amount
        return self.order_total

    def on_receive_payment(self, amount):
        self.payments.append(amount)
        return self.payments

    def after_receive_payment(self):
        self.payment_received = True


# 2. Compound (nested) states
class CompoundSC(StateChart):
    class active(State.Compound, name="Active"):
        idle = State(initial=True)
        working = State()
        begin = idle.to(working)

    off = State(initial=True)
    done = State(final=True)

    turn_on = off.to(active)
    turn_off = active.to(done)


# 3. Parallel regions
class ParallelSC(StateChart):
    class both(State.Parallel, name="Both"):
        class left(State.Compound, name="Left"):
            l1 = State(initial=True)
            l2 = State()
            go_l = l1.to(l2)
            back_l = l2.to(l1)

        class right(State.Compound, name="Right"):
            r1 = State(initial=True)
            r2 = State()
            go_r = r1.to(r2)
            back_r = r2.to(r1)

    start = State(initial=True)
    enter = start.to(both)


# 4. Guards with boolean expressions
class GuardedSC(StateChart):
    s1 = State(initial=True)
    s2 = State()
    s3 = State(final=True)

    def check_a(self):
        return True

    def check_b(self):
        return False

    go = s1.to(s2, cond="check_a") | s1.to(s3, cond="check_b")
    back = s2.to(s1)


# 5. History states (shallow)
class HistoryShallowSC(StateChart):
    class process(State.Compound, name="Process"):
        step1 = State(initial=True)
        step2 = State()
        advance = step1.to(step2)
        h = HistoryState()

    paused = State(initial=True)

    pause = process.to(paused)
    resume = paused.to(process.h)
    begin = paused.to(process)


# 6. Deep history with nested compound states
class DeepHistorySC(StateChart):
    class outer(State.Compound, name="Outer"):
        class inner(State.Compound, name="Inner"):
            a = State(initial=True)
            b = State()
            go = a.to(b)
            back = b.to(a)

        start = State(initial=True)
        enter_inner = start.to(inner)
        h = HistoryState(type="deep")

    away = State(initial=True)

    dive = away.to(outer)
    leave = outer.to(away)
    restore = away.to(outer.h)


# 7. Many-transition stress machine (wide, not deep)
class ManyTransitionsSC(StateChart):
    s1 = State(initial=True)
    s2 = State()
    s3 = State()
    s4 = State()
    s5 = State()

    go_12 = s1.to(s2)
    go_23 = s2.to(s3)
    go_34 = s3.to(s4)
    go_45 = s4.to(s5)
    go_51 = s5.to(s1)
    reset = s2.to(s1) | s3.to(s1) | s4.to(s1) | s5.to(s1)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def create_order():
    order = Order()
    assert order.state_machine.waiting_for_payment.is_active


def add_to_order(sm, amount):
    sm.add_to_order(amount)


# ---------------------------------------------------------------------------
# Benchmark: instance creation
# ---------------------------------------------------------------------------


@pytest.mark.slow()
class TestSetupPerformance:
    """Benchmark the cost of creating and activating state machine instances."""

    def test_flat_machine(self, benchmark):
        benchmark.pedantic(create_order, rounds=10, iterations=1000)

    def test_compound_machine(self, benchmark):
        benchmark.pedantic(lambda: CompoundSC(), rounds=10, iterations=1000)

    def test_parallel_machine(self, benchmark):
        benchmark.pedantic(lambda: ParallelSC(), rounds=10, iterations=1000)

    def test_guarded_machine(self, benchmark):
        benchmark.pedantic(lambda: GuardedSC(), rounds=10, iterations=1000)

    def test_history_machine(self, benchmark):
        benchmark.pedantic(lambda: HistoryShallowSC(), rounds=10, iterations=1000)

    def test_deep_history_machine(self, benchmark):
        benchmark.pedantic(lambda: DeepHistorySC(), rounds=10, iterations=1000)


# ---------------------------------------------------------------------------
# Benchmark: event throughput
# ---------------------------------------------------------------------------


@pytest.mark.slow()
class TestEventPerformance:
    """Benchmark event processing (self-transitions and state changes)."""

    def test_flat_self_transition(self, benchmark):
        """Self-transition on a flat machine with model/listener."""
        order = Order()
        sm = order.state_machine
        benchmark.pedantic(add_to_order, args=(sm, 1), rounds=10, iterations=1000)

    def test_compound_enter_exit(self, benchmark):
        """Enter and exit a compound state repeatedly."""

        def cycle():
            sm = CompoundSC()
            sm.turn_on()
            sm.begin()
            sm.turn_off()

        benchmark.pedantic(cycle, rounds=10, iterations=500)

    def test_parallel_region_events(self, benchmark):
        """Send events within parallel regions."""
        sm = ParallelSC()
        sm.enter()

        def cycle():
            sm.go_l()
            sm.go_r()
            sm.back_l()
            sm.back_r()

        benchmark.pedantic(cycle, rounds=10, iterations=500)

    def test_guarded_transitions(self, benchmark):
        """Guard evaluation + transition selection."""
        sm = GuardedSC()

        def cycle():
            sm.go()
            sm.back()

        benchmark.pedantic(cycle, rounds=10, iterations=1000)

    def test_history_pause_resume(self, benchmark):
        """Shallow history: pause and resume compound state."""
        sm = HistoryShallowSC()
        sm.begin()
        sm.advance()

        def cycle():
            sm.pause()
            sm.resume()

        benchmark.pedantic(cycle, rounds=10, iterations=500)

    def test_deep_history_cycle(self, benchmark):
        """Deep history: leave and restore nested compound state."""
        sm = DeepHistorySC()
        sm.dive()
        sm.enter_inner()
        sm.go()

        def cycle():
            sm.leave()
            sm.restore()

        benchmark.pedantic(cycle, rounds=10, iterations=500)

    def test_many_transitions_full_cycle(self, benchmark):
        """Traverse a 5-state ring (s1→s2→s3→s4→s5→s1)."""
        sm = ManyTransitionsSC()

        def cycle():
            sm.go_12()
            sm.go_23()
            sm.go_34()
            sm.go_45()
            sm.go_51()

        benchmark.pedantic(cycle, rounds=10, iterations=500)

    def test_many_transitions_reset(self, benchmark):
        """Composite event (|) selecting among multiple source states."""
        sm = ManyTransitionsSC()

        def cycle():
            sm.go_12()
            sm.go_23()
            sm.go_34()
            sm.reset()

        benchmark.pedantic(cycle, rounds=10, iterations=500)
