# Testcase: test338

AssertionError: Assertion failed.

Final configuration: `['s0']`

---

## Logs
```py
DEBUG    statemachine.engines.base:base.py:374 States to enter: {S0}
DEBUG    statemachine.engines.sync:sync.py:64 Processing loop started: s0
DEBUG    statemachine.engines.sync:sync.py:116 External event: TriggerData(machine=<weakproxy at 0x7f56c65fde90; to 'statemachine.io.test338' at 0x7f56c654ea50>, event=Event('timeout', delay=2000.0, internal=False), send_id='da02e3b153ad4d2a89b1fcb8f51e035a', _target=None, execution_time=1733943932.702409, model=Model(state=s0), args=(), kwargs={})
DEBUG    statemachine.engines.sync:sync.py:131 Enabled transitions: {}

```

## "On transition" events
```py
No events
```

## Traceback
```py
Assertion of the testcase failed.
```
