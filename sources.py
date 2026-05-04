import re
from urllib.parse import urlparse

from text_utils import split_sentences, tokens
from tools import TRUSTED_DOMAIN_PARTS, validate_url


def domain(url: str) -> str:
    try:
        return urlparse(url).netloc.replace("www.", "") or "unknown"
    except Exception:
        return "unknown"


def trust_score(url: str, title: str = "") -> dict:
    source_domain = domain(url)
    score = 0.45
    reasons = []

    if source_domain.endswith((".gov", ".edu")):
        score += 0.3
        reasons.append("government or education domain")
    if any(part in source_domain for part in TRUSTED_DOMAIN_PARTS):
        score += 0.2
        reasons.append("recognized publisher or research domain")
    if "blog" in source_domain or "medium.com" in source_domain:
        score -= 0.1
        reasons.append("blog-style source")
    if not url.startswith("https://"):
        score -= 0.1
        reasons.append("non-HTTPS URL")
    if title and any(word in title.lower() for word in ("official", "report", "study", "research")):
        score += 0.05
        reasons.append("title suggests primary or research material")

    score = max(0.0, min(1.0, round(score, 2)))
    label = "high" if score >= 0.75 else "medium" if score >= 0.5 else "low"
    return {"score": score, "label": label, "reasons": reasons or ["general web source"]}


def best_snippets(content: str, summary: str, max_snippets: int = 3) -> list[str]:
    scored = []
    summary_tokens = tokens(summary)

    for sentence in split_sentences(content):
        sentence_tokens = tokens(sentence)
        if len(sentence_tokens) < 5:
            continue
        overlap = len(sentence_tokens & summary_tokens)
        score = overlap + min(len(sentence_tokens), 30) / 100
        scored.append((score, sentence))

    if not scored and summary:
        return [summary[:500]]

    snippets = []
    seen = set()
    for _, sentence in sorted(scored, reverse=True):
        normalized = sentence.lower()
        if normalized in seen:
            continue
        snippets.append(sentence[:500])
        seen.add(normalized)
        if len(snippets) >= max_snippets:
            break

    return snippets


def build_reader_output(sources: list[dict], scraped_content: str) -> list[dict]:
    """Create a structured, source-by-source evidence pack for the writer."""
    extracted = []
    chunks = re.split(r"\n(?=Source: )", scraped_content or "")

    for index, source in enumerate(sources, 1):
        raw_url = source.get("url", "")
        safe_url = raw_url if raw_url.startswith("http") else f"https://{raw_url.lstrip('/')}"
        url = safe_url
        matching_chunk = matching_scraped_chunk(url, chunks)
        content = matching_chunk or source.get("summary", "")
        clean_content = re.sub(r"\s+", " ", content).strip()

        summary = source.get("summary", "No summary available.")
        key_points = [summary] if summary and summary != "N/A" else []
        snippets = best_snippets(clean_content, summary)
        trust = trust_score(url, source.get("title", ""))

        extracted.append(
            {
                "source_id": index,
                "title": source.get("title", "Untitled source"),
                "url": url,
                "publisher": domain(url),
                "trust_score": trust["score"],
                "trust_label": trust["label"],
                "trust_reasons": trust["reasons"],
                "key_points": key_points,
                "snippets": snippets,
                "primary_snippet": snippets[0] if snippets else "",
                "evidence_excerpt": clean_content[:1200],
                "content_available": bool(clean_content)
                and not clean_content.lower().startswith("could not scrape"),
            }
        )

    return extracted


def matching_scraped_chunk(url: str, chunks: list[str]) -> str:
    """Match by full source/original URL instead of shortened display text."""
    if not url:
        return ""

    normalized = url.rstrip("/")
    for chunk in chunks:
        source_url = extract_chunk_field(chunk, "Source")
        original_url = extract_chunk_field(chunk, "Original URL")
        candidates = {source_url.rstrip("/"), original_url.rstrip("/")}
        if normalized in candidates:
            return chunk

    return next((chunk for chunk in chunks if normalized and normalized in chunk), "")


def extract_chunk_field(chunk: str, field_name: str) -> str:
    match = re.search(rf"(?m)^{re.escape(field_name)}:\s*(.+)$", chunk or "")
    return match.group(1).strip() if match else ""


def format_evidence_for_writer(extracted_data: list[dict]) -> str:
    blocks = []
    for item in extracted_data:
        blocks.append(
            "\n".join(
                [
                    f"[{item['source_id']}] {item['title']}",
                    f"URL: {item['url']}",
                    f"Publisher: {item['publisher']}",
                    f"Trust: {item.get('trust_label', 'unknown')} ({item.get('trust_score', 0)})",
                    "Key points:",
                    *[f"- {point}" for point in item["key_points"]],
                    "Exact snippets:",
                    *[f"- {snippet}" for snippet in item.get("snippets", [])],
                ]
            )
        )
    return "\n\n---\n\n".join(blocks)


def build_source_cards(extracted_data: list[dict], claim_audit: dict | None = None) -> list[dict]:
    claims_by_source: dict[int, list[dict]] = {}
    if claim_audit:
        for claim in claim_audit.get("checked_claims", []):
            for source_id in claim.get("citations", []):
                claims_by_source.setdefault(source_id, []).append(
                    {
                        "claim": claim.get("claim", ""),
                        "status": claim.get("status", "unknown"),
                        "support_ratio": claim.get("support_ratio", 0),
                    }
                )

    cards = []
    for item in extracted_data:
        url = item.get("url", "")
        normalized_url = url if url.startswith("http") else f"https://{url.lstrip('/')}"
        format_valid = validate_url(normalized_url)
        validation_note = (
            "Source Unverified: URL format passed local checks, but live HTTP status was not verified."
            if format_valid
            else "Source Unverified: URL is missing or malformed; live HTTP status was not verified."
        )
        cards.append(
            {
                "source_id": item["source_id"],
                "title": item.get("title", "Untitled source"),
                "url": normalized_url if format_valid else url,
                "publisher": item.get("publisher", "unknown"),
                "trust_score": item.get("trust_score", 0),
                "trust_label": item.get("trust_label", "unknown"),
                "trust_reasons": item.get("trust_reasons", []),
                "url_format_valid": format_valid,
                "validation_status": "Source Unverified",
                "validation_note": validation_note,
                "summary": item.get("key_points", [""])[0] if item.get("key_points") else "",
                "exact_snippets": item.get("snippets", []),
                "content_available": item.get("content_available", False),
                "used_for_claims": claims_by_source.get(item["source_id"], []),
            }
        )
    return cards
