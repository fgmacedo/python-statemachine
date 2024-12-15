# Testcase: test234

AssertionError: Assertion failed.

Final configuration: `['fail']`

---

## Logs
```py
DEBUG    statemachine.engines.base:base.py:415 States to enter: {P0, P01, P02}
DEBUG    statemachine.engines.base:base.py:93 New event 'timeout' put on the 'external' queue
DEBUG    statemachine.engines.sync:sync.py:64 Processing loop started: {p0, p01, p02}
DEBUG    statemachine.engines.sync:sync.py:116 External event: timeout
DEBUG    statemachine.engines.sync:sync.py:131 Enabled transitions: {transition timeout from P0 to Fail}
DEBUG    statemachine.engines.base:base.py:339 States to exit: {P02, P01, P0}
DEBUG    statemachine.engines.base:base.py:415 States to enter: {Fail}

```

## "On transition" events
```py
OnEnterState(state='p0', event='__initial__', data='{}')
OnEnterState(state='p01', event='__initial__', data='{}')
OnEnterState(state='p02', event='__initial__', data='{}')
OnTransition(source='p0', event='timeout', data='{}', target='fail')
OnEnterState(state='fail', event='timeout', data='{}')
```

## Traceback
```py
Assertion of the testcase failed.
```
