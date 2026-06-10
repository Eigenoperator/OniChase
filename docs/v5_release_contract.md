# OniChase V5 Release Contract

This document defines the current V5 release target. It is narrower than the
long-term V5 data vision in `v5_plan.md` and `v5_bus_data.md`.

## Current Release Scope

V5 is a multimodal gameplay release with these exposed modes:

- Rail, inherited from the V4 gameplay baseline.
- Walking, as generated access and transfer movement.
- Flights, with airport access and advance-ticket gameplay.
- Ships/ferries, with port planning, ship movement, and onward planning.
- Scoped buses, limited to airport buses and port-connector buses.

The current release is not a claim that all nationwide bus gameplay is complete.

## Bus Exposure Policy

Bus source/runtime data can contain more than the public gameplay exposes.

Current gameplay exposes:

- Airport access buses.
- Port connector buses.
- Bus stops and routes needed to continue plans after airport or ship arrival.

Current gameplay does not intentionally expose:

- Ordinary local route buses unrelated to airport or port access.
- Highway buses.
- Night buses.
- Dense city-bus networks.

Those categories remain part of the long-term V5 data target, but they are not
release blockers unless Scorp explicitly promotes them into the current gate.

## Source-Only Data Policy

Some collected data may remain source-only or runtime-support-only. That is
acceptable when the record documents why it is not currently exposed, such as:

- Missing playable coordinates.
- Missing exact stopTimes.
- Calendar not parsed into gameplay rules.
- Fare/source evidence incomplete.
- Service category outside current gameplay exposure.

Do not call a collected source "finished" unless it is either playable in the
current scoped release or explicitly documented as source-only/nonblocking.

## Required Gate Families

The current release gate families are:

- Static readiness: data inventory and no known missing required runtime links.
- Plan-tail anchors: multimodal planning must continue from the full current
  plan tail, not from stale current position.
- Flight-bus interaction: airport bus access must connect to flight planning.
- Ship interaction: ship movement, arrival markers, and onward ship/land
  planning must work.
- Bus interaction: scoped bus UI and planner behavior must stay coherent.
- Remote ship-bus readiness/runtime/quality: official remote island port
  connector buses must remain promoted or explicitly nonblocking.

Run heavy V5 validations carefully. Inside Codex, do not run large V5 bundle
rebuilds, large gzip scans, planner/map tile rewrites, or parallel browser/data
audits unless Scorp explicitly approves that specific run.

## Current Safe Next Step

Before expanding data, reconcile release docs and build a lightweight smoke
matrix from existing audit records. After that, run any V5 audit one at a time
with clear expected cost.
