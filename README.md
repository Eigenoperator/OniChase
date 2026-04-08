# OniChase

OniChase is a public-transit chase game prototype built on real Japanese railway timetable data.

Current focus:

- real Yamanote weekday timetable ingestion
- train-instance-based simulation
- capture-rule prototyping
- planning-oriented local tools
- browser and desktop playtest clients

## Online Playtest

The GitHub Pages site currently exposes only the active public playtest pages:

- landing page: `https://eigenoperator.github.io/OniChase/`
- `v1` Yamanote client: `https://eigenoperator.github.io/OniChase/v1.html`
- `v2` GIS Shinkansen client: `https://eigenoperator.github.io/OniChase/v2.html`

Browser source pages:

- `v1` source: [ui/web_client.html](/home/xincheng/toy/Chase/ui/web_client.html)
- `v2` source: [ui/v2_web_client.html](/home/xincheng/toy/Chase/ui/v2_web_client.html)
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
- `docs/index.html`
- `docs/v1.html`
- `docs/v2.html`

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

## Online Prototype

- architecture: [ONLINE_ARCHITECTURE.md](/home/xincheng/toy/Chase/ONLINE_ARCHITECTURE.md)
- protocol: [ONLINE_PROTOCOL.md](/home/xincheng/toy/Chase/ONLINE_PROTOCOL.md)
- room server: [scripts/engine/v2_online_room_server.py](/home/xincheng/toy/Chase/scripts/engine/v2_online_room_server.py)
- web client: [ui/v2_web_client.html](/home/xincheng/toy/Chase/ui/v2_web_client.html)
- deployment: [ONLINE_DEPLOYMENT.md](/home/xincheng/toy/Chase/ONLINE_DEPLOYMENT.md)

Quick start:

```bash
./START_ONICHASE_V2_SERVER.sh
```

Then open:

- local/public `v2` page: `https://eigenoperator.github.io/OniChase/v2.html`

Current multiplayer flow:

- one player opens `v2`, chooses `Runner`, and clicks `Create Room`
- the second player opens `v2`, chooses `Hunter`, enters the room code, and clicks `Join Room`
- both players build plans, click `Ready`, then either side can click `Start Game`
- the room server is authoritative for phase changes, live time progression, hourly replanning, and capture

Public multiplayer note:

- the public `v2` page reads its default room-server URL from [docs/data/v2_online_config.json](/home/xincheng/toy/Chase/docs/data/v2_online_config.json)
- until that file points to a public deployment, single-player works immediately but multiplayer room creation will remain unconfigured on the public site
