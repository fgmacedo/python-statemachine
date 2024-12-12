# Testcase: test402

AssertionError: Assertion failed.

Final configuration: `['fail']`

---

## Logs
```py
DEBUG    statemachine.engines.base:base.py:374 States to enter: {S0, S01}
DEBUG    statemachine.io.scxml.actions:actions.py:467 Error executing actions
Traceback (most recent call last):
  File "/home/macedo/projects/python-statemachine/statemachine/io/scxml/actions.py", line 463, in __call__
    action(*args, **kwargs)
    ~~~~~~^^^^^^^^^^^^^^^^^
  File "/home/macedo/projects/python-statemachine/statemachine/io/scxml/actions.py", line 239, in __call__
    raise ValueError(
    ...<2 lines>...
    )
ValueError: <assign> 'location' must be a valid Python attribute name and must be declared, got: Var1
DEBUG    statemachine.engines.sync:sync.py:64 Processing loop started: ['s0', 's01']
DEBUG    statemachine.engines.sync:sync.py:89 Eventless/internal queue: {transition event1 from S01 to S02}
DEBUG    statemachine.engines.base:base.py:283 States to exit: {S01}
DEBUG    statemachine.engines.base:base.py:374 States to enter: {S02}
DEBUG    statemachine.engines.sync:sync.py:89 Eventless/internal queue: {transition * from S02 to Fail}
DEBUG    statemachine.engines.base:base.py:283 States to exit: {S0, S02}
DEBUG    statemachine.engines.base:base.py:374 States to enter: {Fail}
DEBUG    statemachine.engines.sync:sync.py:116 External event: TriggerData(machine=<weakproxy at 0x7f4a06dd91c0; to 'statemachine.io.test402' at 0x7f4a06c98050>, event=Event('timeout', delay=1000.0, internal=False), send_id='3bfb4b2532c940ccb0b09f6fe65f3579', _target=None, execution_time=1733943929.609803, model=Model(state=fail), args=(), kwargs={})
DEBUG    statemachine.engines.sync:sync.py:131 Enabled transitions: {}

```

## "On transition" events
```py
DebugEvent(source='s01', event='event1', data='{}', target='s02')
DebugEvent(source='s02', event='error.execution', data='{\'event_id\': None, \'error\': ValueError("<assign> \'location\' must be a valid Python attribute name and must be declared, got: Var1")}', target='fail')
```

## Traceback
```py
Assertion of the testcase failed.
```
