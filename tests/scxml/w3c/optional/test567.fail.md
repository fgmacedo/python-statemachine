# Testcase: test567

AssertionError: Assertion failed.

Final configuration: `['fail']`

---

## Logs
```py
DEBUG    statemachine.engines.base:base.py:415 States to enter: {S0}
DEBUG    statemachine.engines.base:base.py:93 New event 'timeout' put on the 'external' queue
DEBUG    statemachine.io.scxml.actions:actions.py:477 Error executing actions
Traceback (most recent call last):
  File "/home/macedo/projects/python-statemachine/statemachine/io/scxml/actions.py", line 473, in __call__
    action(*args, **kwargs)
    ~~~~~~^^^^^^^^^^^^^^^^^
  File "/home/macedo/projects/python-statemachine/statemachine/io/scxml/actions.py", line 348, in send_action
    raise ValueError(
        "Only 'http://www.w3.org/TR/scxml/#SCXMLEventProcessor' event type is supported"
    )
ValueError: Only 'http://www.w3.org/TR/scxml/#SCXMLEventProcessor' event type is supported
DEBUG    statemachine.engines.base:base.py:93 New event 'error.execution' put on the 'internal' queue
DEBUG    statemachine.engines.sync:sync.py:64 Processing loop started: s0
DEBUG    statemachine.engines.sync:sync.py:89 Eventless/internal queue: {transition * from S0 to Fail}
DEBUG    statemachine.engines.base:base.py:339 States to exit: {S0}
DEBUG    statemachine.engines.base:base.py:415 States to enter: {Fail}
DEBUG    statemachine.engines.sync:sync.py:116 External event: timeout
DEBUG    statemachine.engines.sync:sync.py:131 Enabled transitions: {}

```

## "On transition" events
```py
OnEnterState(state='s0', event='__initial__', data='{}')
OnTransition(source='s0', event='error.execution', data='{\'event_id\': None, \'error\': ValueError("Only \'http://www.w3.org/TR/scxml/#SCXMLEventProcessor\' event type is supported")}', target='fail')
OnEnterState(state='fail', event='error.execution', data='{\'event_id\': None, \'error\': ValueError("Only \'http://www.w3.org/TR/scxml/#SCXMLEventProcessor\' event type is supported")}')
```

## Traceback
```py
Assertion of the testcase failed.
```
