# Testcase: test533

StopIteration: Signal the end from iterator.__next__().

Final configuration: `No configuration`

---

## Logs
```py
DEBUG    statemachine.engines.base:base.py:374 States to enter: {S1}
DEBUG    statemachine.engines.sync:sync.py:64 Processing loop started: s1
DEBUG    statemachine.engines.sync:sync.py:89 Eventless/internal queue: {transition  from S1 to P}
DEBUG    statemachine.engines.base:base.py:283 States to exit: {S1}

```

## "On transition" events
```py
DebugEvent(source='s1', event='None', data='{}', target='p')
```

## Traceback
```py
Traceback (most recent call last):
  File "/home/macedo/projects/python-statemachine/tests/scxml/test_scxml_cases.py", line 116, in test_scxml_usecase
    sm = processor.start(listeners=[debug])
  File "/home/macedo/projects/python-statemachine/statemachine/io/scxml/processor.py", line 126, in start
    self.root = self.root_cls(**kwargs)
                ~~~~~~~~~~~~~^^^^^^^^^^
  File "/home/macedo/projects/python-statemachine/statemachine/statemachine.py", line 101, in __init__
    self._engine.start()
    ~~~~~~~~~~~~~~~~~~^^
  File "/home/macedo/projects/python-statemachine/statemachine/engines/sync.py", line 24, in start
    self.activate_initial_state()
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~^^
  File "/home/macedo/projects/python-statemachine/statemachine/engines/sync.py", line 44, in activate_initial_state
    return self.processing_loop()
           ~~~~~~~~~~~~~~~~~~~~^^
  File "/home/macedo/projects/python-statemachine/statemachine/engines/sync.py", line 91, in processing_loop
    self.microstep(list(enabled_transitions), internal_event)
    ~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/macedo/projects/python-statemachine/statemachine/engines/base.py", line 285, in microstep
    self._enter_states(transitions, trigger_data, states_to_exit)
    ~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/macedo/projects/python-statemachine/statemachine/engines/base.py", line 366, in _enter_states
    self.compute_entry_set(
    ~~~~~~~~~~~~~~~~~~~~~~^
        enabled_transitions, states_to_enter, states_for_default_entry, default_history_content
        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
    )
    ^
  File "/home/macedo/projects/python-statemachine/statemachine/engines/base.py", line 455, in compute_entry_set
    self.add_descendant_states_to_enter(
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~^
        info, states_to_enter, states_for_default_entry, default_history_content
        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
    )
    ^
  File "/home/macedo/projects/python-statemachine/statemachine/engines/base.py", line 526, in add_descendant_states_to_enter
    initial_state = next(s for s in state.states if s.initial)
StopIteration

```
