import json
import logging
import os
import re
import threading
import time
from collections import defaultdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from chat_service import ResearchChatService
from database.database import ResearchDatabase
from dotenv import load_dotenv
from memory import SessionMemory
from tools import youtube_search_link   # ← FIX: imported from tools.py, no local duplicate
from utils import parse_json_safe

load_dotenv(override=True)

logger = logging.getLogger(__name__)

ROOT_DIR = Path(__file__).resolve().parent
DB_PATH = ROOT_DIR / "database" / "research_memory.db"

# ── Read from environment so nothing is hardcoded in source ───────────────────
LOCAL_USER_EMAIL = os.getenv("LOCAL_USER_EMAIL", "local-user@research-app.local")
ALLOWED_ORIGIN = os.getenv("ALLOWED_ORIGIN", "http://localhost:3000")

# ── Simple per-IP rate limiter (10 requests per 60 seconds) ───────────────────
_rate_limit_store: dict[str, list[float]] = defaultdict(list)
_rate_limit_lock = threading.Lock()
_RATE_LIMIT_MAX = 10
_RATE_LIMIT_WINDOW = 60  # seconds


def _is_rate_limited(ip: str) -> bool:
    now = time.time()
    with _rate_limit_lock:
        _rate_limit_store[ip] = [t for t in _rate_limit_store[ip] if now - t < _RATE_LIMIT_WINDOW]
        if len(_rate_limit_store[ip]) >= _RATE_LIMIT_MAX:
            return True
        _rate_limit_store[ip].append(now)
    return False


class ApiHandler(BaseHTTPRequestHandler):
    """HTTP API bridge between the React frontend and the research pipeline."""

    # Suppress default request logging — use the logger instead
    def log_message(self, format: str, *args) -> None:
        logger.debug("%s - %s", self.address_string(), format % args)

    def _send_json(self, payload: dict, status: int = 200) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", ALLOWED_ORIGIN)
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_bytes(self, body: bytes, content_type: str, filename: str) -> None:
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Access-Control-Allow-Origin", ALLOWED_ORIGIN)
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self) -> None:
        self._send_json({})

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)
        db = ResearchDatabase(DB_PATH)
        user_id = int(query.get("user_id", [db.create_user(LOCAL_USER_EMAIL) or 1])[0])

        if parsed.path == "/api/threads":
            self._send_json({"threads": db.list_threads(user_id), "user_id": user_id})
            return

        if parsed.path == "/api/thread":
            thread_id = int(query.get("thread_id", [0])[0])
            if not thread_id or not db.thread_belongs_to_user(thread_id, user_id):
                self._send_json({"error": "Thread not found"}, status=404)
                return
            self._send_json(
                {
                    "thread_id": thread_id,
                    "user_id": user_id,
                    "messages": db.load_messages(thread_id),
                }
            )
            return

        self._send_json({"error": "Not found"}, status=404)

    def do_POST(self) -> None:
        if self.path == "/api/report/pdf":
            try:
                content_length = int(self.headers.get("Content-Length", "0"))
                raw_body = self.rfile.read(content_length).decode("utf-8")
                payload = json.loads(raw_body or "{}")
                pdf = build_pdf(
                    payload.get("title", "Research Report"),
                    payload.get("report", ""),
                )
                self._send_bytes(pdf, "application/pdf", "research_report.pdf")
            except Exception as exc:
                logger.exception("PDF generation failed")
                self._send_json({"error": str(exc)}, status=500)
            return

        if self.path != "/api/chat":
            self._send_json({"error": "Not found"}, status=404)
            return

        # ── Rate limiting ──────────────────────────────────────────────────────
        client_ip = self.client_address[0]
        if _is_rate_limited(client_ip):
            self._send_json(
                {"error": "Rate limit exceeded. Wait before retrying."},
                status=429,
            )
            return

        try:
            content_length = int(self.headers.get("Content-Length", "0"))
            raw_body = self.rfile.read(content_length).decode("utf-8")
            payload = json.loads(raw_body or "{}")

            message = (payload.get("message") or "").strip()

            # ── FIX: image check removed — image handling not implemented in pipeline.
            # Only text messages are accepted. Add image support in pipeline.py first
            # if you need it, then re-enable this check.
            if not message:
                self._send_json({"error": "message is required"}, status=400)
                return

            db = ResearchDatabase(DB_PATH)
            user_id = payload.get("user_id") or db.create_user(LOCAL_USER_EMAIL)
            memory = SessionMemory(max_recent_messages=4)
            service = ResearchChatService(db=db, memory=memory)

            # ── FIX: load existing thread messages into memory so conversation
            # context is restored on every request (was missing before).
            thread_id = payload.get("thread_id")
            if thread_id:
                service.load_thread(thread_id)

            result = service.ask(
                user_input=message,
                thread_id=thread_id,
                user_id=user_id,
                mode=payload.get("mode", "discover"),
            )
            result["user_id"] = user_id
            result["structured_report"] = build_structured_report(result)

            # ── FIX: youtube_search_link is now imported from tools.py.
            # The local duplicate function that always appended " explained"
            # has been removed. tools.py applies " explained" only for short queries.
            result["youtube_link"] = youtube_search_link(message)

            self._send_json(result)
        except Exception as exc:
            logger.exception("Chat request failed")
            self._send_json({"error": str(exc)}, status=500)


# ══════════════════════════════════════════════════════════════════════════════
# REPORT BUILDER
# ══════════════════════════════════════════════════════════════════════════════

def build_structured_report(result: dict) -> dict:
    """Structured components consumed by the React frontend."""
    feedback = parse_json_safe(result.get("feedback", "{}"))
    source_cards = result.get("source_cards", [])
    agent_outputs = result.get("agent_outputs", [])
    weak_claims = feedback.get("claim_support_audit", {}).get("weak_claims", [])
    raw_title = result.get("topic") or result.get("query") or "Research Analysis"
    report = result.get("report") or result.get("final_answer", "")

    return {
        "title_page": {
            "title": " ".join(w.capitalize() for w in raw_title.strip().split())[:120],
            "date": result.get("created_at", ""),
            "introduction": (
                "This report compares evidence collected by the multi-agent research pipeline "
                "and summarizes the verified findings."
            ),
        },
        "methodology": {
            "process": (
                "Search Agent collected candidate sources; Scraper Agent extracted source text; "
                "Writer Agent synthesized the answer; Critic Agent evaluated citation quality "
                "and evidence support."
            ),
            "source_count": len(source_cards),
        },
        "sources_of_data": [
            {
                "title": source.get("title", "Untitled source"),
                "url": source.get("url", ""),
                "publisher": source.get("publisher", ""),
                "trust_score": source.get("trust_score", 0),
                "summary": source.get("summary", ""),
                "url_format_valid": source.get("url_format_valid", False),
                "validation_status": source.get("validation_status", "Source Unverified"),
                "validation_note": source.get(
                    "validation_note",
                    "Source Unverified: live HTTP status was not verified.",
                ),
            }
            for source in source_cards
        ],
        "key_findings": _extract_key_findings(report),
        "deep_analysis": _extract_section(report, "Deep Analysis"),
        "evidence_and_sources": {
            "sources": source_cards,
            "validation_note": "Live HTTP status is not verified by this pipeline; sources are marked Source Unverified.",
        },
        "limitations_data_gaps": _extract_section(report, "Limitations / Data Gaps"),
        "evidence_quality_and_limits": {
            "confidence": feedback.get("confidence", "unknown"),
            "score": feedback.get("score", result.get("final_score")),
            "issues": feedback.get("issues", []),
            "improvements": feedback.get("improvements", []),
            "weak_claims": weak_claims,
            "accuracy_status": result.get("accuracy_status", ""),
            "retry_count": result.get("retry_count", 0),
        },
        "agent_scraped_data": agent_outputs,
        "conclusion": _extract_section(report, "Conclusion"),
        "quality_warning": result.get("quality_warning", False),
        "accuracy_status": result.get("accuracy_status", ""),
        "retry_count": result.get("retry_count", 0),
    }


# ══════════════════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ══════════════════════════════════════════════════════════════════════════════

def _extract_key_findings(report: str) -> list[str]:
    section = _extract_section(report, "Key Findings")
    return [
        line.strip("- ").strip()
        for line in section.splitlines()
        if line.strip().startswith("-")
    ][:8]


def _extract_section(report: str, heading: str) -> str:
    if not report:
        return ""

    heading_name = heading.lstrip("#").strip().rstrip(":")
    pattern = re.compile(
        rf"(?im)^\s*(?:#{{1,3}}\s*)?{re.escape(heading_name)}\s*:?\s*$"
    )
    match = pattern.search(report)
    if not match:
        return ""

    after = report[match.end() :]
    next_heading = re.search(r"(?im)^\s*(?:#{1,3}\s*)?[A-Z][A-Za-z0-9 &'/-]{2,}\s*:?\s*$", after)
    return (after[: next_heading.start()] if next_heading else after).strip()


# ══════════════════════════════════════════════════════════════════════════════
# PDF GENERATOR (stdlib only)
# ══════════════════════════════════════════════════════════════════════════════

def build_pdf(title: str, report: str) -> bytes:
    """Generate a simple text PDF using only the Python standard library."""
    safe_title = clean_pdf_text(title)[:90]
    lines = [safe_title, "", *wrap_pdf_lines(clean_pdf_text(report))]
    pages = [lines[i : i + 42] for i in range(0, len(lines), 42)] or [[safe_title]]

    objects: list[bytes] = []
    page_refs: list[int] = []

    def add_object(payload: bytes) -> int:
        objects.append(payload)
        return len(objects)

    font_id = add_object(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")

    for page_lines in pages:
        content = ["BT", "/F1 10 Tf", "50 780 Td", "14 TL"]
        for line in page_lines:
            content.append(f"({escape_pdf(line)}) Tj")
            content.append("T*")
        content.append("ET")
        stream = "\n".join(content).encode("latin-1", "replace")
        stream_id = add_object(
            b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream"
        )
        page_id = add_object(
            (
                f"<< /Type /Page /Parent 0 0 R /MediaBox [0 0 612 792] "
                f"/Resources << /Font << /F1 {font_id} 0 R >> >> /Contents {stream_id} 0 R >>"
            ).encode()
        )
        page_refs.append(page_id)

    pages_id = len(objects) + 1
    catalog_id = len(objects) + 2

    fixed_objects = []
    for payload in objects:
        if b"/Parent 0 0 R" in payload:
            payload = payload.replace(b"/Parent 0 0 R", f"/Parent {pages_id} 0 R".encode())
        fixed_objects.append(payload)

    kids = " ".join(f"{r} 0 R" for r in page_refs)
    fixed_objects.append(f"<< /Type /Pages /Kids [{kids}] /Count {len(page_refs)} >>".encode())
    fixed_objects.append(f"<< /Type /Catalog /Pages {pages_id} 0 R >>".encode())

    pdf = bytearray(b"%PDF-1.4\n")
    offsets = []
    for idx, payload in enumerate(fixed_objects, 1):
        offsets.append(len(pdf))
        pdf.extend(f"{idx} 0 obj\n".encode())
        pdf.extend(payload)
        pdf.extend(b"\nendobj\n")

    xref = len(pdf)
    pdf.extend(f"xref\n0 {len(fixed_objects) + 1}\n0000000000 65535 f \n".encode())
    for offset in offsets:
        pdf.extend(f"{offset:010d} 00000 n \n".encode())
    pdf.extend(
        (
            f"trailer\n<< /Size {len(fixed_objects) + 1} /Root {catalog_id} 0 R >>\n"
            f"startxref\n{xref}\n%%EOF"
        ).encode()
    )
    return bytes(pdf)


def clean_pdf_text(text: str) -> str:
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text or "")
    text = re.sub(r"[*_`#>]", "", text)
    return text


def wrap_pdf_lines(text: str, width: int = 92) -> list[str]:
    lines = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            lines.append("")
            continue
        while len(line) > width:
            split_at = line.rfind(" ", 0, width) or width
            lines.append(line[:split_at])
            line = line[split_at:].strip()
        lines.append(line)
    return lines


def escape_pdf(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    port = int(os.environ.get("PORT", 8000))
    server = ThreadingHTTPServer(("0.0.0.0", port), ApiHandler)
    logger.info("Backend API running at http://0.0.0.0:%d", port)
    server.serve_forever()
