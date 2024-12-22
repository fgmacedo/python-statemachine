# Testcase: test422

AssertionError: Assertion failed.

Final configuration: `['fail']`

---

## Logs
```py
DEBUG    pydot:__init__.py:15 pydot initializing
DEBUG    pydot:__init__.py:16 pydot 3.0.3
DEBUG    pydot.dot_parser:dot_parser.py:43 pydot dot_parser module initializing
DEBUG    pydot.core:core.py:20 pydot core module initializing
DEBUG    statemachine.engines.base:base.py:415 States to enter: {S1, S11}
DEBUG    statemachine.engines.base:base.py:438 Entering state: S1
DEBUG    statemachine.engines.base:base.py:93 New event 'timeout' put on the 'external' queue
DEBUG    statemachine.engines.base:base.py:438 Entering state: S11
DEBUG    statemachine.engines.sync:sync.py:64 Processing loop started: {s1, s11}
DEBUG    statemachine.engines.sync:sync.py:89 Eventless/internal queue: {transition  from S11 to S12}
DEBUG    statemachine.engines.base:base.py:339 States to exit: {S11}
DEBUG    statemachine.engines.base:base.py:415 States to enter: {S12}
DEBUG    statemachine.engines.base:base.py:438 Entering state: S12
DEBUG    statemachine.engines.sync:sync.py:116 External event: timeout
DEBUG    statemachine.io.scxml.actions:actions.py:183 Cond Var1==2 -> False
DEBUG    statemachine.engines.sync:sync.py:131 Enabled transitions: {transition timeout from S1 to Fail}
DEBUG    statemachine.engines.base:base.py:339 States to exit: {S12, S1}
DEBUG    statemachine.engines.base:base.py:415 States to enter: {Fail}
DEBUG    statemachine.engines.base:base.py:438 Entering state: Fail

```

## "On transition" events
```py
OnEnterState(state='s1', event='__initial__', data='{}')
OnTransition(source='', event='__initial__', data='{}', target='s1')
OnEnterState(state='s11', event='__initial__', data='{}')
OnTransition(source='s11', event='None', data='{}', target='s12')
OnEnterState(state='s12', event='None', data='{}')
OnTransition(source='s1', event='timeout', data='{}', target='fail')
OnEnterState(state='fail', event='timeout', data='{}')
```

## Traceback
```py
Assertion of the testcase failed.
```
