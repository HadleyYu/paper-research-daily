# Discovery, selection, and library state

## Source and freshness rules

Treat discovery, bibliographic verification, publication verification, and full-text reading as separate evidence steps.

For the strict arXiv preset, discover new papers through arXiv's own API, search, recent lists, or feeds. Crossref, OpenAlex, search engines, and publisher sites may verify metadata, locate an older published work, or find lawful copies; they do not establish arXiv-only discovery. Store the discovery URL, query, retrieval time, and relevant list or feed evidence.

Use first public announcement evidence to determine freshness. `submitted` and `updated` timestamps answer different questions: a submission can await announcement; a replacement is not a first release. Record first submission, first announcement, and the downloaded version separately when known. If announcement evidence is missing, mark freshness pending rather than fabricating a date. State which source batches were actually covered, including source holidays or announcement gaps when verified. Do not claim exhaustive coverage from a limited search.

Begin with the configured 72-hour window, widen to the configured maximum (default 7 days), and document widening. If the weekday new-work quota still cannot be filled, use qualified published work where allowed by the confirmed plan. If the total remains insufficient, save the partial evidence with `prepare` and report the actual count, missing slots, and reasons; the helper refuses to publish an incomplete digest. A network failure or rate limit is a retrieval problem, not proof that no papers qualify.

For formal publication, verify an official publisher or proceedings record, with author/title identity and venue/year. A source record should carry a publication/proceedings/publisher role and a verified status of `published` or `online_first`. A DOI, a journal-like title, an accepted badge of uncertain provenance, or a preprint's self-description alone is insufficient. A publisher's online-first article is eligible when explicitly labeled as such. Keep its online date separate from the issue date.

Use the official full text where accessible. An author manuscript or arXiv counterpart may be downloaded for a published work, but identify the version and check that important claims still apply. When no lawful full text is available, retain a verified DOI or official entry. Do not invent a DOI to fill a field.

## Scoring rubric

Score against the user's question and the paper type. The following maximums are defaults and can be changed in the profile.

| Dimension | Maximum | Basis |
| --- | ---: | --- |
| Relevance | 35 | Directly addresses the target question, constraints, setting, or an indispensable method |
| Evidence | 25 | Claims supported by appropriate proofs, experiments, data, comparisons, or a defensible synthesis |
| Inspiration | 20 | Supplies a concrete reusable idea, useful contrast, failure mode, or next research step |
| Novelty | 10 | Substantive advance over the relevant prior work, evaluated at time of publication |
| Representativeness | 5 | Helps explain an influential approach or a distinct part of the research landscape |
| Reproducibility | 5 | Sufficient procedures, assumptions, data/code, or proof detail to audit or reconstruct the result |

Give reasons for each consequential score, particularly when evidence is weak or a highly cited paper ranks poorly. The default recommendation floor is 75 total and 25 relevance. A theorem can have strong evidence without hardware; a systems result can be valuable without a new theorem. Distinguish the strength of evidence for the paper's actual claim from transferability to the user's proposed setting. Reproducibility is not synonymous with a GitHub link.

Scores are editorial judgments with uncertainty. Do not pretend a one-point difference is experimentally calibrated. For ties, explain whether a stronger connection to the current research question, complementary evidence, or less overlap with recent reading determined the order. Never secretly lower thresholds to reach the daily count.

## Paper-type assessment

- **Theory:** identify assumptions, quantifiers, finite versus asymptotic conclusions, guarantee type, constants or omitted terms, and counterexamples. Check whether the implementation actually meets the theorem's assumptions.
- **Empirical method/system:** compare with relevant baselines using matched budgets, report sample sizes and variability, inspect ablations and failures, and separate simulation from real deployment. A throughput number is not automatically end-to-end latency.
- **Dataset/benchmark:** inspect construction, provenance, leakage, splits, annotation or measurement quality, evaluation validity, and what a score fails to measure.
- **Review/conceptual work:** assess search or argument scope, inclusion bias, taxonomy, supporting evidence, and what remains unresolved. Suggest a verification or synthesis task rather than forcing a laboratory experiment.

## Pools and duplicate identity

`registry.json` is the durable identity/history store. The readable pool, pending, archive, index, and dated outputs are views of that state. Store reasons and evidence when moving entries:

- **Active candidates:** sufficiently promising and not previously recommended; qualified unselected full-text candidates remain available for a later day.
- **Pending:** unresolved identity, publication status, freshness, or full-text evidence. Pending is not a low-quality judgment.
- **Archived/deprioritized:** excluded topic, below threshold, duplicate, insufficient contribution, or stale candidate with a recorded reason. Preserve the reason rather than silently deleting history.

Scan preexisting PDFs before downloading new candidates into the library. First compare DOI and versionless arXiv ID, then title/author normalization and explicit version relationships, then PDF hashes. An accepted manuscript, conference PDF, and arXiv version of the same work are one recommendation. Similar titles or coincidentally identical surnames need human/agent inspection; missing identifiers do not prove distinctness. Unidentified existing files remain unresolved until inspected.

Do not reset recommendation history when a score or version changes. `prepare` must never set recommendation dates. A final `publish` is idempotent for the same date and content; changed results require an explicit, traceable correction rather than a second silent publication. At weekends rank the eligible active pool together with newly assessed work and select the configured combined total. This is the best set among the assessed candidates, not a claim to have found the globally best papers. Pool limits and reassessment intervals are agent-managed; review stale entries explicitly rather than expecting the helper to evaluate or prune them automatically.

## Retrieval log

Keep query/source/time/window, covered batches, records screened at each stage, official metadata links, full-text URL/version, failed attempts, fallback and rate-limit handling, and reasons for acceptance or deferral. Log no credentials, session headers, or private library content sent to external services. Use bounded retry with backoff; switch to an official list or HTML endpoint where appropriate, and preserve the unresolved coverage limitation.
