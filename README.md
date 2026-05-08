# Research Intelligence System - Project Explanation

## Overview
The Research Intelligence System (Multi-crew-agent) is a complex, multi-agent conversational application designed to automate deep research. It orchestrates a pipeline of specialized AI agents to search the web, scrape information, synthesize reports, and rigorously verify claims to prevent hallucinations. The application provides a user-friendly frontend to interact with the agents, view source evidence, and inspect the verification processes.

## Functionalities
- **Agentic Research Pipeline**: Automates the entire research workflow from a user query to a fully cited, professionally structured Markdown report.
- **Contextual Search Modes**: Supports specialized search modes (discover, finance, health, academic, patents) to fine-tune the information retrieval process.
- **Web Scraping & Summarization**: Scrapes live URLs concurrently and distills the content into concise, relevant facts while stripping away noise and ads.
- **Strict Evidence Grounding**: Forces the writing model to use zero external knowledge; every claim must be backed by an inline citation linked to a scraped source.
- **Automated Quality Assurance**: Employs a Critic Agent to grade the report. If the report falls below a quality threshold (score < 7), the system automatically fetches new sources and refines the report.
- **Transparent Verification**: Exposes the "claim support audit" to the user, showing exactly how many claims are supported and highlighting weak or unsupported claims.
- **Conversational Interface**: A Streamlit frontend providing a chat feed, session memory, history tracking, and detailed tabs for Answer, Sources, Verification, and Agent logs.
- **Persistent Memory**: Uses a local SQLite database to persist threads and user session histories across interactions.

## Technologies Used
- **Frontend / UI**: html, css, javascript / streamlit
- **LLM Orchestration**: LangChain, LangGraph (for stateful multi-actor pipeline execution), crew ai  
- **AI Models**: Mistral AI (`mistral-small-latest` via `langchain-mistralai`)
- **Web Search**: Tavily API (via `tavily-python`)
- **Web Scraping**: `aiohttp` for async requests, `beautifulsoup4`, and `playwright`
- **Database**: SQLite (via a custom `ResearchDatabase` implementation)
- **Environment Management**: `python-dotenv` for loading API keys and configs.

## Agents: Roles, Responsibilities, and Communication

The system's core relies on LangGraph to pass a shared `AgentState` between specialized nodes (agents). They communicate sequentially by reading and updating this state dictionary.

### 1. Search Agent
- **Role**: Information Retriever.
- **Responsibilities**: Takes the user's query and the active search "mode" (which appends domain-specific hints) to query the web. It normalizes the search results, filters out duplicate domains, and updates the state with a list of candidate source URLs and snippets.

### 2. Scraper Agent (Summarizer)
- **Role**: Data Extractor and Cleaner.
- **Responsibilities**: Receives the URLs from the Search Agent and asynchronously scrapes their content. It then acts as a "fast data cleaner," summarizing the noisy HTML text into concise bullet points of factual data, key insights, and statistics. It packages this into structured "source cards" and "extracted data" for the writer.

### 3. Writer Agent
- **Role**: Expert Research Writer.
- **Responsibilities**: Reads the structured evidence and sources provided by the Scraper Agent to generate a comprehensive report.
- **Rules**: Must use *zero external knowledge*. It is strictly instructed to write "Data unavailable" if evidence is lacking, and to cite every key claim with a valid inline citation (e.g., [1]). It ensures the output adheres to a strict Markdown template (Executive Summary, Key Findings, Deep Analysis, etc.).

### 4. Critic Agent (Verifier / Refiner)
- **Role**: Quality Assurance and Refiner.
- **Responsibilities**: Evaluates the drafted report against the source evidence. It conducts a "claim support audit" to check if the claims in the report are actually backed by the extracted data. It generates a score out of 10.
- **Communication & Looping**: If the score is below the strict threshold of 7, the Critic Agent directs the pipeline to perform a retry loop—searching for specific missing evidence and having the Writer rewrite the report until quality is met or the retry limit is reached. 

### 5. Memory Summary Agent
- **Role**: Context Manager.
- **Responsibilities**: Operates outside the main research graph, primarily maintaining a compact conversation memory (under 180 words). It condenses older chat messages into a durable summary of user intent, preferences, and facts to keep LLM context windows optimized.
