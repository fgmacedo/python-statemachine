# Testcase: test228

AssertionError: Assertion failed.

Final configuration: `['fail']`

---

## Logs
```py
DEBUG    statemachine.engines.base:base.py:374 States to enter: {S0}
DEBUG    statemachine.engines.sync:sync.py:64 Processing loop started: s0
DEBUG    statemachine.engines.sync:sync.py:116 External event: TriggerData(machine=<weakproxy at 0x7f4a06c3b150; to 'statemachine.io.test228' at 0x7f4a06d82900>, event=Event('timeout', delay=3000.0, internal=False), send_id='a835ae264f144a86aaf9fa7bee07c3f6', _target=None, execution_time=1733943926.5683281, model=Model(state=s0), args=(), kwargs={})
DEBUG    statemachine.engines.sync:sync.py:131 Enabled transitions: {transition * from S0 to Fail}
DEBUG    statemachine.engines.base:base.py:283 States to exit: {S0}
DEBUG    statemachine.engines.base:base.py:374 States to enter: {Fail}

```

## "On transition" events
```py
DebugEvent(source='s0', event='timeout', data='{}', target='fail')
```

## Traceback
```py
Assertion of the testcase failed.
```
