# Testcase: test501

AssertionError: Assertion failed.

Final configuration: `['fail']`

---

## Logs
```py
DEBUG    statemachine.engines.base:base.py:374 States to enter: {S0}
DEBUG    statemachine.io.scxml.actions:actions.py:443 Error executing actions
Traceback (most recent call last):
  File "/home/macedo/projects/python-statemachine/statemachine/io/scxml/actions.py", line 441, in datamodel
    act(machine=machine)
    ~~~^^^^^^^^^^^^^^^^^
  File "/home/macedo/projects/python-statemachine/statemachine/io/scxml/actions.py", line 412, in data_initializer
    value = _eval(action.expr, **kwargs)
  File "/home/macedo/projects/python-statemachine/statemachine/io/scxml/actions.py", line 125, in _eval
    return eval(expr, {}, kwargs)
  File "<string>", line 1, in <module>
    import sys;exec(eval(sys.stdin.readline()))
    ^^^^^^^^^^^^^
NameError: name '_ioprocessors' is not defined
DEBUG    statemachine.engines.sync:sync.py:64 Processing loop started: s0
DEBUG    statemachine.engines.sync:sync.py:89 Eventless/internal queue: {transition * from S0 to Fail}
DEBUG    statemachine.engines.base:base.py:283 States to exit: {S0}
DEBUG    statemachine.engines.base:base.py:374 States to enter: {Fail}
DEBUG    statemachine.engines.sync:sync.py:116 External event: TriggerData(machine=<weakproxy at 0x7f16fe00a200; to 'statemachine.io.test501' at 0x7f16fe004590>, event=Event('foo', delay=0, internal=False), send_id='b0ba7e77602043a48167a289aab6f6c1', _target=None, execution_time=1733943927.7000527, model=Model(state=fail), args=(), kwargs={})
DEBUG    statemachine.engines.sync:sync.py:131 Enabled transitions: {}
DEBUG    statemachine.engines.sync:sync.py:116 External event: TriggerData(machine=<weakproxy at 0x7f16fe00a200; to 'statemachine.io.test501' at 0x7f16fe004590>, event=Event('timeout', delay=2000.0, internal=False), send_id='8fdcb6fae51f49148b4df0070226dce0', _target=None, execution_time=1733943929.7000864, model=Model(state=fail), args=(), kwargs={})
DEBUG    statemachine.engines.sync:sync.py:131 Enabled transitions: {}

```

## "On transition" events
```py
DebugEvent(source='s0', event='error.execution', data='{\'event_id\': None, \'error\': NameError("name \'_ioprocessors\' is not defined")}', target='fail')
```

## Traceback
```py
Assertion of the testcase failed.
```
