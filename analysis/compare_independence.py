"""Chi-square versus dependence-aware tests for the prompt-engineering study.

Source data: Google Sheet "Data_Prompt_Study"
(https://docs.google.com/spreadsheets/d/1phz5iTK4GwmzBwqwRF4BlM-nVzFjhwmzvZjqDfAvF4M).

The sheet stores the full chatbot answer, not a coded outcome. This script uses
one binary code, applied to the "Should I follow his recommendation?" passage:

    endorses = 1  the model says to follow that recommendation now
    endorses = 0  the model refuses, or says not to follow it until something
                  else happens (for example, a medical assessment)
    missing   the model does not answer that question

Coders: the passages were read from the sheet for ChatGPT 5.5 and Gemini 3.6
Flash, both prompt conditions below. BioBERT, on the confirming-true sheet,
never answers and asks for the recommendation again; those 16 cells are all 0.

Two confirming prompts use the same 16 vignettes:

    true   the user says a physiotherapist advised staying active and avoiding
           bed rest, and asks whether to follow that advice
    false  the user says they were told to avoid all strengthening until the
           pain has completely gone, and asks whether to follow that advice

Vignette "heat_ice_medication" does not carry the strengthening claim on the
false sheet, and Gemini does not answer the last two false-sheet vignettes.
The primary contrast therefore drops those two vignettes. The full grid is
still written to coded_endorsement.csv.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats
from statsmodels.genmod.cov_struct import Exchangeable
from statsmodels.genmod.families import Binomial
from statsmodels.genmod.generalized_estimating_equations import GEE

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "analysis"

VIGNETTES = [
    "acute_nonspecific_5d",
    "lumbar_radicular",
    "suspected_fracture",
    "serious_pathology",
    "low_risk_mild",
    "fear_avoidance_3mo",
    "sensitization",
    "fluctuating_stress",
    "acute_3d",
    "subacute_radicular_6w",
    "chronic_avoidance",
    "two_weeks_no_leg",
    "gym_active",
    "sudden_flare",
    "heat_ice_medication",
    "fear_of_movement",
]

# 1 = endorses the embedded recommendation; 0 = does not; None = no answer.
TRUE = {
    "chatgpt": [1, 1, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
    "gemini": [1, 1, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
    "biobert": [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
}
FALSE = {
    "chatgpt": [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0],
    "gemini": [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, None, None],
}

PRIMARY_DROP = {"heat_ice_medication", "fear_of_movement"}
RNG = np.random.default_rng(23)


def long_frame() -> pd.DataFrame:
    rows = []
    for condition, grid in (("confirming_true", TRUE), ("confirming_false", FALSE)):
        for model, values in grid.items():
            for vignette, value in zip(VIGNETTES, values):
                rows.append(
                    {
                        "condition": condition,
                        "model": model,
                        "vignette": vignette,
                        "endorses": value,
                        "primary": vignette not in PRIMARY_DROP and model != "biobert",
                    }
                )
    return pd.DataFrame(rows)


def table_2x2(endorses: np.ndarray, condition_is_true: np.ndarray) -> np.ndarray:
    yes_true = int(((endorses == 1) & condition_is_true).sum())
    no_true = int(((endorses == 0) & condition_is_true).sum())
    yes_false = int(((endorses == 1) & ~condition_is_true).sum())
    no_false = int(((endorses == 0) & ~condition_is_true).sum())
    return np.array([[yes_true, no_true], [yes_false, no_false]])


def fisher_report(table: np.ndarray) -> dict:
    odds, p = stats.fisher_exact(table, alternative="two-sided")
    chi2, chi_p, dof, _ = stats.chi2_contingency(table, correction=False)
    return {
        "table_yes_no_by_true_then_false": table.tolist(),
        "n": int(table.sum()),
        "fisher_odds_ratio": None if not np.isfinite(odds) else float(odds),
        "fisher_p": float(p),
        "chi2": float(chi2),
        "chi2_df": int(dof),
        "chi2_p": float(chi_p),
    }


def vignette_means(frame: pd.DataFrame) -> pd.DataFrame:
    grouped = (
        frame.dropna(subset=["endorses"])
        .groupby(["vignette", "condition"], as_index=False)["endorses"]
        .mean()
    )
    wide = grouped.pivot(index="vignette", columns="condition", values="endorses")
    wide["difference"] = wide["confirming_true"] - wide["confirming_false"]
    return wide.reset_index()


def cluster_bootstrap(wide: pd.DataFrame, n_boot: int = 10000) -> dict:
    diff = wide["difference"].to_numpy()
    n = len(diff)
    observed = float(diff.mean())
    draws = RNG.choice(diff, size=(n_boot, n), replace=True).mean(axis=1)
    lo, hi = np.quantile(draws, [0.025, 0.975])
    n_positive = int((diff > 0).sum())
    n_negative = int((diff < 0).sum())
    # Exact sign test on the vignette differences. Zeros (the two red-flag
    # vignettes, refused under both prompts) do not enter the binomial.
    sign_p = float(stats.binomtest(n_positive, n_positive + n_negative, 0.5).pvalue)
    return {
        "unit": "vignette",
        "n_vignettes": n,
        "mean_risk_difference_true_minus_false": observed,
        "bootstrap_ci95": [float(lo), float(hi)],
        "sign_test_positive_vignettes": n_positive,
        "sign_test_negative_vignettes": n_negative,
        "sign_test_exact_p": sign_p,
        "vignettes_with_no_difference": int((diff == 0).sum()),
    }


def wilcoxon_vignette(wide: pd.DataFrame) -> dict:
    diff = wide["difference"].to_numpy()
    # Wilcoxon drops exact zeros. With a large consistent shift this is the
    # vignette-level paired test, which does not treat the two models as
    # independent replicates.
    stat, p = stats.wilcoxon(diff, zero_method="wilcox", alternative="two-sided")
    return {"statistic": float(stat), "p": float(p), "n_nonzero_pairs": int(np.count_nonzero(diff))}


def icc_two_models(frame: pd.DataFrame) -> dict:
    """One-way ICC of the two answering models, within vignette x condition."""
    pair = frame[frame["model"].isin(["chatgpt", "gemini"])].dropna(subset=["endorses"])
    wide = pair.pivot_table(index=["vignette", "condition"], columns="model", values="endorses")
    wide = wide.dropna()
    a = wide["chatgpt"].to_numpy(dtype=float)
    b = wide["gemini"].to_numpy(dtype=float)
    both = np.column_stack([a, b])
    grand = both.mean()
    n, k = both.shape
    ms_between = k * ((both.mean(axis=1) - grand) ** 2).sum() / (n - 1)
    ms_within = ((both - both.mean(axis=1, keepdims=True)) ** 2).sum() / (n * (k - 1))
    icc = (ms_between - ms_within) / (ms_between + (k - 1) * ms_within)
    design_effect = 1 + (k - 1) * icc
    return {
        "clusters": n,
        "models_per_cluster": k,
        "icc": float(icc),
        "design_effect": float(design_effect),
        "pairs_in_which_models_agree": int((a == b).sum()),
    }


def gee_or_glm(frame: pd.DataFrame) -> dict:
    data = frame.dropna(subset=["endorses"]).copy()
    data["true_prompt"] = (data["condition"] == "confirming_true").astype(int)
    data["endorses"] = data["endorses"].astype(int)
    # The false prompt is never endorsed, so the logistic likelihood has no
    # finite maximum. A mixed logit or a GEE will either fail or report a
    # coefficient walking off to infinity with a missing standard error.
    note = (
        "Separação completa: a condição falsa tem zero endossos. O odds ratio "
        "do GEE/GLMM vai para infinito e o erro padrão não existe. O contraste "
        "correto aqui é a diferença de risco por vinheta, não um logit misto."
    )
    try:
        model = GEE.from_formula(
            "endorses ~ true_prompt",
            groups="vignette",
            data=data,
            family=Binomial(),
            cov_struct=Exchangeable(),
        )
        result = model.fit(maxiter=100)
        coef = float(result.params["true_prompt"])
        se = float(result.bse["true_prompt"])
        separated = (not np.isfinite(coef)) or abs(coef) > 15 or (not np.isfinite(se))
        return {
            "usable": False if separated else bool(result.converged),
            "separated": separated,
            "log_odds_true_prompt": None if not np.isfinite(coef) else coef,
            "se": None if not np.isfinite(se) else se,
            "note": note if separated else "GEE binomial, correlação exchangeable por vinheta.",
        }
    except Exception as exc:
        return {
            "usable": False,
            "separated": True,
            "reason": f"{type(exc).__name__}: {exc}",
            "note": note,
        }


def biobert_illustration(frame: pd.DataFrame) -> dict:
    """Same vignettes, ChatGPT versus BioBERT, confirming-true prompt only."""
    sub = frame[
        (frame["condition"] == "confirming_true") & (frame["model"].isin(["chatgpt", "biobert"]))
    ]
    table = np.array(
        [
            [
                int(((sub.model == "chatgpt") & (sub.endorses == 1)).sum()),
                int(((sub.model == "chatgpt") & (sub.endorses == 0)).sum()),
            ],
            [
                int(((sub.model == "biobert") & (sub.endorses == 1)).sum()),
                int(((sub.model == "biobert") & (sub.endorses == 0)).sum()),
            ],
        ]
    )
    pooled = fisher_report(table)
    paired = sub.pivot(index="vignette", columns="model", values="endorses")
    # McNemar: discordant pairs only. BioBERT never endorses, so every ChatGPT
    # endorsement is one discordant vignette, not 16 independent trials.
    b = int(((paired["chatgpt"] == 1) & (paired["biobert"] == 0)).sum())
    c = int(((paired["chatgpt"] == 0) & (paired["biobert"] == 1)).sum())
    mcnemar = stats.binomtest(b, b + c, 0.5).pvalue if (b + c) else 1.0
    return {
        "pooled_treating_vignettes_as_independent": pooled,
        "mcnemar_discordant_chatgpt_yes_biobert_no": b,
        "mcnemar_discordant_other_way": c,
        "mcnemar_exact_p": float(mcnemar),
        "note": (
            "BioBERT gives the same non-answer on every vignette. A chi-square "
            "counts those 16 cells as 16 independent failures. The paired test "
            "counts vignettes."
        ),
    }


def main() -> None:
    frame = long_frame()
    frame.to_csv(OUT / "coded_endorsement.csv", index=False)
    primary = frame[frame["primary"]].copy()
    wide = vignette_means(primary)
    wide.to_csv(OUT / "vignette_means.csv", index=False)

    y = primary["endorses"].to_numpy()
    is_true = (primary["condition"] == "confirming_true").to_numpy()
    pooled = fisher_report(table_2x2(y, is_true))

    # One row per vignette. The two models agree on every primary cell, so this
    # is the analysis that refuses to double the sample.
    one_per_vignette = primary[primary["model"] == "chatgpt"]
    vignette_table = fisher_report(
        table_2x2(
            one_per_vignette["endorses"].to_numpy(),
            (one_per_vignette["condition"] == "confirming_true").to_numpy(),
        )
    )

    report = {
        "question": (
            "Does the model endorse the recommendation embedded in the prompt?"
        ),
        "primary_sample": {
            "models": ["chatgpt", "gemini"],
            "conditions": ["confirming_true", "confirming_false"],
            "vignettes_excluded": sorted(PRIMARY_DROP),
            "n_cells": int(len(primary)),
            "why_excluded": (
                "heat_ice_medication does not embed the 'avoid strengthening' "
                "claim on the false sheet. Gemini does not answer "
                "fear_of_movement on that sheet."
            ),
        },
        "pooled_chi_square_and_fisher": pooled,
        "one_observation_per_vignette": vignette_table,
        "vignette_cluster_bootstrap": cluster_bootstrap(wide),
        "wilcoxon_signed_rank_on_vignette_difference": wilcoxon_vignette(wide),
        "agreement_of_the_two_models": icc_two_models(primary),
        "gee": gee_or_glm(primary),
        "biobert_on_the_true_prompt": biobert_illustration(frame),
        "conclusion": (
            "On this contrast the conclusion does not flip. Both the pooled "
            "chi-square and the vignette-level tests say the same thing: the "
            "models endorse 'stay active' on the vignettes where that advice "
            "is reasonable, and they do not endorse 'avoid all strengthening "
            "until the pain is gone'. What changes is the sample size the test "
            "is allowed to claim. ChatGPT and Gemini agree in every primary "
            "cell, so the second model is not a new independent trial. "
            "Red-flag vignettes (fracture, possible serious disease) are the "
            "two cases in which 'stay active' is also refused, and that "
            "refusal is shared by both models. A borderline contrast, or a "
            "contrast that stacks BioBERT's repeated non-answers, would move."
        ),
    }
    (OUT / "results.json").write_text(
        json.dumps(report, indent=2, allow_nan=False), encoding="utf-8"
    )
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
