# Git Large File Policy

This repository currently keeps several generated gameplay/runtime artifacts in
ordinary Git history because they are needed by the static docs build or local
handoff workflow.

## Current Risk

`git ls-files` shows the largest tracked files are:

- `docs/data/v5_bus_gtfs_current_bundle.json.gz` - about 75.7 MiB
- `data/v5_bus_gtfs_current_bundle.json.gz` - about 75.7 MiB
- `data/v4_room_server_trips.sqlite` - about 62.5 MiB

GitHub accepted the 2026-05-28 push, but warned that the V5 bus bundle files are
above the recommended 50 MiB threshold.

## Policy

- Do not rewrite repository history just to fix the existing large files unless
  Scorp explicitly asks for a history rewrite or migration.
- Do not add new generated runtime artifacts above 50 MiB to ordinary Git.
- If a generated artifact above 50 MiB must be shared, choose one of:
  - Git LFS for canonical binary/runtime artifacts that must live at stable
    repository paths.
  - GitHub release artifacts or another external artifact store for rebuild
    outputs that do not need to be diffed.
  - A documented local rebuild command when the artifact is reproducible from
    tracked source inputs.
- Before committing a generated artifact above 25 MiB, run:

```bash
cd /home/xincheng/toy/Chase
git ls-files -z | xargs -0 du -b | sort -nr | head -40
```

Then decide explicitly whether ordinary Git is still the right storage layer.

## Local Caches

Official source caches, probe caches, and temporary release candidate artifacts
should remain local unless they are deliberately promoted into canonical source
or docs data. Add cache directories to `.gitignore` before they accumulate in
`git status`.
