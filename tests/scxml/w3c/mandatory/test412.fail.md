# Testcase: test412

AssertionError: Assertion failed.

Final configuration: `['fail']`

---

## Logs
```py
DEBUG    statemachine.engines.base:base.py:374 States to enter: {S0, S01, S011}
DEBUG    statemachine.engines.sync:sync.py:64 Processing loop started: ['s0', 's01', 's011']
DEBUG    statemachine.engines.sync:sync.py:89 Eventless/internal queue: {transition  from S011 to S02}
DEBUG    statemachine.engines.base:base.py:283 States to exit: {S01, S011}
DEBUG    statemachine.engines.base:base.py:374 States to enter: {S02}
DEBUG    statemachine.engines.sync:sync.py:89 Eventless/internal queue: {transition event1 from S02 to S03}
DEBUG    statemachine.engines.base:base.py:283 States to exit: {S02}
DEBUG    statemachine.engines.base:base.py:374 States to enter: {S03}
DEBUG    statemachine.engines.sync:sync.py:89 Eventless/internal queue: {transition * from S03 to Fail}
DEBUG    statemachine.engines.base:base.py:283 States to exit: {S0, S03}
DEBUG    statemachine.engines.base:base.py:374 States to enter: {Fail}
DEBUG    statemachine.engines.sync:sync.py:116 External event: TriggerData(machine=<weakproxy at 0x7f14571eccc0; to 'statemachine.io.test412' at 0x7f14571acad0>, event=Event('timeout', delay=1000.0, internal=False), send_id='0079b1a5dba4420fbaa2fd8e35734039', _target=None, execution_time=1733943929.7031717, model=Model(state=fail), args=(), kwargs={})
DEBUG    statemachine.engines.sync:sync.py:131 Enabled transitions: {}

```

## "On transition" events
```py
DebugEvent(source='s011', event='None', data='{}', target='s02')
DebugEvent(source='s02', event='event1', data='{}', target='s03')
DebugEvent(source='s03', event='event3', data='{}', target='fail')
```

## Traceback
```py
Assertion of the testcase failed.
```
