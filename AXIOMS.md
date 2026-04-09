
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
- When a meaningful playtest-facing feature is added to one primary client, evaluate whether the other primary client should receive the same gameplay capability or an explicitly documented temporary gap.
