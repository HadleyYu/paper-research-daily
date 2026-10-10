# Dense reading cards

Write for a reader deciding what to study next. Preserve author names, complete title, venue/year or preprint status, actual PDF version, DOI/official entry, local PDF link when present, reading depth, and a one-sentence positioning statement. Do not fill missing metadata with guesses.

Follow with the nine sections below and a score/ranking explanation. Usually 1,200–1,800 Chinese characters per paper gives enough room; complex results may need more, simple ones less. In English use comparable depth, not a mechanical character conversion. Dense means specific, sourced, and decision-useful, not abbreviated until the assumptions disappear.

## 1. Author abstract, faithfully paraphrased

Link the actual abstract used, verify its correspondence to the paper/version, and summarize its question, approach, main result, and claimed significance in your own words. Translate the meaning faithfully into the requested language. Do not reproduce a complete copyrighted English abstract or mix independent criticism into the author's summary. Say when only abstract-level information was accessible.

## 2. Research problem and setting

State the unresolved problem, input/output, available information and data, assumptions, constraints, and evaluation setting. Define terminology needed to understand the paper. Identify what is learned, estimated, optimized, proved, or measured. A reader should understand the task without opening the PDF first.

## 3. Core method

Explain the causal sequence: what happens first, what is computed from what, and why each component is necessary. Include a small number of essential equations when they clarify the mechanism, defining all symbols introduced. Distinguish the method actually evaluated from a conceptual framework, ideal optimizer, or theorem-only construction. Avoid listing module names without explaining their roles.

## 4. Contribution relative to earlier work

State what the paper changes and against which prior approach. Separate a new formulation, theoretical guarantee, algorithm, dataset, engineering improvement, or synthesis. Explain whether the evidence supports the claimed novelty. Evaluate historical papers against their contemporary context; label comparisons to later work as your analysis.

## 5. Evidence table

Include the conditions, baseline/comparison, metric or claim, numerical result where relevant, source location, and boundary of interpretation. Use more than one row where claims depend on different experiments or theorems.

| Claim or question | Conditions and comparison | Result | Source | What it establishes / does not establish |
| --- | --- | --- | --- | --- |
| Specific author claim | Task, data/budget, assumptions, baseline | Value, uncertainty, sample size; or exact guarantee | §, page, theorem, figure/table | Supported conclusion and transfer limits |

Do not invent numbers to populate the table. Proof-based or conceptual work can use explicit propositions, assumptions, counterexamples, or traceable qualitative comparisons. Report failed conditions, negative results, or missing comparisons when material.

Check distinctions that commonly change the conclusion:

- Finite-sample versus asymptotic, local versus global, expected versus per-trajectory guarantees.
- Simulation versus physical deployment, offline replay versus closed-loop execution.
- Relative improvement versus percentage-point change, means versus best runs, and successful-trial subsets versus all trials.
- Prediction accuracy versus uncertainty calibration; marginal coverage versus conditional or shifted-distribution coverage.
- Data collection time versus training, optimization, inference, or end-to-end runtime.
- Theoretical assumptions versus the approximate or learned implementation that was tested.

## 6. Concrete limitations

Explain where the result stops applying and why. Identify relevant assumptions, failure modes, scalability limits, confounders, missing evidence, and unresolved reproductions. Distinguish an author-reported limitation from your inference. Do not add generic “more research is needed” filler.

## 7. Use for this user's research

Connect the paper to the confirmed research question, a project stage, or a specific design decision. Explain which idea, measurement, proof device, contrast, or negative finding can be reused. Mark this as independent analysis; it is not a promise that a result transfers to a new setting.

## 8. Testable next step

Propose a small discriminating experiment, proof check, replication, data audit, or synthesis task suited to the discipline. State the hypothesis, comparison, controlled variables or assumptions, metric, and result that would weaken the idea. Keep it feasible at the user's level and available resources. Label it a suggestion, not work already performed.

## 9. Reading route and reproduction entry

Point to the sections, figures, or proofs to read first and explain the order. Verify that any linked code/data actually belongs to this paper; do not use similarly named repositories or placeholder links. Note versions, dependency or availability limitations when observed. A repository inspection is not a successful reproduction: do not claim code ran unless it did, and record what ran if so.

## Score and ranking

Show the six component scores and total, followed by a short explanation of why the paper belongs at this priority today. Include evidence uncertainty and tie-break reasons where relevant. Keep score maxima consistent with the confirmed profile.

## Structured record

Save the section text, evidence locations, author-claim/analysis distinction, reading depth, exact source links, and score alongside the rendered Markdown. Future reruns should reuse verified reading work instead of reconstructing a shorter, less careful card. Keep structured content and the rendered overview synchronized. See the candidate JSON contract in [candidate-schema](candidate-schema.md).
