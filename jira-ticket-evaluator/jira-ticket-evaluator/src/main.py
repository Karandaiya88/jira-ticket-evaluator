#!/usr/bin/env python3
"""
Jira Ticket Evaluator — CLI
Usage:
  python -m src.main --jira <ticket-url-or-json> --pr <pr-url> [--output report.json]
"""
import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from src.agents.orchestrator import OrchestratorAgent


def print_verdict(verdict: dict) -> None:
    overall = verdict.get("overall", "unknown").upper()
    icons = {"PASS": "✅", "PARTIAL": "⚠️ ", "FAIL": "❌"}
    icon = icons.get(overall, "❓")

    print(f"\n{'='*60}")
    print(f"  {icon}  VERDICT: {overall}   (confidence: {verdict.get('confidence', 0):.0%})")
    print(f"{'='*60}")
    print(f"\nSummary: {verdict.get('summary', '')}\n")

    reqs = verdict.get("requirements", [])
    if reqs:
        print(f"Requirements ({len(reqs)} evaluated):")
        for r in reqs:
            status = r.get("status", "?").upper()
            s_icon = icons.get(status, "❓")
            print(f"\n  {s_icon} [{r.get('id','?')}] {r.get('text','')}")
            print(f"     Reasoning: {r.get('reasoning','')}")
            for ev in r.get("evidence", [])[:3]:
                print(f"       • {ev}")

    test_results = verdict.get("test_results", [])
    if test_results:
        print(f"\nTest Results ({len(test_results)} tests):")
        for t in test_results:
            t_icon = "✅" if t.get("status") == "pass" else "❌"
            print(f"  {t_icon} {t.get('test_name')}")

    missing = verdict.get("missing_coverage", [])
    if missing:
        print(f"\nMissing coverage:")
        for m in missing:
            print(f"  ⚠️  {m}")

    print(f"\n{'='*60}\n")


def main():
    parser = argparse.ArgumentParser(description="Jira Ticket Evaluator — AI-powered PR compliance checker")
    parser.add_argument("--jira", required=True, help="Jira ticket URL, issue key, or raw JSON")
    parser.add_argument("--pr", required=True, help="GitHub PR URL")
    parser.add_argument("--output", help="Save JSON verdict to this file path")
    parser.add_argument("--json", action="store_true", help="Print raw JSON verdict only")
    args = parser.parse_args()

    print(f"🔍 Evaluating PR against Jira ticket...")
    print(f"   Ticket: {args.jira}")
    print(f"   PR:     {args.pr}\n")

    agent = OrchestratorAgent()
    verdict = agent.evaluate(args.jira, args.pr)

    if "error" in verdict:
        print(f"❌ Error: {verdict['error']}", file=sys.stderr)
        if "raw" in verdict:
            print(f"Raw output:\n{verdict['raw']}", file=sys.stderr)
        sys.exit(1)

    # Add metadata
    verdict["metadata"] = {
        "evaluated_at": datetime.utcnow().isoformat() + "Z",
        "jira_input": args.jira,
        "pr_url": args.pr
    }

    if args.json:
        print(json.dumps(verdict, indent=2))
    else:
        print_verdict(verdict)

    if args.output:
        Path(args.output).write_text(json.dumps(verdict, indent=2))
        print(f"📄 Verdict saved to {args.output}")


if __name__ == "__main__":
    main()
