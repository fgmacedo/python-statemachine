# Testcase: test351

AssertionError: Assertion failed.

Final configuration: `['fail']`

---

## Logs
```py
DEBUG    statemachine.engines.base:base.py:374 States to enter: {S0}
DEBUG    statemachine.engines.sync:sync.py:64 Processing loop started: s0
DEBUG    statemachine.engines.sync:sync.py:116 External event: TriggerData(machine=<weakproxy at 0x7f62aa48ae80; to 'statemachine.io.test351' at 0x7f62aa5f4d70>, event=Event('s0Event', delay=0, internal=False), send_id='send1', _target=None, execution_time=1734003004.3945339, model=Model(state=s0), args=(), kwargs={})
DEBUG    statemachine.engines.sync:sync.py:131 Enabled transitions: {transition s0Event from S0 to S1}
DEBUG    statemachine.engines.base:base.py:283 States to exit: {S0}
DEBUG    statemachine.io.scxml.actions:actions.py:464 Error executing actions
Traceback (most recent call last):
  File "/home/macedo/projects/python-statemachine/statemachine/io/scxml/actions.py", line 460, in __call__
    action(*args, **kwargs)
    ~~~~~~^^^^^^^^^^^^^^^^^
  File "/home/macedo/projects/python-statemachine/statemachine/io/scxml/actions.py", line 231, in __call__
    value = _eval(self.action.expr, **kwargs)
  File "/home/macedo/projects/python-statemachine/statemachine/io/scxml/actions.py", line 125, in _eval
    return eval(expr, {}, kwargs)
  File "<string>", line 1, in <module>
    import sys;exec(eval(sys.stdin.readline()))
    ^^^^^^^^^^^^^
  File "/home/macedo/projects/python-statemachine/statemachine/io/scxml/actions.py", line 102, in __getattr__
    return getattr(self.event_data, name)
AttributeError: 'EventData' object has no attribute 'sendid'
DEBUG    statemachine.engines.base:base.py:374 States to enter: {S1}
DEBUG    statemachine.engines.sync:sync.py:116 External event: TriggerData(machine=<weakproxy at 0x7f62aa48ae80; to 'statemachine.io.test351' at 0x7f62aa5f4d70>, event=Event('timeout', delay=2000.0, internal=False), send_id='9f8e28b9e29a4b8a9d9f331a712aa847', _target=None, execution_time=1734003006.394508, model=Model(state=s1), args=(), kwargs={})
DEBUG    statemachine.engines.sync:sync.py:131 Enabled transitions: {}
DEBUG    statemachine.io.scxml.actions:actions.py:170 Cond Var1=='send1' -> False
DEBUG    statemachine.engines.sync:sync.py:89 Eventless/internal queue: {transition  from S1 to Fail}
DEBUG    statemachine.engines.base:base.py:283 States to exit: {S1}
DEBUG    statemachine.engines.base:base.py:374 States to enter: {Fail}

```

## "On transition" events
```py
DebugEvent(source='s0', event='s0Event', data='{}', target='s1')
DebugEvent(source='s1', event='None', data='{}', target='fail')
```

## Traceback
```py
Assertion of the testcase failed.
```
