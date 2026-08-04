"""Accuracy evaluation for feedback_ai.analyze_feedback against the
hand-labeled samples in sample_feedback.py.

Deliberately does not write anything to feedback_items — this is synthetic
test data, not real customer feedback, so it has no place in the PM
dashboard's real numbers. Rehearses the shape of a mentor's blind 10-input
test: run each sample, compare against ground truth, report per-item and
aggregate accuracy.

category is graded by exact match (a closed taxonomy); theme is
intentionally open vocabulary (see feedback_ai.SYSTEM_PROMPT), so it's
reported but not graded — there's no single "correct" phrasing to match
exactly the way there is for category.
"""
from dataclasses import dataclass

from . import feedback_ai
from .sample_feedback import SAMPLE_FEEDBACK


@dataclass
class EvalResult:
    tag: str
    text: str
    expected_sentiment: str
    actual_sentiment: str
    sentiment_correct: bool
    expected_actionable: bool
    actual_actionable: bool
    actionable_correct: bool
    expected_category: str
    actual_category: str
    category_correct: bool
    expected_theme: str
    actual_theme: str
    mode: str
    latency_ms: int


def run_eval() -> list[EvalResult]:
    results = []
    for sample in SAMPLE_FEEDBACK:
        outcome = feedback_ai.analyze_feedback(sample["text"])
        a = outcome.analysis
        results.append(
            EvalResult(
                tag=sample["tag"],
                text=sample["text"],
                expected_sentiment=sample["expected_sentiment"],
                actual_sentiment=a.sentiment_label.value,
                sentiment_correct=a.sentiment_label.value == sample["expected_sentiment"],
                expected_actionable=sample["expected_actionable"],
                actual_actionable=a.is_actionable_ticket,
                actionable_correct=a.is_actionable_ticket == sample["expected_actionable"],
                expected_category=sample["expected_category"],
                actual_category=a.category.value,
                category_correct=a.category.value == sample["expected_category"],
                expected_theme=sample["expected_theme"],
                actual_theme=a.theme,
                mode=outcome.mode,
                latency_ms=outcome.latency_ms,
            )
        )
    return results


def summarize(results: list[EvalResult]) -> dict:
    n = len(results)
    return {
        "total": n,
        "sentiment_accuracy": round(100 * sum(r.sentiment_correct for r in results) / n, 1),
        "actionable_accuracy": round(100 * sum(r.actionable_correct for r in results) / n, 1),
        "category_accuracy": round(100 * sum(r.category_correct for r in results) / n, 1),
        "all_three_correct": round(
            100 * sum(r.sentiment_correct and r.actionable_correct and r.category_correct for r in results) / n, 1
        ),
    }
