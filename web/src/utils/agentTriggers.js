const FULL_PLAN = [
  { agent: "search", duration: 700 },
  { agent: "scraper", duration: 650 },
  { agent: "writer", duration: 850 },
  { agent: "critic", duration: 600 }
];

const QUICK_PLAN = [
  { agent: "writer", duration: 700 },
  { agent: "critic", duration: 500 }
];

export function getAgentPlanForPrompt(prompt) {
  const text = prompt.toLowerCase();
  if (
    text.includes("search:") ||
    text.includes("latest") ||
    text.includes("source") ||
    text.includes("research")
  ) {
    return FULL_PLAN;
  }
  return QUICK_PLAN;
}
