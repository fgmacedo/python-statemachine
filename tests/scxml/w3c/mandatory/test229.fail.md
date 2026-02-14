# Testcase: test229

AssertionError: Assertion failed.

Final configuration: `['fail']`

---

## Logs
```py
DEBUG    statemachine.engines.base:base.py:436 States to enter: {S0}
DEBUG    statemachine.engines.base:base.py:459 Entering state: S0
DEBUG    statemachine.engines.base:base.py:98 New event 'timeout' put on the 'external' queue
DEBUG    statemachine.engines.sync:sync.py:64 Processing loop started: s0
DEBUG    statemachine.engines.sync:sync.py:119 External event: timeout
DEBUG    statemachine.engines.sync:sync.py:134 Enabled transitions: {transition * from S0 to Fail}
DEBUG    statemachine.engines.base:base.py:360 States to exit: {S0}
DEBUG    statemachine.engines.base:base.py:436 States to enter: {Fail}
DEBUG    statemachine.engines.base:base.py:459 Entering state: Fail

```

## "On transition" events
```py
OnEnterState(state='s0', event='__initial__', data='{}')
OnTransition(source='s0', event='timeout', data='{}', target='fail')
OnEnterState(state='fail', event='timeout', data='{}')
```

## Traceback
```py
Assertion of the testcase failed.
```
