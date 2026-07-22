"""Accuracy evaluation for feedback_ai.analyze_feedback against the
hand-labeled samples in sample_feedback.py.

Deliberately does not write anything to feedback_items — this is synthetic
test data, not real customer feedback, so it has no place in the PM
dashboard's real numbers. Rehearses the shape of a mentor's blind 10-input
test: run each sample, compare against ground truth, report per-item and
aggregate accuracy.
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
    theme_keywords: list[str]
    actual_theme: str
    theme_correct: bool
    mode: str
    latency_ms: int


def _theme_matches(actual_theme: str, keywords: list[str]) -> bool:
    lowered = actual_theme.lower()
    return any(kw.lower() in lowered for kw in keywords)


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
                theme_keywords=sample["theme_keywords"],
                actual_theme=a.theme,
                theme_correct=_theme_matches(a.theme, sample["theme_keywords"]),
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
        "theme_accuracy": round(100 * sum(r.theme_correct for r in results) / n, 1),
        "all_three_correct": round(
            100 * sum(r.sentiment_correct and r.actionable_correct and r.theme_correct for r in results) / n, 1
        ),
    }
