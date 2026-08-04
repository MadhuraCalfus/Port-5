#!/usr/bin/env python3
"""Command-line interface for NykaaPulse.

Usage:
    python -m app.cli route "The app keeps crashing when I upload a photo"
    python -m app.cli demo              # run all 30 bundled sample tickets
    python -m app.cli eval-feedback     # accuracy over the hand-labeled feedback sample set
    python -m app.cli health
    python -m app.cli gen-seed-csv      # write the synthetic 2-year demo CSVs
    python -m app.cli import-seed-csv   # import those CSVs into the database
"""
import argparse
import json
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

from . import classifier, feedback_eval, seed_csv, store
from .sample_tickets import SAMPLE_TICKETS

RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
COLORS = {"High": "\033[91m", "Medium": "\033[93m", "Low": "\033[92m"}


def _print_result(result: dict) -> None:
    color = COLORS.get(result["priority"], "")
    print(f"{BOLD}Category:{RESET}   {result['category']}")
    print(f"{BOLD}Priority:{RESET}   {color}{result['priority']}{RESET}"
          + (f"  {DIM}(escalated due to {result['tone']} tone){RESET}" if result["escalated"] else ""))
    print(f"{BOLD}Team:{RESET}       {result['team']}")
    print(f"{BOLD}Tone:{RESET}       {result['tone']}")
    print(f"{BOLD}Confidence:{RESET} {result['confidence']:.0%}" + ("  (ambiguous)" if result["is_ambiguous"] else ""))
    print(f"{BOLD}Reasoning:{RESET}  {result['reasoning']}")
    print(f"{DIM}mode={result['mode']} model={result['model_used']} latency={result['latency_ms']}ms{RESET}")


def cmd_route(args) -> None:
    store.init_db()
    result = classifier.build_ticket_result(args.message, manual_time_seconds=None, compare=args.compare)
    store.save_ticket(result)
    if args.json:
        print(json.dumps(result, indent=2, default=str))
        return
    _print_result(result)
    if args.compare and result.get("baseline"):
        print(f"\n{BOLD}--- keyword baseline (for comparison) ---{RESET}")
        b = result["baseline"]
        print(f"Category: {b['category']}   Priority: {b['priority']}   Team: {b['team']}")
        print(f"Reasoning: {b['reasoning']}")


def cmd_demo(args) -> None:
    store.init_db()
    print(f"Routing {len(SAMPLE_TICKETS)} sample tickets...\n")
    total_ai = 0.0
    for i, item in enumerate(SAMPLE_TICKETS, 1):
        start = time.monotonic()
        result = classifier.build_ticket_result(item["text"], manual_time_seconds=None, compare=False)
        store.save_ticket(result)
        total_ai += time.monotonic() - start
        print(f"{BOLD}[{i:02d}]{RESET} {item['text'][:70]}")
        print(f"     -> {result['category']} / {result['priority']} / {result['team']}"
              f"  (confidence {result['confidence']:.0%}, tone={result['tone']})")
    manual_estimate = len(SAMPLE_TICKETS) * store.ASSUMED_MANUAL_SECONDS
    print(f"\n{BOLD}Done.{RESET} AI routed {len(SAMPLE_TICKETS)} tickets in {total_ai:.1f}s total.")
    print(f"Estimated manual time for the same batch: ~{manual_estimate/60:.1f} min "
          f"(~{store.ASSUMED_MANUAL_SECONDS:.0f}s/ticket).")


def cmd_health(args) -> None:
    info = classifier.mode_info()
    print(json.dumps(info, indent=2))


def cmd_eval_feedback(args) -> None:
    """Runs feedback_ai against the hand-labeled samples in
    sample_feedback.py and reports accuracy — a rehearsal for a mentor's
    blind-input test, not something that touches the real database."""
    results = feedback_eval.run_eval()
    for r in results:
        ok = "✓" if (r.sentiment_correct and r.actionable_correct and r.theme_correct) else "✗"
        print(f"{ok} {BOLD}[{r.tag}]{RESET} {r.text[:60]!r}")
        sent_mark = "✓" if r.sentiment_correct else "✗"
        act_mark = "✓" if r.actionable_correct else "✗"
        theme_mark = "✓" if r.theme_correct else "✗"
        print(f"    sentiment {sent_mark} expected={r.expected_sentiment} actual={r.actual_sentiment}")
        print(f"    actionable {act_mark} expected={r.expected_actionable} actual={r.actual_actionable}")
        print(f"    theme {theme_mark} actual={r.actual_theme!r} (looking for one of {r.theme_keywords})")
        print(f"    {DIM}mode={r.mode} latency={r.latency_ms}ms{RESET}\n")

    summary = feedback_eval.summarize(results)
    print(f"{BOLD}--- summary over {summary['total']} samples ---{RESET}")
    print(f"Sentiment accuracy:  {summary['sentiment_accuracy']}%")
    print(f"Actionable accuracy: {summary['actionable_accuracy']}%")
    print(f"Theme accuracy:      {summary['theme_accuracy']}%")
    print(f"All three correct:   {summary['all_three_correct']}%")


def cmd_gen_seed_csv(args) -> None:
    """Writes the synthetic 2-year demo CSVs to backend/data/seed/ — no
    database writes here, just files you can open and inspect first."""
    paths = seed_csv.generate_all()
    print(f"{BOLD}Wrote {len(paths)} CSV file(s):{RESET}")
    for p in paths:
        print(f"  {p}")


def cmd_import_seed_csv(args) -> None:
    """Reads the CSVs written by gen-seed-csv and inserts them — Ticket
    Trident tickets/surveys and Nykaa Pulse orders/reviews, all attributed to
    a small pool of demo login accounts (see seed_csv.DEMO_USERS)."""
    counts = seed_csv.import_all()
    print(f"{BOLD}Imported {counts['ticket_trident']}{RESET} Ticket Trident rows "
          f"and {BOLD}{counts['nykaa_pulse']}{RESET} Nykaa Pulse rows.")
    print(f"\nDemo login accounts (password: {seed_csv.DEMO_PASSWORD}):")
    for u in seed_csv.DEMO_USERS:
        print(f"  {u['email']}")


def main() -> None:
    parser = argparse.ArgumentParser(prog="nykaapulse", description="NykaaPulse CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    p_route = sub.add_parser("route", help="Classify a single ticket message")
    p_route.add_argument("message", help="The support ticket text")
    p_route.add_argument("--json", action="store_true", help="Print raw JSON output")
    p_route.add_argument("--compare", action="store_true", help="Also show the keyword-baseline result")
    p_route.set_defaults(func=cmd_route)

    p_demo = sub.add_parser("demo", help="Route all 30 bundled sample tickets")
    p_demo.set_defaults(func=cmd_demo)

    p_health = sub.add_parser("health", help="Show whether live Claude or mock mode is active")
    p_health.set_defaults(func=cmd_health)

    p_eval_feedback = sub.add_parser("eval-feedback", help="Run feedback_ai against the hand-labeled sample set and report accuracy")
    p_eval_feedback.set_defaults(func=cmd_eval_feedback)

    p_gen_seed_csv = sub.add_parser("gen-seed-csv", help="Write the synthetic 2-year demo CSVs to backend/data/seed/")
    p_gen_seed_csv.set_defaults(func=cmd_gen_seed_csv)

    p_import_seed_csv = sub.add_parser("import-seed-csv", help="Import the demo CSVs from backend/data/seed/ into the database")
    p_import_seed_csv.set_defaults(func=cmd_import_seed_csv)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    sys.exit(main())
