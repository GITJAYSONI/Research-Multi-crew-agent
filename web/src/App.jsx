import React, { useState } from "https://esm.sh/react@18.3.1";
import Sidebar from "./components/Sidebar.jsx";
import ChatWindow from "./components/ChatWindow.jsx";
import MessageInput from "./components/MessageInput.jsx";
import AgentColumn from "./components/AgentColumn.jsx";
import ThemeToggle from "./components/ThemeToggle.jsx";
import { useTheme } from "./hooks/useTheme.js";
import { generateProjectResponse } from "./api/projectClient.js";
import { getAgentPlanForPrompt } from "./utils/agentTriggers.js";

const h = React.createElement;
const INITIAL_AGENTS = {
  search: "idle",
  scraper: "idle",
  writer: "idle",
  critic: "idle"
};

const delay = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

export default function App() {
  const { theme, toggleTheme } = useTheme();
  const [messages, setMessages] = useState([]);
  const [agents, setAgents] = useState(INITIAL_AGENTS);
  const [isGenerating, setIsGenerating] = useState(false);

  function resetChat() {
    setMessages([]);
    setAgents(INITIAL_AGENTS);
  }

  function setAgentState(agent, state) {
    setAgents((prev) => ({ ...prev, [agent]: state }));
  }

  async function runAgentSequence(prompt) {
    const plan = getAgentPlanForPrompt(prompt);
    for (const step of plan) {
      setAgentState(step.agent, "searching");
      await delay(step.duration);
      setAgentState(step.agent, "idle");
    }
  }

  async function handleSend({ text, image }) {
    if (isGenerating) return;
    if (!text.trim()) {
      const assistantId = crypto.randomUUID();
      setMessages((prev) => [
        ...prev,
        {
          id: assistantId,
          role: "assistant",
          content: "Please include a text question. The backend does not support image-only requests yet.",
          isStreaming: false,
          createdAt: Date.now()
        }
      ]);
      return;
    }

    const userMessage = {
      id: crypto.randomUUID(),
      role: "user",
      content: text.trim(),
      image,
      createdAt: Date.now()
    };
    const assistantId = crypto.randomUUID();

    setMessages((prev) => [
      ...prev,
      userMessage,
      {
        id: assistantId,
        role: "assistant",
        content: "",
        isStreaming: true,
        createdAt: Date.now()
      }
    ]);
    setIsGenerating(true);

    try {
      const agentPromise = runAgentSequence(text);
      await generateProjectResponse({
        prompt: text,
        image,
        onChunk: (chunk) => {
          setMessages((prev) =>
            prev.map((message) =>
              message.id === assistantId
                ? { ...message, content: message.content + chunk }
                : message
            )
          );
        }
      });
      await agentPromise;
      setMessages((prev) =>
        prev.map((message) =>
          message.id === assistantId ? { ...message, isStreaming: false } : message
        )
      );
    } catch (error) {
      setMessages((prev) =>
        prev.map((message) =>
          message.id === assistantId
            ? {
                ...message,
                isStreaming: false,
                content: `I could not complete the request. ${error.message || "Check the project backend API configuration and try again."}`
              }
            : message
        )
      );
    } finally {
      setAgents(INITIAL_AGENTS);
      setIsGenerating(false);
    }
  }

  return h(
    "div",
    {
      className:
        "min-h-screen bg-white text-zinc-950 transition-colors duration-300 dark:bg-app-bg dark:text-zinc-100"
    },
    h(
      "div",
      { className: "grid min-h-screen grid-cols-1 lg:grid-cols-[280px_minmax(0,1fr)_220px]" },
      h(Sidebar, { onNewChat: resetChat }),
      h(
        "main",
        {
          className:
            "flex min-h-screen min-w-0 flex-col border-x border-zinc-200 bg-zinc-50 dark:border-app-border dark:bg-app-bg"
        },
        h(
          "header",
          {
            className:
              "flex h-16 items-center justify-between border-b border-zinc-200 px-4 dark:border-app-border sm:px-6"
          },
          h("div", null, [
            h("p", { key: "label", className: "text-sm text-zinc-500 dark:text-zinc-400" }, "AI Research Assistant"),
            h("h1", { key: "title", className: "text-lg font-semibold" }, "Ask anything")
          ]),
          h(ThemeToggle, { theme, onToggle: toggleTheme })
        ),
        h(ChatWindow, { messages }),
        h(MessageInput, { onSend: handleSend, disabled: isGenerating })
      ),
      h(AgentColumn, { agents })
    )
  );
}
