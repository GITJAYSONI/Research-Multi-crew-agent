# Multi-Agent Research System Architecture

## Overview

High-performance research system with 4 specialized agents working in sequence to produce accurate, structured research output with minimal latency.

**Pipeline Flow:**

```
Search Agent → Reader Agent → Writer Agent → Critic Agent → [Optional] Refiner Agent
```

---

## Agent Specifications

### 1️⃣ Search Agent

**Role:** Discover and prioritize sources

**Input:** Research topic

**Output Format:**

```json
[
  {
    "title": "Source Title",
    "url": "https://example.com",
    "source": "Source Name",
    "summary": "2-3 line summary"
  }
]
```

**Constraints:**

- Retrieve only top 5–8 highly relevant and recent sources
- Prioritize trusted and authoritative sources
- Avoid duplicates, outdated, or low-quality results
- Stop once sufficient data is collected

**Tools:** Tavily Search API (advanced + YouTube)

---

### 2️⃣ Reader Agent

**Role:** Extract structured insights from sources

**Input:** Raw scraped content from sources

**Output Format:**

```json
{
  "key_points": ["point1", "point2", "point3"],
  "data_points": ["statistic1", "statistic2"],
  "insights": ["insight1", "insight2"]
}
```

**Constraints:**

- Extract ONLY factual information present in content
- Remove fluff, ads, and repetition
- Max 300–500 words per source
- Return valid JSON only

**Processing:**

- Runs on each source independently
- Extracted data compiled for Writer Agent
- Maintains source attribution

---

### 3️⃣ Writer Agent

**Role:** Synthesize insights into professional report

**Input:**

- Topic
- Compiled extracted data from Reader Agent
- Source list with URLs

**Output:** Structured research report (700–1200 words)

**Report Structure:**

1. **Title**
2. **Introduction** - Context and relevance
3. **Key Findings** - Main discoveries with citations [1], [2], etc.
4. **Detailed Analysis** - Deep exploration of findings
5. **Conclusion** - Summary and implications
6. **Sources** - Numbered list of URLs

**Constraints:**

- Cite all claims with inline [1], [2], etc.
- Use ONLY provided data (no external knowledge)
- Present conflicting data from multiple perspectives
- Mark missing data explicitly
- Maintain professional tone
- 700–1200 word count

---

### 4️⃣ Critic Agent

**Role:** Evaluate report quality and accuracy

**Evaluation Criteria (0–10):**

- **Accuracy** (0–10): Claims supported by citations? Hallucinations detected?
- **Clarity** (0–10): Well-structured? Easy to understand?
- **Depth** (0–10): Thorough coverage of topic?
- **Relevance** (0–10): All points address the topic?
- **Structure** (0–10): Professional formatting? Proper citations?

**Output Format:**

```json
{
  "score": 0,
  "accuracy": { "status": "pass/fail", "details": "..." },
  "clarity": { "status": "pass/fail", "details": "..." },
  "depth": { "status": "pass/fail", "details": "..." },
  "relevance": { "status": "pass/fail", "details": "..." },
  "structure": { "status": "pass/fail", "details": "..." },
  "issues": ["issue1", "issue2"],
  "improvements": ["fix1", "fix2"],
  "final_verdict": "Assessment"
}
```

**Rules:**

- Score < 8: Provide EXACT actionable improvements
- Score < 5 with hallucinations: Automatically fail
- No generic feedback
- Strict, analytical evaluation

---

### 5️⃣ Refiner Agent (Optional)

**Role:** Improve report based on critic feedback

**Trigger:** Score 5–7 (below 8 but salvageable)

**Input:**

- Original report
- Critic feedback and improvement suggestions

**Output:** Improved report maintaining structure and citations

**Constraints:**

- Fix all identified issues
- Maintain proper citations
- Preserve original structure
- No hallucinations
- 700–1200 word count

---

## Global Rules

### Minimize Latency

- ✅ Each agent completes only its role
- ✅ No redundant processing
- ✅ Parallel scraping (async)
- ✅ Concise outputs

### Improve Accuracy

- ✅ No hallucinations
- ✅ Prefer facts over assumptions
- ✅ Cross-check via citations
- ✅ Explicit handling of missing data

### Avoid Redundancy

- ✅ No repeated content between agents
- ✅ Single processing of each source
- ✅ Clear role separation

### Efficiency

- ✅ Async scraping of URLs
- ✅ JSON outputs for machine readability
- ✅ Early stopping when sufficient data collected

---

## Execution Flow Detailed

```
START
  ↓
[1] SEARCH AGENT
  ├─ Topic received
  ├─ Query generated
  ├─ 5-8 sources retrieved
  └─ JSON output
  ↓
[2] SCRAPER (Async)
  ├─ URLs extracted
  ├─ Content fetched in parallel
  └─ Raw content stored
  ↓
[3] READER AGENT (Parallel per source)
  ├─ For each source:
  │  ├─ Extract key_points
  │  ├─ Extract data_points
  │  ├─ Extract insights
  │  └─ JSON output per source
  └─ Compile all extractions
  ↓
[4] WRITER AGENT
  ├─ Receive compiled data
  ├─ Structure: Intro → Findings → Analysis → Conclusion
  ├─ Add citations [1], [2], etc.
  └─ Report generated (700-1200 words)
  ↓
[5] CRITIC AGENT
  ├─ Evaluate 5 dimensions
  ├─ Generate score (0-10)
  ├─ List specific issues
  └─ Provide improvements
  ↓
DECISION
  ├─ IF score >= 8:
  │  └─ ✅ Pipeline Complete
  ├─ ELIF score >= 5:
  │  ├─ [6] REFINER AGENT
  │  │  ├─ Apply improvements
  │  │  ├─ Regenerate report
  │  │  └─ Re-evaluate (optional)
  │  └─ ✅ Pipeline Complete
  └─ ELSE:
     └─ ❌ Needs Manual Review
  ↓
END
```

---

## File Structure

```
.
├── agents.py           # Agent definitions & chains
├── pipeline.py         # Main execution orchestrator
├── tools.py            # Search & scraping tools
├── app.py             # Streamlit UI
├── requirements.txt   # Dependencies
└── ARCHITECTURE.md    # This file
```

### Key Dependencies

- **LangChain**: Agent orchestration
- **Mistral AI**: Language model (mistral-small-latest)
- **Tavily**: Web search API
- **BeautifulSoup4**: Web scraping
- **aiohttp**: Async HTTP requests
- **Streamlit**: UI framework

---

## Usage

### Basic Run

```python
from pipeline import run_research_pipeline

result = run_research_pipeline("Your research topic")

# Results include:
# - result["search_results"]: Source list (JSON)
# - result["extracted_data"]: Reader Agent output
# - result["report"]: Final research report
# - result["feedback"]: Critic evaluation
```

### Streamlit UI

```bash
streamlit run app.py
```

---

## Performance Optimization

| Aspect         | Strategy                                                           |
| -------------- | ------------------------------------------------------------------ |
| **Latency**    | Async scraping, minimal LLM calls, concise outputs                 |
| **Accuracy**   | Strict citation requirements, hallucination detection              |
| **Quality**    | Multi-step validation, critic score threshold, optional refinement |
| **Efficiency** | Role-based agents, early stopping, parallel processing             |

---

## Scoring Thresholds

| Score Range | Action                          |
| ----------- | ------------------------------- |
| **8–10**    | ✅ Accept & complete            |
| **5–7**     | 🔄 Refine & improve             |
| **< 5**     | ❌ Requires manual intervention |

---

## Future Enhancements

- [ ] Multi-language support
- [ ] Real-time fact-checking integration
- [ ] Custom source whitelisting
- [ ] Interactive report editing
- [ ] Export to PDF/Word formats
- [ ] Caching layer for common topics
- [ ] A/B testing different critic criteria

---

**Last Updated:** April 30, 2026
**Version:** 1.0
