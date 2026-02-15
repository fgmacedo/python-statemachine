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

### Error handling (`error_on_execution`)

- `StateChart` has `error_on_execution=True` by default; `StateMachine` has `False`.
- Errors are caught at the **block level** (per onentry/onexit block), not per microstep.
- This means `after` callbacks still run even when an action raises — making `after_<event>()`
  a natural **finalize** hook (runs on both success and failure paths).
- `error.execution` is dispatched as an internal event; define transitions for it to handle
  errors within the statechart.
- Error during `error.execution` handling → ignored to prevent infinite loops.

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

## Environment setup

```bash
uv sync --all-extras --dev
pre-commit install
```

## Running tests

Always use `uv` to run commands:

```bash
# Run all tests (parallel)
uv run pytest -n auto

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
uv run pytest -n auto
```

Coverage is enabled by default.

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
- **Imports:** single-line, sorted by isort
- **Docstrings:** Google convention
- **Naming:** PascalCase for classes, snake_case for functions/methods, UPPER_SNAKE_CASE for constants
- **Type hints:** used throughout; `TYPE_CHECKING` for circular imports
- Pre-commit hooks enforce ruff + mypy + pytest

## Design principles

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
