// Project backend client.
// This is the Vite/React hook point for the Python backend.
// Expected backend route:
// POST /api/chat -> ResearchChatService.ask(user_input, thread_id, user_id, mode)

const API_BASE_URL = import.meta.env?.VITE_API_BASE_URL || "http://localhost:8000";

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

async function emitChunks(text, onChunk) {
  const chunks = text.match(/.{1,32}(\s|$)/g) || [text];
  for (const chunk of chunks) {
    await sleep(45);
    onChunk(chunk);
  }
}

export async function generateProjectResponse({
  prompt,
  image,
  mode = "discover",
  threadId = null,
  userId = 1,
  onChunk
}) {
  if (!prompt?.trim()) {
    throw new Error("The backend requires a text message; image-only requests are not supported yet.");
  }

  // Until the Python API route is exposed, keep a local backend-shaped preview.
  if (!import.meta.env?.VITE_USE_BACKEND_API) {
    await emitChunks(localBackendPreview(prompt, image), onChunk);
    return null;
  }

  const response = await fetch(`${API_BASE_URL}/api/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      message: prompt,
      image,
      mode,
      thread_id: threadId,
      user_id: userId
    })
  });

  if (!response.ok) throw new Error(`Project backend request failed: ${response.status}`);
  const data = await response.json();
  const answer = data.final_answer || data.report || "No answer returned by backend.";
  await emitChunks(answer, onChunk);
  return data;
}

function localBackendPreview(prompt, image) {
  return `## Local Backend Response Preview

The frontend is aligned to the project backend pipeline.

- Query: ${prompt || "image-only request"}
- ${image ? "Image attached and converted to a base64-ready payload." : "No image attached."}
- Agent order: Search Agent -> Scraper Agent -> Writer Agent -> Critic Agent.
- Expected backend fields: report/final_answer, source_cards, feedback, and agent_outputs.

Next integration step: expose a Python /api/chat endpoint that calls ResearchChatService.ask(...).`;
}
