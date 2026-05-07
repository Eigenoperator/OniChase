
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
- When Scorp points out one concrete data/display/gameplay defect at a station, line, train, or operator, treat it as evidence of a possible nationwide class of defects. Do not only patch the named example: extract the underlying pattern, run or add a nationwide audit/search for the same pattern, fix all confirmed same-class cases, and record any intentional exceptions or unresolved candidates.

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
- In the current v4 playtest, nearby JR/private-rail terminal station groups with normalized matching names, such as `名古屋` / `名鉄名古屋` / `近鉄名古屋`, are treated as direct transfer-equivalent for planning. The transfer edge must carry an explicit transfer-time field, currently `0`, so a future walking system can replace it with nonzero time without changing the station identity model.
- Branded-prefix station names are direct-transfer candidates in the current v4 playtest, including pairs such as `蒲田` / `京急蒲田`; future walking-time work may keep them transferable while adding nonzero transfer time.

## 15. Through-Running Classification Must Be Physical

- Shinkansen services are never merged by broad JR family, shared station, or shared corridor.
- Different named Shinkansen routes must remain separately classified by their own Shinkansen route name.
- Non-Shinkansen through-running exists only when trains actually run on the same physical track and stop at the same platform/boarding face.
- The unified principle for deciding whether two services should be treated as the same line, equivalent direct service, or mergeable player-facing line is whether a player would board/alight on the same platform or same boarding face for the relevant movement.
- Player-facing route choices must classify the immediate boarding segment by the current physical large line only. Remote through-running labels such as `横須賀線`, `総武快速線`, `湘南新宿ライン`, `京葉線`, or similar destination-side service identities may appear in selected-train labels when the train is chosen, but must not replace `内房線`, `外房線`, `成田線`, or any other current physical boarding line in the route-choice list.
- Physical boundary stations count as belonging to both adjacent lines for route-choice and service-pattern membership. For example, a two-line boundary station must remain present in both line patterns even when a train immediately departs from only one side.
- For v4 player-facing route choices and ordinary train labels, the Ueno-Tokyo/JR East northern trunk must use the physical line scope as the judgment rule: `東北本線` is the main line from `東京` through `上野` and `大宮` toward `盛岡`; `常磐線` is the branch that starts at `上野`; `高崎線` is the branch that starts at `大宮`. `上野東京ライン` is only the public nickname/display label for `東北本線` trains while they are on the `東京`-`上野` segment, and must not be used as the actual classification principle. South of `東京`, use `東海道線`.
- Selected-train row labels must not expose raw subway registry names like `2号線日比谷線`; use the public line name such as `日比谷線`.
- Selected-train row labels for limited express and Shinkansen services must include the public train number when one exists.
- Selected-train row labels for ordinary through-running services should show the line the train is currently heading toward in the direct-service chain: for `A-B-C`, an `A-B` segment train heading toward `C` displays the `C` line, while the reverse direction displays the `A` line even when the vehicle belongs to company `C`; for `A-B(-D)-C`, the branch line appears only when the train is actually heading toward branch `D`. 名古屋鉄道 follows this same direction-side rule, including airport-branch services.
- Player-facing route labels and selected-train labels must not use decorative parentheses around line names. Prefer plain operator-prefixed labels such as `名鉄空港線` instead of `名鉄（空港線）`.
- Coupled split/join trains (`併結運転` / `分割・併合`, similar to `多層建て列車`) are a separate model from ordinary through-running. When reviewed coupled portions represent one physical passenger train at the boarding point, show one umbrella train name joined with the Japanese middle dot, such as `関空快速・紀州路快速`, and selecting it must go directly to alighting stations. Do not show an extra branch/portion picker after the player has already selected the coupled train. Before the physical join point, portions may still appear as separate trains because the passenger has not yet boarded the coupled physical train. During the shared coupled segment, all portions in the same coupled physical group count as `same_train` for capture.
- Shinkansen coupled services are the exception to the coupled-display rule. Do not merge their player-facing route choices or train rows into a shared combined corridor such as `東北・北海道・秋田新幹線`; keep each portion visible under its own Shinkansen route, such as `東北・北海道新幹線`, `秋田新幹線`, or `山形新幹線`. The capture/win-loss engine must still treat coupled Shinkansen portions as `same_train` during the shared physical segment.
- Mini-Shinkansen public route identity and ordinary branch-line identity must stay separate. A `つばさ` or `こまち` route choice and recorded train trace must remain Shinkansen (`山形新幹線` or `秋田新幹線`) on the branch, not fall into ordinary `奥羽線` or `田沢湖線` train categories. The shared trunk before `福島`/`盛岡` may resolve to physical `東北新幹線` for continuous geometry/highlighting, but the branch-side database identity stays independent from ordinary rail services.
- Through-running, stitched-trip, and coupled-service metadata is internal unless it is part of an official public train/route label. Do not append generic explanatory text like `直通` to train rows, train previews, current-plan cards, replay rows, or bottom scrolling playback. Official service names that inherently contain the word, such as `直通快速`, may still display normally.
- Shared operators, shared station groups, transfer permission, nearby geometry, or parallel corridors do not by themselves make two lines through-running equivalents.
- Ordinary lines such as Tokaido Line, Yokosuka Line, Yamanote Line, and Keihin-Tohoku Line must remain separate categories unless the specific train movement truly uses the same track and platform as another service.

## 16. V4 Timetable Station Matching Reuses V3 Method

- V4 timetable stop matching must reuse the v3 station alias and station-group matching method.
- Do not create a separate v4-only station identity system for timetable ingestion unless Scorp explicitly approves a versioned replacement.
- Physical station coordinates and line geometry remain separate from gameplay station groups, following the existing v3/v4 identity split.

## 17. New Data Must Be Audited Against Old Data

- When adding a new timetable, route, station, operator, cache, or derived data source, always check how it overlaps with existing sources before treating the new data as authoritative.
- New data can improve coverage, but it can also conflict with older data on the same station, route segment, train family, operator boundary, route name, public label, or physical trace. These overlaps must be explicitly audited.
- For route-choice and train-label data, verify both the source route identity and the player-facing boarding segment. A new source must not make old correct physical-line choices disappear or leak remote through-service labels into the 1/3 route-choice page.
- If a new source and an old source both describe the same train or same movement, define or reuse a deterministic priority/merge rule, then add an audit or regression sample covering the overlap.
- For sparse-stop limited express collection, do not rely only on intermediate stations that the train may skip. Include the official timetable tabs at boundary/terminal stations that expose the line service, such as 京都 and 敦賀 for 湖西線 Thunderbird, and add number-gap regression checks for the named service family.
- Do not fix only the newly observed station after a conflict is found. Extract the overlap pattern, search for the same class nationwide, and record intentional exceptions in tests or memory.

## 18. Highlights Must Be Continuous

- Every player-facing map highlight must represent one continuous physical path or one continuous reviewed path chain from the selected/current point forward.
- A highlight may contain multiple route ids when a real train runs through multiple lines, but adjacent highlighted segments must connect at the same boundary station or same physical path endpoint.
- Do not display a train highlight as disconnected route fragments just because several future line identities are relevant.
- For selected-train highlights, prefer the train's recorded trace and reviewed path hints over inferred route collections. If the actual route of a train is unclear, verify it from reliable timetable/route sources before adding a reviewed hint.
- If a limited express or other long-distance service has an ambiguous physical route, such as `サンダーバード` or similar, search current sources and record the reviewed route assumption before using it for highlight continuity.
- Selected-train highlights and in-train player movement must never use long station-to-station synthetic geometry as a substitute for a missing physical line. If a sparse-stop train skips many stations, the path must be built from real route geometry or from reviewed path hints. Missing geometry is a data/audit problem, not permission to draw a fake straight branch.
- Conventional trains and limited express trains must not borrow Shinkansen geometry just because the station pair has a shorter Shinkansen-shaped path. Shinkansen geometry is only valid for Shinkansen trips.
