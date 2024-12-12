# Testcase: test525

AssertionError: Assertion failed.

Final configuration: `['fail']`

---

## Logs
```py
DEBUG    statemachine.engines.base:base.py:374 States to enter: {S0}
DEBUG    statemachine.io.scxml.actions:actions.py:467 Error executing actions
Traceback (most recent call last):
  File "/home/macedo/projects/python-statemachine/statemachine/io/scxml/actions.py", line 463, in __call__
    action(*args, **kwargs)
    ~~~~~~^^^^^^^^^^^^^^^^^
  File "/home/macedo/projects/python-statemachine/statemachine/io/scxml/actions.py", line 304, in foreach_action
    act(*args, **kwargs)
    ~~~^^^^^^^^^^^^^^^^^
  File "/home/macedo/projects/python-statemachine/statemachine/io/scxml/actions.py", line 231, in __call__
    value = _eval(self.action.expr, **kwargs)
  File "/home/macedo/projects/python-statemachine/statemachine/io/scxml/actions.py", line 125, in _eval
    return eval(expr, {}, kwargs)
  File "<string>", line 1, in <module>
    import sys;exec(eval(sys.stdin.readline()))
    ^^^^^^^^^^
TypeError: can only concatenate list (not "str") to list
DEBUG    statemachine.engines.sync:sync.py:64 Processing loop started: s0
DEBUG    statemachine.io.scxml.actions:actions.py:170 Cond Var2==3 -> False
DEBUG    statemachine.engines.sync:sync.py:89 Eventless/internal queue: {transition  from S0 to Fail}
DEBUG    statemachine.engines.base:base.py:283 States to exit: {S0}
DEBUG    statemachine.engines.base:base.py:374 States to enter: {Fail}

```

## "On transition" events
```py
DebugEvent(source='s0', event='None', data='{}', target='fail')
```

## Traceback
```py
Assertion of the testcase failed.
```
