# Testcase: test192

AssertionError: Assertion failed.

Final configuration: `['fail']`

---

## Logs
```py
DEBUG    statemachine.engines.base:base.py:374 States to enter: {S0, S01}
DEBUG    statemachine.engines.sync:sync.py:64 Processing loop started: ['s0', 's01']
DEBUG    statemachine.engines.sync:sync.py:116 External event: TriggerData(machine=<weakproxy at 0x7fd4c5346ca0; to 'statemachine.io.test192' at 0x7fd4c5429400>, event=Event('timeout', delay=2000.0, internal=False), send_id='a3f00d7e247a45d4bffc85ffc3540742', _target=None, execution_time=1733943932.6457262, model=Model(state=['s0', 's01']), args=(), kwargs={})
DEBUG    statemachine.engines.sync:sync.py:131 Enabled transitions: {transition timeout from S0 to Fail}
DEBUG    statemachine.engines.base:base.py:283 States to exit: {S0, S01}
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
