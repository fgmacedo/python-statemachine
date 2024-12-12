# Testcase: test533

AssertionError: Assertion failed.

Final configuration: `['fail']`

---

## Logs
```py
DEBUG    statemachine.engines.base:base.py:374 States to enter: {S1}
DEBUG    statemachine.engines.sync:sync.py:64 Processing loop started: s1
DEBUG    statemachine.engines.sync:sync.py:89 Eventless/internal queue: {transition  from S1 to P}
DEBUG    statemachine.engines.base:base.py:283 States to exit: {S1}
DEBUG    statemachine.engines.base:base.py:374 States to enter: {P, Ps1, Ps2}
DEBUG    statemachine.engines.sync:sync.py:89 Eventless/internal queue: {transition foo from P to Ps1}
DEBUG    statemachine.io.scxml.actions:actions.py:244 Assign: Var2 = 1
DEBUG    statemachine.io.scxml.actions:actions.py:244 Assign: Var3 = 1
DEBUG    statemachine.engines.base:base.py:283 States to exit: {Ps1, Ps2}
DEBUG    statemachine.io.scxml.actions:actions.py:244 Assign: Var4 = 1
DEBUG    statemachine.engines.base:base.py:374 States to enter: {Ps1}
DEBUG    statemachine.io.scxml.actions:actions.py:170 Cond Var4==1 -> True
DEBUG    statemachine.engines.sync:sync.py:89 Eventless/internal queue: {transition bar from P to S2}
DEBUG    statemachine.io.scxml.actions:actions.py:244 Assign: Var1 = 1
DEBUG    statemachine.io.scxml.actions:actions.py:244 Assign: Var2 = 2
DEBUG    statemachine.engines.base:base.py:283 States to exit: {P, Ps1}
DEBUG    statemachine.engines.base:base.py:374 States to enter: {S2}
DEBUG    statemachine.io.scxml.actions:actions.py:170 Cond Var1==2 -> False
DEBUG    statemachine.engines.sync:sync.py:89 Eventless/internal queue: {transition  from S2 to Fail}
DEBUG    statemachine.engines.base:base.py:283 States to exit: {S2}
DEBUG    statemachine.engines.base:base.py:374 States to enter: {Fail}

```

## "On transition" events
```py
DebugEvent(source='s1', event='None', data='{}', target='p')
DebugEvent(source='p', event='foo', data='{}', target='ps1')
DebugEvent(source='p', event='bar', data='{}', target='s2')
DebugEvent(source='s2', event='None', data='{}', target='fail')
```

## Traceback
```py
Assertion of the testcase failed.
```
