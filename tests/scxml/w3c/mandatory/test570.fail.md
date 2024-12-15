# Testcase: test570

AssertionError: Assertion failed.

Final configuration: `['fail']`

---

## Logs
```py
DEBUG    statemachine.engines.base:base.py:415 States to enter: {P0, P0s1, P0s2, P0s11, P0s21}
DEBUG    statemachine.engines.base:base.py:93 New event 'timeout' put on the 'external' queue
DEBUG    statemachine.engines.base:base.py:93 New event 'e1' put on the 'internal' queue
DEBUG    statemachine.engines.base:base.py:93 New event 'e2' put on the 'internal' queue
DEBUG    statemachine.engines.sync:sync.py:64 Processing loop started: {p0, p0s1, p0s2, p0s11, p0s21}
DEBUG    statemachine.engines.sync:sync.py:89 Eventless/internal queue: {transition e1 from P0s11 to P0s1final}
DEBUG    statemachine.engines.base:base.py:339 States to exit: {P0s11}
DEBUG    statemachine.engines.base:base.py:415 States to enter: {P0s1final}
DEBUG    statemachine.engines.base:base.py:93 New event 'done.state.p0s1' put on the 'internal' queue
DEBUG    statemachine.engines.sync:sync.py:89 Eventless/internal queue: {transition e2 from P0s21 to P0s2final}
DEBUG    statemachine.engines.base:base.py:339 States to exit: {P0s21}
DEBUG    statemachine.engines.base:base.py:415 States to enter: {P0s2final}
DEBUG    statemachine.engines.base:base.py:93 New event 'done.state.p0s2' put on the 'internal' queue
DEBUG    statemachine.engines.sync:sync.py:89 Eventless/internal queue: {transition done.state.p0s2 from P0 to S1}
DEBUG    statemachine.engines.base:base.py:339 States to exit: {P0s2final, P0s1final, P0s2, P0s1, P0}
DEBUG    statemachine.engines.base:base.py:415 States to enter: {S1}
DEBUG    statemachine.engines.sync:sync.py:116 External event: timeout
DEBUG    statemachine.engines.sync:sync.py:131 Enabled transitions: {transition * from S1 to Fail}
DEBUG    statemachine.engines.base:base.py:339 States to exit: {S1}
DEBUG    statemachine.engines.base:base.py:415 States to enter: {Fail}

```

## "On transition" events
```py
OnEnterState(state='p0', event='__initial__', data='{}')
OnEnterState(state='p0s1', event='__initial__', data='{}')
OnEnterState(state='p0s2', event='__initial__', data='{}')
OnEnterState(state='p0s11', event='__initial__', data='{}')
OnEnterState(state='p0s21', event='__initial__', data='{}')
OnTransition(source='p0s11', event='e1', data='{}', target='p0s1final')
OnEnterState(state='p0s1final', event='e1', data='{}')
OnTransition(source='p0s21', event='e2', data='{}', target='p0s2final')
OnEnterState(state='p0s2final', event='e2', data='{}')
OnTransition(source='p0', event='done.state.p0s2', data="{'donedata': {}}", target='s1')
OnEnterState(state='s1', event='done.state.p0s2', data="{'donedata': {}}")
OnTransition(source='s1', event='timeout', data='{}', target='fail')
OnEnterState(state='fail', event='timeout', data='{}')
```

## Traceback
```py
Assertion of the testcase failed.
```
