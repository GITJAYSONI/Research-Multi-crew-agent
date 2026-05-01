import re

STOPWORDS = {
    "about",
    "after",
    "again",
    "also",
    "because",
    "been",
    "being",
    "between",
    "could",
    "from",
    "have",
    "into",
    "more",
    "most",
    "only",
    "other",
    "over",
    "such",
    "than",
    "that",
    "their",
    "there",
    "these",
    "this",
    "through",
    "were",
    "when",
    "where",
    "which",
    "while",
    "with",
    "would",
}


def split_sentences(text: str) -> list[str]:
    cleaned = re.sub(r"\s+", " ", text or "").strip()
    return [sentence.strip() for sentence in re.split(r"(?<=[.!?])\s+", cleaned) if sentence.strip()]


def tokens(text: str) -> set[str]:
    words = re.findall(r"\b[a-zA-Z][a-zA-Z0-9-]{3,}\b", text.lower())
    return {word for word in words if word not in STOPWORDS}
