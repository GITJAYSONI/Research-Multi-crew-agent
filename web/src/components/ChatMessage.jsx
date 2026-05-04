import React from "https://esm.sh/react@18.3.1";
import { Bot, User } from "https://esm.sh/lucide-react@0.468.0";

const h = React.createElement;

function renderMarkdownLite(text) {
  const lines = String(text || "Thinking...").split("\n");
  return lines.map((line, index) => {
    if (line.startsWith("## ")) {
      return h("h3", { key: index, className: "mt-3 text-base font-semibold" }, line.slice(3));
    }
    if (line.startsWith("- ")) {
      return h("li", { key: index, className: "ml-4 list-disc" }, line.slice(2));
    }
    if (!line.trim()) {
      return h("div", { key: index, className: "h-2" });
    }
    return h("p", { key: index, className: "leading-6" }, line);
  });
}

export default function ChatMessage({ message }) {
  const isUser = message.role === "user";
  return h(
    "div",
    { className: `flex gap-3 ${isUser ? "justify-end" : "justify-start"}` },
    [
      !isUser &&
        h(
          "div",
          {
            key: "ai-avatar",
            className: "mt-1 flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-accent-600 text-white"
          },
          h(Bot, { size: 18 })
        ),
      h(
        "div",
        {
          key: "bubble",
          className: `max-w-[82%] rounded-2xl border px-4 py-3 shadow-sm ${
            isUser
              ? "border-accent-500 bg-accent-600 text-white"
              : "border-zinc-200 bg-white text-zinc-900 dark:border-app-border dark:bg-app-secondary dark:text-zinc-100"
          }`
        },
        [
          message.image?.previewUrl &&
            h("img", {
              key: "image",
              src: message.image.previewUrl,
              alt: message.image.name || "Uploaded image",
              className: "mb-3 max-h-72 rounded-xl object-contain"
            }),
          isUser
            ? h("p", { key: "text", className: "whitespace-pre-wrap text-sm leading-6" }, message.content)
            : h("div", { key: "markdown", className: "space-y-1 text-sm" }, [
                ...renderMarkdownLite(message.content),
                message.isStreaming &&
                  h("span", {
                    key: "cursor",
                    className: "ml-1 inline-block h-4 w-2 animate-pulse rounded bg-accent-500 align-middle"
                  })
              ])
        ]
      ),
      isUser &&
        h(
          "div",
          {
            key: "user-avatar",
            className:
              "mt-1 flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-zinc-900 text-white dark:bg-zinc-100 dark:text-zinc-950"
          },
          h(User, { size: 18 })
        )
    ]
  );
}
