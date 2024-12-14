# Testcase: test570

AssertionError: Assertion failed.

Final configuration: `['fail']`

---

## Logs
```py
DEBUG    statemachine.engines.base:base.py:386 States to enter: {P0, P0s1, P0s11, P0s2, P0s21}
DEBUG    statemachine.engines.sync:sync.py:64 Processing loop started: ['p0', 'p0s1', 'p0s11', 'p0s2', 'p0s21']
DEBUG    statemachine.engines.sync:sync.py:89 Eventless/internal queue: {transition e1 from P0s11 to P0s1final}
DEBUG    statemachine.engines.base:base.py:276 States to exit: {P0s11}
DEBUG    statemachine.engines.base:base.py:386 States to enter: {P0s1final}
DEBUG    statemachine.engines.sync:sync.py:89 Eventless/internal queue: {transition e2 from P0s21 to P0s2final}
DEBUG    statemachine.engines.base:base.py:276 States to exit: {P0s21}
DEBUG    statemachine.engines.base:base.py:386 States to enter: {P0s2final}
DEBUG    statemachine.engines.sync:sync.py:89 Eventless/internal queue: {transition done.state.p0s2 from P0 to S1}
DEBUG    statemachine.engines.base:base.py:276 States to exit: {P0, P0s1, P0s2, P0s1final, P0s2final}
DEBUG    statemachine.engines.base:base.py:386 States to enter: {S1}
DEBUG    statemachine.engines.sync:sync.py:116 External event: timeout
DEBUG    statemachine.engines.sync:sync.py:131 Enabled transitions: {transition * from S1 to Fail}
DEBUG    statemachine.engines.base:base.py:276 States to exit: {S1}
DEBUG    statemachine.engines.base:base.py:386 States to enter: {Fail}

```

## "On transition" events
```py
DebugEvent(source='p0s11', event='e1', data='{}', target='p0s1final')
DebugEvent(source='p0s21', event='e2', data='{}', target='p0s2final')
DebugEvent(source='p0', event='done.state.p0s2', data="{'donedata': {}}", target='s1')
DebugEvent(source='s1', event='timeout', data='{}', target='fail')
```

## Traceback
```py
Assertion of the testcase failed.
```
