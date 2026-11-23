# Statistical analysis

Python 3.13, as in the protocol. Primary sample = 4 LLMs × 9 prompt frames × 16 vignettes = 576 responses. Recommendation-level N is larger.

## Outcomes

| Outcome | Level | Values |
|---|---|---|
| Accuracy | recommendation | accurate / inaccurate / unclear |
| Accurate (binary) | recommendation | accurate vs not (inaccurate+unclear) — secondary sensitivity: drop unclear |
| ≥1 inaccurate rec | turn | yes/no |
| Proportion accurate recs | turn | 0–1 |
| Disclaimer | turn | yes/no |
| Potential harm | turn | yes/no |
| Citation issue | turn | none / unverified / fabricated_suspected |

Primary accuracy comparison uses **recommendation-level** labels, matching the protocol (“each recommendation given in a response”).

## Descriptive (protocol)

Frequencies and percentages of accuracy, disclaimers, and harm, overall and stratified by:

- LLM
- prompt_frame (and confirming_true vs confirming_false vs neutral vs comparative vs disagreeing_*)
- vignette_domain
- turn (1 vs 2)
- authority_profession (authority sheets only)

Also report mean (SD) of the turn-level proportion accurate.

## Inferential (LLM comparison)

1. **Omnibus:** χ² of LLM × accuracy (3 levels). If expected counts <5, Fisher–Freeman–Halton.
2. **Pairwise LLMs:** 2×3 (or 2×2 if collapsed) tests with **Bonferroni** (6 pairs among 4 LLMs). Report raw and adjusted p.
3. **Prompt frame:** same tests for prompt_frame × accuracy, and LLM × prompt_frame on binary accurate.
4. **Turn 2 vs turn 1:** did challenging follow-ups change accuracy? McNemar or mixed model on paired turns within `response_id`.
5. **Authority bias (planned exploratory):** among disagreeing_authority sheets, accuracy and “follow the professional” endorsement by `authority_profession`.

Because recommendations are nested in vignettes, prefer a **mixed-effects logit** as the confirmatory model when `statsmodels` or `pymer4` is available:

```
accurate_binary ~ C(llm) + C(prompt_frame) + C(vignette_domain) + C(turn)
                  + (1 | vignette_id)
```

Add `llm:prompt_frame` if the research question (does framing change LLM accuracy?) is tested formally. If the mixed model fails to converge, report GEE with cluster = vignette_id, plus the χ² tables as sensitivity.

## Consistency / reliability (protocol comment, optional)

The protocol body currently specifies descriptive stats only. A comment proposes consistency (rank gap = 0; χ²/Fisher/Yates + Bonferroni) and Fleiss κ for repeatability.

- **Do not run Fleiss κ on this spreadsheet alone.** There is one recorded answer per LLM × vignette × frame, so there are no repeated trials. Fleiss/Cohen κ applies to **dual human coding** of the same recommendations, or to a future repeated-prompt reliability experiment.
- After a second human rater codes a sample, compute Cohen’s κ (2 raters) or Fleiss κ (>2) on accuracy labels.
- “Consistency” across prompt frames for the same vignette can be described as the proportion of vignettes in which an LLM’s accuracy label is unchanged from turn 1 to turn 2; compare those proportions across LLMs with χ²/Fisher.

## Missing data

- Empty cell: exclude that LLM×frame×vignette; report denominator.
- `split_uncertain`: include in rec-level analysis; sensitivity exclude.
- Unclear: keep in 3-level tables; binary analyses run twice (unclear as not-accurate, and dropped).

## Reporting

CHART-aligned: name models, dates, that prompts were new-chat / English, coding framework, and that agent codes are first-pass until dual review.

Script: `python scripts/analyze_accuracy.py --recs data/recommendations.jsonl --out data/stats/`.
