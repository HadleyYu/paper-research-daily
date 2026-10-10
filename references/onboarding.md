# Research profile and confirmation

## Ask only what changes the work

Start with the user's own words. Clarify a broad topic into a research question: what is being explained, designed, compared, or improved; under which conditions; and what would count as useful evidence? Do not force all disciplines into a robotics or experiment-oriented template.

Present a compact proposed profile with:

| Choice | What to establish |
| --- | --- |
| Scope | Research question, included topics, excluded topics, background level |
| Sources | Allowed discovery sources for new work; official sources for publication verification; relevant venues as guides |
| Quantity | Daily count, weekday source mix, weekend policy, fallback and shortfall handling |
| Judgment | Scoring weights, minimum total, minimum relevance, evidence requirements |
| Output | Library folder, report language, reading depth, PDF preference |
| Time | Report timezone, optional schedule timezone, preparation/final times, deadline |

Use existing context to propose answers. Confirm these standards once before live collection and recommendation. Keep approval tied to the actual profile; a meaningful topic, source, or threshold change needs reconfirmation. Repeated executions under an unchanged confirmed profile do not need another permission question.

## Built-in starting defaults

The starting profile is editable, not a universal prescription:

- 8 papers per day; weekdays 4 new and 4 formally published; weekends a combined Top 8 from active candidates and that day's discoveries.
- New work discovered on arXiv only, first looking back 72 hours and widening to 7 days if needed. A user in another field can configure other new-work sources.
- Scores: relevance 35, evidence 25, inspiration 20, novelty 10, representativeness 5, reproducibility 5. Minimum total 75 and relevance 25; 85 or more is a useful priority for deeper reading, not an automatic acceptance rule.
- Full-text assessment required by default. If abstract-only coverage is explicitly allowed, label it and limit claims to what was accessible.
- Up to 100 active pool entries, reassessed after 14 days. These are agent-managed editorial policies; the Python helper does not automatically prune or reassess scientific value. Record why entries are kept, deferred, or archived.
- Dense Chinese cards, usually 1,200–1,800 Chinese characters each. English is also supported; content and evidence determine length.
- Report date: `Asia/Shanghai`. Scheduling is disabled. Example scheduling values use `America/New_York`, preparation at 19:00, finalization at 20:05, and delivery by 09:30 in the report timezone. Users should choose times suitable for their sources.

## Create and approve a profile

Commands are shown from the skill directory, using an activated Python environment:

```text
python scripts/paper_daily.py init --profile ./my-profile.json --topic "Reliable learning with limited data" --root ./my-literature --language en --timezone Europe/London
python scripts/paper_daily.py check-profile --profile ./my-profile.json
```

`init` creates a draft. Refine `project.research_question`, `topics`, `exclude`, and the other fields in the JSON before presenting it. A relative `output_root` is resolved against the profile's directory, not whichever directory happens to launch the agent.

After the user approves the actual standards:

```text
python scripts/paper_daily.py confirm --profile ./my-profile.json
```

The command records the confirmed state and timestamp. It is a state-management helper, not an authentication or approval mechanism. The agent must retain the real conversational basis for approval. When revising a confirmed profile materially, set its confirmation back to draft, present the revised standards, and reconfirm after approval.

## Profile structure

| Field | Meaning |
| --- | --- |
| `project` | `name`, `research_question`, `topics`, `exclude`, `level` |
| `output_root` | Local library root; keep generated libraries outside the public skill checkout |
| `language` | `zh-CN` or `en` |
| `timezone` | IANA timezone used for report dates and weekend decisions |
| `selection` | Count, weekday mix, freshness window, thresholds, pool bounds |
| `scoring` | The six maximum point values; must sum to 100 |
| `sources` | Allowed `new` and `published` discovery/verification sources |
| `analysis` | Depth, Chinese length guidance, author/analysis distinction |
| `schedule` | Declarative preferences only; does not install or enable a scheduler |
| `confirmation` | Draft/confirmed state and confirmation timestamp |

Preserve the exact profile used with the run's evidence so a later reader can understand selection decisions. Credentials are never configuration fields.
