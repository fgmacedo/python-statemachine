# Testcase: test329

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
DEBUG    statemachine.engines.base:base.py:93 New event 'foo' put on the 'internal' queue
DEBUG    statemachine.io.scxml.actions:actions.py:259 Assign: Var1 = 'test329:140074819308912'
DEBUG    statemachine.io.scxml.actions:actions.py:477 Error executing actions
Traceback (most recent call last):
  File "/home/macedo/projects/python-statemachine/statemachine/io/scxml/actions.py", line 473, in __call__
    action(*args, **kwargs)
    ~~~~~~^^^^^^^^^^^^^^^^^
  File "/home/macedo/projects/python-statemachine/statemachine/io/scxml/actions.py", line 254, in __call__
    raise ValueError(
    ...<2 lines>...
    )
ValueError: <assign> 'location' cannot assign to a protected attribute: _sessionid
DEBUG    statemachine.engines.base:base.py:93 New event 'error.execution' put on the 'internal' queue
DEBUG    statemachine.engines.sync:sync.py:64 Processing loop started: s0
DEBUG    statemachine.io.scxml.actions:actions.py:180 Cond Var1==_sessionid -> True
DEBUG    statemachine.engines.sync:sync.py:89 Eventless/internal queue: {transition foo from S0 to S1}
DEBUG    statemachine.engines.base:base.py:339 States to exit: {S0}
DEBUG    statemachine.engines.base:base.py:415 States to enter: {S1}
DEBUG    statemachine.io.scxml.actions:actions.py:259 Assign: Var2 = <statemachine.io.scxml.actions.EventDataWrapper object at 0x7f65b5c0dd00>
DEBUG    statemachine.io.scxml.actions:actions.py:259 Assign: _event = 27
DEBUG    statemachine.io.scxml.actions:actions.py:180 Cond Var2==_event -> False
DEBUG    statemachine.engines.sync:sync.py:89 Eventless/internal queue: {transition  from S1 to Fail}
DEBUG    statemachine.engines.base:base.py:339 States to exit: {S1}
DEBUG    statemachine.engines.base:base.py:415 States to enter: {Fail}

```

## "On transition" events
```py
OnEnterState(state='s0', event='__initial__', data='{}')
OnTransition(source='s0', event='foo', data='{}', target='s1')
OnEnterState(state='s1', event='foo', data='{}')
OnTransition(source='s1', event='None', data='{}', target='fail')
OnEnterState(state='fail', event='None', data='{}')
```

## Traceback
```py
Assertion of the testcase failed.
```
