from collections.abc import Callable


Message = dict[str, str]


class SessionMemory:
    """
    Temporary chat memory for one active session.

    It keeps all messages locally, but only sends a short summary plus the last
    few messages to the LLM. That keeps context useful without wasting tokens.
    """

    def __init__(self, max_recent_messages: int = 4):
        self.messages: list[Message] = []
        self.summary = ""
        self.max_recent_messages = max_recent_messages

    def add_message(self, role: str, content: str) -> None:
        if role not in {"user", "assistant", "system"}:
            role = "user"
        self.messages.append({"role": role, "content": content or ""})

    def load_messages(self, messages: list[Message]) -> None:
        self.messages = [
            {"role": item.get("role", "user"), "content": item.get("content", "")}
            for item in messages
            if isinstance(item, dict)
        ]

    def trim_history(self, keep_last: int | None = None) -> list[Message]:
        limit = keep_last or self.max_recent_messages
        return self.messages[-limit:]

    def build_context(self, user_input: str) -> str:
        recent = self.trim_history()
        recent_text = "\n".join(
            f"{message['role'].title()}: {message['content']}" for message in recent
        )

        return "\n".join(
            [
                "Previous conversation summary:",
                self.summary or "No previous context.",
                "",
                "Recent messages:",
                recent_text or "No recent messages.",
                "",
                "Current user request:",
                user_input,
            ]
        )

    def update_summary(self, summarize_fn: Callable[[str, str], str]) -> str:
        """
        Summarize older messages only when the chat grows.

        summarize_fn should call a lightweight model. This is the only LLM use
        in the memory layer, and it runs infrequently to reduce API cost.
        """
        if len(self.messages) <= self.max_recent_messages:
            return self.summary

        older_messages = self.messages[: -self.max_recent_messages]
        older_text = "\n".join(
            f"{message['role'].title()}: {message['content']}" for message in older_messages
        )
        self.summary = summarize_fn(self.summary, older_text).strip()
        self.messages = self.messages[-self.max_recent_messages :]
        return self.summary


def repair_messages(value: object) -> list[Message]:
    """Recover safely if a UI/session object is missing or corrupted."""
    if not isinstance(value, list):
        return []

    repaired = []
    for item in value:
        if not isinstance(item, dict):
            continue
        role = item.get("role", "user")
        content = item.get("content", "")
        if role in {"user", "assistant", "system"} and isinstance(content, str):
            repaired.append({"role": role, "content": content})
    return repaired
