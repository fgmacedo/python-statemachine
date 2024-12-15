# Testcase: test326

AssertionError: Assertion failed.

Final configuration: `['fail']`

---

## Logs
```py
DEBUG    statemachine.engines.base:base.py:415 States to enter: {S0}
DEBUG    statemachine.engines.sync:sync.py:64 Processing loop started: s0
DEBUG    statemachine.io.scxml.actions:actions.py:180 Cond Var1 -> <statemachine.io.scxml.processor.IOProcessor object at 0x7f4ec1afa690>
DEBUG    statemachine.engines.sync:sync.py:89 Eventless/internal queue: {transition  from S0 to S1}
DEBUG    statemachine.engines.base:base.py:339 States to exit: {S0}
DEBUG    statemachine.engines.base:base.py:415 States to enter: {S1}
DEBUG    statemachine.io.scxml.actions:actions.py:477 Error executing actions
Traceback (most recent call last):
  File "/home/macedo/projects/python-statemachine/statemachine/io/scxml/actions.py", line 473, in __call__
    action(*args, **kwargs)
    ~~~~~~^^^^^^^^^^^^^^^^^
  File "/home/macedo/projects/python-statemachine/statemachine/io/scxml/actions.py", line 254, in __call__
    raise ValueError(
    ...<2 lines>...
    )
ValueError: <assign> 'location' cannot assign to a protected attribute: _ioprocessors
DEBUG    statemachine.engines.base:base.py:93 New event 'error.execution' put on the 'internal' queue
DEBUG    statemachine.engines.sync:sync.py:89 Eventless/internal queue: {transition error.execution from S1 to S2}
DEBUG    statemachine.engines.base:base.py:339 States to exit: {S1}
DEBUG    statemachine.engines.base:base.py:415 States to enter: {S2}
DEBUG    statemachine.io.scxml.actions:actions.py:259 Assign: Var2 = <statemachine.io.scxml.processor.IOProcessor object at 0x7f4ec1afa930>
DEBUG    statemachine.io.scxml.actions:actions.py:180 Cond Var1==Var2 -> False
DEBUG    statemachine.engines.sync:sync.py:89 Eventless/internal queue: {transition  from S2 to Fail}
DEBUG    statemachine.engines.base:base.py:339 States to exit: {S2}
DEBUG    statemachine.engines.base:base.py:415 States to enter: {Fail}

```

## "On transition" events
```py
OnEnterState(state='s0', event='__initial__', data='{}')
OnTransition(source='s0', event='None', data='{}', target='s1')
OnEnterState(state='s1', event='None', data='{}')
OnTransition(source='s1', event='error.execution', data='{\'event_id\': None, \'error\': ValueError("<assign> \'location\' cannot assign to a protected attribute: _ioprocessors")}', target='s2')
OnEnterState(state='s2', event='error.execution', data='{\'event_id\': None, \'error\': ValueError("<assign> \'location\' cannot assign to a protected attribute: _ioprocessors")}')
OnTransition(source='s2', event='None', data='{}', target='fail')
OnEnterState(state='fail', event='None', data='{}')
```

## Traceback
```py
Assertion of the testcase failed.
```
