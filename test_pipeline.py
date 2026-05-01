#!/usr/bin/env python3
"""Smoke test for the multi-agent research pipeline."""

import json
import sys

from pipeline import run_research_pipeline


def print_section(title: str):
    print(f"\n{'=' * 70}")
    print(f"  {title}")
    print(f"{'=' * 70}\n")


def print_sources(result: dict):
    print_section("SEARCH AGENT OUTPUT")
    source_cards = result.get("source_cards", [])
    print(f"Found {len(source_cards)} source cards.\n")
    for card in source_cards:
        print(f"[{card.get('source_id')}] {card.get('title', 'Untitled')}")
        print(f"    URL: {card.get('url', 'N/A')}")
        print(f"    Trust: {card.get('trust_label')} ({card.get('trust_score')})")
        print(f"    Summary: {card.get('summary', 'N/A')[:180]}...")
        snippets = card.get("exact_snippets", [])
        if snippets:
            print(f"    Snippet: {snippets[0][:180]}...")


def print_reader(result: dict):
    print_section("READER AGENT OUTPUT")
    extracted = result.get("extracted_data", [])
    print(f"Structured evidence from {len(extracted)} sources.\n")
    for item in extracted[:5]:
        print(f"[{item.get('source_id')}] {item.get('title')}")
        print(f"    Publisher: {item.get('publisher')}")
        print(f"    Trust: {item.get('trust_label')} ({item.get('trust_score')})")
        print(f"    Content available: {item.get('content_available')}")
        print(f"    Primary snippet: {item.get('primary_snippet', '')[:180]}...")


def print_writer(result: dict):
    print_section("WRITER AGENT OUTPUT")
    report = result.get("report", "")
    print(f"Report length: {len(report.split())} words\n")
    print("\n".join(report.splitlines()[:35]))
    if len(report.splitlines()) > 35:
        print("\n... report truncated for terminal preview")


def print_critic(result: dict) -> int:
    print_section("CRITIC AGENT OUTPUT")
    feedback = json.loads(result.get("feedback", "{}"))
    score = int(feedback.get("score", 0))
    print(f"Quality score: {score}/10")
    print(f"Verdict: {feedback.get('final_verdict', 'N/A')}\n")

    for name, data in feedback.get("criteria", {}).items():
        print(f"- {name.replace('_', ' ').title()}: {data.get('points', 0)}/2")
        print(f"  {data.get('details', '')}")

    if feedback.get("issues"):
        print("\nIssues:")
        for issue in feedback["issues"]:
            print(f"- {issue}")

    if feedback.get("improvements"):
        print("\nImprovements:")
        for improvement in feedback["improvements"]:
            print(f"- {improvement}")

    return score


def print_agent_outputs(result: dict):
    print_section("ALL AGENT OUTPUTS")
    for item in result.get("agent_outputs", []):
        print(f"{item.get('agent')} [{item.get('status')}]")
        print(f"  {item.get('summary')}")


def main():
    topic = " ".join(arg for arg in sys.argv[1:] if arg not in {"--verbose", "-v"})
    topic = topic or "Python 3.13 new features and improvements"
    verbose = "--verbose" in sys.argv or "-v" in sys.argv

    print_section("MULTI-AGENT RESEARCH TEST")
    print(f"Topic: {topic}")
    print("Running pipeline. This may take 15-30 seconds.\n")

    result = run_research_pipeline(topic)

    print_sources(result)
    print_reader(result)
    print_writer(result)
    score = print_critic(result)
    print_agent_outputs(result)

    print_section("PIPELINE SUMMARY")
    print(f"Sources: {len(result.get('sources_list', []))}")
    print(f"Structured evidence items: {len(result.get('extracted_data', []))}")
    print(f"Report words: {len(result.get('report', '').split())}")
    print(f"Quality score: {score}/10")

    if verbose:
        print_section("FULL STATE KEYS")
        print(json.dumps(sorted(result.keys()), indent=2))

    if score < 5:
        sys.exit(1)


if __name__ == "__main__":
    main()
