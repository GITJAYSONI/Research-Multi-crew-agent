import asyncio
import json
import re
from datetime import datetime
from typing import Any

from agents import writer_chain, summarizer_chain, refiner_chain
from cache_store import cache
from sources import build_reader_output, build_source_cards, format_evidence_for_writer
from tools import async_scrape_all_urls, perform_python_search
from verifier import evaluate_report_quality


def agent_record(name: str, status: str, summary: str, output: Any) -> dict:
    return {
        "agent": name,
        "status": status,
        "summary": summary,
        "output": output,
        "timestamp": datetime.utcnow().isoformat(timespec="seconds") + "Z",
    }


def run_research_pipeline(topic: str, conversation_context: str = "") -> dict:
    """
    Execute the research pipeline:
    Search Agent -> Scraper Agent -> Reader Agent -> Writer Agent -> Critic Agent
    """
    state: dict[str, Any] = {"topic": topic, "agent_outputs": []}

    print("\n" + "=" * 60)
    print("STEP 1: SEARCH AGENT - Gathering sources")
    print("=" * 60)
    sources_list = cache.get_or_set(
        "search_results",
        {"topic": topic},
        lambda: perform_python_search(topic),
        ttl_seconds=24 * 3600,
    )
    state["sources_list"] = sources_list
    state["search_results"] = json.dumps(sources_list, indent=2)
    state["agent_outputs"].append(
        agent_record(
            "Search Agent",
            "passed" if sources_list else "needs_review",
            f"Found {len(sources_list)} candidate sources.",
            sources_list,
        )
    )
    print(f"Search complete. Found {len(sources_list)} sources.")

    print("\n" + "=" * 60)
    print("STEP 2: SCRAPER AGENT - Extracting source content")
    print("=" * 60)
    urls = [source["url"] for source in sources_list if source.get("url")]
    if urls:
        scraped_content = cache.get_or_set(
            "scraped_content",
            {"urls": urls},
            lambda: asyncio.run(async_scrape_all_urls(urls)),
            ttl_seconds=24 * 3600,
        )
        print(f"Scraped {len(urls)} sources.")
        
        # Step 2.5: DATA CLEANING
        print("\n" + "=" * 60)
        print("STEP 2.5: DATA CLEANING - Summarizing scraped content")
        print("=" * 60)
        chunks = re.split(r"\n(?=Source: )", scraped_content or "")
        cleaned_chunks = []
        for chunk in chunks:
            if chunk.strip():
                source_match = re.search(r"Source:\s*(.+)", chunk)
                source_url = source_match.group(1).strip() if source_match else "unknown"
                # Cached summarization prevents repeated LLM calls for the same page text.
                bullet_summary = cache.get_or_set(
                    "summarized_data",
                    {"url": source_url, "content": chunk[:4000]},
                    lambda chunk=chunk: summarizer_chain.invoke({"content": chunk[:4000]}),
                    ttl_seconds=24 * 3600,
                )
                cleaned_chunks.append(f"Source: {source_url}\nContent:\n{bullet_summary}")
        scraped_content = "\n\n".join(cleaned_chunks)
    else:
        scraped_content = "No valid URLs found to scrape."
        print("No valid URLs to scrape.")

    state["scraped_content"] = scraped_content
    state["agent_outputs"].append(
        agent_record(
            "Scraper Agent",
            "passed" if urls else "needs_review",
            f"Processed {len(urls)} URLs for source text.",
            scraped_content[:3000],
        )
    )

    print("\n" + "=" * 60)
    print("STEP 3: READER AGENT - Structuring evidence")
    print("=" * 60)
    extracted_data = build_reader_output(sources_list, scraped_content)
    state["extracted_data"] = extracted_data
    state["source_cards"] = build_source_cards(extracted_data)
    state["agent_outputs"].append(
        agent_record(
            "Reader Agent",
            "passed" if extracted_data else "needs_review",
            f"Built source cards and structured evidence for {len(extracted_data)} sources.",
            {
                "source_cards": state["source_cards"],
                "extracted_data": extracted_data,
            },
        )
    )
    print(f"Structured evidence for {len(extracted_data)} sources.")

    print("\n" + "=" * 60)
    print("STEP 4: WRITER AGENT - Synthesizing final report")
    print("=" * 60)
    sources_formatted = "\n".join(
        f"[{i}] {source.get('title', 'Untitled')} - {source.get('url', '')}"
        for i, source in enumerate(sources_list, 1)
    )
    report = writer_chain.invoke(
        {
            "topic": _writer_topic(topic, conversation_context),
            "research_data": format_evidence_for_writer(extracted_data),
            "sources": sources_formatted,
        }
    )
    state["report"] = report
    state["agent_outputs"].append(
        agent_record(
            "Writer Agent",
            "passed" if report else "needs_review",
            f"Generated a {len(report.split()) if report else 0}-word report.",
            report,
        )
    )
    print("Report generated.")

    print("\n" + "=" * 60)
    print("STEP 5: CRITIC AGENT - Scoring quality")
    print("=" * 60)
    feedback = evaluate_report_quality(report, topic, sources_list, extracted_data)
    score = feedback["score"]
    
    # Conditional Refinement Logic
    if score < 4:
        print(f"Quality score {score}/10 is too low. Returning fallback.")
        report = "**QUALITY WARNING:** The generated report failed to meet the minimum quality standard and was rejected by the system.\n\n" + report
        state["report"] = report
    elif 4 <= score < 7:
        print(f"Quality score {score}/10. Refining ONCE...")
        report = refiner_chain.invoke({"report": report, "feedback": json.dumps(feedback)})
        state["report"] = report
        # Re-evaluate after refinement
        feedback = evaluate_report_quality(report, topic, sources_list, extracted_data)
        score = feedback["score"]
    else:
        print(f"Quality score {score}/10. Draft accepted.")

    state["source_cards"] = build_source_cards(extracted_data, feedback.get("claim_support_audit", {}))
    state["feedback"] = json.dumps(feedback, indent=2)
    state["final_score"] = feedback["score"]
    state["agent_outputs"].append(
        agent_record(
            "Critic Agent",
            "passed" if feedback["score"] >= 8 else "needs_review",
            f"Quality score: {feedback['score']}/10. {feedback['final_verdict']}",
            feedback,
        )
    )
    print(f"Quality score: {feedback['score']}/10.")

    return state


def _writer_topic(topic: str, conversation_context: str) -> str:
    if not conversation_context:
        return topic

    return (
        f"{topic}\n\n"
        "Conversation context for answering follow-up questions. "
        "Use this only for intent and continuity; factual claims must still come from sources.\n"
        f"{conversation_context}"
    )
