# Testcase: test518

AssertionError: Assertion failed.

Final configuration: `['fail']`

---

## Logs
```py
DEBUG    statemachine.engines.base:base.py:374 States to enter: {S0}
DEBUG    statemachine.io.scxml.actions:actions.py:464 Error executing actions
Traceback (most recent call last):
  File "/home/macedo/projects/python-statemachine/statemachine/io/scxml/actions.py", line 460, in __call__
    action(*args, **kwargs)
    ~~~~~~^^^^^^^^^^^^^^^^^
  File "/home/macedo/projects/python-statemachine/statemachine/io/scxml/actions.py", line 335, in send_action
    raise ValueError(
        "Only 'http://www.w3.org/TR/scxml/#SCXMLEventProcessor' event type is supported"
    )
ValueError: Only 'http://www.w3.org/TR/scxml/#SCXMLEventProcessor' event type is supported
DEBUG    statemachine.engines.sync:sync.py:64 Processing loop started: s0
DEBUG    statemachine.engines.sync:sync.py:89 Eventless/internal queue: {transition * from S0 to Fail}
DEBUG    statemachine.engines.base:base.py:283 States to exit: {S0}
DEBUG    statemachine.engines.base:base.py:374 States to enter: {Fail}
DEBUG    statemachine.engines.sync:sync.py:116 External event: TriggerData(machine=<weakproxy at 0x7fd3acaad530; to 'statemachine.io.test518' at 0x7fd3acc35160>, event=Event('timeout', delay=2000.0, internal=False), send_id='882c7a792de841578af0b78e1f36bc51', _target=None, execution_time=1734003011.4323764, model=Model(state=fail), args=(), kwargs={})
DEBUG    statemachine.engines.sync:sync.py:131 Enabled transitions: {}

```

## "On transition" events
```py
DebugEvent(source='s0', event='error.execution', data='{\'event_id\': None, \'error\': ValueError("Only \'http://www.w3.org/TR/scxml/#SCXMLEventProcessor\' event type is supported")}', target='fail')
```

## Traceback
```py
Assertion of the testcase failed.
```
