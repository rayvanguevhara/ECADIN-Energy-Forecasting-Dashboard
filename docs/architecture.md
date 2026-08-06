# Architecture

The project separates production, experiments, frontend, and generated outputs.

Production modules must never import from:

- `ecadin_energy.experiments`
- the legacy project directory
- archived code
- frontend source files

Frontend data refresh may update only:

`frontend-dashboard/src/data/dashboard-production.json`

It must not overwrite TSX, CSS, route, or component source files.
