import re

from text_utils import tokens
from tools import validate_url

REQUIRED_REPORT_SECTIONS = [
    "Executive Summary",
    "Key Findings",
    "Deep Analysis",
    "Evidence & Sources",
    "Limitations / Data Gaps",
    "Conclusion",
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

    body = re.split(r"(?im)^#{0,3}\s*(?:Evidence & Sources|Limitations / Data Gaps)\s*$", report or "")[0]
    sentences = re.split(r"(?<=[.!?])\s+", body)
    checked_claims = []

    for sentence in sentences:
        sentence = strip_section_prefix(sentence.strip())
        if not sentence or sentence.startswith("#"):
            continue
        citation_ids = [int(c) for c in re.findall(r"\[(\d+)\]", sentence)]
        claim_tokens = tokens(re.sub(r"\[\d+\]", "", sentence))
        cited_tokens = set()
        for citation_id in citation_ids:
            cited_tokens.update(source_tokens.get(citation_id, set()))

        overlap = claim_tokens & cited_tokens
        support_ratio = len(overlap) / max(len(claim_tokens), 1)
        sentence_without_citations = re.sub(r"\[\d+\]", "", sentence)
        has_statistic = bool(re.search(r"\b\d+(?:\.\d+)?%?|\$[\d,.]+", sentence_without_citations))
        if not citation_ids and claim_tokens:
            status = "unsupported"
        elif has_statistic and support_ratio < 0.45:
            status = "statistic_not_found"
        elif support_ratio >= 0.55:
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
                "has_statistic": has_statistic,
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
            if item["status"] in {"weak_support", "unclear_support", "unsupported", "statistic_not_found"}
        ][:8],
        "method_limit": "Strict heuristic audit. Claims without citations, unsupported statistics, and weak source overlap are treated as issues.",
    }


def strip_section_prefix(sentence: str) -> str:
    lines = [line.strip() for line in sentence.splitlines() if line.strip()]
    if lines and lines[0].lower().rstrip(":") in {section.lower() for section in REQUIRED_REPORT_SECTIONS}:
        sentence = " ".join(lines[1:]).strip()
    for section in REQUIRED_REPORT_SECTIONS:
        pattern = rf"^#{0,3}\s*{re.escape(section)}\s*"
        sentence = re.sub(pattern, "", sentence, flags=re.IGNORECASE).strip()
    return sentence


def find_report_urls(report: str) -> list[str]:
    return re.findall(r"https?://[^\s)\]]+", report or "")


def detect_duplicate_headings(report: str) -> list[str]:
    seen = set()
    duplicates = []
    for heading in re.findall(r"(?m)^#{1,3}\s+(.+)$", report or ""):
        normalized = heading.strip().lower()
        if normalized in seen:
            duplicates.append(heading.strip())
        seen.add(normalized)
    return duplicates


def formatting_issues(report: str) -> list[str]:
    issues = []
    if "**" in report:
        issues.append("Decorative bold markdown detected.")
    if "$$" in report:
        issues.append("Unwanted math-style symbol '$$' detected.")
    if re.search(r"\n{4,}", report or ""):
        issues.append("Repeated blank lines detected.")
    duplicates = detect_duplicate_headings(report)
    for heading in duplicates:
        issues.append(f"Duplicate section heading detected: {heading}")
    return issues


def evaluate_report_quality(
    report: str,
    sources: list[dict],
    extracted_data: list[dict],
) -> dict:
    """Strict Critic Agent audit for support, URLs, citations, and formatting."""
    report = report or ""
    word_count = len(re.findall(r"\b\w+\b", report))
    citations = re.findall(r"\[(\d+)\]", report)
    unique_citations = {int(c) for c in citations if c.isdigit()}
    valid_citations = {c for c in unique_citations if 1 <= c <= len(sources)}
    sections_present = [section for section in REQUIRED_REPORT_SECTIONS if section.lower() in report.lower()]
    available_sources = sum(1 for item in extracted_data if item.get("content_available"))
    support_audit = audit_claim_support(report, extracted_data)
    support_rate = support_audit["support_rate"]
    report_urls = find_report_urls(report)
    invalid_report_urls = [url for url in report_urls if not validate_url(url)]
    source_urls = [source.get("url", "") for source in sources]
    invalid_source_urls = [url for url in source_urls if url and not validate_url(url)]
    fake_urls = [url for url in report_urls if url not in source_urls]
    format_issues = formatting_issues(report)

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
        invalid = sorted(unique_citations - valid_citations)
        issues.append(f"Some citations do not match the numbered source list: {invalid}")
        improvements.append("Use only citation numbers that exist in the Sources list.")
    if invalid_report_urls:
        issues.append("Broken or malformed URLs detected in report: " + ", ".join(invalid_report_urls[:5]))
        improvements.append("Remove broken URLs and use only validated source URLs.")
    if invalid_source_urls:
        issues.append("Broken or malformed URLs detected in source list: " + ", ".join(invalid_source_urls[:5]))
    if fake_urls:
        issues.append("Report includes URLs not present in the validated source list: " + ", ".join(fake_urls[:5]))
        improvements.append("Do not add URLs that were not returned by search/scrape.")
    for weak_claim in support_audit["weak_claims"][:5]:
        if weak_claim["status"] == "statistic_not_found":
            issues.append("Statistic not found in cited source data: " + weak_claim["claim"][:180])
        elif weak_claim["status"] == "unsupported":
            issues.append("Unsupported uncited claim: " + weak_claim["claim"][:180])
        else:
            issues.append("Unsupported or weakly supported claim: " + weak_claim["claim"][:180])
    issues.extend(format_issues)
    if len(sections_present) < len(REQUIRED_REPORT_SECTIONS):
        missing = sorted(set(REQUIRED_REPORT_SECTIONS) - set(sections_present))
        issues.append("Missing required report sections: " + ", ".join(missing))
        improvements.append("Regenerate using the required Markdown structure.")
    if word_count < 650:
        improvements.append("Add deeper analysis while staying within the provided evidence.")
    if available_sources < min(3, len(sources)):
        issues.append("Limited scraped evidence was available from the selected sources.")
        improvements.append("Try a more specific query or increase source count.")
    if "Insufficient verified information" in report and available_sources == 0:
        score = max(score, 5)

    severe_penalties = 0
    severe_penalties += 2 if invalid_report_urls or invalid_source_urls or fake_urls else 0
    severe_penalties += min(3, len(support_audit["weak_claims"]) // 2)
    severe_penalties += 1 if format_issues else 0
    score = max(1, min(10, score - severe_penalties))
    action = "PASS" if score >= 7 else "RETRY"

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
        "action": action,
        "final_verdict": "Passed quality threshold." if action == "PASS" else "Retry required by Critic Agent.",
        "invalid_report_urls": invalid_report_urls,
        "invalid_source_urls": invalid_source_urls,
        "fake_urls": fake_urls,
        "formatting_issues": format_issues,
    }
