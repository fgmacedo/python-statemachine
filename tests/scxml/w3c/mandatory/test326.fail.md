# Testcase: test326

AssertionError: Assertion failed.

Final configuration: `['fail']`

---

## Logs
```py
DEBUG    statemachine.engines.base:base.py:386 States to enter: {S0}
DEBUG    statemachine.engines.sync:sync.py:64 Processing loop started: s0
DEBUG    statemachine.io.scxml.actions:actions.py:179 Cond Var1 -> <statemachine.io.scxml.processor.IOProcessor object at 0x7f0f23f91190>
DEBUG    statemachine.engines.sync:sync.py:89 Eventless/internal queue: {transition  from S0 to S1}
DEBUG    statemachine.engines.base:base.py:276 States to exit: {S0}
DEBUG    statemachine.engines.base:base.py:386 States to enter: {S1}
DEBUG    statemachine.io.scxml.actions:actions.py:476 Error executing actions
Traceback (most recent call last):
  File "/home/macedo/projects/python-statemachine/statemachine/io/scxml/actions.py", line 472, in __call__
    action(*args, **kwargs)
    ~~~~~~^^^^^^^^^^^^^^^^^
  File "/home/macedo/projects/python-statemachine/statemachine/io/scxml/actions.py", line 253, in __call__
    raise ValueError(
    ...<2 lines>...
    )
ValueError: <assign> 'location' cannot assign to a protected attribute: _ioprocessors
DEBUG    statemachine.engines.sync:sync.py:89 Eventless/internal queue: {transition error.execution from S1 to S2}
DEBUG    statemachine.engines.base:base.py:276 States to exit: {S1}
DEBUG    statemachine.engines.base:base.py:386 States to enter: {S2}
DEBUG    statemachine.io.scxml.actions:actions.py:258 Assign: Var2 = <statemachine.io.scxml.processor.IOProcessor object at 0x7f0f23f915b0>
DEBUG    statemachine.io.scxml.actions:actions.py:179 Cond Var1==Var2 -> False
DEBUG    statemachine.engines.sync:sync.py:89 Eventless/internal queue: {transition  from S2 to Fail}
DEBUG    statemachine.engines.base:base.py:276 States to exit: {S2}
DEBUG    statemachine.engines.base:base.py:386 States to enter: {Fail}

```

## "On transition" events
```py
DebugEvent(source='s0', event='None', data='{}', target='s1')
DebugEvent(source='s1', event='error.execution', data='{\'event_id\': None, \'error\': ValueError("<assign> \'location\' cannot assign to a protected attribute: _ioprocessors")}', target='s2')
DebugEvent(source='s2', event='None', data='{}', target='fail')
```

## Traceback
```py
Assertion of the testcase failed.
```
