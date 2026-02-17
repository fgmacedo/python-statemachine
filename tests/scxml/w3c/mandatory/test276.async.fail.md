# Testcase: test276

AssertionError: Assertion failed.

Final configuration: `['s0']`

---

## Logs
```py
DEBUG    statemachine.engines.base:base.py:125 New event '__initial__' put on the 'external' queue
DEBUG    statemachine.engines.async_:async_.py:358 Processing loop started: None
DEBUG    statemachine.engines.async_:async_.py:369 Macrostep: eventless/internal queue
DEBUG    statemachine.engines.async_:async_.py:402 Macrostep: external queue
DEBUG    statemachine.engines.async_:async_.py:420 External event: __initial__
DEBUG    statemachine.engines.base:base.py:596 States to enter: {S0}
DEBUG    statemachine.engines.async_:async_.py:224 Entering state: S0
DEBUG    statemachine.engines.async_:async_.py:369 Macrostep: eventless/internal queue
DEBUG    statemachine.engines.async_:async_.py:402 Macrostep: external queue

```

## "On transition" events
```py
OnEnterState(state='s0', event='__initial__', data='{}')
```

## Traceback
```py
Assertion of the testcase failed.
```
