# Testcase: test553

AssertionError: Assertion failed.

Final configuration: `['fail']`

---

## Logs
```py
DEBUG    statemachine.engines.base:base.py:374 States to enter: {S0}
DEBUG    statemachine.engines.sync:sync.py:64 Processing loop started: s0
DEBUG    statemachine.engines.sync:sync.py:116 External event: TriggerData(machine=<weakproxy at 0x7f074951e8e0; to 'statemachine.io.test553' at 0x7f07495a5d30>, event=Event('event1', delay=0, internal=False), send_id='c835aa050c1c4e1a949936b88bbb9423', _target=None, execution_time=1733943925.6533868, model=Model(state=s0), args=(), kwargs={})
DEBUG    statemachine.engines.sync:sync.py:131 Enabled transitions: {transition event1 from S0 to Fail}
DEBUG    statemachine.engines.base:base.py:283 States to exit: {S0}
DEBUG    statemachine.engines.base:base.py:374 States to enter: {Fail}
DEBUG    statemachine.engines.sync:sync.py:116 External event: TriggerData(machine=<weakproxy at 0x7f074951e8e0; to 'statemachine.io.test553' at 0x7f07495a5d30>, event=Event('timeout', delay=3000.0, internal=False), send_id='b708e69f8900483cba7e910503452270', _target=None, execution_time=1733943928.6533587, model=Model(state=fail), args=(), kwargs={})
DEBUG    statemachine.engines.sync:sync.py:131 Enabled transitions: {}

```

## "On transition" events
```py
DebugEvent(source='s0', event='event1', data='{}', target='fail')
```

## Traceback
```py
Assertion of the testcase failed.
```
