"""
Example: conversational use of the existing research pipeline.

Run:
    python memory_integration_example.py

This keeps the normal pipeline intact while adding:
- session memory for the active chat
- cache reuse for repeated work
- SQLite persistence for long-term history
"""

from chat_service import ResearchChatService
from database.database import ResearchDatabase
from memory import SessionMemory


def main():
    db = ResearchDatabase("research_memory.db")
    memory = SessionMemory(max_recent_messages=4)
    chat = ResearchChatService(db=db, memory=memory)
    user_id = db.create_user("local-demo@research-app.local")

    thread_id = chat.start_thread(user_id=user_id, title="AI research demo")
    if not thread_id:
        print("Could not start thread.")
        return

    first = chat.ask(
        "Research latest trends in AI search engines.",
        thread_id=thread_id,
        user_id=user_id,
    )
    print(first.get("report", "")[:1000])

    follow_up = chat.ask(
        "Now compare the risks and benefits.",
        thread_id=thread_id,
        user_id=user_id,
    )
    print(follow_up.get("report", "")[:1000])

    print("\nThread saved:", thread_id)
    print("Memory summary:", follow_up.get("memory_summary", ""))


if __name__ == "__main__":
    main()
