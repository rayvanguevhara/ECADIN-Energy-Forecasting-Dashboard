# Architecture

The project separates production, experiments, frontend, generated outputs,
and portable test fixtures.

Production modules must never import from:

- `ecadin_energy.experiments`;
- the legacy project directory;
- archived code;
- frontend source files;
- test fixtures.

Frontend data refresh may update only:

```text
frontend-dashboard/src/data/dashboard-production.json
```

It must not overwrite TSX, CSS, route, or component source files.

## Production layers

```text
data_processing.reference
→ pipeline.data
→ pipeline.production
→ pipeline.dashboard
→ pipeline.release
→ pipeline.full
```

`pipeline.full` is a fail-fast orchestrator. Every stage remains callable and
validatable independently.

## Test portability

`tests/fixtures` contains a deterministic canonical forecasting fixture and a
minimal set of validated production outputs. These fixtures allow source-only
checkouts to test contracts without committing local raw data or generated
production directories.

Production code cannot import from `tests` or `tests/fixtures`.
