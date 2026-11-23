"""Clustered logistic models for the 4,768 coded recommendations.

The manuscript tests model and prompt frame with a chi-square that treats
each recommendation as an independent trial. Recommendations are nested in
responses, and the same vignette is reused across models and frames. The
analysis plan already names a mixed logit with a vignette random intercept
as the confirmatory model.

This script fits that dependence on data/recommendations.jsonl:

- chi-square on the same file, so the published tables can be checked
- logistic GLM with cluster-robust standard errors by response and by vignette
- GEE, exchangeable correlation, clustered by vignette
- a vignette-level paired comparison, which does not rely on the logit MLE
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm
import statsmodels.formula.api as smf
from scipy import stats
from statsmodels.genmod.bayes_mixed_glm import BinomialBayesMixedGLM
from statsmodels.genmod.cov_struct import Exchangeable

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "recommendations.jsonl"
OUT = Path(__file__).resolve().parent / "clustered_results.json"

LLM_REF = "ChatGPT"
FRAME_REF = "neutral"


def load() -> pd.DataFrame:
    rows = [json.loads(line) for line in DATA.read_text().splitlines() if line.strip()]
    frame = pd.DataFrame(rows)
    frame["accurate"] = (frame["accuracy"] == "accurate").astype(int)
    frame["frame"] = np.where(
        frame["prompt_frame"].eq("disagreeing_authority"),
        "authority_" + frame["authority_profession"].astype(str),
        frame["prompt_frame"],
    )
    return frame


def chi2_block(table: pd.DataFrame) -> dict:
    stat, p, dof, _ = stats.chi2_contingency(table.values, correction=False)
    return {
        "table": table.to_dict(),
        "chi2": float(stat),
        "df": int(dof),
        "p": float(p),
        "n": int(table.values.sum()),
    }


def coef_table(result) -> list[dict]:
    rows = []
    params = result.params
    bse = result.bse
    pvalues = result.pvalues
    conf = result.conf_int()
    for name in params.index:
        lo, hi = conf.loc[name]
        rows.append(
            {
                "term": str(name),
                "log_odds": float(params[name]),
                "odds_ratio": float(np.exp(params[name])),
                "se": float(bse[name]),
                "p": float(pvalues[name]),
                "or_ci95": [float(np.exp(lo)), float(np.exp(hi))],
            }
        )
    return rows


def fit_glm(data: pd.DataFrame, groups: pd.Series, label: str) -> dict:
    formula = (
        f"accurate ~ C(llm, Treatment(reference='{LLM_REF}'))"
        f" + C(frame, Treatment(reference='{FRAME_REF}'))"
    )
    model = smf.glm(formula, data=data, family=sm.families.Binomial())
    result = model.fit(cov_type="cluster", cov_kwds={"groups": groups})
    return {"cluster": label, "n_clusters": int(groups.nunique()), "coefficients": coef_table(result)}


def fit_gee(data: pd.DataFrame) -> dict:
    formula = (
        f"accurate ~ C(llm, Treatment(reference='{LLM_REF}'))"
        f" + C(frame, Treatment(reference='{FRAME_REF}'))"
    )
    model = smf.gee(
        formula,
        groups="vignette_id",
        data=data,
        family=sm.families.Binomial(),
        cov_struct=Exchangeable(),
    )
    result = model.fit()
    return {
        "cluster": "vignette_id",
        "n_clusters": int(data["vignette_id"].nunique()),
        "coefficients": coef_table(result),
    }


def fit_bayes_mixed(data: pd.DataFrame) -> dict:
    formula = (
        f"accurate ~ C(llm, Treatment(reference='{LLM_REF}'))"
        f" + C(frame, Treatment(reference='{FRAME_REF}'))"
    )
    model = BinomialBayesMixedGLM.from_formula(
        formula,
        {"vignette": "0 + C(vignette_id)"},
        data,
    )
    result = model.fit_vb()
    terms = list(result.model.exog_names)
    rows = []
    for i, name in enumerate(terms):
        mean = float(result.fe_mean[i])
        sd = float(np.sqrt(result.fe_sd[i] ** 2))
        # Posterior mean ± 1.96 posterior sd. This is not a frequentist p-value.
        lo, hi = mean - 1.96 * sd, mean + 1.96 * sd
        rows.append(
            {
                "term": name,
                "log_odds": mean,
                "odds_ratio": float(np.exp(mean)),
                "posterior_sd": sd,
                "or_ci95": [float(np.exp(lo)), float(np.exp(hi))],
                "interval_excludes_1": bool(lo > 0 or hi < 0),
            }
        )
    return {"random_intercept": "vignette_id", "coefficients": rows}


def pick(rows: list[dict], needle: str) -> dict | None:
    for row in rows:
        if needle in row["term"]:
            return row
    return None


def vignette_pairs(data: pd.DataFrame) -> dict:
    """One proportion per vignette, then a paired test. n = 16."""
    rate = (
        data.groupby(["vignette_id", "llm"], as_index=False)["accurate"]
        .mean()
        .pivot(index="vignette_id", columns="llm", values="accurate")
    )
    out = {}
    for other in ("Gemini", "DeepSeek", "BioBERT"):
        diff = (rate[other] - rate["ChatGPT"]).dropna()
        stat, p = stats.wilcoxon(diff, zero_method="wilcox", alternative="two-sided")
        out[f"{other}_minus_ChatGPT"] = {
            "n_vignettes": int(len(diff)),
            "mean_difference": float(diff.mean()),
            "vignettes_lower_than_chatgpt": int((diff < 0).sum()),
            "wilcoxon_p": float(p),
            "statistic": float(stat),
        }
    # Cupping sheets versus manual-therapy or massage sheets, within vignette.
    cup = data[data["frame"].isin(["authority_physiotherapist", "authority_physician"])]
    manual = data[data["frame"].isin(["authority_osteopath", "authority_massage_therapist"])]
    cup_rate = cup.groupby("vignette_id")["accurate"].mean()
    manual_rate = manual.groupby("vignette_id")["accurate"].mean()
    diff = (cup_rate - manual_rate).dropna()
    stat, p = stats.wilcoxon(diff, zero_method="wilcox", alternative="two-sided")
    out["cupping_minus_manual"] = {
        "n_vignettes": int(len(diff)),
        "mean_difference": float(diff.mean()),
        "vignettes_lower_on_cupping": int((diff < 0).sum()),
        "wilcoxon_p": float(p),
        "statistic": float(stat),
    }
    return out


def main() -> None:
    data = load()
    counts = pd.crosstab(data["llm"], data["accuracy"])[["accurate", "inaccurate", "unclear"]]
    frame_counts = pd.crosstab(data["frame"], data["accuracy"])[["accurate", "inaccurate", "unclear"]]
    report: dict = {
        "n_recommendations": int(len(data)),
        "n_responses": int(data["response_id"].nunique()),
        "n_vignettes": int(data["vignette_id"].nunique()),
        "chi2_llm_by_accuracy": chi2_block(counts),
        "chi2_frame_by_accuracy": chi2_block(frame_counts),
        "glm_cluster_response": fit_glm(data, data["response_id"], "response_id"),
        "glm_cluster_vignette": fit_glm(data, data["vignette_id"], "vignette_id"),
    }
    try:
        report["gee_vignette"] = fit_gee(data)
    except Exception as exc:
        report["gee_vignette"] = {"error": f"{type(exc).__name__}: {exc}"}
    try:
        report["bayes_mixed_vignette"] = fit_bayes_mixed(data)
    except Exception as exc:
        report["bayes_mixed_vignette"] = {"error": f"{type(exc).__name__}: {exc}"}
    report["vignette_paired"] = vignette_pairs(data)

    # The contrasts Bruno's comment is about.
    focus = {}
    for key in ("glm_cluster_response", "glm_cluster_vignette"):
        block = report[key]
        if "coefficients" not in block:
            continue
        focus[key] = {
            "BioBERT": pick(block["coefficients"], "BioBERT"),
            "Gemini": pick(block["coefficients"], "Gemini"),
            "DeepSeek": pick(block["coefficients"], "DeepSeek"),
            "physiotherapist_cupping": pick(block["coefficients"], "authority_physiotherapist"),
            "physician_cupping": pick(block["coefficients"], "authority_physician"),
            "osteopath": pick(block["coefficients"], "authority_osteopath"),
            "massage": pick(block["coefficients"], "authority_massage_therapist"),
        }
    report["focus"] = focus
    OUT.write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps({"chi2_llm": report["chi2_llm_by_accuracy"]["chi2"], "focus": focus, "paired": report["vignette_paired"]}, indent=2))


if __name__ == "__main__":
    main()
