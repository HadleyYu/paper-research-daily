# Host and operating-system adapters

## What is portable

The repository is an [Agent Skills](https://agentskills.io/specification) folder with a `SKILL.md` entrypoint and standard Python helpers. The instructions are independent of a particular model or account. The agent still needs web retrieval, file access, and command execution to complete the workflow. A host with only text generation can use the rubric and card structure, but cannot claim it downloaded, registered, or validated files.

The documented host integrations are configuration guidance, not a claim that every product/version has been tested. Use the host's supported skill directory or installer. If the host has no skill discovery, explicitly provide `SKILL.md` and let the agent open referenced files when needed.

## Local installation

Python 3.11 or newer is required. Clone or download this repository into a folder named `paper-research-daily`. From that directory:

macOS (zsh/bash):

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -e .
.venv/bin/python scripts/paper_daily.py doctor
```

Windows (PowerShell):

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\python.exe scripts/paper_daily.py doctor
```

These commands invoke the environment's Python directly, so shell activation and PowerShell execution-policy changes are unnecessary. If `py -3` selects a Python older than 3.11, choose an installed supported version explicitly. `tzdata` supplies IANA timezone data where the operating system does not, particularly on Windows.

Run helper commands with this same Python, or activate the environment and use the installed `paper-daily` entrypoint. Quoting a path containing spaces is necessary in both shells. The Python code uses portable paths; scripts must not hard-code a macOS desktop, Windows drive letter, or a specific agent's runtime path.

## Install into a skill directory

Use the host's installer when available. The optional local helper copies the distributable skill files into a chosen parent directory:

```text
python scripts/install_skill.py --dest /path/to/skills
```

The resulting folder is `/path/to/skills/paper-research-daily`. On Windows pass a quoted native path, for example `--dest "C:\Agent Skills"`. Do not copy a virtual environment, personal profile, or literature library into a shared skill package. After copying, install Python dependencies for the environment that will execute the installed copy.

For Codex, use its supported skill installation path or skill installer. For other agents, configure the repository as a skill or attach `SKILL.md` according to that host's current documentation. Do not assume that `agents/openai.yaml` is portable metadata: it is an optional Codex/OpenAI UI adapter, while `SKILL.md` is the shared entrypoint.

## Capability fallback

| Missing capability | Honest behavior |
| --- | --- |
| Web/search connector | Use available official HTTP endpoints via the Python search helper; if networking is unavailable, analyze supplied sources and report discovery as incomplete |
| PDF text extraction | Use an available PDF reader/OCR tool; identify scanned pages and verify important values visually; report unresolved text instead of pretending to have read it |
| Browser/institutional access | Use authorized official or author-hosted copies; preserve DOI/official entry when unavailable |
| Agent scheduling | Provide manual invocation and an external-runner plan; do not claim recurrence is installed |
| Local execution | Provide review text only and clearly state that the library lifecycle was not executed |

The four reference workflows—arXiv retrieval, paper-daily curation, paper-analysis, and nature-academic-search—are optional inspiration, not runtime dependencies. This package does not silently install third-party skills or inherit their upload defaults.

## Portability verification

The repository's CI matrix exercises the Python tests on macOS and Windows, including multiple supported Python versions. Consult the actual Actions run for results. A checked-in workflow is not proof that CI passed, and passing helper tests is not proof of end-to-end compatibility with every agent.

Keep report dates and weekends in the profile's IANA timezone, independent of the machine timezone. Relative library paths are profile-relative. Use filename-safe titles, preserve Unicode content, and keep private paths and credentials out of exported samples.
