# Testcase: test236

AssertionError: Assertion failed.

Final configuration: `['s0']`

---

## Logs
```py
DEBUG    statemachine.engines.base:base.py:374 States to enter: {S0}
DEBUG    statemachine.engines.sync:sync.py:64 Processing loop started: s0
DEBUG    statemachine.engines.sync:sync.py:116 External event: TriggerData(machine=<weakproxy at 0x7f16fdfb67a0; to 'statemachine.io.test236' at 0x7f16fdf51940>, event=Event('timeout', delay=2000.0, internal=False), send_id='745d6d958ee54a1ca9fd9900d54af04f', _target=None, execution_time=1733943925.4977725, model=Model(state=s0), args=(), kwargs={})
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
