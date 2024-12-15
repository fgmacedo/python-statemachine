# Testcase: test223

AssertionError: Assertion failed.

Final configuration: `['fail']`

---

## Logs
```py
DEBUG    statemachine.engines.base:base.py:415 States to enter: {S0}
DEBUG    statemachine.engines.base:base.py:93 New event 'timeout' put on the 'external' queue
DEBUG    statemachine.engines.sync:sync.py:64 Processing loop started: s0
DEBUG    statemachine.engines.sync:sync.py:116 External event: timeout
DEBUG    statemachine.engines.sync:sync.py:131 Enabled transitions: {transition * from S0 to S1}
DEBUG    statemachine.engines.base:base.py:339 States to exit: {S0}
DEBUG    statemachine.engines.base:base.py:415 States to enter: {S1}
DEBUG    statemachine.io.scxml.actions:actions.py:180 Cond Var1 -> None
DEBUG    statemachine.engines.sync:sync.py:89 Eventless/internal queue: {transition  from S1 to Fail}
DEBUG    statemachine.engines.base:base.py:339 States to exit: {S1}
DEBUG    statemachine.engines.base:base.py:415 States to enter: {Fail}

```

## "On transition" events
```py
OnEnterState(state='s0', event='__initial__', data='{}')
OnTransition(source='s0', event='timeout', data='{}', target='s1')
OnEnterState(state='s1', event='timeout', data='{}')
OnTransition(source='s1', event='None', data='{}', target='fail')
OnEnterState(state='fail', event='None', data='{}')
```

## Traceback
```py
Assertion of the testcase failed.
```
