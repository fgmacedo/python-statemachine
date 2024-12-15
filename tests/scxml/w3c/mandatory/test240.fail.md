# Testcase: test240

AssertionError: Assertion failed.

Final configuration: `['fail']`

---

## Logs
```py
DEBUG    pydot:__init__.py:15 pydot initializing
DEBUG    pydot:__init__.py:16 pydot 3.0.3
DEBUG    pydot.dot_parser:dot_parser.py:43 pydot dot_parser module initializing
DEBUG    pydot.core:core.py:20 pydot core module initializing
DEBUG    statemachine.engines.base:base.py:415 States to enter: {S0, S01}
DEBUG    statemachine.engines.base:base.py:93 New event 'timeout' put on the 'external' queue
DEBUG    statemachine.engines.sync:sync.py:64 Processing loop started: {s0, s01}
DEBUG    statemachine.engines.sync:sync.py:116 External event: timeout
DEBUG    statemachine.engines.sync:sync.py:131 Enabled transitions: {transition timeout from S0 to Fail}
DEBUG    statemachine.engines.base:base.py:339 States to exit: {S01, S0}
DEBUG    statemachine.engines.base:base.py:415 States to enter: {Fail}

```

## "On transition" events
```py
OnEnterState(state='s0', event='__initial__', data='{}')
OnEnterState(state='s01', event='__initial__', data='{}')
OnTransition(source='s0', event='timeout', data='{}', target='fail')
OnEnterState(state='fail', event='timeout', data='{}')
```

## Traceback
```py
Assertion of the testcase failed.
```
