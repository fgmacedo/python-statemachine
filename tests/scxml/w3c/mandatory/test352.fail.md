# Testcase: test352

AssertionError: Assertion failed.

Final configuration: `['fail']`

---

## Logs
```py
DEBUG    statemachine.engines.base:base.py:374 States to enter: {S0}
DEBUG    statemachine.engines.sync:sync.py:64 Processing loop started: s0
DEBUG    statemachine.engines.sync:sync.py:116 External event: TriggerData(machine=<weakproxy at 0x7fd4c53451c0; to 'statemachine.io.test352' at 0x7fd4c5428d70>, event=Event('s0Event', delay=0, internal=False), send_id='33ad105527074833b84526680cb720bb', _target=None, execution_time=1733943928.6378632, model=Model(state=s0), args=(), kwargs={})
DEBUG    statemachine.engines.sync:sync.py:131 Enabled transitions: {transition s0Event from S0 to S1}
DEBUG    statemachine.engines.base:base.py:283 States to exit: {S0}
DEBUG    statemachine.io.scxml.actions:actions.py:244 Assign: Var1 = 'http://www.w3.org/TR/scxml/#SCXMLEventProcessor'
DEBUG    statemachine.engines.base:base.py:374 States to enter: {S1}
DEBUG    statemachine.engines.sync:sync.py:116 External event: TriggerData(machine=<weakproxy at 0x7fd4c53451c0; to 'statemachine.io.test352' at 0x7fd4c5428d70>, event=Event('timeout', delay=2000.0, internal=False), send_id='273529c5fefc402cb02e75c69f94afb8', _target=None, execution_time=1733943930.6378362, model=Model(state=s1), args=(), kwargs={})
DEBUG    statemachine.engines.sync:sync.py:131 Enabled transitions: {}
DEBUG    statemachine.io.scxml.actions:actions.py:170 Cond Var1=='scxml' -> False
DEBUG    statemachine.engines.sync:sync.py:89 Eventless/internal queue: {transition  from S1 to Fail}
DEBUG    statemachine.engines.base:base.py:283 States to exit: {S1}
DEBUG    statemachine.engines.base:base.py:374 States to enter: {Fail}

```

## "On transition" events
```py
DebugEvent(source='s0', event='s0Event', data='{}', target='s1')
DebugEvent(source='s1', event='None', data='{}', target='fail')
```

## Traceback
```py
Assertion of the testcase failed.
```
