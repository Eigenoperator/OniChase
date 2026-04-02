# WORKSPACE

## Purpose
Keep the project readable by separating runtime code, tooling, and player-facing prototypes by responsibility.

## Layout
- `app/`
  Native local client code. Current entry: `app/local_client.py`.
- `ui/`
  Browser-based prototypes and visualization surfaces. Current pages: `ui/planner.html`, `ui/debug_gui.html`.
- `scripts/engine/`
  Engine-facing executable scripts, especially simulation entry points.
- `scripts/ingest/`
  Timetable crawling, parsing, normalization, merging, validation, and rendering tools.
- `scripts/dev/`
  Local developer helpers such as the browser launcher.
- `data/`
  Datasets, scenarios, and generated simulation results.
- `visuals/`
  Exported diagrams and timetable visualizations.
- `rule/`
  Versioned game rules. Never edit older rule files in place.

## Root-Level Files
The root should stay small and stable:
- launchers such as `START_ONICHASE_CLIENT.sh`
- control docs such as `STATUS.md`, `AXIOMS.md`, `HISTORY.md`, `MEMORY.md`
- high-level design docs such as `SCHEMA.md`, `STATE_MACHINE.md`, `ENGINE_ARCHITECTURE.md`

## Boundary Rule
- Runtime app code should not live in the root.
- Ingestion and engine scripts should not be mixed together in one flat `scripts/` folder.
- Frontend tools should access engine outputs through JSON boundaries, not direct shared in-memory state.
