# Testcase: test401

AssertionError: Assertion failed.

Final configuration: `['fail']`

---

## Logs
```py
DEBUG    statemachine.engines.base:base.py:374 States to enter: {S0}
DEBUG    statemachine.io.scxml.actions:actions.py:467 Error executing actions
Traceback (most recent call last):
  File "/home/macedo/projects/python-statemachine/statemachine/io/scxml/actions.py", line 463, in __call__
    action(*args, **kwargs)
    ~~~~~~^^^^^^^^^^^^^^^^^
  File "/home/macedo/projects/python-statemachine/statemachine/io/scxml/actions.py", line 236, in __call__
    obj = getattr(obj, p)
AttributeError: 'Model' object has no attribute 'foo'
DEBUG    statemachine.engines.sync:sync.py:64 Processing loop started: s0
DEBUG    statemachine.engines.sync:sync.py:116 External event: TriggerData(machine=<weakproxy at 0x7fbd01b8c220; to 'statemachine.io.test401' at 0x7fbd01b374d0>, event=Event('foo', delay=0, internal=False), send_id='3d6a3122afb64231b8b8cac7e74e6170', _target=None, execution_time=1733943928.6420543, model=Model(state=s0), args=(), kwargs={})
DEBUG    statemachine.engines.sync:sync.py:131 Enabled transitions: {transition foo from S0 to Fail}
DEBUG    statemachine.engines.base:base.py:283 States to exit: {S0}
DEBUG    statemachine.engines.base:base.py:374 States to enter: {Fail}

```

## "On transition" events
```py
DebugEvent(source='s0', event='foo', data='{}', target='fail')
```

## Traceback
```py
Assertion of the testcase failed.
```
