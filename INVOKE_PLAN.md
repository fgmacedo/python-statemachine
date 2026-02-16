# SCXML `<invoke>` Implementation Plan

## Overview

Implement SCXML `<invoke>` support (W3C spec §6.4) for spawning child state machine
sessions when entering a state, with automatic cancellation on exit.

**Branch:** `feat/invoke`
**Base:** `develop`
**Worktree:** `../python-statemachine-invoke`

---

## Steps

### 1. Create worktree and branch
- [x] Create git worktree and branch `feat/invoke`

### 2. Schema + Parser SCXML
- [x] Add `InvokeDefinition` dataclass to `schema.py`
- [x] Add `invocations` field to `schema.State`
- [x] Add `parse_invoke()` to `parser.py`
- [x] Call from `parse_state()` for `<invoke>` elements
- [x] **Commit:** `feat: parse SCXML <invoke> elements` (fe19eca → rebased to 6d8067d)

### 3. InvokeConfig and InvokeManager
- [x] Create `statemachine/invoke.py` with:
  - `InvokeConfig` — static configuration
  - `Invocation` — runtime state
  - `ParentBridge` — listener on child for `#_parent` sends
  - `InvokeManager` — spawn/cancel/finalize lifecycle
- [x] **Commit:** `feat: add InvokeManager for child session lifecycle` (76b9627 → rebased to 2b94c34)

### 4. Engine integration — spawn and cancel
- [x] Add `invoke_manager` and `states_to_invoke` to `BaseEngine.__init__`
- [x] Track states with invocations in `_enter_states()`
- [x] Cancel invocations in `_exit_states()` and `_handle_final_state()`
- [x] Replace TODO in `sync.py` with actual invoke spawn code
- [x] Replace TODO in `sync.py` with finalize + autoforward
- [x] Mirror changes in `async_.py`
- [ ] **Commit** (pending — code written, needs final test pass)

### 5. Event routing (#_parent, invokeid, done.invoke)
- [x] Add `invokeid` field to `TriggerData` in `event_data.py`
- [x] Update `Event.put()` and `Event.build_trigger()` to accept `invokeid`
- [x] Update `StateChart.send()` to accept `invokeid`
- [x] Update `EventDataWrapper.__init__` to read `invokeid` from trigger_data
- [x] Implement `#_parent` target in `create_send_action_callable()`
- [x] Implement `#_child` target
- [x] Implement `#_<invokeid>` target
- [x] Fix `_eval_send_params` duplicate `machine` kwarg bug
- [x] Fix `#_scxml_` vs `#_invokeid` target ordering (test496/521 regression)
- [ ] **Commit** (pending — code written, needs final test pass)

### 6. done_invoke_ naming convention and State(invoke=...) API
- [x] Add `invoke` parameter to `State.__init__()`
- [x] Add `_normalize_invoke()` static method
- [x] Add `invocations` property to `InstanceState`
- [x] Add `invoke` to `BaseStateKwargs` in `io/__init__.py`
- [ ] Add `done_invoke_` handler in `factory.py` (not yet implemented)
- [ ] **Commit**

### 7. SCXML advanced invoke features
- [x] `src` — load SCXML from external file
- [x] `namelist` / `<param>` — pass initial data to child
- [x] `autoforward` — forward all external events to child
- [x] `<finalize>` — execute before processing child event
- [ ] `typeexpr` — evaluate expression for type (not yet)
- [ ] `srcexpr` — evaluate expression for src (not yet)
- [ ] **Commit**

### 8. Run W3C invoke tests and fix failures
- [ ] Remove `.fail.md` for passing tests
- [ ] Group failures by root cause and fix
- [ ] Current status (post-rebase, post-bug-fixes):
  - Tests that now xpass (need .fail.md removed): test191, test207, test220, test223, test228,
    test232, test233, test235, test237, test241, test242, test245, test247, test338, test347,
    test422, test554
  - Tests still expected to fail: test187, test192, test216, test226, test229, test234, test236,
    test240, test243, test244, test276, test530
- [ ] **Commits per group**

### 9. Unit tests for Python invoke API
- [ ] Create `tests/test_invoke.py`
- [ ] Test basic: `State(invoke=ChildMachine)`, child terminates, parent gets `done.invoke`
- [ ] Test cancellation: parent exits state, child is cancelled
- [ ] Test cross-engine: sync parent + async child, async parent + sync child
- [ ] Test `done_invoke_` naming convention
- [ ] Test autoforward
- [ ] Test multiple invocations
- [ ] Use `sm_runner` fixture for sync/async coverage
- [ ] **Commit**

### 10. Documentation and release notes
- [ ] Create `docs/invoke.md` (concept, Python API, SCXML, examples)
- [ ] Add to `docs/index.md` toctree
- [ ] Add section in `docs/releases/3.0.0.md`
- [ ] Reference from `docs/statecharts.md`
- [ ] **Commit**

### 11. Final cleanup and verification
- [ ] `uv run ruff check .` — all clean
- [ ] `uv run ruff format .` — all clean
- [ ] `uv run mypy statemachine/` — no errors
- [ ] `uv run pytest -n auto` — full suite passes
- [ ] Verify W3C invoke tests pass (`.fail.md` removed for passing tests)
- [ ] Fix any regressions

---

## Key Files

| File | Status |
|------|--------|
| `statemachine/invoke.py` | Committed + uncommitted changes |
| `statemachine/engines/base.py` | Uncommitted changes |
| `statemachine/engines/sync.py` | Uncommitted changes |
| `statemachine/engines/async_.py` | Uncommitted changes |
| `statemachine/event.py` | Uncommitted changes |
| `statemachine/event_data.py` | Uncommitted changes |
| `statemachine/state.py` | Uncommitted changes |
| `statemachine/statemachine.py` | Uncommitted changes |
| `statemachine/io/__init__.py` | Uncommitted changes |
| `statemachine/io/scxml/actions.py` | Uncommitted changes |
| `statemachine/io/scxml/processor.py` | Uncommitted changes |
| `statemachine/io/scxml/schema.py` | Committed |
| `statemachine/io/scxml/parser.py` | Committed |

## Bugs Fixed

1. **`_eval_send_params` duplicate `machine` kwarg** — function took `machine` as positional
   AND received it via `**kwargs`. Fixed by taking only `**kwargs` and extracting `machine` from it.
2. **`#_scxml_` vs `#_invokeid` target ordering** — `#_scxml_foo` targets were caught by the
   generic `#_` invoke handler before reaching the `#_scxml_` → `error.communication` handler.
   Fixed by checking `#_scxml_` first.
3. **Child `_parent_sm` not set during initial entry** — fixed by setting `_parent_sm` and
   `_invokeid` on the child CLASS before instantiation.
