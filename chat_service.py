import json
from copy import deepcopy

from agents import memory_summary_chain
from cache_store import cache
from database.database import ResearchDatabase
from memory import SessionMemory, repair_messages
from pipeline import run_research_pipeline


def summarize_memory(existing_summary: str, older_messages: str) -> str:
    """Lightweight LLM call used only when older chat history needs compression."""
    cache_payload = {
        "summary": existing_summary,
        "messages": older_messages,
    }
    return cache.get_or_set(
        "memory_summary",
        cache_payload,
        lambda: memory_summary_chain.invoke(cache_payload),
        ttl_seconds=24 * 3600,
    )


class ResearchChatService:
    """
    ChatGPT/Perplexity-style wrapper around the existing research pipeline.

    SessionMemory is temporary, cache is fast reuse, and SQLite is durable storage.
    """

    def __init__(
        self,
        db: ResearchDatabase | None = None,
        memory: SessionMemory | None = None,
    ):
        self.db = db or ResearchDatabase()
        self.memory = memory or SessionMemory(max_recent_messages=4)

    def start_thread(self, user_id: int, title: str) -> int | None:
        return self.db.create_thread(user_id=user_id, title=title)

    def load_thread(self, thread_id: int) -> None:
        messages = self.db.load_messages(thread_id)
        self.memory.load_messages(repair_messages(messages))

    def ask(
        self,
        user_input: str,
        thread_id: int | None = None,
        user_id: int | None = None,
    ) -> dict:
        if user_id is None:
            return {
                "error": "A user_id is required before creating or continuing a thread.",
                "thread_id": None,
            }

        if not thread_id:
            thread_id = self.start_thread(user_id, user_input[:80])
        elif not self.db.thread_belongs_to_user(thread_id, user_id):
            return {
                "error": "This thread does not belong to the current user.",
                "thread_id": None,
            }

        if not thread_id:
            return {
                "error": "Could not create or load a conversation thread.",
                "thread_id": None,
            }

        self.memory.add_message("user", user_input)
        self.db.save_message(thread_id, "user", user_input)

        answer_context = self.memory.build_context(user_input)
        cache_payload = {
            "thread_summary": self.memory.summary,
            "recent_messages": self.memory.trim_history(),
            "user_input": user_input,
        }

        # Search should use the user's current query, not the full conversation
        # context. The context is provided separately to the writer.
        result = deepcopy(cache.get_or_set(
            "final_response",
            cache_payload,
            lambda: run_research_pipeline(
                topic=user_input,
                conversation_context=answer_context,
            ),
            ttl_seconds=6 * 3600,
        ))

        assistant_response = result.get("report", "")
        self.memory.add_message("assistant", assistant_response)
        self.memory.update_summary(summarize_memory)

        self.db.save_message(thread_id, "assistant", assistant_response)
        self.db.save_sources(thread_id, result.get("source_cards", []))

        feedback = _parse_feedback(result.get("feedback", "{}"))
        report_id = self.db.save_report(
            thread_id=thread_id,
            final_answer=assistant_response,
            quality_score=feedback.get("score"),
            confidence=feedback.get("confidence", "unknown"),
        )
        if report_id:
            claim_audit = feedback.get("claim_support_audit", {})
            self.db.save_claim_checks(report_id, claim_audit.get("checked_claims", []))

        result["thread_id"] = thread_id
        result["memory_summary"] = self.memory.summary
        result["context_sent_to_pipeline"] = answer_context
        return result


def _parse_feedback(value: str | dict) -> dict:
    if isinstance(value, dict):
        return value
    try:
        return json.loads(value)
    except Exception:
        return {}
