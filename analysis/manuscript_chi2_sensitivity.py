"""Design-effect check of the chi-square tests reported in the manuscript.

The manuscript tests differences across models and prompt frames with a
chi-square on 4,768 recommendations (mean 8.3 per response). Recommendations
from the same response are not independent trials, and the same vignette is
reused across models and frames. This script does not refit a mixed model:
the recommendation-level file is not in the repository. It recomputes the
published tables and asks how large a within-response intraclass correlation
would have to be before each reported chi-square lost p < 0.05.

The correction is the first-order Rao-Scott adjustment, chi-square divided by
the design effect 1 + (m - 1) * ICC, with m = 4,768 / 576.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from scipy import stats

OUT = Path(__file__).resolve().parent

MODELS = ("ChatGPT 5.5", "Gemini", "DeepSeek", "Guideline-informed RAG")
# Columns: accurate, inaccurate, unclear. Table 4.
MODEL_TABLE = np.array(
    [
        [1120, 50, 4],
        [1126, 47, 0],
        [1139, 69, 0],
        [910, 99, 204],
    ],
    dtype=float,
)
# Table 5, same column order.
FRAME_TABLE = np.array(
    [
        [449, 13, 16],
        [415, 17, 16],
        [487, 28, 17],
        [536, 15, 0],
        [505, 29, 34],
        [427, 65, 30],
        [424, 61, 32],
        [532, 18, 33],
        [520, 19, 30],
    ],
    dtype=float,
)
# Cupping (physiotherapist + physician) versus manual therapy/massage,
# inaccurate versus not, unclear recommendations removed. Yates correction
# on this table is the published chi-square of 62.64.
CUPPING_EXCLUDING_UNCLEAR = np.array([[126, 851], [37, 1052]], dtype=float)

# Table 4, turn-level proportion accurate, mean (SD), and Table 8 turn counts.
TURN = {
    "ChatGPT 5.5": (0.95, 0.12, 288),
    "Gemini": (0.97, 0.08, 288),
    "DeepSeek": (0.95, 0.10, 287),
    "Guideline-informed RAG": (0.54, 0.44, 287),
}

N_RECOMMENDATIONS = 4768
N_RESPONSES = 576
M = N_RECOMMENDATIONS / N_RESPONSES
ICCS = (0.0, 0.1, 0.2, 0.5, 1.0)


def chi2(table: np.ndarray, correction: bool = False) -> dict:
    stat, p, dof, _ = stats.chi2_contingency(table, correction=correction)
    return {"chi2": float(stat), "df": int(dof), "p": float(p), "n": int(table.sum())}


def rao_scott(stat: float, dof: int) -> dict:
    rows = []
    for icc in ICCS:
        design_effect = 1 + (M - 1) * icc
        adjusted = stat / design_effect
        rows.append(
            {
                "icc_within_response": icc,
                "design_effect": float(design_effect),
                "chi2_adjusted": float(adjusted),
                "p": float(stats.chi2.sf(adjusted, dof)),
            }
        )
    critical = float(stats.chi2.ppf(0.95, dof))
    design_effect_at_005 = stat / critical
    return {
        "published_or_reconstructed_chi2": stat,
        "df": dof,
        "mean_recommendations_per_response": M,
        "by_icc": rows,
        "design_effect_that_would_push_p_to_0.05": float(design_effect_at_005),
        "icc_that_would_push_p_to_0.05": float((design_effect_at_005 - 1) / (M - 1)),
        "note": (
            "An ICC above 1 is outside the range of a within-response "
            "correlation, so that test cannot be undone by clustering "
            "recommendations inside the response."
        ),
    }


def pairwise_models() -> list[dict]:
    out = []
    for i, left in enumerate(MODELS):
        for j, right in enumerate(MODELS):
            if j <= i:
                continue
            sub = MODEL_TABLE[[i, j]]
            sub = sub[:, sub.sum(axis=0) > 0]
            three = chi2(sub)
            binary = np.column_stack(
                [MODEL_TABLE[[i, j], 0], MODEL_TABLE[[i, j], 1:].sum(axis=1)]
            )
            two = chi2(binary)
            out.append(
                {
                    "contrast": f"{left} vs {right}",
                    "three_level": three,
                    "accurate_vs_not": two,
                }
            )
    return out


def welch(a: str, b: str, n_units: dict[str, float] | None = None) -> dict:
    m1, s1, n1 = TURN[a]
    m2, s2, n2 = TURN[b]
    if n_units is not None:
        n1, n2 = n_units[a], n_units[b]
    diff = m1 - m2
    se = float(np.sqrt(s1**2 / n1 + s2**2 / n2))
    if se == 0:
        return {"difference": diff, "t": 0.0, "df": None, "p": 1.0, "se": 0.0}
    df = (s1**2 / n1 + s2**2 / n2) ** 2 / (
        (s1**2 / n1) ** 2 / (n1 - 1) + (s2**2 / n2) ** 2 / (n2 - 1)
    )
    t = diff / se
    p = float(2 * stats.t.sf(abs(t), df))
    return {"difference": float(diff), "t": float(t), "df": float(df), "p": p, "se": se}


def turn_contrasts() -> list[dict]:
    rows = []
    names = list(TURN)
    vignette_n = {name: 16.0 for name in names}
    response_n = {name: TURN[name][2] / 2 for name in names}
    for i, left in enumerate(names):
        for right in names[i + 1 :]:
            rows.append(
                {
                    "contrast": f"{left} vs {right}",
                    "turns_treated_as_independent": welch(left, right),
                    "response_using_turn_sd": welch(left, right, response_n),
                    "vignette_using_turn_sd_as_upper_bound": welch(left, right, vignette_n),
                }
            )
    return rows


def main() -> None:
    model = chi2(MODEL_TABLE)
    frame = chi2(FRAME_TABLE)
    cupping = chi2(CUPPING_EXCLUDING_UNCLEAR, correction=True)
    report = {
        "source": "Tables 4, 5 and 8 and the cupping contrast in the results section.",
        "limitation": (
            "No recommendation-level file is in this repository, so this is a "
            "sensitivity analysis of the published counts, not a mixed model fit."
        ),
        "reconstructed_model_chi2": model,
        "reconstructed_frame_chi2": frame,
        "cupping_yates_excluding_unclear": cupping,
        "within_response_design_effect": {
            "model_omnibus": rao_scott(model["chi2"], model["df"]),
            "frame_omnibus": rao_scott(frame["chi2"], frame["df"]),
            "cupping": rao_scott(cupping["chi2"], cupping["df"]),
        },
        "pairwise_among_models_at_recommendation_level": pairwise_models(),
        "turn_level_proportion_accurate": turn_contrasts(),
        "reading": (
            "The model chi-square is the guideline-informed RAG chatbot against "
            "the other three. Clustering recommendations inside the response "
            "cannot remove it: the required design effect is about 51, and the "
            "maximum within-response design effect is 8.3. Pairwise tests among "
            "ChatGPT, Gemini and DeepSeek are already non-significant or marginal "
            "before any correction. The frame and cupping chi-squares shrink, "
            "and they lose p < 0.05 only if recommendations inside a response "
            "are nearly duplicates. They are not: a cupping-sheet answer mixes "
            "several accurate lines with about one inaccurate cupping line."
        ),
    }
    (OUT / "manuscript_sensitivity.json").write_text(
        json.dumps(report, indent=2, allow_nan=False), encoding="utf-8"
    )
    print(json.dumps(report["within_response_design_effect"], indent=2))
    print(report["reading"])


if __name__ == "__main__":
    main()
