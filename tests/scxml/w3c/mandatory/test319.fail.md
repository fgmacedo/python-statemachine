# Testcase: test319

AssertionError: Assertion failed.

Final configuration: `['fail']`

---

## Logs
```py
DEBUG    statemachine.engines.base:base.py:374 States to enter: {S0}
DEBUG    statemachine.io.scxml.actions:actions.py:170 Cond _event -> <statemachine.io.scxml.actions.EventDataWrapper object at 0x7fd4c52d9550>
DEBUG    statemachine.engines.sync:sync.py:64 Processing loop started: s0
DEBUG    statemachine.engines.sync:sync.py:89 Eventless/internal queue: {transition bound from S0 to Fail}
DEBUG    statemachine.engines.base:base.py:283 States to exit: {S0}
DEBUG    statemachine.engines.base:base.py:374 States to enter: {Fail}

```

## "On transition" events
```py
DebugEvent(source='s0', event='bound', data='{}', target='fail')
```

## Traceback
```py
Assertion of the testcase failed.
```
