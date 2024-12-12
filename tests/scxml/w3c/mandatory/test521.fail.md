# Testcase: test521

AssertionError: Assertion failed.

Final configuration: `['fail']`

---

## Logs
```py
DEBUG    statemachine.engines.base:base.py:374 States to enter: {S0}
DEBUG    statemachine.io.scxml.actions:actions.py:464 Error executing actions
Traceback (most recent call last):
  File "/home/macedo/projects/python-statemachine/statemachine/io/scxml/actions.py", line 460, in __call__
    action(*args, **kwargs)
    ~~~~~~^^^^^^^^^^^^^^^^^
  File "/home/macedo/projects/python-statemachine/statemachine/io/scxml/actions.py", line 339, in send_action
    raise ValueError(f"Invalid target: {target}. Must be one of {_valid_targets}")
ValueError: Invalid target: #_scxml_foo. Must be one of (None, '#_internal', 'internal', '#_parent', 'parent')
DEBUG    statemachine.engines.sync:sync.py:64 Processing loop started: s0
DEBUG    statemachine.engines.sync:sync.py:89 Eventless/internal queue: {transition * from S0 to Fail}
DEBUG    statemachine.engines.base:base.py:283 States to exit: {S0}
DEBUG    statemachine.engines.base:base.py:374 States to enter: {Fail}

```

## "On transition" events
```py
DebugEvent(source='s0', event='error.execution', data='{\'event_id\': None, \'error\': ValueError("Invalid target: #_scxml_foo. Must be one of (None, \'#_internal\', \'internal\', \'#_parent\', \'parent\')")}', target='fail')
```

## Traceback
```py
Assertion of the testcase failed.
```
