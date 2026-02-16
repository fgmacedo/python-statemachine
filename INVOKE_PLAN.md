# SCXML `<invoke>` Implementation Plan

## Overview

Implement SCXML `<invoke>` support (W3C spec §6.4) for spawning child state machine
sessions when entering a state, with automatic cancellation on exit.

**Branch:** `feat/invoke`
**Base:** `develop`
**Worktree:** `../python-statemachine-invoke`

---

## Rules

### SCXML Test Fail Marks
- Only variant-specific marks exist: `testXXX.sync.fail.md` / `testXXX.async.fail.md`
- No generic `.fail.md` — each variant is tracked independently
- Marks are ephemeral: delete all and regenerate with `--upd-fail`
- During development, let tests fail — don't manage marks manually

### Investigation Methodology
- SCXML W3C tests are black-box integration tests
- To investigate failures, write **unit tests** that verify specific hypotheses
- Only modify code after hypotheses are confirmed by failing unit tests

---

## Steps

### 1. Create worktree and branch
- [x] Done

### 2. Schema + Parser SCXML
- [x] `InvokeDefinition` dataclass, `parse_invoke()`, `invocations` field
- [x] **Commit:** 6d8067d

### 3. InvokeConfig and InvokeManager
- [x] `InvokeConfig`, `Invocation`, `ParentBridge`, `InvokeManager`
- [x] **Commit:** 2b94c34

### 4. Engine integration — spawn and cancel
- [x] `invoke_manager` + `states_to_invoke` in BaseEngine
- [x] Track invocations in `_enter_states()`, cancel in `_exit_states()`
- [x] Spawn in sync (daemon thread) and async (asyncio task) engines
- [x] Finalize and autoforward in processing loops
- [x] Fix async `_enter_states` missing `states_to_invoke`
- [x] **Commit:** 0780e4f, 33edf3b

### 5. Event routing (#_parent, invokeid, done.invoke)
- [x] `invokeid` field on `TriggerData`
- [x] `#_parent`, `#_child`, `#_<invokeid>` send targets
- [x] Fix `_eval_send_params` kwarg conflict
- [x] Fix `#_scxml_` vs `#_invokeid` target ordering
- [x] **Commit:** 0780e4f

### 6. done_invoke_ naming convention and State(invoke=...) API
- [x] `State(invoke=...)` parameter + `_normalize_invoke()` + `InstanceState.invocations`
- [ ] `done_invoke_` handler in `factory.py`
- [ ] Unit tests for Python API
- [ ] **Commit**

### 7. SCXML advanced invoke features
- [x] `src` — load SCXML from file
- [x] `namelist` / `<param>` — pass data to child
- [x] `autoforward` / `<finalize>`
- [ ] `srcexpr` / `typeexpr`
- [ ] Fix relative `src` path resolution (test239 failure)
- [ ] **Commit**

### 8. Fix W3C invoke test failures
- [ ] Write unit tests to reproduce specific failure modes
- [ ] Fix root causes identified by unit tests
- [ ] Regenerate fail marks with `--upd-fail`
- Known failure categories:
  - **Async timing**: child events not reaching parent before timeout
  - **Relative src paths**: `src="file:test239sub1.scxml"` not resolved
  - **Cross-session event routing**: `#_parent` send from child thread
  - **Session termination**: child onexit not firing on cancel

### 9. Unit tests for Python invoke API
- [ ] `tests/test_invoke.py`
- [ ] Basic: `State(invoke=ChildMachine)`, child terminates, `done.invoke`
- [ ] Cancellation: parent exits state, child cancelled
- [ ] `done_invoke_` naming convention
- [ ] Autoforward, multiple invocations
- [ ] Use `sm_runner` fixture

### 10. Documentation and release notes
- [ ] `docs/invoke.md`
- [ ] `docs/index.md` toctree
- [ ] `docs/releases/3.0.0.md`

### 11. Final cleanup
- [ ] Linting, mypy, full test suite
- [ ] Regenerate fail marks with `--upd-fail`

---

## Bugs Fixed

1. **`_eval_send_params` duplicate `machine` kwarg** — took `machine` as positional AND via
   `**kwargs`. Fixed by taking only `**kwargs`.
2. **`#_scxml_` vs `#_invokeid` target ordering** — `#_scxml_foo` caught by generic `#_`
   handler. Fixed by checking `#_scxml_` first.
3. **Child `_parent_sm` not set during initial entry** — fixed by setting on child CLASS
   before instantiation.
4. **Async `_enter_states` missing `states_to_invoke`** — async override didn't track states
   with invocations. Fixed by adding the tracking.
