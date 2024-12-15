# Testcase: test343

AssertionError: Assertion failed.

Final configuration: `['fail']`

---

## Logs
```py
DEBUG    statemachine.engines.base:base.py:415 States to enter: {S0, S01}
DEBUG    statemachine.engines.sync:sync.py:64 Processing loop started: {s0, s01}
DEBUG    statemachine.engines.sync:sync.py:89 Eventless/internal queue: {transition  from S01 to S02}
DEBUG    statemachine.engines.base:base.py:339 States to exit: {S01}
DEBUG    statemachine.engines.base:base.py:415 States to enter: {S02}
DEBUG    statemachine.engines.base:base.py:93 New event 'done.state.s0' put on the 'internal' queue
DEBUG    statemachine.engines.sync:sync.py:89 Eventless/internal queue: {transition done.state.s0 from S0 to Fail}
DEBUG    statemachine.engines.base:base.py:339 States to exit: {S02, S0}
DEBUG    statemachine.engines.base:base.py:415 States to enter: {Fail}

```

## "On transition" events
```py
OnEnterState(state='s0', event='__initial__', data='{}')
OnEnterState(state='s01', event='__initial__', data='{}')
OnTransition(source='s01', event='None', data='{}', target='s02')
OnEnterState(state='s02', event='None', data='{}')
OnTransition(source='s0', event='done.state.s0', data="{'donedata': {}}", target='fail')
OnEnterState(state='fail', event='done.state.s0', data="{'donedata': {}}")
```

## Traceback
```py
Assertion of the testcase failed.
```
