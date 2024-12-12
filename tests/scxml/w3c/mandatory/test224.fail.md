# Testcase: test224

AssertionError: Assertion failed.

Final configuration: `['fail']`

---

## Logs
```py
DEBUG    statemachine.engines.base:base.py:374 States to enter: {S0}
DEBUG    statemachine.engines.sync:sync.py:64 Processing loop started: s0
DEBUG    statemachine.engines.sync:sync.py:116 External event: TriggerData(machine=<weakproxy at 0x7efc22b150d0; to 'statemachine.io.test224' at 0x7efc22b086e0>, event=Event('timeout', delay=1000.0, internal=False), send_id='12659b12b1564599a696ff11a69db53d', _target=None, execution_time=1733943927.5427735, model=Model(state=s0), args=(), kwargs={})
DEBUG    statemachine.engines.sync:sync.py:131 Enabled transitions: {transition * from S0 to S1}
DEBUG    statemachine.engines.base:base.py:283 States to exit: {S0}
DEBUG    statemachine.engines.base:base.py:374 States to enter: {S1}
DEBUG    statemachine.engines.sync:sync.py:89 Eventless/internal queue: {transition  from S1 to Fail}
DEBUG    statemachine.engines.base:base.py:283 States to exit: {S1}
DEBUG    statemachine.engines.base:base.py:374 States to enter: {Fail}

```

## "On transition" events
```py
DebugEvent(source='s0', event='timeout', data='{}', target='s1')
DebugEvent(source='s1', event='None', data='{}', target='fail')
```

## Traceback
```py
Assertion of the testcase failed.
```
