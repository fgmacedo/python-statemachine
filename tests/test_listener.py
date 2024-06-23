EXPECTED_LOG_ADD = """Frodo on: draft--(add_job)-->draft
Frodo enter: draft from add_job
Frodo on: draft--(produce)-->producing
Frodo enter: producing from produce
"""

EXPECTED_LOG_CREATION = """Frodo enter: draft from __initial__
Frodo on: draft--(add_job)-->draft
Frodo enter: draft from add_job
Frodo on: draft--(produce)-->producing
Frodo enter: producing from produce
"""


class TestObserver:
    def test_add_log_observer(self, campaign_machine, capsys):
        class LogObserver:
            def __init__(self, name):
                self.name = name

            def on_transition(self, event, state, target):
                print(f"{self.name} on: {state.id}--({event})-->{target.id}")

            def on_enter_state(self, target, event):
                print(f"{self.name} enter: {target.id} from {event}")

        sm = campaign_machine()

        sm.add_listener(LogObserver("Frodo"))

        sm.add_job()
        sm.produce()

        captured = capsys.readouterr()
        assert captured.out == EXPECTED_LOG_ADD

    def test_log_observer_on_creation(self, campaign_machine, capsys):
        class LogObserver:
            def __init__(self, name):
                self.name = name

            def on_transition(self, event, state, target):
                print(f"{self.name} on: {state.id}--({event})-->{target.id}")

            def on_enter_state(self, target, event):
                print(f"{self.name} enter: {target.id} from {event}")

        sm = campaign_machine(listeners=[LogObserver("Frodo")])

        sm.add_job()
        sm.produce()

        captured = capsys.readouterr()
        assert captured.out == EXPECTED_LOG_CREATION

    def test_deprecated_api(self, campaign_machine, capsys):
        class LogObserver:
            def __init__(self, name):
                self.name = name

            def on_transition(self, event, state, target):
                print(f"{self.name} on: {state.id}--({event})-->{target.id}")

            def on_enter_state(self, target, event):
                print(f"{self.name} enter: {target.id} from {event}")

        sm = campaign_machine()

        sm.add_observer(LogObserver("Frodo"))

        sm.add_job()
        sm.produce()

        captured = capsys.readouterr()
        assert captured.out == EXPECTED_LOG_ADD
