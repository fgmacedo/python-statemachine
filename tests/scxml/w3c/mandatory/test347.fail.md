# Testcase: test347

AssertionError: Assertion failed.

Final configuration: `['fail']`

---

## Logs
```py
DEBUG    statemachine.engines.base:base.py:374 States to enter: {S0, S01}
DEBUG    statemachine.engines.sync:sync.py:64 Processing loop started: ['s0', 's01']
DEBUG    statemachine.engines.sync:sync.py:116 External event: TriggerData(machine=<weakproxy at 0x7f7dedad1c10; to 'statemachine.io.test347' at 0x7f7deda35a90>, event=Event('timeout', delay=20000.0, internal=False), send_id='918fd577b4fe436599b82f59e2bf2917', _target=None, execution_time=1733943947.7045631, model=Model(state=['s0', 's01']), args=(), kwargs={})
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
