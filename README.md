# Paper Research Daily

**A portable Agent Skill for a personal, evidence-based research reading habit.** Choose a topic, agree on selection standards, and let a tool-enabled agent maintain a local library of verified papers, dense reading cards, and a ranked candidate pool.

[中文说明](README.zh-CN.md) · [Skill instructions](SKILL.md) · [Selection rubric](references/selection.md) · [Reading-card format](references/reading-card.md)

The research question is yours. Robotics, machine learning, biology, social science, or another field can use the same workflow with suitable sources and evidence criteria. The agent reads and reasons; Python handles retrieval, deduplication, state, and report assembly.

## What it does

- Confirms the topic, scope, source policy, quantity, scoring, language, and delivery preferences before starting.
- Defaults to 8 papers: weekdays 4 new + 4 formally published, weekends a combined Top 8; all configurable.
- Supports arXiv search/recent listings, Crossref, and OpenAlex helpers, with official publication and version verification by the agent.
- Scores relevance, evidence, inspiration, novelty, representativeness, and reproducibility; records why a candidate is selected, held, or archived.
- Checks DOI, versionless arXiv ID, normalized title/authors, and file hashes to avoid repeats across versions, dates, and existing PDFs.
- Produces dense cards with a paraphrased abstract, method, sourced evidence, limitations, research relevance, and a testable next step.
- Saves local dated folders, available PDFs, metadata, logs, an index, and candidate history. Preparation never consumes recommendation slots.

This is an agent workflow with deterministic helpers. The Python CLI alone does not read papers, judge scientific quality, or generate scholarly reviews. No paid model service or API key is bundled.

## Install

Requires **Python 3.11+**, a tool-enabled agent, and network access for live discovery. Clone or download this repository, open a terminal in it, and create an environment.

macOS:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -e .
.venv/bin/python scripts/paper_daily.py doctor
```

Windows PowerShell:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\python.exe scripts/paper_daily.py doctor
```

Install the folder with your agent's skill installer, or copy it into the host's skill directory. The included helper accepts a destination parent:

```text
python scripts/install_skill.py --dest /path/to/skills
```

It installs `paper-research-daily` beneath that directory. Use the environment's Python in these commands; Windows paths may be passed with quotes. See [agent and OS adapters](references/adapters.md) for details. For an agent without skill discovery, supply `SKILL.md` explicitly and allow access to its references and scripts.

## Start with your research question

Ask the agent:

> Use paper-research-daily. I study reliable learning from limited data. Help me define the scope and selection standards, then create a daily literature folder. Ask me to confirm the profile before starting. Use English and my local timezone.

The agent creates a draft, discusses choices, and records your approval. You can also initialize the draft yourself:

```text
python scripts/paper_daily.py init --profile ./my-profile.json --topic "Reliable learning with limited data" --root ./my-literature --language en --timezone Europe/London
python scripts/paper_daily.py check-profile --profile ./my-profile.json
```

After reviewing and approving the real profile:

```text
python scripts/paper_daily.py confirm --profile ./my-profile.json
```

`confirm` records your decision; it does not ask for or independently authenticate approval. Editing a confirmed profile invalidates its fingerprint and requires reconfirmation. Keep personal profiles and libraries outside the public repository. A relative library root is resolved from the profile's directory.

## Default selection policy

| Setting | Starting value |
| --- | --- |
| Daily count | 8 |
| Weekday mix | 4 new + 4 formally published |
| Weekend | Combined Top 8 from active candidates and new discoveries |
| New-work discovery | arXiv only; configurable for other fields |
| Freshness | 72 hours, widened to 7 days when needed |
| Scores | Relevance 35, evidence 25, inspiration 20, novelty 10, representativeness 5, reproducibility 5 |
| Recommendation floor | 75 total and 25 relevance; reasons required |
| Reading depth | Full-text, dense; Chinese or English |
| Active pool | Up to 100 entries, reassessed after 14 days |
| Scheduling | Disabled; manual execution by default |

First announcement, submission, revision, online publication, and issue dates are distinct. A preprint DOI does not prove peer review. Source failures are reported; the agent does not lower quality standards to fill a quota. If too few papers qualify, version 0.1 saves partial prepared work and reports the shortfall instead of publishing an incomplete digest. Pool size and reassessment are agent-managed policies, not automatic pruning. See [onboarding](references/onboarding.md) and [selection](references/selection.md).

## Library layout

```text
my-literature/
├── YYYY-MM-DD/
│   ├── 00_overview.md
│   ├── 01_...pdf
│   ├── metadata.json
│   └── search_log.json
├── index.md
├── pool.md
├── pending.md
├── archive.md
├── registry.json
└── .work/
```

Each card includes the original abstract in faithful paraphrase, problem and setting, core method, innovation, an evidence table with locations, concrete limitations, relevance to your question, a proposed next step, reading/reproduction links, and a score rationale. Suggested experiments are labeled as suggestions. Missing full text, unverified code, and scanned PDFs remain visible limitations.

## Helper commands

Use `python scripts/paper_daily.py COMMAND --help` for arguments, or `paper-daily` after activating the installed environment.

| Command | Purpose |
| --- | --- |
| `init`, `check-profile`, `confirm` | Create, inspect, and record approval of a research profile |
| `scan` | Register existing local PDFs before new candidate downloads |
| `search` | Retrieve discovery records from `arxiv`, `arxiv-recent`, `crossref`, or `openalex` |
| `download` | Download and inspect a PDF |
| `prepare` | Store reading work without recommendation history |
| `pool` | Update candidate/pending/archive records |
| `publish` | Assemble an agent-curated digest and update the library |
| `validate` | Check library integrity and optional date output |
| `doctor` | Check Python dependencies and timezone support |

Search results are unverified candidates. The agent must enrich them with source evidence, reading cards, and scores before publication. Candidate inputs accept an array or `{"papers": [...]}`; see [the candidate contract](references/candidate-schema.md) and the deliberately synthetic examples. Examples are not publishable research evidence.

## Recurring execution

An agent app's scheduler, macOS `launchd`, Windows Task Scheduler, or another runner can wake a real agent with this skill and the confirmed profile. There is no scheduler installed by default. A schedule must invoke the actual agent runtime; scheduling the Python helper alone will not produce a reviewed digest. Timezone, daylight-saving, source release, overlap, and recovery guidance is in [scheduling](references/scheduling.md).

## Compatibility and tests

The core is standard Python with a macOS/Windows CI matrix. Check the repository's Actions results for the actual tested commits and platforms. The skill follows the [Agent Skills specification](https://agentskills.io/specification); instructions for additional agents are adapters, not a claim of end-to-end validation on every product. Host tool access, authentication, PDF reading, and scheduling capabilities still matter.

Run the test suite from the repository:

```text
python -m pip install -e ".[test]"
python -m pytest -q
```

## Privacy, sources, and license

Output stays local by default. No library upload, email delivery, account login, or persistent schedule is silently enabled. Credentials, cookies, private PDFs, and recommendation histories do not belong in the public skill package. Institutional access uses the host's authorized session; human verification can remain pending without blocking other papers.

The workflow draws inspiration from [arxiv](https://smithery.ai/skills/lianggs8/arxiv), [paper-daily](https://smithery.ai/skills/su-lan/paper-daily), [paper-read-skill](https://github.com/Ayanami0730/paper-read-skill), and [nature-academic-search](https://github.com/Yuan1z0825/nature-skills/tree/main/skills/nature-academic-search). They are not installed or required by this package. The implementation and documentation here are independently authored; third-party papers and services retain their own terms.

Code and skill materials: [MIT](LICENSE).
