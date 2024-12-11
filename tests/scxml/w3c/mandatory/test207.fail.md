# Testcase: test207

AssertionError: Assertion failed.

Final configuration: `No configuration`

---

## Logs
```py
DEBUG    statemachine.engines.base:base.py:374 States to enter: {S0, S01}
DEBUG    statemachine.engines.sync:sync.py:64 Processing loop started: ['s0', 's01']
DEBUG    statemachine.engines.sync:sync.py:116 External event: TriggerData(machine=<weakproxy at 0x7efc22ac3d30; to 'statemachine.io.test207' at 0x7efc22b08590>, event=Event('timeout', delay=2000.0, internal=False), send_id='c56c759204124df98a1d96e2678a307a', _target=None, execution_time=1733943926.5340483, model=Model(state=['s0', 's01']), args=(), kwargs={})
DEBUG    statemachine.engines.sync:sync.py:131 Enabled transitions: {transition timeout from S0 to }
DEBUG    statemachine.engines.base:base.py:283 States to exit: {S0, S01}
DEBUG    statemachine.engines.base:base.py:374 States to enter: {}

```

## "On transition" events
```py
DebugEvent(source='s0', event='timeout', data='{}', target='')
```

## Traceback
```py
Assertion of the testcase failed.
```
