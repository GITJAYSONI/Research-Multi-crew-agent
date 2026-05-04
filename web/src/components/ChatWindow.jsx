import React from "https://esm.sh/react@18.3.1";
import ChatMessage from "./ChatMessage.jsx";

const h = React.createElement;

export default function ChatWindow({ messages }) {
  return h(
    "section",
    { className: "flex-1 overflow-y-auto px-4 py-6 sm:px-6" },
    h(
      "div",
      { className: "mx-auto flex max-w-3xl flex-col gap-5" },
      messages.length === 0
        ? h("div", { className: "mt-20 text-center" }, [
            h(
              "div",
              {
                key: "badge",
                className:
                  "mx-auto mb-5 flex h-14 w-14 items-center justify-center rounded-2xl bg-accent-600 text-xl font-bold text-white shadow-soft"
              },
              "AI"
            ),
            h("h2", { key: "title", className: "text-2xl font-semibold" }, "What can I help you research?"),
            h(
              "p",
              {
                key: "copy",
                className: "mx-auto mt-3 max-w-xl text-sm leading-6 text-zinc-500 dark:text-zinc-400"
              },
              "Send a prompt, attach one image if needed, and watch the agents activate."
            )
          ])
        : messages.map((message) => h(ChatMessage, { key: message.id, message }))
    )
  );
}
