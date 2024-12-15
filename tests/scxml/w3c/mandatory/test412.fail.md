# Testcase: test412

AssertionError: Assertion failed.

Final configuration: `['fail']`

---

## Logs
```py
DEBUG    statemachine.engines.base:base.py:415 States to enter: {S0, S01, S011}
DEBUG    statemachine.engines.base:base.py:93 New event 'timeout' put on the 'external' queue
DEBUG    statemachine.engines.base:base.py:93 New event 'event1' put on the 'internal' queue
DEBUG    statemachine.engines.base:base.py:93 New event 'event3' put on the 'internal' queue
DEBUG    statemachine.engines.sync:sync.py:64 Processing loop started: {s0, s01, s011}
DEBUG    statemachine.engines.sync:sync.py:89 Eventless/internal queue: {transition  from S011 to S02}
DEBUG    statemachine.engines.base:base.py:339 States to exit: {S011, S01}
DEBUG    statemachine.engines.base:base.py:415 States to enter: {S02}
DEBUG    statemachine.engines.sync:sync.py:89 Eventless/internal queue: {transition event1 from S02 to S03}
DEBUG    statemachine.engines.base:base.py:339 States to exit: {S02}
DEBUG    statemachine.engines.base:base.py:415 States to enter: {S03}
DEBUG    statemachine.engines.sync:sync.py:89 Eventless/internal queue: {transition * from S03 to Fail}
DEBUG    statemachine.engines.base:base.py:339 States to exit: {S03, S0}
DEBUG    statemachine.engines.base:base.py:415 States to enter: {Fail}
DEBUG    statemachine.engines.sync:sync.py:116 External event: timeout
DEBUG    statemachine.engines.sync:sync.py:131 Enabled transitions: {}

```

## "On transition" events
```py
OnEnterState(state='s0', event='__initial__', data='{}')
OnEnterState(state='s01', event='__initial__', data='{}')
OnEnterState(state='s011', event='__initial__', data='{}')
OnTransition(source='s011', event='None', data='{}', target='s02')
OnEnterState(state='s02', event='None', data='{}')
OnTransition(source='s02', event='event1', data='{}', target='s03')
OnEnterState(state='s03', event='event1', data='{}')
OnTransition(source='s03', event='event3', data='{}', target='fail')
OnEnterState(state='fail', event='event3', data='{}')
```

## Traceback
```py
Assertion of the testcase failed.
```
