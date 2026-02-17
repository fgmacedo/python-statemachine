# Testcase: test558

AssertionError: Assertion failed.

Final configuration: `['fail']`

---

## Logs
```py
DEBUG    statemachine.engines.base:base.py:596 States to enter: {S0}
DEBUG    statemachine.engines.base:base.py:701 Entering state: S0
DEBUG    statemachine.engines.sync:sync.py:78 Processing loop started: s0
DEBUG    statemachine.engines.sync:sync.py:92 Macrostep: eventless/internal queue
DEBUG    statemachine.io.scxml.actions:actions.py:204 Cond var1 == 'this is a string' -> True
DEBUG    statemachine.engines.sync:sync.py:106 Enabled transitions: {transition  from S0 to S1}
DEBUG    statemachine.engines.base:base.py:495 States to exit: {S0}
DEBUG    statemachine.engines.base:base.py:596 States to enter: {S1}
DEBUG    statemachine.engines.base:base.py:701 Entering state: S1
DEBUG    statemachine.engines.sync:sync.py:92 Macrostep: eventless/internal queue
DEBUG    statemachine.io.scxml.actions:actions.py:204 Cond var2 == 'this is a string' -> False
DEBUG    statemachine.engines.sync:sync.py:106 Enabled transitions: {transition  from S1 to Fail}
DEBUG    statemachine.engines.base:base.py:495 States to exit: {S1}
DEBUG    statemachine.engines.base:base.py:596 States to enter: {Fail}
DEBUG    statemachine.engines.base:base.py:701 Entering state: Fail
DEBUG    statemachine.engines.sync:sync.py:92 Macrostep: eventless/internal queue
DEBUG    statemachine.engines.sync:sync.py:129 Macrostep: external queue

```

## "On transition" events
```py
OnEnterState(state='s0', event='__initial__', data='{}')
OnTransition(source='s0', event='None', data='{}', target='s1')
OnEnterState(state='s1', event='None', data='{}')
OnTransition(source='s1', event='None', data='{}', target='fail')
OnEnterState(state='fail', event='None', data='{}')
```

## Traceback
```py
Assertion of the testcase failed.
```
