# Testcase: test239

AssertionError: Assertion failed.

Final configuration: `['fail']`

---

## Logs
```py
DEBUG    statemachine.engines.base:base.py:374 States to enter: {S0, S01}
DEBUG    statemachine.engines.sync:sync.py:64 Processing loop started: ['s0', 's01']
DEBUG    statemachine.engines.sync:sync.py:116 External event: TriggerData(machine=<weakproxy at 0x7f7dee0951c0; to 'statemachine.io.test239' at 0x7f7deda35be0>, event=Event('timeout', delay=2000.0, internal=False), send_id='c7b351efd17b4dcfac0b8f287757b7b3', _target=None, execution_time=1733943925.4895623, model=Model(state=['s0', 's01']), args=(), kwargs={})
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
