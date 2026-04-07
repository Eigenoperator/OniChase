# OniChase

OniChase is a public-transit chase game prototype built on real Japanese railway timetable data.

Current focus:

- real Yamanote weekday timetable ingestion
- train-instance-based simulation
- capture-rule prototyping
- planning-oriented local tools
- browser and desktop playtest clients

## Online Playtest

The GitHub Pages site now has separate entry pages for each playable version:

- landing page: `https://eigenoperator.github.io/OniChase/`
- `v1` Yamanote client: `https://eigenoperator.github.io/OniChase/v1.html`
- `v2` Shinkansen client: `https://eigenoperator.github.io/OniChase/v2.html`
- `v3` GIS Shinkansen pilot: `https://eigenoperator.github.io/OniChase/v3.html`

Browser source pages:

- `v1` source: [ui/web_client.html](/home/xincheng/toy/Chase/ui/web_client.html)
- `v2` source: [ui/v2_web_client.html](/home/xincheng/toy/Chase/ui/v2_web_client.html)
- `v3` source: [ui/v3_web_client.html](/home/xincheng/toy/Chase/ui/v3_web_client.html)
- landing page output: [docs/index.html](/home/xincheng/toy/Chase/docs/index.html)
- Pages workflow: [.github/workflows/deploy-pages.yml](/home/xincheng/toy/Chase/.github/workflows/deploy-pages.yml)

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
- `ui/web_client.html`
- `ui/v2_web_client.html`
- `ui/v3_web_client.html`
- `docs/index.html`
- `docs/v1.html`
- `docs/v2.html`
- `docs/v3.html`

Workspace layout:

- `app/` native local client and future desktop-facing app code
- `ui/` browser source pages and playtest-facing web client code
- `docs/` generated static web bundle for GitHub Pages publishing
- `scripts/engine/` simulation and game-engine entry scripts
- `scripts/ingest/` timetable ingestion, normalization, validation, and rendering tools
- `scripts/dev/` local developer utilities such as the local site launcher and web bundle builder
- `data/` real timetable datasets, scenarios, and simulation results

Local testing and setup:

- [DEPLOYMENT.md](/home/xincheng/toy/Chase/DEPLOYMENT.md)
- [LOCAL_CLIENT.md](/home/xincheng/toy/Chase/LOCAL_CLIENT.md)
