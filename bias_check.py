"""
bias_check.py — No-Masking bias check: literal_concrete_low_affect vs
concise_confident (PROJECT_PLAN.md Week 2, Day 9).

Generates matched-question answers under TWO personas —
literal_concrete_low_affect (evidence-based, see prompts/persona_prompts.py
for citations) and concise_confident (the existing "control" persona meant
for exactly this comparison, per personas.py's own docstring) — then
evaluates EACH with the evaluator (prompt variant A) and checks whether the
category distribution differs, and whether the No-Masking guardrail ever
flags style-leakage language in the rationale for either persona.

Uses a chi-square test of independence (scipy.stats.chi2_contingency) on
the (persona x category) contingency table — same statistical approach as
ab_test.py, applied to persona instead of prompt variant.
"""

import argparse
import json
import os

import pandas as pd
from scipy.stats import chi2_contingency

import config
import personas
import evaluator
import guardrail
from question_bank import QuestionBank

PERSONA_A = "literal_concrete_low_affect"
PERSONA_B = "concise_confident"
DEFAULT_SESSION = 1
DEFAULT_N = 20


def _output_paths(session_number: int) -> tuple:
    csv_path = os.path.join(config.DATA_DIR, f"bias_check_results_session{session_number}.csv")
    json_path = os.path.join(config.DATA_DIR, f"bias_check_results_session{session_number}.json")
    return csv_path, json_path


def _build_matched_question_pool(n: int, session_number: int = DEFAULT_SESSION) -> list:
    """N questions from the given session, cycling if n > session size."""
    questions = QuestionBank().session(session_number)
    return [questions[i % len(questions)] for i in range(n)]


def _chi_square_report(df: pd.DataFrame, column: str) -> dict:
    """Chi-square test of independence between persona and the given column.
    Prints the contingency table + verdict, returns the numbers for the
    saved JSON. Used for category, valence, and arousal — category alone
    can look "unbiased" while valence/arousal (an independent interpretive
    signal, not meant to reflect quality) still differ by persona."""
    crosstab = pd.crosstab(df["persona"], df[column])
    chi2, p, dof, expected = chi2_contingency(crosstab)
    chi2, p, dof = float(chi2), float(p), int(dof)
    significant = p < 0.05
    small_sample_warning = bool((crosstab.values < 5).any())

    print(f"\n=== Contingency table (persona x {column}) ===")
    print(crosstab)
    print(f"\n=== Chi-square test of independence ({column}) ===")
    print(f"chi2 = {chi2:.4f}")
    print(f"p-value = {p:.4f}")
    print(f"dof = {dof}")
    verdict = (
        f"Significant difference in {column} (p<0.05) — possible style bias"
        if significant
        else f"No significant difference in {column} detected"
    )
    print(f"Verdict: {verdict}")
    if small_sample_warning:
        print(
            f"Caveat: at least one {column} cell has count < 5 — p-value may "
            "be unreliable at this sample size."
        )

    return {
        "chi2": chi2,
        "p": p,
        "dof": dof,
        "significant": significant,
        "small_sample_warning": small_sample_warning,
    }


def run_bias_check(n: int = DEFAULT_N, session_number: int = DEFAULT_SESSION) -> pd.DataFrame:
    questions = _build_matched_question_pool(n, session_number)

    rows = []
    for i, q in enumerate(questions):
        for persona_key in (PERSONA_A, PERSONA_B):
            ans = personas.generate_synthetic_answer(persona_key, q["text"])
            ev = evaluator.evaluate(q["text"], ans.answer_text)
            gr = guardrail.check_rationale(ev.rationale)
            rows.append(
                {
                    "question_id": i,
                    "persona": persona_key,
                    "category": ev.category,
                    "valence": ev.valence,
                    "arousal": ev.arousal,
                    "confidence": ev.confidence,
                    "guardrail_passed": gr.passed,
                    "style_leakage_score": gr.style_leakage_score,
                }
            )
            print(
                f"question_id={i} persona={persona_key} category={ev.category} "
                f"confidence={ev.confidence} guardrail_passed={gr.passed}"
            )

    return pd.DataFrame(rows)


def main():
    parser = argparse.ArgumentParser(
        description="No-Masking bias check: literal_concrete_low_affect vs concise_confident."
    )
    parser.add_argument(
        "--n", type=int, default=DEFAULT_N,
        help="Number of matched questions (default 20, cycles if > session size).",
    )
    parser.add_argument(
        "--session", type=int, default=DEFAULT_SESSION,
        help="question_bank.py session to draw questions from, 1-5.",
    )
    args = parser.parse_args()

    df = run_bias_check(args.n, args.session)

    # category alone can look "unbiased" while valence/arousal — an
    # independent interpretive signal that's explicitly NOT meant to be a
    # quality readout — still differs by persona. Check all three.
    chi_square_results = {
        column: _chi_square_report(df, column) for column in ("category", "valence", "arousal")
    }

    guardrail_flags = df[df["guardrail_passed"] == False]
    print(
        f"\nGuardrail flags: {len(guardrail_flags)} / {len(df)} rationales "
        f"flagged for style-leakage language"
    )
    if len(guardrail_flags) > 0:
        print(guardrail_flags[["question_id", "persona", "category"]])

    csv_path, json_path = _output_paths(args.session)
    os.makedirs(config.DATA_DIR, exist_ok=True)
    df.to_csv(csv_path, index=False)

    results = {
        "n": args.n,
        "session": args.session,
        "persona_a": PERSONA_A,
        "persona_b": PERSONA_B,
        **chi_square_results,
        "guardrail_flags": int(len(guardrail_flags)),
    }
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"\nSaved: {csv_path}")
    print(f"Saved: {json_path}")


if __name__ == "__main__":
    main()
