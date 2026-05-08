import unittest

import chat_service
import pipeline
from api_server import build_structured_report
from chat_service import ResearchChatService
from database.database import ResearchDatabase
from memory import SessionMemory
from sources import build_reader_output, build_source_cards
from tools import flatten_json_text, source_quality_score


class ReportOutputTests(unittest.TestCase):
    def setUp(self):
        chat_service.cache.clear()

    def tearDown(self):
        chat_service.cache.clear()

    def test_chat_service_uses_final_answer_when_report_key_is_missing(self):
        original_pipeline = chat_service.run_research_pipeline

        def fake_pipeline(**_kwargs):
            return {
                "final_answer": "# Test Report\n\n## Executive Summary\nVisible final answer.",
                "feedback": '{"score": 8, "confidence": "high"}',
                "source_cards": [],
                "agent_outputs": [],
            }

        chat_service.run_research_pipeline = fake_pipeline
        try:
            db = ResearchDatabase(":memory:")
            user_id = db.create_user()
            service = ResearchChatService(
                db=db,
                memory=SessionMemory(max_recent_messages=4),
            )

            result = service.ask("test topic", user_id=user_id)

            self.assertIn("Visible final answer.", result["report"])
            self.assertEqual(result["report"], result["final_answer"])
            self.assertEqual(service.memory.messages[-1]["content"], result["report"])
            self.assertEqual(
                db.load_messages(result["thread_id"])[-1]["content"],
                result["report"],
            )
        finally:
            chat_service.run_research_pipeline = original_pipeline

    def test_structured_report_extracts_from_final_answer_and_plain_headings(self):
        result = {
            "query": "test topic",
            "final_answer": (
                "Test Topic\n\n"
                "Executive Summary\n"
                "Summary text.\n\n"
                "Key Findings\n"
                "- Finding one.\n"
                "- Finding two.\n\n"
                "Deep Analysis\n"
                "Analysis text.\n\n"
                "Evidence & Sources\n"
                "1. Example - https://example.com/report\n\n"
                "Limitations / Data Gaps\n"
                "Limit text.\n\n"
                "Conclusion\n"
                "Conclusion text."
            ),
            "feedback": '{"score": 8, "confidence": "high"}',
            "source_cards": [],
            "agent_outputs": [],
        }

        structured = build_structured_report(result)

        self.assertEqual(structured["key_findings"], ["Finding one.", "Finding two."])
        self.assertEqual(structured["deep_analysis"], "Analysis text.")
        self.assertEqual(structured["limitations_data_gaps"], "Limit text.")
        self.assertEqual(structured["conclusion"], "Conclusion text.")

    def test_chat_service_never_saves_empty_assistant_response(self):
        original_pipeline = chat_service.run_research_pipeline

        def fake_pipeline(**_kwargs):
            return {
                "feedback": '{"score": 1, "confidence": "low"}',
                "source_cards": [],
                "agent_outputs": [],
            }

        chat_service.run_research_pipeline = fake_pipeline
        try:
            db = ResearchDatabase(":memory:")
            user_id = db.create_user()
            service = ResearchChatService(
                db=db,
                memory=SessionMemory(max_recent_messages=4),
            )

            result = service.ask("empty topic", user_id=user_id)
            messages = db.load_messages(result["thread_id"])

            self.assertIn("Data unavailable.", result["report"])
            self.assertTrue(result["quality_warning"])
            self.assertTrue(messages[-1]["content"].strip())
        finally:
            chat_service.run_research_pipeline = original_pipeline

    def test_database_rejects_empty_messages_and_reports(self):
        db = ResearchDatabase(":memory:")
        user_id = db.create_user()
        thread_id = db.create_thread(user_id, "storage")

        self.assertFalse(db.save_message(thread_id, "assistant", "   "))
        self.assertIsNone(db.save_report(thread_id, "   ", None, "low"))
        self.assertEqual(db.load_messages(thread_id), [])

    def test_source_cards_mark_urls_as_unverified(self):
        cards = build_source_cards(
            [
                {
                    "source_id": 1,
                    "title": "Example Report",
                    "url": "https://example.com/research/report",
                    "publisher": "example.com",
                    "trust_score": 0.5,
                    "trust_label": "medium",
                    "trust_reasons": [],
                    "key_points": ["Summary"],
                    "snippets": ["Snippet"],
                    "content_available": True,
                }
            ]
        )

        self.assertTrue(cards[0]["url_format_valid"])
        self.assertEqual(cards[0]["validation_status"], "Source Unverified")
        self.assertIn("live HTTP status was not verified", cards[0]["validation_note"])

    def test_reader_output_matches_redirected_chunks_by_original_url(self):
        source_url = "https://example.com/research/article?utm_source=long-query"
        extracted = build_reader_output(
            [{"title": "Example", "url": source_url, "summary": "Summary text"}],
            (
                "Source: https://example.com/final/article\n"
                f"Original URL: {source_url}\n"
                "Content:\n"
                "This is the full rendered evidence text with enough details for the report."
            ),
        )

        self.assertIn("full rendered evidence text", extracted[0]["evidence_excerpt"])
        self.assertEqual(extracted[0]["url"], source_url)

    def test_critic_reruns_search_scrape_write_once_below_score_seven(self):
        original_evaluate = pipeline.evaluate_report_quality
        original_search = pipeline.perform_python_search
        original_scraper = pipeline.scraper_agent
        original_writer = pipeline.writer_agent
        calls = {"evaluate": 0, "search": 0, "scrape": 0, "write": 0}

        def fake_evaluate(_report, _sources, _extracted_data):
            calls["evaluate"] += 1
            score = 6 if calls["evaluate"] == 1 else 7
            return {
                "score": score,
                "issues": ["Needs stronger support"],
                "claim_support_audit": {},
                "final_verdict": "Reviewed.",
            }

        def fake_search(_query, max_results=5):
            calls["search"] += 1
            return [
                {
                    "title": "New Source",
                    "url": "https://example.com/new-source",
                    "summary": "New evidence.",
                    "quality_score": 90,
                }
            ]

        def fake_scraper(state):
            calls["scrape"] += 1
            state["extracted_data"] = [
                {
                    "source_id": 1,
                    "title": "New Source",
                    "url": "https://example.com/new-source",
                    "content_available": True,
                }
            ]
            return state

        def fake_writer(state):
            calls["write"] += 1
            state["final_answer"] = "# Refined\n\n## Executive Summary\nImproved with new evidence."
            state["report"] = state["final_answer"]
            return state

        pipeline.evaluate_report_quality = fake_evaluate
        pipeline.perform_python_search = fake_search
        pipeline.scraper_agent = fake_scraper
        pipeline.writer_agent = fake_writer
        try:
            state = pipeline.critic_agent(
                {
                    "query": "test",
                    "final_answer": "# Draft\n\n## Executive Summary\nWeak report.",
                    "report": "# Draft\n\n## Executive Summary\nWeak report.",
                    "sources": [
                        {
                            "title": "Old Source",
                            "url": "https://example.com/old-source",
                            "summary": "Old evidence.",
                            "quality_score": 40,
                        }
                    ],
                    "extracted_data": [],
                    "agent_outputs": [],
                    "errors": [],
                    "retry_count": 0,
                }
            )

            self.assertEqual(calls["search"], 1)
            self.assertEqual(calls["scrape"], 1)
            self.assertEqual(calls["write"], 1)
            self.assertEqual(state["retry_count"], 1)
            self.assertEqual(state["final_score"], 7)
            self.assertEqual(state["accuracy_status"], "accuracy was improving")
            self.assertIn("accuracy was improving", state["agent_outputs"][-1]["summary"])
        finally:
            pipeline.evaluate_report_quality = original_evaluate
            pipeline.perform_python_search = original_search
            pipeline.scraper_agent = original_scraper
            pipeline.writer_agent = original_writer

    def test_critic_does_not_rerun_at_score_seven(self):
        original_evaluate = pipeline.evaluate_report_quality
        original_search = pipeline.perform_python_search
        calls = {"search": 0}

        def fake_evaluate(_report, _sources, _extracted_data):
            return {
                "score": 7,
                "issues": [],
                "claim_support_audit": {},
                "final_verdict": "Passed quality threshold.",
            }

        pipeline.evaluate_report_quality = fake_evaluate
        pipeline.perform_python_search = lambda *_args, **_kwargs: calls.__setitem__("search", calls["search"] + 1) or []
        try:
            state = pipeline.critic_agent(
                {
                    "query": "test",
                    "final_answer": "# Draft\n\n## Executive Summary\nGood enough.",
                    "report": "# Draft\n\n## Executive Summary\nGood enough.",
                    "sources": [],
                    "extracted_data": [],
                    "agent_outputs": [],
                    "errors": [],
                    "retry_count": 0,
                }
            )

            self.assertEqual(calls["search"], 0)
            self.assertEqual(state["retry_count"], 0)
            self.assertEqual(state["final_score"], 7)
            self.assertEqual(state["accuracy_status"], "")
        finally:
            pipeline.evaluate_report_quality = original_evaluate
            pipeline.perform_python_search = original_search

    def test_reader_does_not_treat_search_summary_as_scraped_evidence(self):
        extracted = build_reader_output(
            [
                {
                    "title": "Search Only",
                    "url": "https://example.com/search-only",
                    "summary": "A short search snippet should not be treated as verified evidence.",
                }
            ],
            scraped_content="",
        )

        self.assertFalse(extracted[0]["content_available"])
        self.assertEqual(extracted[0]["extraction_status"], "missing_or_low_signal")
        self.assertEqual(pipeline.usable_evidence(extracted), [])

    def test_reader_allows_substantial_search_excerpt_as_limited_evidence(self):
        summary = (
            "Company ABC reported revenue of 10.2 billion for the quarter, with operating "
            "margin improving to 18 percent and management citing stronger enterprise demand. "
            "The filing also listed cash flow, debt levels, and regional performance details."
        )
        extracted = build_reader_output(
            [{"title": "Search Excerpt", "url": "https://example.com/report", "summary": summary}],
            scraped_content="",
        )

        self.assertTrue(extracted[0]["content_available"])
        self.assertEqual(extracted[0]["extraction_status"], "search_excerpt")
        self.assertTrue(pipeline.usable_evidence(extracted))

    def test_reader_rejects_navigation_shell_content(self):
        nav_text = (
            "Source: https://example.com/shell\n"
            "Content:\n"
            + " ".join(
                [
                    "menu login sign in subscribe cookie privacy policy terms of use "
                    "javascript enable javascript advertisement newsletter"
                ]
                * 40
            )
        )
        extracted = build_reader_output(
            [{"title": "Shell", "url": "https://example.com/shell", "summary": "Shell page"}],
            nav_text,
        )

        self.assertFalse(extracted[0]["content_available"])

    def test_json_payload_becomes_usable_structured_evidence(self):
        text = flatten_json_text(
            {
                "data": [
                    {
                        "symbol": "ABC",
                        "open": 101.4,
                        "lastPrice": 105.2,
                        "pChange": 2.1,
                        "volume": 1250000,
                    }
                ]
            }
        )
        scraped = f"Source: https://example.com/api/data\nContent:\n{text}"
        extracted = build_reader_output(
            [
                {
                    "title": "API data",
                    "url": "https://example.com/api/data",
                    "summary": "Structured market data",
                }
            ],
            scraped,
        )

        self.assertTrue(extracted[0]["content_available"])
        self.assertTrue(pipeline.usable_evidence(extracted))

    def test_search_quality_rejects_spam_source(self):
        score = source_quality_score(
            {
                "title": "Ultimate Guide With Coupon",
                "url": "https://medium.com/example/ultimate-guide",
                "summary": "Sponsored coupon content.",
            },
            query="verified market data",
        )

        self.assertLess(score, 50)


if __name__ == "__main__":
    unittest.main()
