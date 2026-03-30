# Public Transit Chase Game Rules Draft v0.5

## 1. Purpose

This document captures the currently agreed game rules and serves as the shared foundation for:

- Further gameplay discussion and iteration
- Technical architecture design
- Data model design
- Node and edge data preparation
- Backend state machine implementation
- Frontend interaction and UI design
- Modular development with Codex

This is **rules draft v0.5**. Some parts are already fixed, while other parts are intentionally left open for later focused discussion.

## 2. Game Overview

This game is an asymmetric chase game built on the **real Japanese public transit network**.  
The first version targets a 1v1 chase system based on the greater Tokyo rail network.

### 2.1 Core Theme

- Inspired by Japanese public-transit chase-and-escape shows
- Built on a real map of Japan
- Movement is based on real public transit routes
- Version 1 focuses on the Tokyo metropolitan area as a playable, testable MVP

### 2.2 Core Gameplay

- Players are divided into the **Runner** side and the **Hunter** side
- Both sides move through public transit plus limited walking
- The Runner wins by surviving until the time limit
- The Hunter wins by catching the Runner before that
- The match is not fully observable; both players rely on periodic location reveals
- The game uses a **real-time flow + periodic planning pause** hybrid structure

## 3. Match Structure

### 3.1 Sides and Player Count

Default mode:

- **1v1**
- Runner: 1 player
- Hunter: 1 player

### 3.2 Default Win Conditions

- **Runner victory**: survive until the time limit
- **Hunter victory**: catch the Runner within the time limit

### 3.3 Default Survival Duration

Current default:

- **2 in-game days**

This is the initial default configuration and may be adjusted after balancing.

## 4. Map and Transit Scope

### 4.1 Version 1 Map Scope

Initial focus:

- **JR Tokyo metropolitan area as the main backbone**

The goal is to validate chase mechanics, capture rules, reveal rules, and movement logic before expanding further.

### 4.2 Included Transit Types

Version 1 includes:

- Rail
- Subway
- Private railways

### 4.3 Excluded Transit Types for Version 1

Version 1 does not include:

- Bus
- Airplane
- Ship
- Overnight bus

These are postponed to reduce system complexity.

## 5. Timetable Rules

### 5.1 Core Principle

Version 1 requires:

- **Strict use of real timetables**

Trains are not abstract frequency spawns. Movement depends on real departures, arrivals, stops, and transfers.

### 5.2 Calendar Type for Version 1

Default:

- **Real weekday timetable**

### 5.3 Future Extensions

- Weekend timetables
- Holiday timetables
- Special operation days
- Mixed or composite timetable sets

## 6. Time System

### 6.1 Base Form

The game uses:

- **Real-time progression**

But not fully uninterrupted real time. It combines:

- Real-time flow
- Periodic pauses
- Pause windows for longer-term planning

### 6.2 Time Scale

Current setting:

- **Game time = real time x 30**

So:

- 1 real minute = 30 in-game minutes
- 1 real hour = 30 in-game hours

Default multiplier for now: **30x**

### 6.3 Periodic Pause

Current setting:

- **Every 1 real hour**, enter a planning pause

### 6.4 Pause Duration

Current setting:

- **60 seconds by default**
- **Configurable**

## 7. Planning Pause and Auto Execution

### 7.1 Behavior During Pause

During the pause:

- Both sides act **simultaneously**
- Decisions are **secret**

### 7.2 What Can Be Planned

Players can pre-plan:

- Which nodes to go to next
- Which trains to board
- Where to get off
- Which nodes to transfer at
- Whether to enter a walking edge
- A future action chain

### 7.3 Auto Execution

After the pause:

- The game resumes in real time
- The system automatically executes the player's planned route

### 7.4 Plan Revisions

At later pause phases:

- Existing plans can be changed
- Future routes can be overwritten
- Players can replan based on new information

## 8. Opening Rules

### 8.1 Default Opening Mode

Version 1 default:

- **Both start from the same game node**
- **Runner starts 1 hour earlier**

### 8.2 Hunter Starting Knowledge

When the Hunter starts:

- The shared starting node is known
- The Runner's full first-hour route is **not** known

### 8.3 Runner Head Start Time Rules

The Runner's 1-hour head start still follows the standard **30x** time system.

### 8.4 Future Opening Variants

Possible later variants:

- Same start, Runner gets 30 minutes
- Different starting nodes
- Randomized balanced start pools
- Free starting point selection

But Version 1 only implements:

- **Same starting node**
- **Runner starts 1 hour earlier**

## 9. Capture Rules

Version 1 uses **automatic capture**. No extra capture action is required.

### 9.1 Same Train Capture

If both players are on:

- **The same train instance**

Then:

- **Immediate capture**

### 9.2 Same Node Capture

If both players are at:

- **The same game node**

And:

- The Runner is **not on a train**

Then:

- **Immediate capture**

### 9.3 Arrival Into Waiting Hunter

If the Hunter is already waiting at a node, and the Runner arrives and enters node state there:

- **Immediate capture**

### 9.4 Walking Edge Capture

If both players are simultaneously on:

- **The same walking edge**

Then:

- **Immediate capture**

Direction does not matter.

### 9.5 Capture Method

Current rule:

- **Automatic capture**

Not used in Version 1:

- Active capture action
- Search action
- Delay-before-capture rules
- Complex contact resolution

## 10. Information Reveal Rules

### 10.1 Core Principle

Normally:

- Neither side sees the opponent's live position

But the system provides periodic intelligence.

### 10.2 Reveal Frequency

Current setting:

- **Every 1 real hour**
- Each side receives one location reveal for the opponent

### 10.3 Reveal Behavior

The reveal is:

- **Instantaneous**

And:

- It does not persist as a last-known-position marker
- It is a one-time reveal at that moment only

## 11. Reveal Details

### 11.1 If the Target Is in a Node

Show:

- **Exact game node**

### 11.2 If the Target Is on a Train

Show:

- **Current segment**

For example:

- `Tokyo -> Shinagawa segment`

This is segment-level information, not necessarily the exact train instance.

### 11.3 If the Target Is Walking

Show:

- **The last departed station or node**

Do not show:

- The walking edge itself
- The current midpoint
- The destination

## 12. Node System

### 12.1 Why Game Nodes Exist

Game positions are not identical to raw real-world station data. To support:

- Capture resolution
- Information reveals
- Transfer modeling
- Walking edge modeling
- Later balance adjustments

The system introduces:

- **Game Nodes**

### 12.2 Nodes Are Not Raw Stations

Game nodes are not directly equal to:

- GTFS raw `stop_id`
- A single operator's real station definition
- A pure station-name merge

They are gameplay-oriented abstractions.

### 12.3 Node Partitioning Principle

Current choice:

- **Hybrid plan C**

Principles:

1. Start from physical structure
2. Reference operator information
3. Adjust for playability

### 12.4 Node Granularity

Current principle:

- **Coarsen normal stations**
- **Split major hubs more finely**

### 12.5 Major Hub Details Deferred

The document currently fixes only the principle, not the exact split plans for each major station.

## 13. In-Node Transfer Rules

### 13.1 Current Rule

Current preference:

- **Instant transfer inside one node**

### 13.2 Meaning

If two routes, platforms, or transit states are modeled inside one game node:

- The player can switch instantly
- No additional transfer duration is added

### 13.3 Not Used for Now

- Tiered transfer times
- 1-minute / 3-minute / 5-minute categories
- Pairwise transfer duration definitions

### 13.4 Design Note

If a node becomes too large, instant transfer may create too much mobility. This should be compensated by splitting large hubs into multiple nodes.

## 14. Walking System

### 14.1 Overall Principle

Walking is allowed, but:

- It is not free movement in continuous space
- It is a special edge on the graph

### 14.2 Walking Edge

The system introduces:

- **Walk Edge**

to represent walk-based transfers between nodes.

### 14.3 Walk Edge Limit

Version 1 rule:

- Legal walking edges must take **15 minutes or less**

### 14.4 Data Source

All walking edges must be generated in **offline preprocessing**.

- No live network queries during gameplay
- No real-time routing search during the match

### 14.5 Why Offline Generation Is Required

- Online queries are unstable
- Third-party map results may change
- Game data must stay fixed and reproducible
- The scale is too large for manual lookup
- Local batch generation and versioning are needed

### 14.6 Accepted Preparation Direction

- Local batch search, preprocessing, and filtering
- Export to static data files
- Read directly at runtime

### 14.7 Walking Reveal and Capture

If a player is walking:

- Reveal shows only the previous station or node
- If both players occupy the same walk edge at the same time, capture happens immediately

## 15. Explicitly Out of Scope or Deferred for Now

### 15.1 No Active Capture Action

Version 1 does not require:

- A button press to capture
- Search then capture
- Delayed capture

### 15.2 No Persistent Trail Visualization

After a reveal:

- Last known position is not persistently shown

### 15.3 No Freeform Walking

Players cannot:

- Draw arbitrary walking paths on a continuous map
- Move freely across city space

Only predefined walking edges are allowed.

### 15.4 No Extra Transit Types Yet

Version 1 does not include:

- Bus
- Airplane
- Ship
- Overnight bus

### 15.5 Exact Major-Hub Splits Not Finalized

Examples still pending:

- How to split Shinjuku
- How to split Tokyo
- How to handle JR Hachioji and Keio Hachioji
- How to handle Daimon and Hamamatsucho

## 16. Technical Implications

These rules imply that Version 1 is fundamentally:

- **An asymmetric chase game on a discrete transit graph**

Player position always belongs to one of three carriers:

1. **Game node**
2. **Train instance**
3. **Walking edge**

Capture can only happen on these three discrete carriers:

- Same node
- Same train
- Same walking edge

This makes the system well-suited for:

- Graph-based modeling
- Discrete state machines
- Event-driven progression
- Timed intelligence reveals
- Auto-executed plans
- Server-authoritative synchronization

## 17. Topics Reserved for Later

- Exact split plans for major hubs
- Offline generation rules for walking edges
- More opening variants
- Weekend, holiday, and composite timetables
- Enhanced reveal formatting

## 18. Current Conclusion

At this stage, rules draft v0.5 is already sufficient to begin technical design. It defines:

- Match structure
- Win conditions
- Map scope
- Timetable realism
- Time progression rules
- Planning pauses
- Auto route execution
- Opening logic
- Capture logic
- Information reveal rules
- Node system
- Walking system

So work can now move into:

- Data model design
- Node and edge schema
- State machine definition
- Opening flow definition
- Capture pseudocode
- Offline preprocessing pipeline design

## 19. Version Info

- Document name: Public Transit Chase Game Rules Draft
- Current version: **v0.5**
- Status: still evolving
- Purpose: the base rules document for future design, development, and Codex collaboration
