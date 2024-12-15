# Testcase: test338

AssertionError: Assertion failed.

Final configuration: `['s0']`

---

## Logs
```py
DEBUG    statemachine.engines.base:base.py:415 States to enter: {S0}
DEBUG    statemachine.engines.base:base.py:93 New event 'timeout' put on the 'external' queue
DEBUG    statemachine.engines.sync:sync.py:64 Processing loop started: s0
DEBUG    statemachine.engines.sync:sync.py:116 External event: timeout
DEBUG    statemachine.engines.sync:sync.py:131 Enabled transitions: {}

```

## "On transition" events
```py
OnEnterState(state='s0', event='__initial__', data='{}')
```

## Traceback
```py
Assertion of the testcase failed.
```
