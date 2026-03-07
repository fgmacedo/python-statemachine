# Performance Benchmarks

Structured workflow for measuring and documenting optimization impact.

## Quick reference

```bash
# Run benchmarks and save a named snapshot
uv run pytest tests/test_profiling.py -m slow \
    --benchmark-only --benchmark-disable-gc \
    --benchmark-save=<label>

# Compare current run against a named baseline
uv run pytest tests/test_profiling.py -m slow \
    --benchmark-only --benchmark-disable-gc \
    --benchmark-compare=0001  # or use the full ID

# Compare two saved snapshots (no test run)
uv run pytest-benchmark compare \
    .benchmarks/Darwin-CPython-3.14-64bit/0001_*.json \
    .benchmarks/Darwin-CPython-3.14-64bit/0002_*.json \
    --columns=mean,stddev \
    --sort=name \
    --group-by=name

# Generate cProfile data for the top 20 functions per benchmark
uv run pytest tests/test_profiling.py -m slow \
    --benchmark-only --benchmark-disable-gc \
    --benchmark-cprofile=cumtime --benchmark-cprofile-top=20

# Export to JSON for scripted analysis
uv run pytest tests/test_profiling.py -m slow \
    --benchmark-only --benchmark-disable-gc \
    --benchmark-json=/tmp/bench.json
```

## Optimization workflow

### 1. Establish baseline

Before any optimization, save a named baseline:

```bash
uv run pytest tests/test_profiling.py -m slow \
    --benchmark-only --benchmark-disable-gc \
    --benchmark-save=baseline
```

This creates a file like `.benchmarks/.../0001_<hash>_<date>_baseline.json`.
Note the run number (e.g., `0001`) — you'll use it for comparisons.

### 2. Apply one optimization at a time

Each optimization should be:
- A single, focused change
- On its own commit (or branch)
- Measured immediately after

### 3. Measure and compare

After applying an optimization:

```bash
uv run pytest tests/test_profiling.py -m slow \
    --benchmark-only --benchmark-disable-gc \
    --benchmark-save=<optimization-label> \
    --benchmark-compare=<baseline-number>
```

This runs the benchmarks, saves the results, and prints a comparison table
showing the delta (%) against the baseline.

### 4. Log results

After each optimization, add a row to the progress log below.

### 5. Validate correctness

Always run the full test suite after each optimization:

```bash
timeout 120 uv run pytest -n 4
```

## Benchmark matrix

| Category | Benchmark | What it exercises |
|----------|-----------|-------------------|
| **Setup** | `test_flat_machine` | Instance + listener + callback registration |
| **Setup** | `test_compound_machine` | Nested state setup |
| **Setup** | `test_parallel_machine` | Parallel region setup |
| **Setup** | `test_guarded_machine` | Guard/cond expression parsing |
| **Setup** | `test_history_machine` | History state setup |
| **Setup** | `test_deep_history_machine` | Deep nested history setup |
| **Events** | `test_flat_self_transition` | Self-transition + model callbacks |
| **Events** | `test_compound_enter_exit` | Enter/exit compound state |
| **Events** | `test_parallel_region_events` | Events in parallel regions |
| **Events** | `test_guarded_transitions` | Guard evaluation + selection |
| **Events** | `test_history_pause_resume` | Shallow history save/restore |
| **Events** | `test_deep_history_cycle` | Deep history save/restore |
| **Events** | `test_many_transitions_full_cycle` | 5-state ring traversal |
| **Events** | `test_many_transitions_reset` | Composite event (multi-source `\|`) |

## Progress log

Record each optimization here. Use `--benchmark-compare` output as source.

### Baseline (run `0512`, CPython 3.14, Apple Silicon)

| Benchmark | Mean | StdDev |
|-----------|------|--------|
| test_flat_machine | 189.6 µs | 2.0 µs |
| test_compound_machine | 172.7 µs | 50.2 µs |
| test_parallel_machine | 159.3 µs | 4.8 µs |
| test_guarded_machine | 162.8 µs | 7.6 µs |
| test_history_machine | 151.8 µs | 5.3 µs |
| test_deep_history_machine | 164.0 µs | 7.0 µs |
| test_flat_self_transition | 267.0 µs | 8.5 µs |
| test_compound_enter_exit | 1018.5 µs | 18.6 µs |
| test_parallel_region_events | 1280.4 µs | 16.0 µs |
| test_guarded_transitions | 502.9 µs | 7.3 µs |
| test_history_pause_resume | 631.6 µs | 14.8 µs |
| test_deep_history_cycle | 706.0 µs | 10.5 µs |
| test_many_transitions_full_cycle | 1262.0 µs | 22.3 µs |
| test_many_transitions_reset | 1016.0 µs | 21.1 µs |

<!-- Copy this template for each optimization:

### Optimization N: <title>

| Benchmark | Before | After | Delta |
|-----------|--------|-------|-------|
| ... | ... | ... | ...% |

**Commit:** `<hash>`
**Description:** ...
**Tests pass:** yes/no
-->

---

## Advanced: ad-hoc profiling

For deeper investigation of a specific benchmark, use the cProfile integration:

```bash
# cProfile sorted by cumulative time
uv run pytest tests/test_profiling.py::TestEventPerformance::test_parallel_region_events \
    -m slow --benchmark-only --benchmark-disable-gc \
    --benchmark-cprofile=cumtime --benchmark-cprofile-top=30
```

To generate `.prof` files for visualization (snakeviz, speedscope, etc.):

```bash
uv run pytest tests/test_profiling.py::TestEventPerformance::test_parallel_region_events \
    -m slow --benchmark-only --benchmark-disable-gc \
    --benchmark-cprofile=cumtime \
    --benchmark-cprofile-dump=/tmp/bench

# Opens interactive flamegraph in the browser
uv run snakeviz /tmp/bench-test_parallel_region_events.prof
```
