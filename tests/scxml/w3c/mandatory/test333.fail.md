# Testcase: test333

AssertionError: Assertion failed.

Final configuration: `['fail']`

---

## Logs
```py
DEBUG    pydot:__init__.py:15 pydot initializing
DEBUG    pydot:__init__.py:16 pydot 3.0.3
DEBUG    pydot.dot_parser:dot_parser.py:43 pydot dot_parser module initializing
DEBUG    pydot.core:core.py:20 pydot core module initializing
DEBUG    statemachine.engines.base:base.py:415 States to enter: {S0}
DEBUG    statemachine.engines.base:base.py:93 New event 'foo' put on the 'external' queue
DEBUG    statemachine.engines.sync:sync.py:64 Processing loop started: s0
DEBUG    statemachine.engines.sync:sync.py:116 External event: foo
DEBUG    statemachine.engines.base:base.py:93 New event 'error.execution' put on the 'internal' queue
DEBUG    statemachine.engines.sync:sync.py:131 Enabled transitions: {transition * from S0 to Fail}
DEBUG    statemachine.engines.base:base.py:339 States to exit: {S0}
DEBUG    statemachine.engines.base:base.py:415 States to enter: {Fail}

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
