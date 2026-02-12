import pytest
from statemachine.orderedset import OrderedSet

from statemachine import State
from statemachine import StateMachine


@pytest.fixture()
def sm_class():
    class SM(StateMachine):
        pending = State(initial=True)
        waiting_approval = State()
        approved = State(final=True)

        start = pending.to(waiting_approval)
        approve = waiting_approval.to(approved)

    return SM


class TestState:
    def test_name_derived_from_id(self, sm_class):
        assert sm_class.pending.name == "Pending"
        assert sm_class.waiting_approval.name == "Waiting approval"
        assert sm_class.approved.name == "Approved"

    def test_state_from_instance_is_hashable(self, sm_class):
        sm = sm_class()
        states_set = {sm.pending, sm.waiting_approval, sm.approved, sm.approved}
        assert states_set == {sm.pending, sm.waiting_approval, sm.approved}

    def test_state_knows_if_its_initial(self, sm_class):
        sm = sm_class()
        assert sm.pending.initial
        assert not sm.waiting_approval.initial
        assert not sm.approved.initial

    def test_state_knows_if_its_final(self, sm_class):
        sm = sm_class()
        assert not sm.pending.final
        assert not sm.waiting_approval.final
        assert sm.approved.final


def test_ordered_set_clear():
    """OrderedSet.clear empties the set."""
    s = OrderedSet([1, 2, 3])
    s.clear()
    assert len(s) == 0


def test_ordered_set_getitem():
    """OrderedSet supports index access."""
    s = OrderedSet([10, 20, 30])
    assert s[0] == 10
    assert s[2] == 30


def test_ordered_set_getitem_out_of_range():
    """OrderedSet raises IndexError for out-of-range index."""
    s = OrderedSet([10, 20])
    with pytest.raises(IndexError, match="index 5 out of range"):
        s[5]


def test_ordered_set_union():
    """OrderedSet.union returns new set with elements from both."""
    s1 = OrderedSet([1, 2])
    result = s1.union([3, 4], [5, 6])
    assert list(result) == [1, 2, 3, 4, 5, 6]
