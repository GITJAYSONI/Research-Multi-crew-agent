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
- Zero external knowledge: use ONLY the provided scraped data, exact snippets, and search summaries.
- If a fact is not explicitly present in the provided research data, write exactly: "Data unavailable."
- NEVER invent claims, numbers, statistics, dates, company names, prices, URLs, or references.
- NEVER fabricate source links. Use only the provided numbered source list.
- If verified evidence is weak, missing, or unclear, write exactly: "Data unavailable."
- Every paragraph must be grounded in the source input.
- Every key claim must have a valid inline citation like [1] that maps to the numbered source list.
- If source text conflicts, explicitly mention uncertainty instead of choosing a side.
- Use a professional, neutral tone. Prefer concise verified facts over broad speculation.
- Do not include YouTube links, placeholder text, raw JSON, debug logs, or unrelated sections.

OUTPUT STRUCTURE:
Use this exact Markdown structure:

# Title

## Executive Summary
Short, direct overview of the answer.

## Key Findings
- 4-7 evidence-backed bullets, each with citations.

## Deep Analysis
Explain patterns, tradeoffs, causes, implications, and limits. Avoid generic filler.

## Evidence & Sources
List the cited sources with URL validation notes. Mark each as "Source Unverified" because live HTTP status is not checked here.

## Limitations / Data Gaps
State what the sources do and do not prove.

## Conclusion
Practical, concise closing.

DO NOT:
- Write generic or vague content
- Repeat the same ideas
- Add filler text
- Invent facts not found in the provided material
- Add decorative markdown, strange symbols, fake citations, or unsupported statistics
IMPORTANT: Output raw Markdown directly. Do NOT wrap your response in triple backticks
or a code block of any kind. Do not write ```markdown or ``` anywhere in your output.""",
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
- Zero external knowledge: use ONLY the original report and critic feedback.
- Do NOT hallucinate facts.
- Keep all valid citations [1], [2].
- Remove unsupported claims instead of rewriting them creatively.
- If the critic says evidence is missing, replace that claim with "Data unavailable."
- Do not introduce new URLs, statistics, or references.
IMPORTANT: Output raw Markdown directly. Do NOT wrap your response in triple backticks
or a code block of any kind. Do not write ```markdown or ``` anywhere in your output.""",
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
