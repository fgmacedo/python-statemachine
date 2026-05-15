# python-statemachine

Python Finite State Machines made easy.

## Project overview

A library for building finite state machines in Python, with support for sync and async engines,
Django integration, diagram generation, and a flexible callback/listener system.

- **Source code:** `statemachine/`
- **Tests:** `tests/`
- **Documentation:** `docs/` (Sphinx + MyST Markdown, hosted on ReadTheDocs)

## Architecture

- `statemachine.py` — Core `StateMachine` and `StateChart` classes
- `factory.py` — `StateMachineMetaclass` handles class construction, state/transition validation
- `state.py` / `event.py` — Descriptor-based `State` and `Event` definitions
- `transition.py` / `transition_list.py` — Transition logic and composition (`|` operator)
- `callbacks.py` — Priority-based callback registry (`CallbackPriority`, `CallbackGroup`)
- `dispatcher.py` — Listener/observer pattern, `callable_method` wraps callables with signature adaptation
- `signature.py` — `SignatureAdapter` for dependency injection into callbacks
- `engines/base.py` — Shared engine logic (microstep, transition selection, error handling)
- `engines/sync.py`, `engines/async_.py` — Sync and async processing loops
- `registry.py` — Global state machine registry (used by `MachineMixin`)
- `mixins.py` — `MachineMixin` for domain model integration (e.g., Django models)
- `spec_parser.py` — Boolean expression parser for condition guards
- `contrib/diagram.py` — Diagram generation via pydot/Graphviz

## Processing model

The engine follows the SCXML run-to-completion (RTC) model with two processing levels:

- **Microstep**: atomic execution of one transition set (before → exit → on → enter → after).
- **Macrostep**: complete processing cycle for one external event; repeats microsteps until
  the machine reaches a **stable configuration** (no eventless transitions enabled, internal
  queue empty).

### Event queues

- `send()` → **external queue** (processed after current macrostep ends).
- `raise_()` → **internal queue** (processed within the current macrostep, before external events).

### Error handling (`catch_errors_as_events`)

- `StateChart` has `catch_errors_as_events=True` by default; `StateMachine` has `False`.
- Errors are caught at the **block level** (per onentry/onexit/transition `on` block), not per
  microstep. This means `after` callbacks still run even when an action raises — making
  `after_<event>()` a natural **finalize** hook (runs on both success and failure paths).
- `error.execution` is dispatched as an internal event; define transitions for it to handle
  errors within the statechart.
- Error during `error.execution` handling → ignored to prevent infinite loops.

#### `on_error` asymmetry: transition `on` vs onentry/onexit

Transition `on` content uses `on_error` **only for non-`error.execution` events**. During
`error.execution` processing, `on_error` is disabled for transition `on` content — errors
propagate to `microstep()` where `_send_error_execution` ignores them. This prevents infinite
loops in self-transition error handlers (e.g., `error_execution = s1.to(s1, on="handler")`
where `handler` raises). `onentry`/`onexit` blocks always use `on_error` regardless of the
current event.

### Eventless transitions

- Bare transition statements (not assigned to a variable) are **eventless** — they fire
  automatically when their guard condition is met.
- Assigned transitions (e.g., `go = s1.to(s2)`) create **named events**.
- `error_` prefix naming convention: `error_X` auto-registers both `error_X` and `error.X`
  event names (explicit `id=` takes precedence).

### Callback conventions

- Generic callbacks (always available): `prepare_event()`, `before_transition()`,
  `on_transition()`, `on_exit_state()`, `on_enter_state()`, `after_transition()`.
- Event-specific: `before_<event>()`, `on_<event>()`, `after_<event>()`.
- State-specific: `on_enter_<state>()`, `on_exit_<state>()`.
- `on_error_execution()` works via naming convention but **only** when a transition for
  `error.execution` is declared — it is NOT a generic callback.

### Thread safety

- The sync engine is **thread-safe**: multiple threads can send events to the same SM instance
  concurrently. The processing loop uses a `threading.Lock` so at most one thread executes
  transitions at a time. Event queues use `PriorityQueue` (stdlib, thread-safe).
- **Do not replace `PriorityQueue`** with non-thread-safe alternatives (e.g., `collections.deque`,
  plain `list`) — this would break concurrent access guarantees.
- Stress tests in `tests/test_threading.py::TestThreadSafety` exercise real contention with
  barriers and multiple sender threads. Any change to queue or locking internals must pass these.

### Invoke (`<invoke>`)

- `invoke.py` — `InvokeManager` on the engine manages the lifecycle: `mark_for_invoke()`,
  `cancel_for_state()`, `spawn_pending_sync/async()`, `send_to_child()`.
- `_cleanup_terminated()` only removes invocations that are both terminated **and** cancelled.
  A terminated-but-not-cancelled invocation means the handler's `run()` returned but the owning
  state is still active — it must stay in `_active` so `send_to_child()` can still route events.
- **Child machine constructor blocks** in the processing loop. Use a listener pattern (e.g.,
  `_ChildRefSetter`) to capture the child reference during the first `on_enter_state`, before
  the loop spins.
- `#_<invokeid>` send target: routed via `_send_to_invoke()` in `io/scxml/actions.py` →
  `InvokeManager.send_to_child()` → handler's `on_event()`.
- **Tests with blocking threads**: use `threading.Event.wait(timeout=)` instead of
  `time.sleep()` for interruptible waits — avoids thread leak errors in teardown.

## Environment setup

```bash
uv sync --all-extras --dev
pre-commit install
```

## Running tests

Always use `uv` to run commands. Also, use a timeout to avoid being stuck in the case of a leaked thread or infinite loop:

```bash
# Run all tests (parallel)
timeout 120 uv run pytest -n 4

# Run a specific test file
uv run pytest tests/test_signature.py

# Run a specific test
uv run pytest tests/test_signature.py::TestSignatureAdapter::test_wrap_fn_single_positional_parameter

# Skip slow tests
uv run pytest -m "not slow"
```

When trying to run all tests, prefer to use xdist (`-n`) as some SCXML tests uses timeout of 30s to verify fallback mechanism.
Don't specify the directory `tests/`, because this will exclude doctests from both source modules (`--doctest-modules`) and markdown docs
(`--doctest-glob=*.md`) (enabled by default):

```bash
timeout 120 uv run pytest -n 4
```

Testes normally run under 60s (~40s on average), so take a closer look if they take longer, it can be a regression.

### Debug logging

`log_cli_level` defaults to `WARNING` in `pyproject.toml`. The engine caches a no-op
for `logger.debug` at init time — running tests with `DEBUG` would bypass this
optimization and inflate benchmark numbers. To enable debug logs for a specific run:

```bash
uv run pytest -o log_cli_level=DEBUG tests/test_something.py
```

When analyzing warnings or extensive output, run the tests **once** saving the output to a file
(`> /tmp/pytest-output.txt 2>&1`), then analyze the file — instead of running the suite
repeatedly with different greps.

Coverage is enabled by default (`--cov` is in `pyproject.toml`'s `addopts`). To generate a
coverage report to a file, pass `--cov-report` **in addition to** `--cov`:

```bash
# JSON report (machine-readable, includes missing_lines per file)
timeout 120 uv run pytest -n auto --cov=statemachine --cov-report=json:cov.json

# Terminal report with missing lines
timeout 120 uv run pytest -n auto --cov=statemachine --cov-report=term-missing
```

Note: `--cov=statemachine` is required to activate coverage collection; `--cov-report`
alone only changes the output format.

### Testing both sync and async engines

Use the `sm_runner` fixture (from `tests/conftest.py`) when you need to test the same
statechart on both sync and async engines. It is parametrized with `["sync", "async"]`
and provides `start()` / `send()` helpers that handle engine selection automatically:

```python
async def test_something(self, sm_runner):
    sm = await sm_runner.start(MyStateChart)
    await sm_runner.send(sm, "some_event")
    assert "expected_state" in sm.configuration_values
```

Do **not** manually add async no-op listeners or duplicate test classes — prefer `sm_runner`.

### TDD and coverage requirements

Follow a **test-driven development** approach: tests are not an afterthought — they are a
first-class requirement that must be part of every implementation plan.

- **Planning phase:** every plan must include test tasks as explicit steps, not a final
  "add tests" bullet. Identify what needs to be tested (new branches, edge cases, error
  paths) while designing the implementation.
- **100% branch coverage is mandatory.** The pre-commit hook enforces `--cov-fail-under=100`
  with branch coverage enabled. Code that drops coverage will not pass CI.
- **Verify coverage before committing:** after writing tests, run coverage on the affected
  modules and check for missing lines/branches:
  ```bash
  timeout 120 uv run pytest tests/<test_file>.py --cov=statemachine.<module> --cov-report=term-missing --cov-branch
  ```
- **Use pytest fixtures** (`tmp_path`, `monkeypatch`, etc.) — never hardcode paths or
  use mutable global state when a fixture exists.
- **Unreachable defensive branches** (e.g., `if` guards that can never be True given the
  type system) may be marked with `pragma: no cover`, but prefer writing a test first.

## Linting and formatting

```bash
# Lint
uv run ruff check .

# Auto-fix lint issues
uv run ruff check --fix .

# Format
uv run ruff format .

# Type check
uv run mypy statemachine/ tests/
```

## Code style

- **Formatter/Linter:** ruff (line length 99, target Python 3.9)
- **Rules:** pycodestyle, pyflakes, isort, pyupgrade, flake8-comprehensions, flake8-bugbear, flake8-pytest-style
- **Imports:** single-line, sorted by isort. **Always prefer top-level imports** — only use
  lazy (in-function) imports when strictly necessary to break circular dependencies
- **Docstrings:** Google convention
- **Naming:** PascalCase for classes, snake_case for functions/methods, UPPER_SNAKE_CASE for constants
- **Type hints:** used throughout; `TYPE_CHECKING` for circular imports
- Pre-commit hooks enforce ruff + mypy + pytest

## Design principles

- **Use GRASP/SOLID patterns to guide decisions.** When refactoring or designing, explicitly
  apply patterns like Information Expert, Single Responsibility, and Law of Demeter to decide
  where logic belongs — don't just pick a convenient location.
  - **Information Expert (GRASP):** Place logic in the module/class that already has the
    knowledge it needs. If a method computes a result, it should signal or return it rather
    than forcing another method to recompute the same thing.
  - **Law of Demeter:** Methods should depend only on the data they need, not on the
    objects that contain it. Pass the specific value (e.g., a `Future`) rather than the
    parent object (e.g., `TriggerData`) — this reduces coupling and removes the need for
    null-checks on intermediate accessors.
  - **Single Responsibility:** Each module, class, and function should have one clear reason
    to change. Functions and types belong in the module that owns their domain (e.g.,
    event-name helpers belong in `event.py`, not in `factory.py`).
  - **Interface Segregation:** Depend on narrow interfaces. If a helper only needs one field
    from a dataclass, accept that field directly.
- **Decouple infrastructure from domain:** Modules like `signature.py` and `dispatcher.py` are
  general-purpose (signature adaptation, listener/observer pattern) and intentionally not coupled
  to the state machine domain. Prefer this separation even for modules that are only used
  internally — it keeps responsibilities clear and the code easier to reason about.
- **Favor small, focused modules:** When adding new functionality, consider whether it can live in
  its own module with a well-defined boundary, rather than growing an existing one.

## Building documentation

```bash
# Build HTML docs
uv run sphinx-build docs docs/_build/html

# Live reload for development
uv run sphinx-autobuild docs docs/_build/html --re-ignore "auto_examples/.*"
```

### Documentation code examples

All code examples in `docs/*.md` **must** be testable doctests (using ```` ```py ```` with
`>>>` prompts), not plain ```` ```python ```` blocks. The test suite collects them via
`--doctest-glob=*.md`. If an example cannot be expressed as a doctest (e.g., it requires
real concurrency), write it as a unit test in `tests/` and reference it from the docs instead.

## Git workflow

- Main branch: `develop`
- PRs target `develop`
- Releases are tagged as `v*.*.*`
- Signed commits preferred (`git commit -s`)
- Use [Conventional Commits](https://www.conventionalcommits.org/) messages
  (e.g., `feat:`, `fix:`, `refactor:`, `test:`, `docs:`, `chore:`, `perf:`)

## Security

- Do not commit secrets, credentials, or `.env` files
- Validate at system boundaries; trust internal code
