import pickle
from functools import partial

import pytest
from statemachine.exceptions import InvalidDefinition

from statemachine import State
from statemachine import StateChart


class RecordingListener:
    """Listener that records transitions for testing."""

    def __init__(self):
        self.transitions = []

    def after_transition(self, event, source, target):
        self.transitions.append((event, source.id, target.id))


class SetupListener:
    """Listener that uses setup() to receive runtime dependencies."""

    def __init__(self):
        self.session = None
        self.transitions = []

    def setup(self, sm, session=None, **kwargs):
        self.session = session

    def after_transition(self, event, source, target):
        self.transitions.append((event, source.id, target.id, self.session))


class TestClassLevelListeners:
    def test_class_level_listener_callable_creates_per_instance(self):
        class MyChart(StateChart):
            listeners = [RecordingListener]

            s1 = State(initial=True)
            s2 = State(final=True)
            go = s1.to(s2)

        sm1 = MyChart()
        sm2 = MyChart()

        sm1.send("go")

        # Each SM gets its own listener instance
        assert len(sm1._class_listener_instances) == 1
        assert len(sm2._class_listener_instances) == 1
        assert sm1._class_listener_instances[0] is not sm2._class_listener_instances[0]

        # Only sm1 should have the transition recorded
        assert sm1._class_listener_instances[0].transitions == [("go", "s1", "s2")]
        assert sm2._class_listener_instances[0].transitions == []

    def test_class_level_listener_shared_instance(self):
        shared = RecordingListener()

        class MyChart(StateChart):
            listeners = [shared]

            s1 = State(initial=True)
            s2 = State(final=True)
            go = s1.to(s2)

        sm1 = MyChart()
        sm2 = MyChart()

        sm1.send("go")
        sm2.send("go")

        # Both SMs share the same listener instance
        assert sm1._class_listener_instances[0] is shared
        assert sm2._class_listener_instances[0] is shared
        assert len(shared.transitions) == 2

    def test_class_level_listener_partial(self):
        class ConfigurableListener:
            def __init__(self, prefix="default"):
                self.prefix = prefix
                self.messages = []

            def after_transition(self, event, source, target):
                self.messages.append(f"{self.prefix}: {source.id} -> {target.id}")

        class MyChart(StateChart):
            listeners = [partial(ConfigurableListener, prefix="custom")]

            s1 = State(initial=True)
            s2 = State(final=True)
            go = s1.to(s2)

        sm = MyChart()
        sm.send("go")

        listener = sm._class_listener_instances[0]
        assert listener.prefix == "custom"
        assert listener.messages == ["custom: s1 -> s2"]

    def test_class_level_listener_lambda(self):
        class SimpleListener:
            def __init__(self, tag):
                self.tag = tag

        class MyChart(StateChart):
            listeners = [lambda: SimpleListener("from_lambda")]

            s1 = State(initial=True)
            s2 = State(final=True)
            go = s1.to(s2)

        sm = MyChart()
        assert sm._class_listener_instances[0].tag == "from_lambda"

    def test_runtime_listeners_merge_with_class_level(self):
        class MyChart(StateChart):
            listeners = [RecordingListener]

            s1 = State(initial=True)
            s2 = State(final=True)
            go = s1.to(s2)

        runtime_listener = RecordingListener()
        sm = MyChart(listeners=[runtime_listener])

        sm.send("go")

        # Class-level listener should have recorded
        class_listener = sm._class_listener_instances[0]
        assert class_listener.transitions == [("go", "s1", "s2")]

        # Runtime listener should also have recorded
        assert runtime_listener.transitions == [("go", "s1", "s2")]


class TestClassListenerInheritance:
    def test_child_extends_parent_listeners(self):
        class ParentListener:
            pass

        class ChildListener:
            pass

        class Parent(StateChart):
            listeners = [ParentListener]

            s1 = State(initial=True)
            s2 = State(final=True)
            go = s1.to(s2)

        class Child(Parent):
            listeners = [ChildListener]

        sm = Child()
        assert len(sm._class_listener_instances) == 2
        assert isinstance(sm._class_listener_instances[0], ParentListener)
        assert isinstance(sm._class_listener_instances[1], ChildListener)

    def test_child_replaces_parent_listeners(self):
        class ParentListener:
            pass

        class ChildListener:
            pass

        class Parent(StateChart):
            listeners = [ParentListener]

            s1 = State(initial=True)
            s2 = State(final=True)
            go = s1.to(s2)

        class Child(Parent):
            listeners_inherit = False
            listeners = [ChildListener]

        sm = Child()
        assert len(sm._class_listener_instances) == 1
        assert isinstance(sm._class_listener_instances[0], ChildListener)

    def test_grandchild_inherits_full_chain(self):
        class L1:
            pass

        class L2:
            pass

        class L3:
            pass

        class Base(StateChart):
            listeners = [L1]

            s1 = State(initial=True)
            s2 = State(final=True)
            go = s1.to(s2)

        class Mid(Base):
            listeners = [L2]

        class Leaf(Mid):
            listeners = [L3]

        sm = Leaf()
        assert len(sm._class_listener_instances) == 3
        assert isinstance(sm._class_listener_instances[0], L1)
        assert isinstance(sm._class_listener_instances[1], L2)
        assert isinstance(sm._class_listener_instances[2], L3)

    def test_no_listeners_declared_inherits_parent(self):
        class ParentListener:
            pass

        class Parent(StateChart):
            listeners = [ParentListener]

            s1 = State(initial=True)
            s2 = State(final=True)
            go = s1.to(s2)

        class Child(Parent):
            pass

        sm = Child()
        assert len(sm._class_listener_instances) == 1
        assert isinstance(sm._class_listener_instances[0], ParentListener)


class TestListenerSetupProtocol:
    def test_setup_receives_kwargs(self):
        class MyChart(StateChart):
            listeners = [SetupListener]

            s1 = State(initial=True)
            s2 = State(final=True)
            go = s1.to(s2)

        sm = MyChart(session="my_db_session")
        listener = sm._class_listener_instances[0]
        assert listener.session == "my_db_session"

    def test_setup_ignores_unknown_kwargs(self):
        class MyChart(StateChart):
            listeners = [SetupListener]

            s1 = State(initial=True)
            s2 = State(final=True)
            go = s1.to(s2)

        sm = MyChart(session="db", unknown_arg="ignored")
        listener = sm._class_listener_instances[0]
        assert listener.session == "db"

    def test_setup_not_called_on_shared_instances(self):
        shared = SetupListener()

        class MyChart(StateChart):
            listeners = [shared]

            s1 = State(initial=True)
            s2 = State(final=True)
            go = s1.to(s2)

        MyChart(session="db")
        # Shared instance should NOT have setup() called
        assert shared.session is None

    def test_multiple_listeners_with_different_deps(self):
        class DBListener:
            def __init__(self):
                self.session = None

            def setup(self, sm, session=None, **kwargs):
                self.session = session

        class CacheListener:
            def __init__(self):
                self.redis = None

            def setup(self, sm, redis=None, **kwargs):
                self.redis = redis

        class MyChart(StateChart):
            listeners = [DBListener, CacheListener]

            s1 = State(initial=True)
            s2 = State(final=True)
            go = s1.to(s2)

        sm = MyChart(session="db_conn", redis="redis_conn")
        db = sm._class_listener_instances[0]
        cache = sm._class_listener_instances[1]
        assert db.session == "db_conn"
        assert cache.redis == "redis_conn"

    def test_setup_receives_sm_instance(self):
        class IntrospectiveListener:
            def __init__(self):
                self.sm = None

            def setup(self, sm, **kwargs):
                self.sm = sm

        class MyChart(StateChart):
            listeners = [IntrospectiveListener]

            s1 = State(initial=True)
            s2 = State(final=True)
            go = s1.to(s2)

        sm = MyChart()
        listener = sm._class_listener_instances[0]
        assert listener.sm is sm

    def test_setup_optional_kwargs_default_to_none(self):
        class MyChart(StateChart):
            listeners = [SetupListener]

            s1 = State(initial=True)
            s2 = State(final=True)
            go = s1.to(s2)

        sm = MyChart()  # No session kwarg provided
        listener = sm._class_listener_instances[0]
        assert listener.session is None

    def test_setup_required_kwarg_missing_raises_error(self):
        class StrictListener:
            def setup(self, sm, session):
                self.session = session

        class MyChart(StateChart):
            listeners = [StrictListener]

            s1 = State(initial=True)
            s2 = State(final=True)
            go = s1.to(s2)

        with pytest.raises(TypeError, match="Error calling setup.*StrictListener"):
            MyChart()

    def test_setup_required_kwarg_provided(self):
        class StrictListener:
            def setup(self, sm, session):
                self.session = session

        class MyChart(StateChart):
            listeners = [StrictListener]

            s1 = State(initial=True)
            s2 = State(final=True)
            go = s1.to(s2)

        sm = MyChart(session="db_conn")
        assert sm._class_listener_instances[0].session == "db_conn"


class TestListenerValidation:
    def test_rejects_none_in_listeners(self):
        with pytest.raises(InvalidDefinition, match="Invalid entry"):

            class MyChart(StateChart):
                listeners = [None]

                s1 = State(initial=True)
                s2 = State(final=True)
                go = s1.to(s2)

    def test_rejects_string_in_listeners(self):
        with pytest.raises(InvalidDefinition, match="Invalid entry"):

            class MyChart(StateChart):
                listeners = ["not_a_listener"]

                s1 = State(initial=True)
                s2 = State(final=True)
                go = s1.to(s2)

    def test_rejects_number_in_listeners(self):
        with pytest.raises(InvalidDefinition, match="Invalid entry"):

            class MyChart(StateChart):
                listeners = [42]

                s1 = State(initial=True)
                s2 = State(final=True)
                go = s1.to(s2)

    def test_rejects_bool_in_listeners(self):
        with pytest.raises(InvalidDefinition, match="Invalid entry"):

            class MyChart(StateChart):
                listeners = [True]

                s1 = State(initial=True)
                s2 = State(final=True)
                go = s1.to(s2)


class _PickleChart(StateChart):
    listeners = [RecordingListener]

    s1 = State(initial=True)
    s2 = State(final=True)
    go = s1.to(s2)


class _PickleMultiStepChart(StateChart):
    listeners = [RecordingListener]

    s1 = State(initial=True)
    s2 = State()
    s3 = State(final=True)
    step1 = s1.to(s2)
    step2 = s2.to(s3)


class TestListenerSerialization:
    def test_pickle_with_class_listeners(self):
        sm = _PickleChart()
        sm.send("go")

        data = pickle.dumps(sm)
        sm2 = pickle.loads(data)

        # Class listener instances are preserved through serialization
        assert len(sm2._class_listener_instances) == 1
        assert sm2._class_listener_instances[0].transitions == [("go", "s1", "s2")]
        assert "s2" in sm2.configuration_values

    def test_pickle_does_not_duplicate_class_listeners(self):
        sm = _PickleChart()
        assert len(sm.active_listeners) == 1

        data = pickle.dumps(sm)
        sm2 = pickle.loads(data)

        # Must not duplicate class listeners after deserialization
        assert len(sm2.active_listeners) == 1

    def test_pickle_with_runtime_listeners(self):
        runtime = RecordingListener()
        sm = _PickleMultiStepChart(listeners=[runtime])
        sm.send("step1")

        data = pickle.dumps(sm)
        sm2 = pickle.loads(data)

        # After deserialization, both class and runtime listeners are re-registered
        assert "s2" in sm2.configuration_values
        sm2.send("step2")
        assert "s3" in sm2.configuration_values


class TestEmptyClassListeners:
    def test_no_listeners_attribute(self):
        class MyChart(StateChart):
            s1 = State(initial=True)
            s2 = State(final=True)
            go = s1.to(s2)

        sm = MyChart()
        assert sm._class_listener_instances == []

    def test_empty_listeners_list(self):
        class MyChart(StateChart):
            listeners = []

            s1 = State(initial=True)
            s2 = State(final=True)
            go = s1.to(s2)

        sm = MyChart()
        assert sm._class_listener_instances == []
