# Quick Start Guide - Multi-Agent Research System

## Prerequisites

1. **Python 3.10+**
2. **API Keys:**
   - `MISTRAL_API_KEY` - Mistral AI API key
   - `TAVILY_API_KEY` - Tavily Search API key

3. **Environment Setup:**

   ```bash
   # Create virtual environment
   python -m venv .venv

   # Activate (Windows)
   .\.venv\Scripts\Activate

   # Or (Mac/Linux)
   source .venv/bin/activate
   ```

## Installation

```bash
# Install dependencies
pip install -r requirements.txt

# Create .env file with your API keys
echo MISTRAL_API_KEY=your_key_here > .env
echo TAVILY_API_KEY=your_key_here >> .env
```

---

## Running the Pipeline

### Option 1: Python Script

```python
from pipeline import run_research_pipeline

# Run research on a topic
result = run_research_pipeline("Impact of AI on Job Market in 2024")

# Access results
print(result["report"])           # Final report
print(result["feedback"])         # Critic evaluation
print(result["extracted_data"])   # Reader Agent output
```

### Option 2: Streamlit UI

```bash
streamlit run app.py
```

Then open browser to: `http://localhost:8501`

---

## Pipeline Output Structure

```python
{
  "search_results": "JSON string of sources",
  "sources_list": [
    {
      "title": "...",
      "url": "...",
      "source": "...",
      "summary": "..."
    }
  ],
  "scraped_content": "Raw text from all sources",
  "extracted_data": [
    {
      "source": "Source Name",
      "url": "https://...",
      "data": {
        "key_points": [...],
        "data_points": [...],
        "insights": [...]
      }
    }
  ],
  "report": "Final 700-1200 word report with citations",
  "feedback": "Critic evaluation JSON"
}
```

---

## Agent Execution Details

### 1. Search Agent (Tavily API)

- Searches web + YouTube
- Returns 5-8 sources max
- Score-based relevance ranking

**Example Output:**

```json
[
  {
    "title": "AI Job Impact Report 2024",
    "url": "https://example.com/report",
    "source": "Example Research",
    "summary": "Study shows 30% job displacement in manufacturing..."
  }
]
```

### 2. Reader Agent (Per Source)

- Extracts key information
- Structures as key_points, data_points, insights
- ~500 words per source max

**Example Output:**

```json
{
  "key_points": [
    "AI adoption accelerating in enterprise",
    "Skill gap widening for non-technical roles"
  ],
  "data_points": [
    "37% of companies planning AI investment",
    "2.1M new AI-related jobs created in 2024"
  ],
  "insights": [
    "Reskilling initiatives critical",
    "Remote work patterns shifting"
  ]
}
```

### 3. Writer Agent

- Combines all extracted data
- Generates structured report
- Adds citations: [1], [2], etc.
- 700-1200 words

**Report Structure:**

```
# Impact of AI on Job Market in 2024

## Introduction
Context about global job market and AI...

## Key Findings
- Finding 1 [1]
- Finding 2 [2]
- Finding 3 [3]

## Detailed Analysis
Deep dive into market segments...

## Conclusion
Summary and implications...

## Sources
[1] https://example.com/report
[2] https://example2.com/study
```

### 4. Critic Agent

- Evaluates accuracy (0-10)
- Checks clarity, depth, relevance
- Identifies issues & improvements

**Example Output:**

```json
{
  "score": 7,
  "accuracy": {
    "status": "pass",
    "details": "All claims properly cited"
  },
  "clarity": {
    "status": "pass",
    "details": "Well-structured sections"
  },
  "depth": {
    "status": "fail",
    "details": "Missing analysis on regional impacts"
  },
  "relevance": {
    "status": "pass",
    "details": "All points address the topic"
  },
  "structure": {
    "status": "pass",
    "details": "Professional formatting"
  },
  "issues": [
    "Insufficient coverage of Asia-Pacific region",
    "Missing data on salary adjustments"
  ],
  "improvements": [
    "Add sources on regional job market trends",
    "Include compensation survey data"
  ],
  "final_verdict": "Good report, needs regional depth"
}
```

### 5. Refiner Agent (If Score 5-7)

- Fixes identified issues
- Maintains citations
- Regenerates improved report

---

## Testing Examples

### Example 1: Quick Test

```python
from pipeline import run_research_pipeline

# Simple, narrow topic
result = run_research_pipeline("Python 3.13 release features")
print(result["report"])
```

### Example 2: Complex Topic

```python
# Broader topic requiring synthesis
result = run_research_pipeline(
    "Impact of quantum computing on cybersecurity and financial markets"
)
print(f"Score: {result['feedback']}")
print(f"Sources: {len(result['sources_list'])} found")
```

### Example 3: Error Handling

```python
import json

result = run_research_pipeline("Your topic")

# Parse feedback
try:
    feedback = json.loads(result["feedback"])
    print(f"Quality Score: {feedback['score']}/10")
    print(f"Issues: {feedback['issues']}")
except json.JSONDecodeError:
    print("Feedback parsing failed")
```

---

## Troubleshooting

### Issue: "API Key not found"

```
Solution: Create .env file with:
MISTRAL_API_KEY=sk-...
TAVILY_API_KEY=tvly-...
```

### Issue: "No sources found"

```
Solution:
- Check internet connection
- Verify Tavily API key is valid
- Try different, more specific topic
```

### Issue: "Reader Agent output not valid JSON"

```
Solution:
- This is handled gracefully
- Source is skipped if parsing fails
- System continues with remaining sources
```

### Issue: "Low critic score (< 5)"

```
Solution:
- Topic may be too broad
- Try more specific research question
- Add domain-specific context
```

---

## Performance Metrics

| Component                | Typical Time      |
| ------------------------ | ----------------- |
| Search Agent             | 2-4 seconds       |
| Scraper (5 URLs)         | 3-6 seconds       |
| Reader Agent (5 sources) | 5-8 seconds       |
| Writer Agent             | 3-5 seconds       |
| Critic Agent             | 2-3 seconds       |
| **Total Pipeline**       | **15-25 seconds** |

---

## Customization

### Change LLM Model

Edit [agents.py](agents.py#L10):

```python
llm = ChatMistralAI(
    model="mistral-medium-latest",  # Change here
    temperature=0
)
```

### Adjust Search Results

Edit [tools.py](tools.py#L14):

```python
web_results = tavily.search(
    query=query,
    search_depth="advanced",
    max_results=10  # Change here (was 8)
)
```

### Modify Report Length

Edit [agents.py](agents.py#L57):

```python
- Target: 1000-1500 words  # Change here
```

---

## Tips for Best Results

✅ **Do:**

- Use specific, clear research questions
- Include year/timeframe in topic (e.g., "2024")
- Break complex topics into multiple queries
- Review critic feedback even if score ≥ 8

❌ **Don't:**

- Use vague topics ("technology is important")
- Request obviously biased topics
- Mix too many unrelated subtopics
- Rely solely on score without reading report

---

## Architecture Components

```
Pipeline Flow:
┌─────────────────┐
│ Search Agent    │ ← Tavily API
└────────┬────────┘
         ↓
┌─────────────────┐
│ Async Scraper   │ ← aiohttp
└────────┬────────┘
         ↓
┌─────────────────┐
│ Reader Agent    │ ← LLM
└────────┬────────┘
         ↓
┌─────────────────┐
│ Writer Agent    │ ← LLM
└────────┬────────┘
         ↓
┌─────────────────┐
│ Critic Agent    │ ← LLM
└────────┬────────┘
         ↓
    [Score >= 8?]
    /            \
  YES            NO (5-7)
   │              │
   ↓              ↓
[DONE]    ┌──────────────────┐
          │ Refiner Agent    │ ← LLM
          └──────────────────┘
                   ↓
                [DONE]
```

---

## Support & Debugging

**Enable verbose logging:**

```python
import logging
logging.basicConfig(level=logging.DEBUG)

result = run_research_pipeline("Your topic")
```

**Check individual agent output:**

```python
from pipeline import run_research_pipeline

result = run_research_pipeline("Topic")

# Examine each step
print("1. Search:", result["search_results"][:200])
print("2. Reader:", result["extracted_data"])
print("3. Report:", result["report"][:300])
print("4. Feedback:", result["feedback"])
```

---

**Version:** 1.0 | **Last Updated:** April 30, 2026
