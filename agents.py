import os

from dotenv import load_dotenv
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_mistralai import ChatMistralAI

load_dotenv()

llm = ChatMistralAI(
    model="mistral-small-latest",
    temperature=0,
    api_key=os.getenv("MISTRAL_AI_API_KEY") or os.getenv("MISTRAL_API_KEY"),
    max_retries=3,
)

# ========== WRITER AGENT ==========
writer_prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """You are an expert research writer. Generate a professional, highly structured research report.

RULES:
- Synthesize the provided scraped data and search summaries into a clear, useful report.
- Use only the provided data. Do not hallucinate or add unsupported facts.
- Cite sources inline using [1], [2], etc. based on the provided Sources list.
- If evidence is thin, say so clearly and limit conclusions.
- Every key claim must have a citation.
- Before finalizing, check clarity, structure, repetition, source support, and usefulness.

OUTPUT STRUCTURE:
Use this exact Markdown structure:

# Title

## Executive Summary
Short, direct overview of the answer.

## Key Findings
- 4-7 evidence-backed bullets, each with citations.

## Deep Analysis
Explain patterns, tradeoffs, causes, implications, and limits. Avoid generic filler.

## Evidence Quality And Limits
State what the sources do and do not prove.

## Conclusion
Practical, concise closing.

## Sources
Numbered source list matching the citations.

DO NOT:
- Write generic or vague content
- Repeat the same ideas
- Add filler text
- Invent facts not found in the provided material""",
        ),
        (
            "human",
            """Write a comprehensive research report on: {topic}

Extracted Research Data:
{research_data}

Sources:
{sources}

Generate a well-structured, source-grounded report following the exact structure.""",
        ),
    ]
)

writer_chain = writer_prompt | llm | StrOutputParser()

# ========== SUMMARIZER AGENT ==========
summarizer_prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """You are a fast data cleaner. Summarize the following article text into concise bullet points.
Extract ONLY factual data, key insights, and statistics. Remove noise, ads, and irrelevant filler.
Keep it extremely concise. Do not add outside information.""",
        ),
        ("human", "Article Content:\n{content}"),
    ]
)

summarizer_chain = summarizer_prompt | llm | StrOutputParser()

# ========== REFINER AGENT ==========
refiner_prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """You are an expert report refiner. Improve the report based on critic feedback.
RULES:
- Fix all identified issues in the feedback.
- Maintain the exact markdown structure required.
- Do NOT hallucinate facts.
- Keep all valid citations [1], [2].""",
        ),
        (
            "human",
            """Original Report:
{report}

Critic Feedback & Improvements:
{feedback}

Rewrite the report addressing all feedback while maintaining accuracy and citations.""",
        ),
    ]
)

refiner_chain = refiner_prompt | llm | StrOutputParser()

# ========== MEMORY SUMMARY AGENT ==========
memory_summary_prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """You maintain compact conversation memory for a research assistant.
Update the existing summary using the older messages.
Keep durable user intent, preferences, decisions, and important facts.
Do not include filler. Keep the summary under 180 words.""",
        ),
        (
            "human",
            """Existing summary:
{summary}

Older messages:
{messages}

Updated compact summary:""",
        ),
    ]
)

memory_summary_chain = memory_summary_prompt | llm | StrOutputParser()
