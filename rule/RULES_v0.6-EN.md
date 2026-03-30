# Public Transit Chase Game Rules Draft v0.6

## Main Change

- Added the same-minute alight/board boundary capture rule: same-train crossing captures, different-train crossing does not.

## 1. Purpose

This document records one newly confirmed capture-boundary rule on top of [RULES_v0.5.md](/home/xincheng/toy/Chase/rule/RULES_v0.5.md).

`RULES_v0.5.md` remains unchanged.  
This file only adds the newly confirmed ruling.

## 2. Inheritance

- All rules not explicitly overridden here continue to follow `RULES_v0.5.md`

## 3. Newly Confirmed Rule

### 3.1 Same-Minute Arrival / Boarding Boundary

If the following happens within the same minute:

- one player arrives and enters `node` state
- the other player boards and leaves from that same `node`

then the ruling is:

- capture succeeds if both players are tied to the **same train instance**
- capture fails if the two players are tied to **different train instances**

### 3.2 Interpretation

This rule is specifically for the boundary case where one player is finishing an alight transition into node state while the other is starting a boarding transition out of that node.

This means:

- the simulator must not treat this case as automatic `same_node` capture only because both players touched the same node during the same minute
- this boundary must first distinguish same-train overlap from different-train crossing

## 4. Implementation Impact

The implementation must satisfy:

- same-minute `BOARD_TRAIN` / `ALIGHT_TRAIN` crossing cannot be resolved by a coarse “same minute, same station, capture” rule
- it must distinguish:
  - same-train crossing
  - different-train crossing

## 5. Status

- This rule has been explicitly confirmed by Scorp
- It is active from this version onward
