# Testcase: test350

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
                 ^^^^^^^^^^
NameError: name '_sessionid' is not defined
DEBUG    statemachine.engines.sync:sync.py:64 Processing loop started: s0
DEBUG    statemachine.engines.sync:sync.py:89 Eventless/internal queue: {transition * from S0 to Fail}
DEBUG    statemachine.engines.base:base.py:283 States to exit: {S0}
DEBUG    statemachine.engines.base:base.py:374 States to enter: {Fail}
DEBUG    statemachine.engines.sync:sync.py:116 External event: TriggerData(machine=<weakproxy at 0x7f56c6be67f0; to 'statemachine.io.test350' at 0x7f56c654f770>, event=Event('s0Event', delay=0, internal=False), send_id='cc3d92954a2b482d9052d25ecee0312c', _target=None, execution_time=1733943923.5413163, model=Model(state=fail), args=(), kwargs={})
DEBUG    statemachine.engines.sync:sync.py:131 Enabled transitions: {}
DEBUG    statemachine.engines.sync:sync.py:116 External event: TriggerData(machine=<weakproxy at 0x7f56c6be67f0; to 'statemachine.io.test350' at 0x7f56c654f770>, event=Event('timeout', delay=2000.0, internal=False), send_id='6e0da412f8784941953f0bb447c31531', _target=None, execution_time=1733943925.5412385, model=Model(state=fail), args=(), kwargs={})
DEBUG    statemachine.engines.sync:sync.py:131 Enabled transitions: {}

```

## "On transition" events
```py
DebugEvent(source='s0', event='error.execution', data='{\'event_id\': None, \'error\': NameError("name \'_sessionid\' is not defined")}', target='fail')
```

## Traceback
```py
Assertion of the testcase failed.
```
