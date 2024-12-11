# Testcase: test234

AssertionError: Assertion failed.

Final configuration: `['fail']`

---

## Logs
```py
DEBUG    statemachine.engines.base:base.py:374 States to enter: {P0, P01}
DEBUG    statemachine.engines.sync:sync.py:64 Processing loop started: ['p0', 'p01']
DEBUG    statemachine.engines.sync:sync.py:116 External event: TriggerData(machine=<weakproxy at 0x7fd4c533acf0; to 'statemachine.io.test234' at 0x7fd4c54292b0>, event=Event('timeout', delay=3000.0, internal=False), send_id='fa21c3b086b346cba8302840844f1f63', _target=None, execution_time=1733943928.6257, model=Model(state=['p0', 'p01']), args=(), kwargs={})
DEBUG    statemachine.engines.sync:sync.py:131 Enabled transitions: {transition timeout from P0 to Fail}
DEBUG    statemachine.engines.base:base.py:283 States to exit: {P0, P01}
DEBUG    statemachine.engines.base:base.py:374 States to enter: {Fail}

```

## "On transition" events
```py
DebugEvent(source='p0', event='timeout', data='{}', target='fail')
```

## Traceback
```py
Assertion of the testcase failed.
```
