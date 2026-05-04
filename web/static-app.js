// Frontend-to-backend alignment notes:
// These agent keys map to backend pipeline.py agent records:
// Search Agent -> Scraper Agent -> Writer Agent -> Critic Agent.
const AGENTS = [
  ["search", "Search Agent", "S"],
  ["scraper", "Scraper Agent", "R"],
  ["writer", "Writer Agent", "W"],
  ["critic", "Critic Agent", "C"]
];

const state = {
  theme: localStorage.getItem("theme") || "dark",
  messages: [],
  agents: {
    search: "idle",
    scraper: "idle",
    writer: "idle",
    critic: "idle"
  },
  image: null,
  generating: false,
  threadId: null,
  userId: 1,
  lastResult: null,
  history: []
};

const root = document.getElementById("root");
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

function el(tag, attrs = {}, children = []) {
  const node = document.createElement(tag);
  Object.entries(attrs).forEach(([key, value]) => {
    if (key === "class") node.className = value;
    else if (key.startsWith("on")) node.addEventListener(key.slice(2).toLowerCase(), value);
    else if (value !== false && value != null) node.setAttribute(key, value);
  });
  children.flat().forEach((child) => {
    if (child == null || child === false) return;
    node.append(child.nodeType ? child : document.createTextNode(String(child)));
  });
  return node;
}

function render() {
  document.documentElement.classList.toggle("dark", state.theme === "dark");
  localStorage.setItem("theme", state.theme);
  root.replaceChildren(
    el("div", { class: "app" }, [renderSidebar(), renderMain(), renderAgents()])
  );
  const chat = document.querySelector(".chat");
  if (chat) chat.scrollTop = chat.scrollHeight;
}

function renderSidebar() {
  return el("aside", { class: "sidebar" }, [
    el("div", { class: "brand" }, [
      el("div", { class: "brand-mark" }, ["AI"]),
      el("div", {}, [
        el("p", { class: "brand-title" }, ["Research AI"]),
        el("p", { class: "brand-sub" }, ["Multi-agent research"])
      ])
    ]),
    el("button", { class: "new-chat", onClick: resetChat }, ["+ New Chat"]),
    el("div", { class: "history-label" }, ["History"]),
    state.history.length
      ? state.history.map((thread) =>
          el(
            "button",
            { class: "history-item", onClick: () => loadThread(thread.id) },
            [thread.id === state.threadId ? `* ${thread.title}` : thread.title]
          )
        )
      : el("div", { class: "history-item" }, ["No saved chats yet"])
  ]);
}

function renderMain() {
  return el("main", { class: "main" }, [
    el("header", { class: "topbar" }, [
      el("div", {}, [
        el("p", { class: "kicker" }, ["Research Intelligence System"]),
        el("p", { class: "header-title" }, ["Ask anything"])
      ]),
      el("button", { class: "theme-btn", onClick: toggleTheme }, [
        state.theme === "dark" ? "Light" : "Dark"
      ])
    ]),
    renderChat(),
    renderComposer()
  ]);
}

function renderChat() {
  const actions =
    state.lastResult && !state.generating
      ? el("div", { class: "report-actions" }, [
          el("button", { class: "pdf-btn", onClick: downloadLatestPdf }, ["Download PDF"])
        ])
      : null;
  const content =
    state.messages.length === 0
      ? el("div", { class: "empty" }, [
          el("div", { class: "empty-badge" }, ["AI"]),
          el("h1", { class: "empty-title" }, ["What can I help you research?"]),
          el("p", { class: "empty-copy" }, [
            "Send a prompt, attach one image if needed, and watch Search Agent, Scraper Agent, Writer Agent, and Critic Agent activate."
          ])
        ])
      : state.messages.map(renderMessage);
  return el("section", { class: "chat" }, [actions, el("div", { class: "chat-inner" }, [content])]);
}

function renderMessage(message) {
  const isUser = message.role === "user";
  const bubble = el("div", { class: "bubble" }, [
    message.image ? el("img", { src: message.image.previewUrl, alt: message.image.name }) : null,
    isUser ? el("p", {}, [message.content]) : renderMarkdownLite(message.content, message.streaming)
  ]);
  return el("div", { class: `message ${isUser ? "user" : "assistant"}` }, [
    !isUser ? el("div", { class: "avatar ai" }, ["AI"]) : null,
    bubble,
    isUser ? el("div", { class: "avatar user" }, ["You"]) : null
  ]);
}

function renderMarkdownLite(text, streaming) {
  const wrap = el("div");
  String(text || "Thinking...")
    .split("\n")
    .forEach((line) => {
      if (line.startsWith("## ")) wrap.append(el("h3", {}, [line.slice(3)]));
      else if (line.startsWith("- ")) wrap.append(el("li", {}, [line.slice(2)]));
      else if (!line.trim()) wrap.append(el("div", { style: "height: 8px" }));
      else wrap.append(el("p", {}, [line]));
    });
  if (streaming) wrap.append(el("span", { class: "cursor" }));
  return wrap;
}

function renderComposer() {
  return el("footer", { class: "composer" }, [
    el("div", { class: "composer-inner" }, [
      state.image
        ? el("div", { class: "preview" }, [
            el("img", { src: state.image.previewUrl, alt: state.image.name }),
            el("span", { class: "preview-name" }, [state.image.name]),
            el("button", { class: "remove-btn", onClick: () => setImage(null) }, ["x"])
          ])
        : null,
      el("div", { class: "input-shell" }, [
        el("button", { class: "icon-btn", onClick: openFilePicker }, ["Img"]),
        el("input", {
          id: "image-input",
          type: "file",
          accept: "image/*",
          style: "display:none",
          onChange: handleImage
        }),
        el("textarea", {
          id: "prompt-input",
          rows: "1",
          placeholder: "Ask anything...",
          disabled: state.generating,
          onKeydown: (event) => {
            if (event.key === "Enter" && !event.shiftKey) {
              event.preventDefault();
              submitPrompt();
            }
          }
        }),
        el("button", { class: "send-btn", disabled: state.generating, onClick: submitPrompt }, [">"])
      ])
    ])
  ]);
}

function renderAgents() {
  return el("aside", { class: "agents" }, [
    el("p", { class: "kicker" }, ["Agents"]),
    el("h2", { class: "agent-title", style: "margin-bottom: 18px" }, ["Pipeline State"]),
    AGENTS.map(([key, label, icon]) => {
      const active = state.agents[key] === "searching";
      const done = state.agents[key] === "done";
      const review = state.agents[key] === "review";
      return el("div", { class: `agent-card ${active ? "active" : done ? "done" : review ? "review" : ""}` }, [
        el("div", { class: "agent-row" }, [
          el("div", { class: "agent-icon" }, [icon]),
          el("div", {}, [
            el("div", { class: "agent-name" }, [label]),
            el("div", { class: "agent-state" }, [
              el("span", { class: "dot" }),
              active ? "running" : done ? "done" : review ? "review" : "idle"
            ])
          ])
        ])
      ]);
    }),
    renderDebugPanel()
  ]);
}

function renderDebugPanel() {
  if (!state.lastResult) {
    return el("p", { class: "agent-note" }, [
      "Agent names and order match pipeline.py. The frontend is connected to /api/chat."
    ]);
  }

  const feedback = parseFeedback(state.lastResult.feedback);
  const quality = state.lastResult.structured_report?.evidence_quality_and_limits || {};
  return el("details", { class: "debug-panel" }, [
    el("summary", {}, ["Debug"]),
    el("p", {}, [`Score: ${state.lastResult.final_score ?? "n/a"}/10`]),
    el("p", {}, [`Confidence: ${feedback.confidence || "unknown"}`]),
    el("p", {}, [`Sources: ${(state.lastResult.source_cards || []).length}`]),
    state.lastResult.accuracy_status ? el("p", {}, [state.lastResult.accuracy_status]) : null,
    quality.issues?.length
      ? el("ul", {}, quality.issues.slice(0, 5).map((issue) => el("li", {}, [issue])))
      : el("p", {}, ["No critic issues reported."])
  ]);
}

function toggleTheme() {
  state.theme = state.theme === "dark" ? "light" : "dark";
  render();
}

function resetChat() {
  state.messages = [];
  state.image = null;
  state.threadId = null;
  state.lastResult = null;
  setAllAgents("idle");
  render();
}

async function refreshHistory() {
  try {
    const response = await fetch(`http://localhost:8000/api/threads?user_id=${state.userId}`);
    const data = await response.json();
    state.history = data.threads || [];
    state.userId = data.user_id || state.userId;
    render();
  } catch {
    // History is a convenience surface; chat can still work if this fails.
  }
}

async function loadThread(threadId) {
  try {
    const response = await fetch(
      `http://localhost:8000/api/thread?thread_id=${threadId}&user_id=${state.userId}`
    );
    const data = await response.json();
    if (data.error) throw new Error(data.error);
    state.threadId = data.thread_id;
    state.messages = (data.messages || []).map((message) => ({
      id: crypto.randomUUID(),
      role: message.role,
      content: message.content
    }));
    state.lastResult = null;
    setAllAgents("idle");
    render();
  } catch (error) {
    alert(`Could not load chat: ${error.message}`);
  }
}

function openFilePicker() {
  document.getElementById("image-input")?.click();
}

function setImage(image) {
  state.image = image;
  render();
}

function handleImage(event) {
  const file = event.target.files?.[0];
  if (!file) return;
  if (!file.type.startsWith("image/")) {
    alert("Please upload an image file.");
    return;
  }
  const reader = new FileReader();
  reader.onload = () => {
    const dataUrl = String(reader.result);
    setImage({
      name: file.name,
      mimeType: file.type,
      previewUrl: dataUrl,
      base64: dataUrl.split(",")[1]
    });
  };
  reader.readAsDataURL(file);
}

async function submitPrompt() {
  const input = document.getElementById("prompt-input");
  const text = input?.value.trim() || "";
  if (state.generating) return;
  if (!text) {
    state.messages.push({
      id: crypto.randomUUID(),
      role: "assistant",
      content: "Please include a text question. The backend does not support image-only requests yet.",
      streaming: false
    });
    render();
    return;
  }
  const image = state.image;
  state.lastResult = null;
  setAllAgents("idle");
  state.messages.push({
    id: crypto.randomUUID(),
    role: "user",
    content: text,
    image
  });
  const aiMessage = {
    id: crypto.randomUUID(),
    role: "assistant",
    content: "",
    streaming: true
  };
  state.messages.push(aiMessage);
  state.image = null;
  state.generating = true;
  render();

  const agentPromise = runAgentSequence(text);
  const response = await callProjectBackend(text, image);
  applyBackendAgentOutputs(response.data);
  const answer = response.answer;
  const chunks = answer.match(/.{1,32}(\s|$)/g) || [answer];
  for (const chunk of chunks) {
    await sleep(45);
    aiMessage.content += chunk;
    render();
  }
  await agentPromise;
  aiMessage.streaming = false;
  state.generating = false;
  render();
}

async function callProjectBackend(prompt, image) {
  try {
    const response = await fetch("http://localhost:8000/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        message: prompt,
        image,
        mode: "discover",
        user_id: state.userId,
        thread_id: state.threadId
      })
    });
    const data = await response.json();
    if (!response.ok || data.error) {
      throw new Error(data.error || `Backend request failed: ${response.status}`);
    }
    state.threadId = data.thread_id || state.threadId;
    state.userId = data.user_id || state.userId;
    state.lastResult = data;
    await refreshHistory();
    return {
      data,
      answer: formatBackendAnswer(data)
    };
  } catch (error) {
    return {
      data: null,
      answer: `## Backend Connection Error

The frontend could not reach the project backend API.

- Error: ${error.message}
- Make sure the API is running at http://localhost:8000
- Start it with: .\\.venv\\Scripts\\python.exe .\\api_server.py`
    };
  }
}

function formatBackendAnswer(data) {
  const report = data.final_answer || data.report || "The backend completed but returned no answer.";
  return report;
}

async function downloadLatestPdf() {
  if (!state.lastResult) return;
  const report = formatBackendAnswer(state.lastResult);
  const title = state.lastResult.structured_report?.title_page?.title || "Research Report";
  const response = await fetch("http://localhost:8000/api/report/pdf", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title, report })
  });
  if (!response.ok) {
    alert("Could not generate PDF report.");
    return;
  }
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = "research_report.pdf";
  document.body.append(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

function parseFeedback(value) {
  if (!value) return {};
  if (typeof value === "object") return value;
  try {
    return JSON.parse(value);
  } catch {
    return {};
  }
}

function applyBackendAgentOutputs(data) {
  if (!data?.agent_outputs?.length) return;
  setAllAgents("idle");
  const nameToKey = {
    "Search Agent": "search",
    "Scraper Agent": "scraper",
    "Writer Agent": "writer",
    "Critic Agent": "critic"
  };
  data.agent_outputs.forEach((item) => {
    const key = nameToKey[item.agent];
    if (key) state.agents[key] = item.status === "passed" ? "done" : "review";
  });
  render();
}

function getAgentPlan(prompt) {
  const text = prompt.toLowerCase();
  const full =
    text.includes("search") ||
    text.includes("latest") ||
    text.includes("source") ||
    text.includes("research");
  return full
    ? [
        ["search", 700],
        ["scraper", 650],
        ["writer", 850],
        ["critic", 600]
      ]
    : [
        ["writer", 700],
        ["critic", 500]
      ];
}

async function runAgentSequence(prompt) {
  for (const [agent, duration] of getAgentPlan(prompt)) {
    if (state.lastResult) break;
    state.agents[agent] = "searching";
    render();
    await sleep(duration);
    if (state.lastResult) break;
    state.agents[agent] = "done";
    render();
  }
}

function setAllAgents(value) {
  Object.keys(state.agents).forEach((key) => {
    state.agents[key] = value;
  });
}

refreshHistory().finally(render);
