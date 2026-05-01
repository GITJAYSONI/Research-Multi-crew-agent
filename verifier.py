import re

from text_utils import tokens

REQUIRED_REPORT_SECTIONS = [
    "## Executive Summary",
    "## Key Findings",
    "## Deep Analysis",
    "## Evidence Quality And Limits",
    "## Conclusion",
    "## Sources",
]


def audit_claim_support(report: str, extracted_data: list[dict]) -> dict:
    """
    Heuristic evidence audit.

    This does not prove every fact is true. It only checks whether cited report
    sentences share meaningful terms with the exact source excerpts they cite.
    """
    source_tokens = {
        item["source_id"]: tokens(
            " ".join(
                [
                    item.get("title", ""),
                    " ".join(item.get("key_points", [])),
                    item.get("evidence_excerpt", ""),
                ]
            )
        )
        for item in extracted_data
    }

    body = report.split("## Sources")[0]
    sentences = re.split(r"(?<=[.!?])\s+", body)
    checked_claims = []

    for sentence in sentences:
        citation_ids = [int(c) for c in re.findall(r"\[(\d+)\]", sentence)]
        if not citation_ids:
            continue

        claim_tokens = tokens(re.sub(r"\[\d+\]", "", sentence))
        cited_tokens = set()
        for citation_id in citation_ids:
            cited_tokens.update(source_tokens.get(citation_id, set()))

        overlap = claim_tokens & cited_tokens
        support_ratio = len(overlap) / max(len(claim_tokens), 1)
        if support_ratio >= 0.55:
            status = "heuristically_supported"
        elif support_ratio >= 0.25:
            status = "unclear_support"
        else:
            status = "weak_support"

        checked_claims.append(
            {
                "claim": sentence.strip(),
                "citations": citation_ids,
                "support_ratio": round(support_ratio, 2),
                "matched_terms": sorted(overlap)[:12],
                "status": status,
            }
        )

    supported = sum(1 for item in checked_claims if item["status"] == "heuristically_supported")
    support_rate = supported / len(checked_claims) if checked_claims else 0

    return {
        "checked_claims": checked_claims,
        "checked_claim_count": len(checked_claims),
        "supported_claim_count": supported,
        "support_rate": round(support_rate, 2),
        "weak_claims": [
            item
            for item in checked_claims
            if item["status"] in {"weak_support", "unclear_support"}
        ][:8],
        "method_limit": "Heuristic word-overlap support check only. It can reduce hallucination risk, but it is not factual verification or entailment.",
    }


def evaluate_report_quality(
    report: str,
    topic: str,
    sources: list[dict],
    extracted_data: list[dict],
) -> dict:
    """Score structure, citations, source use, and heuristic claim support."""
    report = report or ""
    word_count = len(re.findall(r"\b\w+\b", report))
    citations = re.findall(r"\[(\d+)\]", report)
    unique_citations = {int(c) for c in citations if c.isdigit()}
    valid_citations = {c for c in unique_citations if 1 <= c <= len(sources)}
    sections_present = [section for section in REQUIRED_REPORT_SECTIONS if section in report]
    available_sources = sum(1 for item in extracted_data if item.get("content_available"))
    support_audit = audit_claim_support(report, extracted_data)
    support_rate = support_audit["support_rate"]

    criteria = {
        "citation_validity": {
            "points": 2 if citations and unique_citations == valid_citations else 1 if citations else 0,
            "details": "Checks whether citations exist and match the numbered source list.",
        },
        "claim_support": {
            "points": 2 if support_rate >= 0.7 else 1 if support_rate >= 0.4 else 0,
            "details": (
                f"{support_audit['supported_claim_count']} of "
                f"{support_audit['checked_claim_count']} cited claims show heuristic source-text support."
            ),
        },
        "source_coverage": {
            "points": 2 if len(valid_citations) >= min(3, len(sources)) else 1 if valid_citations else 0,
            "details": f"Uses {len(valid_citations)} of {len(sources)} available sources.",
        },
        "structure": {
            "points": 2 if len(sections_present) == len(REQUIRED_REPORT_SECTIONS) else 1 if len(sections_present) >= 4 else 0,
            "details": f"Includes {len(sections_present)} of {len(REQUIRED_REPORT_SECTIONS)} required sections.",
        },
        "evidence_readiness": {
            "points": 2 if available_sources >= min(3, len(sources)) else 1 if available_sources else 0,
            "details": f"Readable scraped content found for {available_sources} sources.",
        },
    }

    score = sum(item["points"] for item in criteria.values())
    issues = []
    improvements = []

    if not citations:
        issues.append("No inline citations were found.")
        improvements.append("Add source citations like [1] to every key claim.")
    if support_audit["checked_claim_count"] == 0:
        issues.append("No cited claims could be audited for source support.")
    elif support_rate < 0.7:
        issues.append(
            f"Only {support_audit['supported_claim_count']} of "
            f"{support_audit['checked_claim_count']} cited claims had strong heuristic source-text support."
        )
        improvements.append(
            "Rewrite unclear or weak claims using only wording and facts found in the cited source excerpts."
        )
    if unique_citations != valid_citations:
        issues.append("Some citations do not match the numbered source list.")
        improvements.append("Use only citation numbers that exist in the Sources list.")
    if len(sections_present) < len(REQUIRED_REPORT_SECTIONS):
        missing = sorted(set(REQUIRED_REPORT_SECTIONS) - set(sections_present))
        issues.append("Missing required report sections: " + ", ".join(missing))
        improvements.append("Regenerate using the required Markdown structure.")
    if word_count < 650:
        improvements.append("Add deeper analysis while staying within the provided evidence.")
    if available_sources < min(3, len(sources)):
        issues.append("Limited scraped evidence was available from the selected sources.")
        improvements.append("Try a more specific query or increase source count.")

    return {
        "score": score,
        "score_meaning": (
            "This score measures report structure, citation validity, source coverage, "
            "evidence availability, and heuristic claim support. It is not factual verification "
            "and does not guarantee that every fact is true."
        ),
        "confidence": (
            "high"
            if score >= 8 and support_rate >= 0.7 and available_sources >= 3
            else "medium"
            if score >= 6
            else "low"
        ),
        "word_count": word_count,
        "citations": len(citations),
        "sources_used": len(valid_citations),
        "sources_available": len(sources),
        "claim_support_audit": support_audit,
        "criteria": criteria,
        "issues": issues,
        "improvements": improvements,
        "final_verdict": "Passed quality threshold." if score >= 8 else "Needs review or refinement.",
    }
