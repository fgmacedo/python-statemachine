# Testcase: test399

AssertionError: Assertion failed.

Final configuration: `['fail']`

---

## Logs
```py
DEBUG    statemachine.engines.base:base.py:374 States to enter: {S0, S01}
DEBUG    statemachine.engines.sync:sync.py:64 Processing loop started: ['s0', 's01']
DEBUG    statemachine.engines.sync:sync.py:89 Eventless/internal queue: {transition foo bar from S01 to S02}
DEBUG    statemachine.engines.base:base.py:283 States to exit: {S01}
DEBUG    statemachine.engines.base:base.py:374 States to enter: {S02}
DEBUG    statemachine.engines.sync:sync.py:89 Eventless/internal queue: {transition foo bar from S02 to S03}
DEBUG    statemachine.engines.base:base.py:283 States to exit: {S02}
DEBUG    statemachine.engines.base:base.py:374 States to enter: {S03}
DEBUG    statemachine.engines.sync:sync.py:116 External event: TriggerData(machine=<weakproxy at 0x7f3c5f2e0a40; to 'statemachine.io.test399' at 0x7f3c5f217e00>, event=Event('timeout', delay=2000.0, internal=False), send_id='5df67c4a1d2c4ef790da91beab398028', _target=None, execution_time=1733943927.648826, model=Model(state=['s0', 's03']), args=(), kwargs={})
DEBUG    statemachine.engines.sync:sync.py:131 Enabled transitions: {transition timeout from S0 to Fail}
DEBUG    statemachine.engines.base:base.py:283 States to exit: {S0, S03}
DEBUG    statemachine.engines.base:base.py:374 States to enter: {Fail}

```

## "On transition" events
```py
DebugEvent(source='s01', event='foo', data='{}', target='s02')
DebugEvent(source='s02', event='bar', data='{}', target='s03')
DebugEvent(source='s0', event='timeout', data='{}', target='fail')
```

## Traceback
```py
Assertion of the testcase failed.
```
