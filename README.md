# OniChase

OniChase is a public-transit chase game prototype built on real Japanese railway timetable data.

Current focus:

- real Yamanote weekday timetable ingestion
- train-instance-based simulation
- capture-rule prototyping
- planning-oriented local tools

## Local Test Build

The main current playtest target is the native local client:

- [app/local_client.py](/home/xincheng/toy/Chase/app/local_client.py)

Quick start:

```bash
git clone https://github.com/Eigenoperator/OniChase.git
cd OniChase
./START_ONICHASE_CLIENT.sh
```

If `tkinter` is missing on your system, see:

- [DEPLOYMENT.md](/home/xincheng/toy/Chase/DEPLOYMENT.md)

Key entry points:

- `STATUS.md`
- `SCHEMA.md`
- `STATE_MACHINE.md`
- `SIMULATION_INPUT.md`
- `PLANNING_FORMAT.md`
- `ui/planner.html`

Workspace layout:

- `app/` native local client and future desktop-facing app code
- `ui/` browser prototypes and planning/debug pages
- `scripts/engine/` simulation and game-engine entry scripts
- `scripts/ingest/` timetable ingestion, normalization, validation, and rendering tools
- `scripts/dev/` local developer utilities such as the local site launcher
- `data/` real timetable datasets, scenarios, and simulation results

Local testing and setup:

- [DEPLOYMENT.md](/home/xincheng/toy/Chase/DEPLOYMENT.md)
- [LOCAL_CLIENT.md](/home/xincheng/toy/Chase/LOCAL_CLIENT.md)
