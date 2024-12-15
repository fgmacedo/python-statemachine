# Testcase: test533

AssertionError: Assertion failed.

Final configuration: `['fail']`

---

## Logs
```py
DEBUG    statemachine.engines.base:base.py:415 States to enter: {S1}
DEBUG    statemachine.engines.base:base.py:93 New event 'foo' put on the 'internal' queue
DEBUG    statemachine.engines.base:base.py:93 New event 'bar' put on the 'internal' queue
DEBUG    statemachine.engines.sync:sync.py:64 Processing loop started: s1
DEBUG    statemachine.engines.sync:sync.py:89 Eventless/internal queue: {transition  from S1 to P}
DEBUG    statemachine.engines.base:base.py:339 States to exit: {S1}
DEBUG    statemachine.engines.base:base.py:415 States to enter: {P, Ps1, Ps2}
DEBUG    statemachine.engines.sync:sync.py:89 Eventless/internal queue: {transition foo from P to Ps1}
DEBUG    statemachine.engines.base:base.py:339 States to exit: {Ps2, Ps1}
DEBUG    statemachine.io.scxml.actions:actions.py:259 Assign: Var3 = 1
DEBUG    statemachine.io.scxml.actions:actions.py:259 Assign: Var2 = 1
DEBUG    statemachine.engines.base:base.py:415 States to enter: {Ps1}
DEBUG    statemachine.io.scxml.actions:actions.py:259 Assign: Var4 = 1
DEBUG    statemachine.io.scxml.actions:actions.py:180 Cond Var4==1 -> True
DEBUG    statemachine.engines.sync:sync.py:89 Eventless/internal queue: {transition bar from P to S2}
DEBUG    statemachine.engines.base:base.py:339 States to exit: {Ps1, P}
DEBUG    statemachine.io.scxml.actions:actions.py:259 Assign: Var2 = 2
DEBUG    statemachine.io.scxml.actions:actions.py:259 Assign: Var1 = 1
DEBUG    statemachine.engines.base:base.py:415 States to enter: {S2}
DEBUG    statemachine.io.scxml.actions:actions.py:180 Cond Var1==2 -> False
DEBUG    statemachine.engines.sync:sync.py:89 Eventless/internal queue: {transition  from S2 to Fail}
DEBUG    statemachine.engines.base:base.py:339 States to exit: {S2}
DEBUG    statemachine.engines.base:base.py:415 States to enter: {Fail}

```

## "On transition" events
```py
OnEnterState(state='s1', event='__initial__', data='{}')
OnTransition(source='s1', event='None', data='{}', target='p')
OnEnterState(state='p', event='None', data='{}')
OnEnterState(state='ps1', event='None', data='{}')
OnEnterState(state='ps2', event='None', data='{}')
OnTransition(source='p', event='foo', data='{}', target='ps1')
OnEnterState(state='ps1', event='foo', data='{}')
OnTransition(source='p', event='bar', data='{}', target='s2')
OnEnterState(state='s2', event='bar', data='{}')
OnTransition(source='s2', event='None', data='{}', target='fail')
OnEnterState(state='fail', event='None', data='{}')
```

## Traceback
```py
Assertion of the testcase failed.
```
