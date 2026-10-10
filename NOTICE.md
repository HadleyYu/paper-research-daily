# Provenance and scope

This repository implements an original, configurable workflow for evidence-based
literature curation. Its code and documentation are distributed under the MIT
license in `LICENSE`.

The workflow was informed by these independently distributed projects:

- [lianggs8/arxiv](https://github.com/Lianggs8/auto-survey-agent/tree/master/skills/arxiv): arXiv retrieval.
- [su-lan/paper-daily](https://github.com/Su-LAN/paper-daily): recurring literature organization.
- [paper-read-skill](https://github.com/Ayanami0730/paper-read-skill): paper-type-aware reading.
- [nature-academic-search](https://github.com/Yuan1z0825/nature-skills/tree/main/skills/nature-academic-search): citation verification.
- [Agent Skills specification](https://agentskills.io/specification): portable skill packaging.

These projects are references, not bundled dependencies. Their source files,
prompt text and licenses have not been copied into this distribution. Installing
this skill does not install or authorize their integrations. If adding borrowed
code in a future contribution, verify its license and retain required notices.

Examples are synthetic configuration and card demonstrations, not reviewed-paper
recommendations. Downloaded papers and users' private profiles, credentials,
libraries, recommendation histories and logs do not belong in this repository.
The MIT license does not relicense papers fetched by users or third-party content.
