EXPECTED_LOG = """Frodo on: draft--(add_job)-->draft
Frodo enter: draft from add_job
Frodo on: draft--(produce)-->producing
Frodo enter: producing from produce
"""


class TestObserver:
    def test_add_log_observer(self, campaign_machine, capsys):
        class LogObserver(object):
            def __init__(self, name):
                self.name = name

            def on_transition(self, event, state, target):
                print(
                    "{} on: {}--({})-->{}".format(self.name, state.id, event, target.id)
                )

            def on_enter_state(self, target, event):
                print("{} enter: {} from {}".format(self.name, target.id, event))

        sm = campaign_machine()

        sm.add_observer(LogObserver("Frodo"))

        sm.add_job()
        sm.produce()

        captured = capsys.readouterr()
        assert captured.out == EXPECTED_LOG
