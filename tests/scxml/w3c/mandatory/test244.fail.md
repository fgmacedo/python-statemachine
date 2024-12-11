# Testcase: test244

AssertionError: Assertion failed.

Final configuration: `['fail']`

---

## Logs
```py
DEBUG    statemachine.engines.base:base.py:374 States to enter: {S0}
DEBUG    statemachine.engines.sync:sync.py:64 Processing loop started: s0
DEBUG    statemachine.engines.sync:sync.py:116 External event: TriggerData(machine=<weakproxy at 0x7f56c65b3920; to 'statemachine.io.test244' at 0x7f56c654f770>, event=Event('timeout', delay=2000.0, internal=False), send_id='35957a5df98a439c9e99d326768ba64e', _target=None, execution_time=1733943929.6695473, model=Model(state=s0), args=(), kwargs={})
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
