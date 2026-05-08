import json
import sys
import time
from html import escape
from pathlib import Path
from typing import Any

import streamlit as st

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

try:
    from chat_service import ResearchChatService
    from database.database import ResearchDatabase
    from memory import SessionMemory, repair_messages
except ImportError as exc:
    st.error(f"Could not import application modules: {exc}")
    st.stop()


PAGE_TITLE = "Research Intelligence System"


def configure_page() -> None:
    st.set_page_config(
        page_title=PAGE_TITLE,
        page_icon="R",
        layout="wide",
        initial_sidebar_state="collapsed",
    )


def inject_styles() -> None:
    st.markdown(
        """
<style>
html, body, [class*="css"] {
    font-family: Inter, Segoe UI, sans-serif;
    background: #0b1020;
    color: #eef2ff;
}
.stApp {
    background:
        radial-gradient(circle at 18% 10%, rgba(34, 211, 238, .15), transparent 28rem),
        radial-gradient(circle at 90% 8%, rgba(99, 102, 241, .16), transparent 26rem),
        linear-gradient(135deg, #0b1020 0%, #111827 54%, #0f172a 100%);
}
.block-container {
    padding-top: 1.1rem;
    padding-bottom: 2rem;
}
.app-title {
    margin-bottom: 1rem;
}
.app-title h1 {
    font-size: clamp(1.8rem, 4vw, 3.6rem);
    line-height: 1;
    margin: 0;
}
.app-title p {
    max-width: 48rem;
    color: #a5b4fc;
    font-size: .95rem;
    margin-top: .55rem;
}
.panel {
    border: 1px solid rgba(148, 163, 184, .22);
    background: rgba(15, 23, 42, .62);
    border-radius: 8px;
    padding: .9rem;
}
.metric-row {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: .55rem;
    margin: .7rem 0 1rem;
}
.metric {
    border: 1px solid rgba(148, 163, 184, .18);
    background: rgba(2, 6, 23, .42);
    border-radius: 8px;
    padding: .7rem;
}
.metric span {
    display: block;
    color: #94a3b8;
    font-size: .72rem;
    text-transform: uppercase;
    letter-spacing: .08em;
}
.metric strong {
    display: block;
    color: #e0f2fe;
    font-size: 1.1rem;
    margin-top: .2rem;
}
.thread-button {
    width: 100%;
}
.source-box {
    border-left: 3px solid #38bdf8;
    padding-left: .75rem;
    margin-bottom: .9rem;
}
.trust-pill, .claim-pill {
    display: inline-block;
    border: 1px solid rgba(148, 163, 184, .35);
    border-radius: 999px;
    padding: .12rem .55rem;
    margin: .25rem .25rem .45rem 0;
    font-size: .8rem;
    color: #bfdbfe;
}
.snippet {
    color: #dbeafe;
    background: rgba(15, 23, 42, .64);
    border: 1px solid rgba(148, 163, 184, .22);
    border-radius: 8px;
    padding: .7rem;
    margin: .35rem 0;
}
.agent-card {
    border: 1px solid rgba(148, 163, 184, .24);
    background: rgba(15, 23, 42, .72);
    border-radius: 8px;
    padding: 1rem;
    margin-bottom: .8rem;
}
.empty-chat {
    border: 1px dashed rgba(148, 163, 184, .32);
    border-radius: 8px;
    padding: 1.2rem;
    color: #cbd5e1;
    background: rgba(15, 23, 42, .4);
}
div[data-testid="stChatMessage"] {
    border-radius: 8px;
    border: 1px solid rgba(148, 163, 184, .14);
    background: rgba(15, 23, 42, .34);
}
</style>
""",
        unsafe_allow_html=True,
    )


def init_state() -> None:
    defaults = {
        "state": None,
        "running": False,
        "last_error": "",
        "current_thread_id": None,
        "current_user_id": None,
        "show_history": True,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

    if "memory" not in st.session_state:
        st.session_state.memory = SessionMemory(max_recent_messages=4)

    if st.session_state.current_user_id is None:
        st.session_state.current_user_id = get_database().create_user()


@st.cache_resource
def get_database() -> ResearchDatabase:
    db_path = ROOT_DIR / "database" / "research_memory.db"
    return ResearchDatabase(db_path)


def get_chat_service() -> ResearchChatService:
    return ResearchChatService(db=get_database(), memory=st.session_state.memory)


def parse_json(value: Any, fallback: Any) -> Any:
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except Exception:
        return fallback


def render_title() -> None:
    st.markdown(
        """
<div class="app-title">
  <h1>Research Intelligence System</h1>
  <p>Ask a question, inspect the sources, and verify how strongly the answer is supported.</p>
</div>
""",
        unsafe_allow_html=True,
    )


def start_new_thread() -> None:
    st.session_state.current_thread_id = None
    st.session_state.state = None
    st.session_state.last_error = ""
    st.session_state.memory = SessionMemory(max_recent_messages=4)


def load_thread(thread_id: int) -> None:
    db = get_database()
    user_id = st.session_state.current_user_id
    if not db.thread_belongs_to_user(thread_id, user_id):
        st.session_state.last_error = "This thread does not belong to the current user."
        return

    st.session_state.current_thread_id = thread_id
    st.session_state.state = None
    st.session_state.last_error = ""
    st.session_state.memory = SessionMemory(max_recent_messages=4)
    st.session_state.memory.load_messages(repair_messages(db.load_messages(thread_id)))


def run_research(prompt: str) -> None:
    st.session_state.running = True
    st.session_state.last_error = ""

    try:
        with st.status("Research agents are working...", expanded=True) as status:
            st.write("Searching for sources")
            st.write("Scraping and cleaning source text")
            st.write("Building evidence and source cards")
            st.write("Writing and verifying the answer")

            result = get_chat_service().ask(
                prompt,
                thread_id=st.session_state.current_thread_id,
                user_id=st.session_state.current_user_id,
            )
            if result.get("error"):
                st.session_state.last_error = result["error"]
                status.update(label="Research failed", state="error", expanded=True)
            else:
                st.session_state.state = result
                st.session_state.current_thread_id = result.get("thread_id")
                status.update(label="Research complete", state="complete", expanded=False)
    except Exception as exc:
        st.session_state.last_error = str(exc)
    finally:
        st.session_state.running = False


def render_history_panel() -> None:
    st.markdown('<div class="panel">', unsafe_allow_html=True)
    top_left, top_right = st.columns([1.2, .8])
    with top_left:
        st.subheader("History")
    with top_right:
        if st.button("Hide", use_container_width=True, key="hide_history_btn"):
            st.session_state.show_history = False

    if st.button("New Chat", use_container_width=True, key="new_chat_btn"):
        start_new_thread()

    threads = get_database().list_threads(st.session_state.current_user_id)
    if not threads:
        st.caption("No saved conversations yet.")
        st.markdown("</div>", unsafe_allow_html=True)
        return

    for thread in threads[:35]:
        thread_id = int(thread["id"])
        active = thread_id == st.session_state.current_thread_id
        title = thread.get("title") or "Untitled"
        label = f"{'* ' if active else ''}{title[:64]}"
        if st.button(label, key=f"thread_{thread_id}", use_container_width=True):
            load_thread(thread_id)

    st.markdown("</div>", unsafe_allow_html=True)


def render_control_panel() -> None:
    if not st.session_state.show_history:
        if st.button("Show History", use_container_width=True, key="show_history_btn"):
            st.session_state.show_history = True

    st.markdown('<div class="panel">', unsafe_allow_html=True)
    st.subheader("Session")
    if st.session_state.current_thread_id:
        st.caption(f"Thread #{st.session_state.current_thread_id}")
    else:
        st.caption("New conversation")

    state = st.session_state.state or {}
    feedback = parse_json(state.get("feedback", "{}"), {})
    score = feedback.get("score", state.get("final_score", "-"))
    confidence = feedback.get("confidence", "-")
    sources_count = len(state.get("source_cards", []))

    st.markdown(
        f"""
<div class="metric-row">
  <div class="metric"><span>Score</span><strong>{score}/10</strong></div>
  <div class="metric"><span>Confidence</span><strong>{escape(str(confidence))}</strong></div>
  <div class="metric"><span>Sources</span><strong>{sources_count}</strong></div>
</div>
""",
        unsafe_allow_html=True,
    )

    st.caption("Pipeline")
    st.markdown(
        """
1. Search
2. Scrape
3. Evidence
4. Write
5. Verify
"""
    )

    if st.session_state.last_error:
        st.error(st.session_state.last_error)
    st.markdown("</div>", unsafe_allow_html=True)


def render_chat_feed() -> None:
    messages = st.session_state.memory.messages
    if not messages:
        return

    for message in messages:
        role = message.get("role", "user")
        content = message.get("content", "")
        avatar = "assistant" if role == "assistant" else "user"
        with st.chat_message(role, avatar=avatar):
            st.markdown(content)


def render_report_tab(state: dict) -> None:
    report = state.get("report", "No report generated.")
    st.markdown(report)
    st.download_button(
        label="Download Report (.md)",
        data=report,
        file_name=f"research_report_{int(time.time())}.md",
        mime="text/markdown",
        use_container_width=True,
        key=f"download_report_{state.get('thread_id', 'new')}_{state.get('final_score', 0)}",
    )


def render_sources_tab(state: dict) -> None:
    source_cards = state.get("source_cards", [])
    if not source_cards:
        st.warning("No sources were returned.")
        return

    for card in source_cards:
        source_id = card.get("source_id")
        st.markdown(
            f"""
<div class="source-box">
  <strong>[{source_id}] {escape(card.get('title', 'Untitled'))}</strong><br>
  <a href="{escape(card.get('url', ''))}" target="_blank">{escape(card.get('url', ''))}</a><br>
  <span class="trust-pill">Trust: {escape(str(card.get('trust_label', 'unknown')))} ({card.get('trust_score', 0)})</span><br>
  <span>{escape(card.get('summary', ''))}</span>
</div>
""",
            unsafe_allow_html=True,
        )

        with st.expander(f"Snippets and claims from source [{source_id}]"):
            for snippet in card.get("exact_snippets", []):
                st.markdown(f'<div class="snippet">{escape(snippet)}</div>', unsafe_allow_html=True)

            reasons = card.get("trust_reasons", [])
            if reasons:
                st.caption("Trust reasons: " + ", ".join(reasons))

            used_claims = card.get("used_for_claims", [])
            if used_claims:
                st.json(used_claims)
            else:
                st.caption("No verified report claims used this source yet.")


def render_evidence_tab(state: dict, feedback: dict) -> None:
    support_audit = feedback.get("claim_support_audit", {})
    if support_audit:
        st.write(
            f"Supported cited claims: {support_audit.get('supported_claim_count', 0)} "
            f"of {support_audit.get('checked_claim_count', 0)} "
            f"({support_audit.get('support_rate', 0)})"
        )
        st.caption(support_audit.get("method_limit", ""))
        weak_claims = support_audit.get("weak_claims", [])
        if weak_claims:
            st.warning("Weak or unclear claims found:")
            st.json(weak_claims)

    with st.expander("Structured evidence"):
        st.json(state.get("extracted_data", []))

    with st.expander("Critic details"):
        st.json(feedback)


def render_agents_tab(state: dict) -> None:
    for item in state.get("agent_outputs", []):
        output = item.get("output", "")
        if not isinstance(output, str):
            output = json.dumps(output, indent=2)

        with st.expander(f"{item.get('agent')} - {item.get('status')}"):
            st.markdown(
                f"""
<div class="agent-card">
  <strong>{escape(item.get('summary', ''))}</strong><br>
  <span>{escape(item.get('timestamp', ''))}</span>
</div>
""",
                unsafe_allow_html=True,
            )
            language = "json" if output.strip().startswith(("{", "[")) else None
            st.code(output[:8000], language=language)


def render_research_details() -> None:
    state = st.session_state.state
    if not state:
        return

    feedback = parse_json(state.get("feedback", "{}"), {})
    tab_answer, tab_sources, tab_evidence, tab_agents = st.tabs(
        ["Answer", "Sources", "Verification", "Agents"]
    )

    with tab_answer:
        render_report_tab(state)
    with tab_sources:
        render_sources_tab(state)
    with tab_evidence:
        render_evidence_tab(state, feedback)
    with tab_agents:
        render_agents_tab(state)


def render_main_area() -> None:
    render_title()
    render_chat_feed()

    prompt = st.chat_input(
        "Ask a research question...",
        disabled=st.session_state.running,
    )
    if prompt and prompt.strip():
        run_research(prompt.strip())
        st.rerun()

    render_research_details()


def main() -> None:
    configure_page()
    inject_styles()
    init_state()

    if st.session_state.show_history:
        history, controls, main_col = st.columns([0.78, 0.9, 2.4], gap="large")
        with history:
            render_history_panel()
        with controls:
            render_control_panel()
        with main_col:
            render_main_area()
    else:
        controls, main_col = st.columns([0.9, 2.6], gap="large")
        with controls:
            render_control_panel()
        with main_col:
            render_main_area()


if __name__ == "__main__":
    main()
