# Testcase: test333

AssertionError: Assertion failed.

Final configuration: `['fail']`

---

## Logs
```py
DEBUG    statemachine.engines.base:base.py:374 States to enter: {S0}
DEBUG    statemachine.engines.sync:sync.py:64 Processing loop started: s0
DEBUG    statemachine.engines.sync:sync.py:116 External event: TriggerData(machine=<weakproxy at 0x7f85fc545ad0; to 'statemachine.io.test333' at 0x7f85f7e16270>, event=Event('foo', delay=0, internal=False), send_id='4fd143c528ed44bc95318d4861d04821', _target=None, execution_time=1734002804.2679229, model=Model(state=s0), args=(), kwargs={})
DEBUG    statemachine.engines.sync:sync.py:131 Enabled transitions: {transition * from S0 to Fail}
DEBUG    statemachine.engines.base:base.py:283 States to exit: {S0}
DEBUG    statemachine.engines.base:base.py:374 States to enter: {Fail}

```

## "On transition" events
```py
DebugEvent(source='s0', event='foo', data='{}', target='fail')
```

## Traceback
```py
Assertion of the testcase failed.
```
