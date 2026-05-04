import asyncio
import json
import logging
import re
from datetime import datetime
from typing import Any, Callable, Literal, TypedDict

try:
    from langgraph.graph import END, StateGraph
except Exception as exc:  # pragma: no cover
    import logging as _log

    _log.getLogger(__name__).warning("langgraph unavailable (%s); using FallbackStateGraph", exc)
    END = "__end__"
    StateGraph = None

from agents import summarizer_chain, writer_chain
from cache_store import cache
from sources import build_reader_output, build_source_cards, format_evidence_for_writer
from tools import async_scrape_all_urls, perform_python_search, validate_url
from utils import parse_json_safe
from verifier import evaluate_report_quality

logger = logging.getLogger(__name__)

PipelineMode = Literal["discover", "finance", "health", "academic", "patents"]

# ── Single source of truth for the critic pass threshold ──────────────────────
CRITIC_PASS_THRESHOLD = 7
MAX_CRITIC_RETRIES = 1

MODE_SEARCH_HINTS = {
    "discover": "",
    "finance": " financial markets stocks earnings filings investor relations",
    "health": " medical evidence official health sources WHO NIH CDC",
    "academic": " research paper study journal arxiv pubmed scholar",
    "patents": " patent database USPTO WIPO Google Patents filing",
}


class AgentState(TypedDict, total=False):
    query: str
    topic: str
    mode: str
    conversation_context: str
    search_results: list[dict]
    scraped_content: list[dict]
    final_answer: str
    critic_feedback: dict | str
    sources: list[dict]
    chat_history: list[dict]
    agent_outputs: list[dict]
    errors: list[dict]
    extracted_data: list[dict]
    source_cards: list[dict]
    report: str
    feedback: str
    final_score: int
    retry_count: int
    accuracy_status: str
    quality_warning: bool


def agent_record(name: str, status: str, summary: str, output: Any) -> dict:
    return {
        "agent": name,
        "status": status,
        "summary": summary,
        "output": output,
        "timestamp": datetime.utcnow().isoformat(timespec="seconds") + "Z",
    }


def run_research_pipeline(
    topic: str,
    conversation_context: str = "",
    mode: str = "discover",
    chat_history: list[dict] | None = None,
) -> dict:
    """
    Execute the pipeline flow:
    Search Agent → Scraper Agent → Writer Agent → Critic Agent.
    """
    initial_state = create_initial_state(topic, conversation_context, mode, chat_history)
    graph = build_pipeline_graph()
    final_state = graph.invoke(initial_state)
    return finalize_state(final_state)


def create_initial_state(
    query: str,
    conversation_context: str,
    mode: str,
    chat_history: list[dict] | None,
) -> AgentState:
    normalized_mode = mode if mode in MODE_SEARCH_HINTS else "discover"
    return {
        "query": query,
        "topic": query,
        "mode": normalized_mode,
        "conversation_context": conversation_context,
        "search_results": [],
        "scraped_content": [],
        "final_answer": "",
        "critic_feedback": "",
        "sources": [],
        "chat_history": chat_history or [],
        "agent_outputs": [],
        "errors": [],
        "retry_count": 0,
        "accuracy_status": "",
        "quality_warning": False,
    }


def build_pipeline_graph():
    if StateGraph is None:
        return FallbackStateGraph(
            [search_agent, scraper_agent, writer_agent, critic_agent],
        )

    graph = StateGraph(AgentState)
    graph.add_node("search", search_agent)
    graph.add_node("scrape", scraper_agent)
    graph.add_node("write", writer_agent)
    graph.add_node("critic", critic_agent)
    graph.set_entry_point("search")
    graph.add_edge("search", "scrape")
    graph.add_edge("scrape", "write")
    graph.add_edge("write", "critic")
    graph.add_edge("critic", END)
    return graph.compile()


class FallbackStateGraph:
    """Minimal StateGraph-compatible runner used when langgraph is not installed."""

    def __init__(self, nodes: list[Callable[[AgentState], AgentState]]):
        self.nodes = nodes

    def invoke(self, state: AgentState) -> AgentState:
        for node in self.nodes:
            state = node(state)
        return state


# ══════════════════════════════════════════════════════════════════════════════
# AGENT NODES
# ══════════════════════════════════════════════════════════════════════════════

def search_agent(state: AgentState) -> AgentState:
    log_agent_start("Search Agent", state)
    query = state["query"]
    search_query = mode_search_query(query, state.get("mode", "discover"))

    try:
        search_results = cache.get_or_set(
            "search_results",
            {"query": search_query, "mode": state.get("mode", "discover")},
            lambda: perform_python_search(search_query),
            ttl_seconds=24 * 3600,
        )
        normalized = normalize_search_results(search_results)
        if not normalized:
            raise ValueError("Search returned no usable results.")

        state["search_results"] = normalized
        state["sources"] = normalized
        append_agent_output(
            state,
            "Search Agent",
            "passed",
            f"Found {len(normalized)} candidate sources.",
            normalized,
        )
        log_agent_output("Search Agent", normalized)
    except Exception as exc:
        record_error(state, "Search Agent", exc)
        # ── FIX: fallback_search_results now logs a warning and returns []
        # so downstream agents still run rather than crashing silently.
        fallback = fallback_search_results(query)
        state["search_results"] = fallback
        state["sources"] = fallback
        append_agent_output(
            state,
            "Search Agent",
            "fallback",
            "Search failed; continuing with a no-source fallback so downstream agents still run.",
            fallback,
        )

    return state


def scraper_agent(state: AgentState) -> AgentState:
    log_agent_start("Scraper Agent", state)
    urls = [
        source["url"]
        for source in state.get("search_results", [])
        if validate_url(source.get("url", ""))
    ]

    try:
        if not urls:
            raise ValueError("No valid URLs available for scraping.")

        scraped_blob = cache.get_or_set(
            "scraped_content",
            {"urls": sorted(urls)},           # sorted → stable cache key
            lambda: asyncio.run(async_scrape_all_urls(urls)),
            ttl_seconds=24 * 3600,
        )
        scraped_content = summarize_scraped_content(scraped_blob)
        extracted_data = build_reader_output(state.get("search_results", []), scraped_blob)
        extracted_data = [item for item in extracted_data if validate_url(item.get("url", ""))]

        state["scraped_content"] = scraped_content
        state["extracted_data"] = extracted_data
        state["source_cards"] = build_source_cards(extracted_data)
        append_agent_output(
            state,
            "Scraper Agent",
            "passed",
            f"Scraped and structured {len(scraped_content)} sources.",
            scraped_content,
        )
        log_agent_output("Scraper Agent", scraped_content)
    except Exception as exc:
        record_error(state, "Scraper Agent", exc)
        fallback_content = fallback_scraped_content(state.get("search_results", []))
        fallback_blob = scraped_content_to_blob(fallback_content)
        extracted_data = build_reader_output(state.get("search_results", []), fallback_blob)

        state["scraped_content"] = fallback_content
        state["extracted_data"] = extracted_data
        state["source_cards"] = build_source_cards(extracted_data)
        append_agent_output(
            state,
            "Scraper Agent",
            "fallback",
            "Scraping failed; continuing with search snippets as evidence.",
            fallback_content,
        )

    return state


def writer_agent(state: AgentState) -> AgentState:
    log_agent_start("Writer Agent", state)

    try:
        extracted_data = state.get("extracted_data", [])
        usable = [d for d in extracted_data if d.get("content_available")]
        if not usable:
            report = fallback_answer(state)
            state["final_answer"] = report
            state["report"] = report
            append_agent_output(
                state,
                "Writer Agent",
                "fallback",
                "No usable scraped evidence — returned a clean no-results message.",
                report,
            )
            return state
        sources_formatted = format_sources_for_writer(state.get("sources", []))
        report = writer_chain.invoke(
            {
                "topic": writer_topic(state),
                "research_data": format_evidence_for_writer(extracted_data),
                "sources": sources_formatted,
            }
        )
        if not report:
            raise ValueError("Writer returned an empty answer.")

        state["final_answer"] = report
        state["report"] = report
        append_agent_output(
            state,
            "Writer Agent",
            "passed",
            f"Generated a {len(report.split())}-word cited draft.",
            report,
        )
        log_agent_output("Writer Agent", report)
    except Exception as exc:
        record_error(state, "Writer Agent", exc)
        report = fallback_answer(state)
        state["final_answer"] = report
        state["report"] = report
        append_agent_output(
            state,
            "Writer Agent",
            "fallback",
            "Writer failed; generated a source-limited fallback answer.",
            report,
        )

    return state


def critic_agent(state: AgentState) -> AgentState:
    log_agent_start("Critic Agent", state)

    try:
        report = state.get("final_answer") or fallback_answer(state)
        extracted_data = state.get("extracted_data", [])
        sources = state.get("sources", [])

        # topic parameter removed from evaluate_report_quality — not used internally
        feedback = evaluate_report_quality(report, sources, extracted_data)

        score = int(feedback.get("score", 0) or 0)
        retry_count = state.get("retry_count", 0)

        while score < CRITIC_PASS_THRESHOLD and retry_count < MAX_CRITIC_RETRIES:
            retry_count += 1
            state["accuracy_status"] = "accuracy was improving"
            improved = improve_report_with_new_sources(state, feedback, retry_count)
            if not improved:
                break
            report = state.get("final_answer") or state.get("report") or report
            extracted_data = state.get("extracted_data", [])
            sources = state.get("sources", [])
            feedback = evaluate_report_quality(report, sources, extracted_data)
            score = int(feedback.get("score", 0) or 0)

        if score < CRITIC_PASS_THRESHOLD:
            report = sanitize_final_output(report)
            state["quality_warning"] = True
        else:
            report = sanitize_final_output(report)
            state["quality_warning"] = False

        state["final_answer"] = report
        state["report"] = report
        state["critic_feedback"] = feedback
        state["feedback"] = json.dumps(feedback, indent=2)
        state["final_score"] = score
        state["retry_count"] = retry_count
        state["accuracy_status"] = "accuracy was improving" if retry_count else ""
        state["source_cards"] = build_source_cards(
            extracted_data,
            feedback.get("claim_support_audit", {}),
        )
        append_agent_output(
            state,
            "Critic Agent",
            "passed" if score >= CRITIC_PASS_THRESHOLD else "needs_review",
            critic_summary(score, feedback, retry_count, state.get("accuracy_status", "")),
            feedback,
        )
        log_agent_output("Critic Agent", feedback)
    except Exception as exc:
        record_error(state, "Critic Agent", exc)
        fallback_feedback = fallback_critic_feedback(state)
        report = state.get("final_answer") or fallback_answer(state)
        state["final_answer"] = report
        state["report"] = report
        state["critic_feedback"] = fallback_feedback
        state["feedback"] = json.dumps(fallback_feedback, indent=2)
        state["final_score"] = fallback_feedback["score"]
        state["retry_count"] = 0
        state["accuracy_status"] = ""
        state["quality_warning"] = True
        append_agent_output(
            state,
            "Critic Agent",
            "fallback",
            "Critic failed; fallback feedback was recorded so the pipeline completed.",
            fallback_feedback,
        )

    return state


# ══════════════════════════════════════════════════════════════════════════════
# PIPELINE UTILITIES
# ══════════════════════════════════════════════════════════════════════════════

def finalize_state(state: AgentState) -> dict:
    final_answer = state.get("final_answer") or state.get("report") or fallback_answer(state)
    feedback = state.get("critic_feedback") or parse_json_safe(state.get("feedback", "{}"))

    state["final_answer"] = final_answer
    state["report"] = final_answer
    state["feedback"] = json.dumps(feedback, indent=2) if isinstance(feedback, dict) else str(feedback)
    state["sources"] = state.get("sources") or state.get("search_results", [])
    state["source_cards"] = state.get("source_cards") or build_source_cards(
        state.get("extracted_data", []),
        feedback.get("claim_support_audit", {}) if isinstance(feedback, dict) else {},
    )
    return dict(state)


def mode_search_query(query: str, mode: str) -> str:
    hint = MODE_SEARCH_HINTS.get(mode, "")
    return f"{query}{hint}".strip()


def normalize_search_results(results: list[dict]) -> list[dict]:
    normalized = []
    seen_domains = set()
    for result in results or []:
        url = result.get("url") or ""
        if not validate_url(url):
            continue
        domain = re.sub(r"^www\.", "", re.sub(r"^https?://", "", url).split("/")[0].lower())
        if domain in seen_domains:
            continue
        seen_domains.add(domain)
        normalized.append(
            {
                "title": result.get("title") or "Untitled source",
                "url": url,
                "snippet": result.get("snippet") or result.get("summary") or "",
                "summary": result.get("summary") or result.get("snippet") or "",
                "quality_score": result.get("quality_score", 50),
            }
        )
    return sorted(normalized, key=lambda item: item.get("quality_score", 0), reverse=True)


def summarize_scraped_content(scraped_blob: str) -> list[dict]:
    chunks = re.split(r"\n(?=Source: )", scraped_blob or "")
    cleaned = []
    for chunk in chunks:
        if not chunk.strip():
            continue
        source_match = re.search(r"Source:\s*(.+)", chunk)
        source_url = source_match.group(1).strip() if source_match else "unknown"
        try:
            summary = cache.get_or_set(
                "summarized_data",
                {"url": source_url, "content": chunk[:4000]},
                lambda chunk=chunk: summarizer_chain.invoke({"content": chunk[:4000]}),
                ttl_seconds=24 * 3600,
            )
        except Exception as exc:
            logger.exception("Scraper summarization failed for %s", source_url)
            summary = f"Summary unavailable: {exc}"

        cleaned.append({"url": source_url, "content": summary})
    return cleaned


def scraped_content_to_blob(scraped_content: list[dict]) -> str:
    return "\n\n".join(
        f"Source: {item.get('url', 'unknown')}\nContent:\n{item.get('content', '')}"
        for item in scraped_content
    )


def critic_summary(score: int, feedback: dict, retry_count: int, accuracy_status: str) -> str:
    summary = (
        f"Quality score: {score}/10. "
        f"{feedback.get('final_verdict', 'Reviewed.')} "
        f"Retries: {retry_count}."
    )
    if accuracy_status:
        summary = f"{summary} {accuracy_status}"
    return summary


def improve_report_with_new_sources(
    state: AgentState,
    feedback: dict,
    retry_count: int,
) -> bool:
    """Low critic scores mean evidence is weak, so fetch more evidence before rewriting."""
    query = low_score_search_query(state, feedback, retry_count)
    try:
        new_results = cache.get_or_set(
            "search_results",
            {"query": query, "mode": state.get("mode", "discover"), "retry": retry_count},
            lambda: perform_python_search(query, max_results=5),
            ttl_seconds=6 * 3600,
        )
        new_sources = normalize_search_results(new_results)
    except Exception as exc:
        record_error(state, "Search Agent", exc)
        new_sources = []

    merged_sources = merge_sources(state.get("sources", []), new_sources)
    if len(merged_sources) <= len(state.get("sources", [])):
        append_agent_output(
            state,
            "Search Agent",
            "needs_review",
            "Low critic score triggered a source refresh, but no new usable sources were found.",
            new_sources,
        )
        return False

    state["search_results"] = merged_sources
    state["sources"] = merged_sources
    append_agent_output(
        state,
        "Search Agent",
        "retry",
        "Low critic score triggered a new source search before rewriting the report.",
        new_sources,
    )

    scraper_agent(state)
    writer_agent(state)
    return bool(state.get("final_answer") or state.get("report"))


def low_score_search_query(state: AgentState, feedback: dict, retry_count: int) -> str:
    issues = " ".join(feedback.get("issues", [])[:3])
    improvements = " ".join(feedback.get("improvements", [])[:2])
    base_query = mode_search_query(state.get("query", ""), state.get("mode", "discover"))
    return " ".join(
        part
        for part in [
            base_query,
            "primary sources evidence data report",
            issues,
            improvements,
            f"retry {retry_count}",
        ]
        if part
    ).strip()


def merge_sources(existing: list[dict], additions: list[dict]) -> list[dict]:
    merged = []
    seen_urls = set()
    for source in [*(existing or []), *(additions or [])]:
        url = source.get("url", "")
        if not validate_url(url) or url in seen_urls:
            continue
        seen_urls.add(url)
        merged.append(source)
    return sorted(merged, key=lambda item: item.get("quality_score", 0), reverse=True)[:8]


# ── FALLBACK FUNCTIONS ────────────────────────────────────────────────────────

def fallback_search_results(query: str) -> list[dict]:
    """
    Returns empty list when search fails completely.
    Downstream agents continue with fallback_answer().
    Warning logged so failure is always visible in logs.
    """
    logger.warning(
        "Search agent failed for query '%s'. "
        "Returning empty source list. "
        "Check TAVILY_API_KEY and network connectivity.",
        query,
    )
    return []


def fallback_scraped_content(sources: list[dict]) -> list[dict]:
    """Uses Tavily search snippets as evidence when live scraping fails."""
    return [
        {
            "url": source.get("url", ""),
            "content": source.get("snippet") or source.get("summary") or "No source text available.",
        }
        for source in sources
    ]


def fallback_answer(state: AgentState) -> str:
    sources = state.get("sources", [])
    source_lines = "\n".join(
        f"{index}. {source.get('title', 'Untitled source')} - {source.get('url', '')}"
        for index, source in enumerate(sources, 1)
    )
    if not source_lines:
        source_lines = "No usable sources were available."

    return (
        f"{state.get('query', 'Research answer')}\n\n"
        "Executive Summary\n"
        "Data unavailable.\n\n"
        "Key Findings\n"
        "- Data unavailable.\n\n"
        "Deep Analysis\n"
        "Data unavailable.\n\n"
        "Evidence & Sources\n"
        f"{source_lines}\n\n"
        "Limitations / Data Gaps\n"
        "Data unavailable.\n\n"
        "Conclusion\n"
        "Data unavailable."
    )


def fallback_critic_feedback(state: AgentState) -> dict:
    return {
        "score": 1,
        "score_meaning": "Fallback critic feedback created after critic execution failed.",
        "confidence": "low",
        "word_count": len((state.get("final_answer") or "").split()),
        "citations": 0,
        "sources_used": 0,
        "sources_available": len(state.get("sources", [])),
        "claim_support_audit": {
            "checked_claims": [],
            "checked_claim_count": 0,
            "supported_claim_count": 0,
            "support_rate": 0,
            "weak_claims": [],
            "method_limit": "Critic fallback; full quality evaluation did not complete.",
        },
        "criteria": {},
        "issues": ["Critic agent failed and fallback feedback was used."],
        "improvements": ["Inspect pipeline logs and retry."],
        "final_verdict": "Needs review.",
    }


# ── REPORT QUALITY FUNCTIONS ──────────────────────────────────────────────────

def quality_warning(report: str) -> str:
    """Return report unchanged — quality flag is passed as metadata, not injected into text."""
    return report


def retry_instruction(retry_count: int) -> str:
    if retry_count == 1:
        return (
            "Regenerate by fixing all critic issues, removing unsupported claims, "
            "and keeping only valid citations that match the source list."
        )
    return (
        "Simplify the report drastically. Keep only the strongest supported facts. "
        "Replace every weak or unverified claim with 'Insufficient verified information.'"
    )


def sanitize_final_output(report: str) -> str:
    text = report or ""
    text = re.sub(r"^```(?:markdown)?\s*\n?", "", text.strip())
    text = re.sub(r"\n?```\s*$", "", text)
    text = text.replace("**", "").replace("$$", "")
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = remove_duplicate_headings(text)
    return text.strip()


def remove_duplicate_headings(text: str) -> str:
    seen: set[str] = set()
    lines = []
    heading_names = {
        "title",
        "executive summary",
        "key findings",
        "deep analysis",
        "evidence & sources",
        "limitations / data gaps",
        "conclusion",
    }
    for line in text.splitlines():
        normalized = line.strip().lower().rstrip(":")
        if normalized in heading_names:
            if normalized in seen:
                continue
            seen.add(normalized)
        lines.append(line.rstrip())
    return "\n".join(lines)


def writer_topic(state: AgentState) -> str:
    query = state["query"]
    context = state.get("conversation_context", "")
    history = state.get("chat_history", [])
    mode = state.get("mode", "discover")
    history_text = "\n".join(
        f"{message.get('role', 'unknown')}: {message.get('content', '')}"
        for message in history[-6:]
    )

    parts = [f"Mode: {mode}", f"Current query: {query}"]
    if context:
        parts.append(
            "Conversation context for continuity. Use it for intent only; "
            f"factual claims must still come from sources.\n{context}"
        )
    if history_text:
        parts.append(f"Recent chat history:\n{history_text}")
    return "\n\n".join(parts)


def format_sources_for_writer(sources: list[dict]) -> str:
    return "\n".join(
        f"[{index}] {source.get('title', 'Untitled')} - {source.get('url', '')}"
        for index, source in enumerate(sources, 1)
    )


# ── AGENT LOGGING & STATE HELPERS ─────────────────────────────────────────────

def append_agent_output(
    state: AgentState,
    name: str,
    status: str,
    summary: str,
    output: Any,
) -> None:
    state.setdefault("agent_outputs", []).append(agent_record(name, status, summary, output))


def record_error(state: AgentState, agent_name: str, exc: Exception) -> None:
    logger.exception("%s failed", agent_name)
    error = {
        "agent": agent_name,
        "error": str(exc),
        "timestamp": datetime.utcnow().isoformat(timespec="seconds") + "Z",
    }
    state.setdefault("errors", []).append(error)


def log_agent_start(agent_name: str, state: AgentState) -> None:
    logger.info(
        "%s start | query=%s mode=%s",
        agent_name,
        state.get("query"),
        state.get("mode"),
    )


def log_agent_output(agent_name: str, output: Any) -> None:
    logger.info("%s output | %s", agent_name, safe_preview(output))


def safe_preview(value: Any, limit: int = 1200) -> str:
    try:
        text = json.dumps(value, default=str) if not isinstance(value, str) else value
    except Exception:
        text = str(value)
    return text[:limit]
