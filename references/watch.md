# Optional researcher and team watch (v0.2)

Use this workflow only when the user enables `watch`. The agent searches, reads, verifies, and decides; Python records and validates supplied evidence. A missing `watch` field means disabled. Loading an old profile does not add defaults or change its confirmation fingerprint. An intentional enabled configuration is a standards change; existing explicit approval for that change is sufficient to record confirmation.

## Discovery and judgment

Keep broad topic discovery alongside directed author searches. For an arXiv-only new-paper quota, run arXiv topic/author queries first, then official team publication pages, project pages, and repositories explicitly linked by authors. Social posts are leads only. An item first discovered on a lab website can be a news event; do not retroactively claim independent arXiv discovery for its paper quota.

Track only the user's chosen researchers/teams. Verify membership and ownership from official sources; do not silently include all alumni or coauthors. Do not add author prestige to paper scores. Event impact (0–5) expresses how much a verified change affects a present research/experiment decision; it is separate from the paper's 100-point rubric.

Eligible events: new papers, substantive revisions, code/weights/datasets, technical reports and talks with usable technical content. Exclude promotion, awards, recruitment and trivial commits. A daily item normally contains 150–250 Chinese characters across its substantive prose (or comparable concise English), plus dates and links: what changed, evidence, connection to the topic, next action, limits. Do not pad or report an event solely because an important person posted it.

First observation establishes a baseline. Save known older work as `baseline`; unknown publication dates as `unknown_date`. Never substitute HTTP Last-Modified, page refresh time or your discovery date for the event date. A demonstrably recent event can be eligible during initialization, but explain the dated evidence. A partial/failed fetch is neither an empty source nor proof of no news. Coverage must account for every configured target, including failures.

## Profile

Add an optional `watch` object; see [synthetic profile](../examples/profile.watch.example.json). No personal researcher names ship in the default profile.

```json
{
  "enabled": true,
  "daily_limit": 3,
  "targets": [
    {"id": "example-lab", "name": "Example Lab", "relevance": "Limited-data decisions",
     "official_urls": ["https://example.org/lab"]}
  ],
  "weekly": {"enabled": true, "weekday": 6}
}
```

`daily_limit` is 0–3; `weekday: 6` means Sunday in the profile's report timezone. The report's date can differ from the scheduler's date. The last seven days are an exact timestamp interval ending at generation, not a calendar week selected in the host timezone.

## Input and identity contract

[watch.example.json](../examples/watch.example.json) is synthetic and intentionally cannot be published as real evidence. A real input is one object:

- `schema_version: 1`, `date: YYYY-MM-DD`, `timezone`, `generated_at` (aware ISO timestamp).
- `coverage`: one row per target: `target_id`, `status` (`checked`, `baseline`, `partial`, `failed`), `checked_at`, `detail`, attempted `sources` URLs. Store query strings, fetch errors and raw evidence paths as extra fields if useful.
- `events`: every assessed event, including excluded, baseline, undated and quota-deferred items. Each has `kind` (`paper`, `revision`, `code`, `weights`, `dataset`, `talk`), `revision`, `title`, `target_ids`, `work`, `occurred_at`, `date_evidence`, `first_discovered_at`, `verified_at`, `disposition`, six prose fields below, `impact`, `impact_reason`, and original `sources`.
- Prose fields: `summary`, `delta`, `relevance`, `action`, `limitations`; noneligible entries also require `reason`. `sources` rows require `url`, `primary: true` for at least one, `supports`, `verified_at`. These record the agent's verification; Python does not establish scholarly truth or fetch pages.
- `work` supplies `arxiv_id` (versions stripped for matching), `doi`, or `title` + `authors`, or `official_url`. Include all verified identifiers to bridge publication and preprint versions. The event is matched by overlapping work identities **plus kind and revision**, not by author name. Multiple target/source observations of the same event merge. Conflicting dates/dispositions or an ambiguous bridge require reconciliation, not a guessed merge.
- `revision` identifies the actual event, e.g. `v3` for a paper revision, or `owner/repository@release-tag-or-commit` for code. Do not use the scrape date. Several small commits belonging to one substantive release are one event.
- `occurred_at: null` requires `disposition: unknown_date`. `eligible` requires dated evidence within seven days. Old material remains baseline/archive. If only a calendar date is known, record its precision and source timezone explicitly; do not invent an exact release hour in the prose.
- An old recommended paper can have a new code event. The paper's recommendation history stays untouched. If the work is also in today's selected papers, set `in_daily_papers: true` and supply `additional_information` describing the actual new material; otherwise omit the redundant event and link from the paper card. `paper_ref` may link to its official entry.

Retain not-selected reasons. Python sorts eligible events by impact and then occurrence time, limits them to the configured count, and rejects previously displayed or baseline-identical events. Prepared snapshots do not update display history. The agent must carry still-relevant unselected candidates from `watch/registry.json` into later input and recheck freshness; helpers do not autonomously search or revive them.

## Sunday route review

On an enabled local Sunday, supply `weekly` even if evidence is insufficient:

```json
{
  "status": "insufficient_evidence",
  "reason": "Only a baseline is established; no verified change of research route.",
  "window_start": "2026-10-11T00:05:00+00:00",
  "window_end": "2026-10-18T00:05:00+00:00",
  "changes": [], "questions": []
}
```

For `status: reviewed`, give 1–3 `changes` and 1–2 testable `questions`. Every change contains `before`, `addition`, `remaining`, `relevance`, and `sources` with `url`, `occurred_at`, `supports` for evidence in the window. Link older prior work in `before`; do not present that older publication as new evidence. Use “previous problem → new addition → remaining gap.” Unrelated publications are not evidence that a team is changing direction. When coverage fails or evidence is thin, state the limit rather than inventing a trend.

## Commands and output

From the skill directory (same syntax on macOS and Windows with the chosen Python):

```text
python scripts/paper_daily.py watch prepare --profile my-profile.json --input observed-events.json --date YYYY-MM-DD
python scripts/paper_daily.py watch publish --profile my-profile.json --input observed-events.json --date YYYY-MM-DD
python scripts/paper_daily.py watch validate --profile my-profile.json --date YYYY-MM-DD
python scripts/paper_daily.py prepare --profile my-profile.json --input papers.json --date YYYY-MM-DD --updates literature/watch/.work/prepared/YYYY-MM-DD/snapshot.json
python scripts/paper_daily.py publish --profile my-profile.json --input papers.json --date YYYY-MM-DD --updates literature/watch/YYYY-MM-DD/updates.json
```

Dynamic updates appear **before the paper table and reading cards**; the Sunday review follows updates, also before papers. Omit `--updates` for unchanged v0.1 paper behavior. All three existing paper inputs (array, `papers`, `candidates`) remain supported. Publication needs a committed watch snapshot; preparation can use prepared or published snapshots. The supplied snapshot is copied into the paper transaction. Invalid/unavailable optional snapshots are reported as `updates_error` by the CLI while papers proceed; disclose that failure to the user. A valid failed-coverage snapshot displays its gaps in the overview. Do not retry inaccessible sources indefinitely or miss the paper deadline for news.

Watch-only commands write exclusively beneath `output_root/watch/`:

```text
watch/
  registry.json
  .watch.lock                         # only while writing
  .work/prepared/YYYY-MM-DD/           # candidate snapshot, no displayed slots
  .work/publication.json               # recoverable commit journal, normally absent
  YYYY-MM-DD/updates.json
  YYYY-MM-DD/00_updates.md
```

An identical same-date input returns `unchanged` / `notify: false`. Changed content for a committed date is refused, protecting the archive. Resume an interrupted publication with the same command/input; it completes its journal. If a process died leaving a lock, inspect the process before removing that specific stale lock. Neither the watch lock nor transaction touches the paper registry or dated paper folders. Do not mutate historical digests to install this feature.

## Existing personal/custom libraries

Do not migrate an existing Chinese/custom paper registry into the public tool schema. Create a separate, local watch-enabled profile pointing at that library and use **only `watch` subcommands** there. Let its existing paper writer read `watch/YYYY-MM-DD/00_updates.md` (or render `updates.json`) and insert the section before its paper table. Keep the existing paper validation and add watch validation. Do not invoke public `scan`, `prepare`, `pool`, or `publish` against a foreign registry.

Prepare phase: fetch/verify targets, compare the baseline, save events without consuming slots. Final phase: recheck public sources, publish the independent watch snapshot, prepend it to that day's new paper report, and validate both. Next-day activation and output order belong in both persistent tasks, not merely in a chat reply. Credentials and private state stay local; only generic code, instructions and synthetic examples belong in a public release.

`disposition` uses these exact values: `eligible` (consider for display), `baseline` (already-known work), `unknown_date` (cannot verify when it happened), `exclude` (not relevant/substantive enough). Only `eligible` competes for daily slots. The helper additionally excludes previously displayed events and records quota-deferred reasons.
