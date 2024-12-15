# Testcase: test446

AssertionError: Assertion failed.

Final configuration: `['fail']`

---

## Logs
```py
DEBUG    statemachine.engines.base:base.py:415 States to enter: {S0}
DEBUG    statemachine.engines.sync:sync.py:64 Processing loop started: s0
DEBUG    statemachine.engines.base:base.py:93 New event 'error.execution' put on the 'internal' queue
DEBUG    statemachine.engines.sync:sync.py:89 Eventless/internal queue: {transition  from S0 to Fail}
DEBUG    statemachine.engines.base:base.py:339 States to exit: {S0}
DEBUG    statemachine.engines.base:base.py:415 States to enter: {Fail}

```

## "On transition" events
```py
OnEnterState(state='s0', event='__initial__', data='{}')
OnTransition(source='s0', event='None', data='{}', target='fail')
OnEnterState(state='fail', event='None', data='{}')
```

## Traceback
```py
Assertion of the testcase failed.
```
