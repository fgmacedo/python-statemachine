# Testcase: test529

AssertionError: Assertion failed.

Final configuration: `['fail']`

---

## Logs
```py
DEBUG    statemachine.engines.base:base.py:386 States to enter: {S0, S01}
DEBUG    statemachine.engines.sync:sync.py:64 Processing loop started: ['s0', 's01']
DEBUG    statemachine.engines.sync:sync.py:89 Eventless/internal queue: {transition  from S01 to S02}
DEBUG    statemachine.engines.base:base.py:276 States to exit: {S01}
DEBUG    statemachine.engines.base:base.py:386 States to enter: {S02}
DEBUG    statemachine.io.scxml.actions:actions.py:179 Cond _event.data == 21 -> False
DEBUG    statemachine.engines.sync:sync.py:89 Eventless/internal queue: {transition done.state.s0 from S0 to Fail}
DEBUG    statemachine.engines.base:base.py:276 States to exit: {S0, S02}
DEBUG    statemachine.engines.base:base.py:386 States to enter: {Fail}

```

## "On transition" events
```py
DebugEvent(source='s01', event='None', data='{}', target='s02')
DebugEvent(source='s0', event='done.state.s0', data="{'donedata': {}}", target='fail')
```

## Traceback
```py
Assertion of the testcase failed.
```
