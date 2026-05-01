import json
import time
from html import escape
from typing import Any

import streamlit as st

import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

try:
    from chat_service import ResearchChatService
    from database.database import ResearchDatabase
    from memory import SessionMemory, repair_messages
except ImportError as exc:
    st.error(f"Could not import pipeline modules: {exc}")
    st.stop()


PAGE_TITLE = "Multi-Agent Research System"
LOCAL_USER_EMAIL = "local-user@research-app.local"


def configure_page() -> None:
    st.set_page_config(
        page_title=PAGE_TITLE,
        page_icon="🔬",
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
        radial-gradient(circle at 20% 10%, rgba(34, 211, 238, .14), transparent 28rem),
        linear-gradient(135deg, #0b1020 0%, #111827 54%, #0f172a 100%);
}
.hero {
    padding: 1.5rem 0 1rem;
}
.hero h1 {
    font-size: clamp(2.1rem, 5vw, 4.3rem);
    line-height: 1;
    margin: 0;
}
.hero p {
    max-width: 58rem;
    color: #a5b4fc;
    font-size: 1rem;
}
.agent-card {
    border: 1px solid rgba(148, 163, 184, .24);
    background: rgba(15, 23, 42, .72);
    border-radius: 8px;
    padding: 1rem;
    margin-bottom: .8rem;
}
.agent-card strong {
    color: #67e8f9;
}
.score-good {
    color: #86efac;
    font-weight: 800;
}
.score-warn {
    color: #facc15;
    font-weight: 800;
}
.source-box {
    border-left: 3px solid #38bdf8;
    padding-left: .75rem;
    margin-bottom: .9rem;
}
.trust-pill {
    display: inline-block;
    border: 1px solid rgba(148, 163, 184, .35);
    border-radius: 999px;
    padding: .12rem .55rem;
    margin: .25rem 0 .45rem;
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
</style>
""",
        unsafe_allow_html=True,
    )


def init_state() -> None:
    defaults = {
        "state": None,
        "running": False,
        "last_error": "",
        "last_topic": "",
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
        st.session_state.current_user_id = get_database().create_user(LOCAL_USER_EMAIL)


@st.cache_resource
def get_database() -> ResearchDatabase:
    import os
    db_path = os.path.join(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')), 'database', 'research_memory.db')
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


def render_header() -> None:
    st.markdown(
        """
<div class="hero">
  <p style="color: red; font-weight: bold; font-family: monospace; letter-spacing: 0.18em; text-transform: uppercase;">Jai Shree Ram</p>
  <h1>Research Intelligence System</h1>
  <p>Search, scrape, structure, write, and evaluate with transparent agent outputs and source-grounded quality scoring.</p>
</div>
""",
        unsafe_allow_html=True,
    )


def run_pipeline(topic: str) -> None:
    st.session_state.running = True
    st.session_state.last_error = ""
    st.session_state.last_topic = topic

    try:
        with st.spinner("Agents are working through search, scrape, evidence, writing, and quality checks..."):
            service = get_chat_service()
            result = service.ask(
                topic,
                thread_id=st.session_state.current_thread_id,
                user_id=st.session_state.current_user_id,
            )
            if result.get("error"):
                st.session_state.last_error = result["error"]
            else:
                st.session_state.state = result
                st.session_state.current_thread_id = result.get("thread_id")
    except Exception as exc:
        st.session_state.last_error = str(exc)
    finally:
        st.session_state.running = False


def start_new_thread() -> None:
    st.session_state.current_thread_id = None
    st.session_state.state = None
    st.session_state.last_topic = ""
    st.session_state.last_error = ""
    st.session_state.memory = SessionMemory(max_recent_messages=4)


def load_thread(thread_id: int) -> None:
    db = get_database()
    if not db.thread_belongs_to_user(thread_id, st.session_state.current_user_id):
        st.session_state.last_error = "This thread does not belong to the current user."
        return

    messages = db.load_messages(thread_id)
    st.session_state.current_thread_id = thread_id
    st.session_state.memory = SessionMemory(max_recent_messages=4)
    st.session_state.memory.load_messages(repair_messages(messages))
    st.session_state.state = None
    st.session_state.last_topic = ""
    st.session_state.last_error = ""


def render_history_panel() -> None:
    header_cols = st.columns([1, 1])
    with header_cols[0]:
        st.subheader("History")
    with header_cols[1]:
        if st.button("Hide", use_container_width=True, key="hide_history_btn"):
            st.session_state.show_history = False

    if st.button("New Chat", use_container_width=True, key="new_chat_btn"):
        start_new_thread()

    threads = get_database().list_threads(st.session_state.current_user_id)
    if not threads:
        st.caption("No saved conversations yet.")
        return

    for thread in threads[:30]:
        thread_id = int(thread["id"])
        is_active = thread_id == st.session_state.current_thread_id
        label = f"{'● ' if is_active else ''}{thread.get('title') or 'Untitled'}"
        if st.button(label[:80], key=f"thread_{thread_id}", use_container_width=True):
            load_thread(thread_id)


def render_sidebar() -> None:
    if not st.session_state.show_history:
        if st.button("Show History", use_container_width=True, key="show_history_btn"):
            st.session_state.show_history = True

    st.subheader("Research Topic")
    if st.session_state.current_thread_id:
        st.caption(f"Continuing thread #{st.session_state.current_thread_id}")
    else:
        st.caption("New conversation")

    with st.form("research_form", clear_on_submit=False):
        topic = st.text_input(
            "Research topic",
            value=st.session_state.last_topic,
            placeholder="e.g. Latest advances in quantum computing",
            label_visibility="collapsed",
        )
        submitted = st.form_submit_button(
            "Run Research Pipeline",
            disabled=st.session_state.running,
            use_container_width=True,
        )

    if submitted:
        cleaned_topic = topic.strip()
        if cleaned_topic:
            run_pipeline(cleaned_topic)
        else:
            st.warning("Please enter a research topic first.")

    st.subheader("Pipeline")
    st.markdown(
        """
1. Search Agent: finds candidate sources
2. Scraper Agent: extracts page text
3. Reader Agent: structures source evidence
4. Writer Agent: creates the cited report
5. Critic Agent: scores quality transparently
"""
    )

    if st.session_state.last_error:
        st.error(st.session_state.last_error)


def render_score(feedback: dict, state: dict) -> None:
    score = int(feedback.get("score", state.get("final_score", 0)) or 0)
    score_class = "score-good" if score >= 8 else "score-warn"

    st.markdown(
        f'<p class="{score_class}">Quality Score: {score}/10</p>',
        unsafe_allow_html=True,
    )
    st.caption(feedback.get("final_verdict", "No critic verdict recorded."))
    st.info(
        feedback.get(
            "score_meaning",
            "The score is a quality signal, not a guarantee of factual truth.",
        )
    )
    st.caption(f"Confidence: {feedback.get('confidence', 'unknown')}")


def render_report_tab(state: dict) -> None:
    report = state.get("report", "No report generated.")
    st.markdown(report)
    st.download_button(
        label="Download Report (.md)",
        data=report,
        file_name=f"research_report_{int(time.time())}.md",
        mime="text/markdown",
        use_container_width=True,
        key=f"download_report_{state.get('topic', 'untitled')}_{state.get('final_score', 0)}",
    )


def render_agents_tab(state: dict) -> None:
    for index, item in enumerate(state.get("agent_outputs", []), 1):
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

        with st.expander(f"Exact snippets from source [{source_id}]"):
            for snippet in card.get("exact_snippets", []):
                st.markdown(f'<div class="snippet">{escape(snippet)}</div>', unsafe_allow_html=True)

            reasons = card.get("trust_reasons", [])
            if reasons:
                st.caption("Trust reasons: " + ", ".join(reasons))

            used_claims = card.get("used_for_claims", [])
            if used_claims:
                st.markdown("Claims that used this source:")
                st.json(used_claims)
            else:
                st.caption("No verified report claims used this source yet.")


def render_evidence_tab(state: dict, feedback: dict) -> None:
    st.json(state.get("extracted_data", []))

    support_audit = feedback.get("claim_support_audit", {})
    if support_audit:
        st.subheader("Claim Support Audit")
        st.write(
            f"Supported cited claims: {support_audit.get('supported_claim_count', 0)} "
            f"of {support_audit.get('checked_claim_count', 0)} "
            f"({support_audit.get('support_rate', 0)})"
        )
        st.caption(support_audit.get("method_limit", ""))

        weak_claims = support_audit.get("weak_claims", [])
        if weak_claims:
            st.warning("Weakly supported cited claims found:")
            st.json(weak_claims)

    with st.expander("Critic Details"):
        st.json(feedback)


def render_results() -> None:
    st.subheader("Results")
    state = st.session_state.state

    if not state:
        st.info("Enter a topic and run the pipeline to generate a report.")
        return

    feedback = parse_json(state.get("feedback", "{}"), {})
    render_score(feedback, state)

    tab_report, tab_agents, tab_sources, tab_evidence = st.tabs(
        ["Final Report", "Agent Outputs", "Sources", "Evidence"]
    )

    with tab_report:
        render_report_tab(state)
    with tab_agents:
        render_agents_tab(state)
    with tab_sources:
        render_sources_tab(state)
    with tab_evidence:
        render_evidence_tab(state, feedback)


def main() -> None:
    configure_page()
    inject_styles()
    init_state()
    render_header()

    if st.session_state.show_history:
        history, main_left, main_right = st.columns([0.75, 0.95, 1.65], gap="large")
        with history:
            render_history_panel()
        with main_left:
            render_sidebar()
        with main_right:
            render_results()
    else:
        left, right = st.columns([0.95, 1.65], gap="large")
        with left:
            render_sidebar()
        with right:
            render_results()


if __name__ == "__main__":
    main()
