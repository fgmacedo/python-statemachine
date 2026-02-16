# Testcase: test276

FileNotFoundError: File not found.

Final configuration: `No configuration`

---

## Logs
```py
DEBUG    statemachine.engines.base:base.py:556 States to enter: {S0}
DEBUG    statemachine.engines.base:base.py:629 Entering state: S0
DEBUG    statemachine.engines.sync:sync.py:78 Processing loop started: s0
DEBUG    statemachine.engines.sync:sync.py:92 Macrostep: eventless/internal queue

```

## "On transition" events
```py
OnEnterState(state='s0', event='__initial__', data='{}')
```

## Traceback
```py
Traceback (most recent call last):
  File "/Users/fernando.macedo/projects/python-statemachine-invoke/tests/scxml/test_scxml_cases.py", line 162, in _run_scxml_testcase
    sm = processor.start(listeners=listeners)
  File "/Users/fernando.macedo/projects/python-statemachine-invoke/statemachine/io/scxml/processor.py", line 256, in start
    self.root = self.root_cls(**kwargs)
                ~~~~~~~~~~~~~^^^^^^^^^^
  File "/Users/fernando.macedo/projects/python-statemachine-invoke/statemachine/statemachine.py", line 164, in __init__
    self._engine.start()
    ~~~~~~~~~~~~~~~~~~^^
  File "/Users/fernando.macedo/projects/python-statemachine-invoke/statemachine/engines/sync.py", line 38, in start
    self.activate_initial_state()
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~^^
  File "/Users/fernando.macedo/projects/python-statemachine-invoke/statemachine/engines/sync.py", line 58, in activate_initial_state
    return self.processing_loop()
           ~~~~~~~~~~~~~~~~~~~~^^
  File "/Users/fernando.macedo/projects/python-statemachine-invoke/statemachine/engines/sync.py", line 116, in processing_loop
    self.invoke_manager.spawn_sync(state, config, internal_event)
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/fernando.macedo/projects/python-statemachine-invoke/statemachine/invoke.py", line 102, in spawn_sync
    child_sm = self._create_child(config, invokeid, invocation, trigger_data)
  File "/Users/fernando.macedo/projects/python-statemachine-invoke/statemachine/invoke.py", line 208, in _create_child
    processor.parse_scxml_file(path)
    ~~~~~~~~~~~~~~~~~~~~~~~~~~^^^^^^
  File "/Users/fernando.macedo/projects/python-statemachine-invoke/statemachine/io/scxml/processor.py", line 76, in parse_scxml_file
    scxml_content = path.read_text()
  File "/Users/fernando.macedo/.local/share/uv/python/cpython-3.13.1-macos-aarch64-none/lib/python3.13/pathlib/_local.py", line 546, in read_text
    return PathBase.read_text(self, encoding, errors, newline)
           ~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/fernando.macedo/.local/share/uv/python/cpython-3.13.1-macos-aarch64-none/lib/python3.13/pathlib/_abc.py", line 632, in read_text
    with self.open(mode='r', encoding=encoding, errors=errors, newline=newline) as f:
         ~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/fernando.macedo/.local/share/uv/python/cpython-3.13.1-macos-aarch64-none/lib/python3.13/pathlib/_local.py", line 537, in open
    return io.open(self, mode, buffering, encoding, errors, newline)
           ~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
FileNotFoundError: [Errno 2] No such file or directory: 'test276sub1.scxml'

```
