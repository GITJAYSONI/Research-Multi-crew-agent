import React from "https://esm.sh/react@18.3.1";
import { MessageSquarePlus, Sparkles } from "https://esm.sh/lucide-react@0.468.0";

const h = React.createElement;

export default function Sidebar({ onNewChat }) {
  const history = ["Market brief", "Academic summary", "Product analysis"];
  return h(
    "aside",
    {
      className:
        "hidden min-h-screen border-r border-zinc-200 bg-white p-4 dark:border-app-border dark:bg-app-secondary lg:block"
    },
    h("div", { className: "mb-6 flex items-center gap-3" }, [
      h(
        "div",
        {
          key: "logo",
          className:
            "flex h-10 w-10 items-center justify-center rounded-xl bg-accent-600 text-white shadow-soft"
        },
        h(Sparkles, { size: 20 })
      ),
      h("div", { key: "copy" }, [
        h("h2", { key: "title", className: "font-semibold" }, "Neural Desk"),
        h("p", { key: "sub", className: "text-xs text-zinc-500 dark:text-zinc-400" }, "Research chat")
      ])
    ]),
    h(
      "button",
      {
        onClick: onNewChat,
        className:
          "mb-6 flex w-full items-center justify-center gap-2 rounded-xl bg-zinc-950 px-4 py-3 text-sm font-medium text-white transition hover:bg-zinc-800 dark:bg-zinc-100 dark:text-zinc-950"
      },
      [h(MessageSquarePlus, { key: "icon", size: 17 }), "New Chat"]
    ),
    h("p", { className: "mb-2 text-xs font-semibold uppercase tracking-wide text-zinc-500" }, "History"),
    h(
      "div",
      { className: "space-y-1" },
      history.map((item) =>
        h(
          "button",
          {
            key: item,
            className:
              "w-full rounded-lg px-3 py-2 text-left text-sm text-zinc-600 transition hover:bg-zinc-100 dark:text-zinc-300 dark:hover:bg-white/5"
          },
          item
        )
      )
    )
  );
}
