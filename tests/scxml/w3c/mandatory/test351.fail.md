# Testcase: test351

AssertionError: Assertion failed.

Final configuration: `['fail']`

---

## Logs
```py
DEBUG    statemachine.engines.base:base.py:415 States to enter: {S0}
DEBUG    statemachine.engines.base:base.py:93 New event 'timeout' put on the 'external' queue
DEBUG    statemachine.engines.base:base.py:93 New event 's0Event' put on the 'external' queue
DEBUG    statemachine.engines.sync:sync.py:64 Processing loop started: s0
DEBUG    statemachine.engines.sync:sync.py:116 External event: s0Event
DEBUG    statemachine.engines.sync:sync.py:131 Enabled transitions: {transition s0Event from S0 to S1}
DEBUG    statemachine.engines.base:base.py:339 States to exit: {S0}
DEBUG    statemachine.engines.base:base.py:415 States to enter: {S1}
DEBUG    statemachine.io.scxml.actions:actions.py:477 Error executing actions
Traceback (most recent call last):
  File "/home/macedo/projects/python-statemachine/statemachine/io/scxml/actions.py", line 473, in __call__
    action(*args, **kwargs)
    ~~~~~~^^^^^^^^^^^^^^^^^
  File "/home/macedo/projects/python-statemachine/statemachine/io/scxml/actions.py", line 241, in __call__
    value = _eval(self.action.expr, **kwargs)
  File "/home/macedo/projects/python-statemachine/statemachine/io/scxml/actions.py", line 138, in _eval
    return eval(expr, {}, kwargs)
  File "<string>", line 1, in <module>
    import sys;exec(eval(sys.stdin.readline()))
    ^^^^^^^^^^^^^
  File "/home/macedo/projects/python-statemachine/statemachine/io/scxml/actions.py", line 111, in __getattr__
    return getattr(self.event_data, name)
AttributeError: 'EventData' object has no attribute 'sendid'
DEBUG    statemachine.engines.base:base.py:93 New event 'error.execution' put on the 'internal' queue
DEBUG    statemachine.engines.sync:sync.py:116 External event: timeout
DEBUG    statemachine.engines.sync:sync.py:131 Enabled transitions: {}
DEBUG    statemachine.io.scxml.actions:actions.py:180 Cond Var1=='send1' -> False
DEBUG    statemachine.engines.sync:sync.py:89 Eventless/internal queue: {transition  from S1 to Fail}
DEBUG    statemachine.engines.base:base.py:339 States to exit: {S1}
DEBUG    statemachine.engines.base:base.py:415 States to enter: {Fail}

```

## "On transition" events
```py
OnEnterState(state='s0', event='__initial__', data='{}')
OnTransition(source='s0', event='s0Event', data='{}', target='s1')
OnEnterState(state='s1', event='s0Event', data='{}')
OnTransition(source='s1', event='None', data='{}', target='fail')
OnEnterState(state='fail', event='None', data='{}')
```

## Traceback
```py
Assertion of the testcase failed.
```
