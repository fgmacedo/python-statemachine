# Testcase: test561

AssertionError: Assertion failed.

Final configuration: `['fail']`

---

## Logs
```py
DEBUG    statemachine.engines.base:base.py:374 States to enter: {S0}
DEBUG    statemachine.engines.sync:sync.py:64 Processing loop started: s0
DEBUG    statemachine.engines.sync:sync.py:116 External event: TriggerData(machine=<weakproxy at 0x7fd3aca772e0; to 'statemachine.io.test561' at 0x7fd3acc34ec0>, event=Event('foo', delay=0, internal=False), send_id='1f50c54a640f4a89b221c4d1152d62c9', _target=None, execution_time=1734003009.39881, model=Model(state=s0), args=(), kwargs={})
DEBUG    statemachine.engines.sync:sync.py:131 Enabled transitions: {transition * from S0 to Fail}
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
