# DEPLOYMENT

## Purpose

This document explains how someone else can download OniChase and run the current playtest builds on their own machine, or publish the browser build online.

Right now, the intended public test targets are:

- [app/local_client.py](/home/xincheng/toy/Chase/app/local_client.py)
- [ui/web_client.html](/home/xincheng/toy/Chase/ui/web_client.html)

The local desktop client is still the richest playtest path, and the browser build is the easiest shareable online path.

## Browser Build And GitHub Pages

The repository now includes:

- browser source: [ui/web_client.html](/home/xincheng/toy/Chase/ui/web_client.html)
- static publish bundle: [docs/index.html](/home/xincheng/toy/Chase/docs/index.html)
- bundle builder: [scripts/dev/build_web_client_bundle.py](/home/xincheng/toy/Chase/scripts/dev/build_web_client_bundle.py)
- Pages workflow: [.github/workflows/deploy-pages.yml](/home/xincheng/toy/Chase/.github/workflows/deploy-pages.yml)

To rebuild the static bundle locally:

```bash
python3 scripts/dev/build_web_client_bundle.py
```

This refreshes:

- `docs/index.html`
- `docs/data/yamanote_stations.json`
- `docs/data/yamanote_weekday_train_instances_merged.json`

When the `main` branch is pushed, the GitHub Actions workflow will publish `docs/` to GitHub Pages.

Expected public URL:

```text
https://eigenoperator.github.io/OniChase/
```

If this URL does not open yet, check these one-time GitHub conditions:

1. In repository `Settings -> Pages`, make sure the site is configured to deploy from `GitHub Actions`.
2. In repository `Actions`, make sure the `Deploy Web Client` workflow has run successfully on `main`.
3. After the first successful Pages deployment, wait a short time for propagation and then try the URL again.

## Current Supported Path

The simplest supported setup is:

- Linux
- Python 3
- `tkinter` available in the Python installation

The project does not currently require a Python virtual environment for basic local client testing.

## Download

Clone the repository:

```bash
git clone https://github.com/Eigenoperator/OniChase.git
cd OniChase
```

Or download the repository ZIP from GitHub and extract it locally.

## Check Python

Make sure Python 3 is available:

```bash
python3 --version
```

Then check whether `tkinter` is installed:

```bash
python3 -c "import tkinter; print('tkinter_ok')"
```

If this fails, install the Python Tk package for your system.

Examples:

Ubuntu / Debian:

```bash
sudo apt install python3-tk
```

Fedora:

```bash
sudo dnf install python3-tkinter
```

Arch:

```bash
sudo pacman -S tk
```

## Launch The Local Client

From the project root:

```bash
./START_ONICHASE_CLIENT.sh
```

If the shell script is not executable after download:

```bash
chmod +x START_ONICHASE_CLIENT.sh
./START_ONICHASE_CLIENT.sh
```

You can also launch it directly with Python:

```bash
python3 app/local_client.py
```

## About The Desktop Entry

The repository currently includes:

- [START_ONICHASE_CLIENT.desktop](/home/xincheng/toy/Chase/START_ONICHASE_CLIENT.desktop)

But this file is mainly for the original local workspace, because its `Exec=` and `Path=` fields currently point to the original absolute path.

If another tester wants to use the desktop entry, they should either:

1. edit the `.desktop` file to match their local clone path, or
2. ignore it and use `./START_ONICHASE_CLIENT.sh`

For most testers, the shell script is the recommended path.

## Basic Test Flow

Once the client opens:

1. Stay in `Runner Mode`
2. Wait for the local test preset to load, or use `Load Test Preset`
3. In `STEP 1`, choose a train
4. In `STEP 2`, choose a destination
5. Press `Run Simulation`

Right now, Step 2 supports multiple inputs:

- click `Ride Here` in the right-side destination list
- click `Ride Here` in the horizontal destination strip
- click a highlighted reachable station on the left map

## Troubleshooting

If the client does not open, inspect:

```text
.onichase-client-launch.log
```

Common issues:

- `python3` is missing
- `tkinter` is not installed
- the shell script is not executable

## Notes

This is still a local playtest build, not a packaged release.

There is no installer yet, and there is no cross-platform release bundle yet.

For now, the goal is simply to make it easy for another developer or tester to either:

1. clone the repo and run the current prototype locally, or
2. open the GitHub Pages build and try the browser version immediately.
