
## 1. Canonical Files

- All markdown filenames must use uppercase letters, such as `STATUS.md` and `MEMORY.md`.
- Root control markdown files use uppercase names.
- Daily raw logs use `memory/MEMORY-YYYY-MM-DD.md`.
- Daily summaries use `diary/DIARY-YYYY-MM-DD.md`.

## 2. Memory Discipline

- Every meaningful change must be appended to the daily `memory` file with a real timestamp.
- Never overwrite a daily `memory` file; always read first and append by edit.
- `MEMORY.md` is curated long-term memory, not a raw log.
- Daily memory files must use the header format `# Daily Memory - YYYY-MM-DD`.
- Each daily memory entry must use the format `- YYYY-MM-DD HH:MM:SS ZZZ - ...`.
- Daily memory timestamps must be exact to the second; never use rounded, placeholder, or invented times.

## 3. Status Discipline

- Read `STATUS.md` before starting work.
- Update `STATUS.md` before ending work.
- At the start of work, always read `STATUS.md`.
- At the end of work, `STATUS.md` must be updated in `Done`, `In Progress`, `Blockers`, and `Next`.
- `STATUS.md` must stay short and directly useful for handoff.
- `STATUS.md` must stay at or under 50 lines.
- When it grows, archive older done items and older decisions into `HISTORY.md`.
- If today's work changes project direction or adds stable milestones, reflect that the same day in `STATUS.md` and `HISTORY.md`.

## 4. Diary Discipline

- On the first prompt of a natural day, check and backfill yesterday's diary if missing.
- Do not proactively write today's diary at the start of the day.
- Diary entries stay concise, in Chinese, and may include a small amount of key technical detail.

## 5. System Rules Belong Here

- Any stable project-wide workflow, naming, documentation, backup, or coordination rule from Scorp must be promoted into `AXIOMS.md`.
- Do not leave system-level rules only in chat context.
- Talk with Scorp in Chinese by default. Use English only where code, commands, file names, commit messages, technical identifiers, or source text make English clearer.

## 6. Environment Isolation

- One module, one dedicated conda environment.
- Do not reuse another module's environment just because it already exists.
- Under `~/code`, module-specific conda setup is pre-approved.

## 7. Reusable Scripts

- Project scripts must be scene-agnostic and reusable.
- Do not hardcode `toycase`, `img1`, or similar one-off names into core logic.
- Scene-specific information belongs in arguments, config, inputs, or output directories.
- When writing scripts, focus on the real game architecture and real production data flow, not throwaway test-map-specific logic.
- Script names should describe responsibility or external source format, not the current temporary map choice unless the script is truly dataset-specific.

## 8. Reproducible Commands

- If Scorp needs to view or rerun a result, provide a complete command.
- Include the exact `cd`, executable, arguments, and relevant environment usage.

## 9. Git Backup Hygiene

- Keep the project under git version control.
- Use English commit messages.
- Do not commit and push for every small change.
- Commit and push when there is a significant change worth syncing.
- Still make sure the project is committed and pushed at least once per natural day when work happened that day.
- When writing or backfilling a diary, also check whether the current project state should be committed and synced.
- If diary-time sync does not happen, record the reason immediately in `STATUS.md` or the daily `memory` file as an explicit blocker.
- Prefer syncing stable control files, scripts, docs, and selected experiment artifacts, not caches or third-party dependencies.

## 10. Rule Violations Must Be Fixed Systemically

- If a stable rule is violated, do not only apologize in chat; update the relevant control files so the same mistake is less likely next time.
- Use `AXIOMS.md`, `STATUS.md`, `HISTORY.md`, and git history together as the memory system for tomorrow's session.

## 11. Rule File Protection

- If a game rule should be changed, ask Scorp first before making any rule change proposal active.
- Never edit an existing rule document in place.
- Any rule evolution must be written as a new rule file or a new versioned rule document.
- Rule documents in `rule/` must use the naming pattern `RULES_vX.Y.md`.
- English working translations of rule documents in `rule/` must use the naming pattern `RULES_vX.Y-EN.md`.
- When a new rule version is created, keep older rule versions unchanged and preserved side by side.
- Every new rule version file must state the main change at the top, immediately below the title, before the detailed sections.

## 12. Local And Online Playtest Parity

- The local playtest client and the online browser playtest must stay aligned to the same primary gameplay flow.
- Do not let the online version drift into a separate product or legacy prototype.
- Do not deploy the Render room server anymore. Room-server deployment is forbidden unless Scorp explicitly reverses this axiom in a future written instruction.
- When a meaningful playtest-facing feature is added to one primary client, evaluate whether the other primary client should receive the same gameplay capability or an explicitly documented temporary gap.
- Single-player mode and multiplayer mode must preserve the same core gameplay loop, timing rules, and planning/live/capture logic.
- Single-player mode should be treated as the same game against an AI or automated opponent, not as a separate ruleset or simplified variant.

## 13. Line Scope Completeness

- If a line is added to a version scope, add the whole line rather than only an arbitrary partial segment.
- Temporary implementation limits may still delay some data ingestion, but the intended version scope should not define a line as “partially included” unless the line itself is formally split into different services or route families.
- For private rail operators, if one line from that company is added to scope, the intended scope should include that company's whole rail network rather than only a hand-picked subset of lines.

## 14. Interchange Geometry Must Stay Physical

- Do not collapse distinct physical interchange stations into one fake shared latitude/longitude point just because gameplay allows transfers there.
- This is especially important when the interchange spans different operators or companies.
- Gameplay may still group nearby physical stations into one transfer-capable station group, but the map and physical-network layers must preserve the distinct real station locations and distinct real line geometry.

## 15. Through-Running Classification Must Be Physical

- Shinkansen services are never merged by broad JR family, shared station, or shared corridor.
- Different named Shinkansen routes must remain separately classified by their own Shinkansen route name.
- Non-Shinkansen through-running exists only when trains actually run on the same physical track and stop at the same platform/boarding face.
- The unified principle for deciding whether two services should be treated as the same line, equivalent direct service, or mergeable player-facing line is whether a player would board/alight on the same platform or same boarding face for the relevant movement.
- For v4 player-facing route choices and ordinary train labels, the Ueno-Tokyo/JR East northern trunk must use the physical line scope as the judgment rule: `東北本線` is the main line from `東京` through `上野` and `大宮` toward `盛岡`; `常磐線` is the branch that starts at `上野`; `高崎線` is the branch that starts at `大宮`. `上野東京ライン` is only the public nickname/display label for `東北本線` trains while they are on the `東京`-`上野` segment, and must not be used as the actual classification principle. South of `東京`, use `東海道線`.
- Selected-train row labels must not expose raw subway registry names like `2号線日比谷線`; use the public line name such as `日比谷線`.
- Selected-train row labels for limited express and Shinkansen services must include the public train number when one exists.
- Selected-train row labels for ordinary through-running services should show the line the train is currently heading toward in the direct-service chain: for `A-B-C`, an `A-B` segment train heading toward `C` displays the `C` line, while the reverse direction displays the `A` line even when the vehicle belongs to company `C`; for `A-B(-D)-C`, the branch line appears only when the train is actually heading toward branch `D`.
- Shared operators, shared station groups, transfer permission, nearby geometry, or parallel corridors do not by themselves make two lines through-running equivalents.
- Ordinary lines such as Tokaido Line, Yokosuka Line, Yamanote Line, and Keihin-Tohoku Line must remain separate categories unless the specific train movement truly uses the same track and platform as another service.

## 16. V4 Timetable Station Matching Reuses V3 Method

- V4 timetable stop matching must reuse the v3 station alias and station-group matching method.
- Do not create a separate v4-only station identity system for timetable ingestion unless Scorp explicitly approves a versioned replacement.
- Physical station coordinates and line geometry remain separate from gameplay station groups, following the existing v3/v4 identity split.
