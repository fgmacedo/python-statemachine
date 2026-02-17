# Testcase: test561

AssertionError: Assertion failed.

Final configuration: `['fail']`

---

## Logs
```py
DEBUG    statemachine.engines.base:base.py:596 States to enter: {S0}
DEBUG    statemachine.engines.base:base.py:701 Entering state: S0
DEBUG    statemachine.engines.base:base.py:125 New event 'foo' put on the 'external' queue
DEBUG    statemachine.engines.sync:sync.py:78 Processing loop started: s0
DEBUG    statemachine.engines.sync:sync.py:92 Macrostep: eventless/internal queue
DEBUG    statemachine.engines.sync:sync.py:129 Macrostep: external queue
DEBUG    statemachine.engines.sync:sync.py:147 External event: foo
DEBUG    statemachine.engines.base:base.py:125 New event 'error.execution' put on the 'internal' queue
DEBUG    statemachine.engines.sync:sync.py:160 Enabled transitions: {transition * from S0 to Fail}
DEBUG    statemachine.engines.base:base.py:495 States to exit: {S0}
DEBUG    statemachine.engines.base:base.py:596 States to enter: {Fail}
DEBUG    statemachine.engines.base:base.py:701 Entering state: Fail

```

## "On transition" events
```py
OnEnterState(state='s0', event='__initial__', data='{}')
OnTransition(source='s0', event='foo', data='{}', target='fail')
OnEnterState(state='fail', event='foo', data='{}')
```

## Traceback
```py
Assertion of the testcase failed.
```
