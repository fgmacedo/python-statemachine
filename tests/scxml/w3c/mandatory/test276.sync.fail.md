# Testcase: test276

AssertionError: Assertion failed.

Final configuration: `['s0']`

---

## Logs
```py
DEBUG    statemachine.engines.base:base.py:596 States to enter: {S0}
DEBUG    statemachine.engines.base:base.py:701 Entering state: S0
DEBUG    statemachine.engines.sync:sync.py:78 Processing loop started: s0
DEBUG    statemachine.engines.sync:sync.py:92 Macrostep: eventless/internal queue
DEBUG    statemachine.engines.sync:sync.py:129 Macrostep: external queue

```

## "On transition" events
```py
OnEnterState(state='s0', event='__initial__', data='{}')
```

## Traceback
```py
Assertion of the testcase failed.
```
