import React from "https://esm.sh/react@18.3.1";
import { Activity, BookOpen, FileSearch, PenLine, ShieldCheck } from "https://esm.sh/lucide-react@0.468.0";

const h = React.createElement;
const AGENTS = [
  ["search", "Search Agent", FileSearch],
  ["scraper", "Scraper Agent", BookOpen],
  ["writer", "Writer Agent", PenLine],
  ["critic", "Critic Agent", ShieldCheck]
];

export default function AgentColumn({ agents }) {
  return h(
    "aside",
    {
      className:
        "hidden min-h-screen border-l border-zinc-200 bg-white p-4 dark:border-app-border dark:bg-app-secondary lg:block"
    },
    [
      h("p", { key: "kicker", className: "text-xs font-semibold uppercase tracking-wide text-zinc-500" }, "Agents"),
      h("h2", { key: "title", className: "mb-5 mt-1 text-lg font-semibold" }, "Search State"),
      h(
        "div",
        { key: "list", className: "space-y-3" },
        AGENTS.map(([key, label, Icon]) => {
          const active = agents[key] === "searching";
          return h(
            "div",
            {
              key,
              className: `rounded-2xl border p-4 shadow-sm transition-all duration-300 ${
                active
                  ? "scale-[1.02] border-accent-500 bg-accent-600 text-white shadow-soft"
                  : "border-zinc-200 bg-zinc-50 dark:border-app-border dark:bg-app-bg"
              }`
            },
            h("div", { className: "flex items-center gap-3" }, [
              h(Icon, { key: "icon", size: 20 }),
              h("div", { key: "body" }, [
                h("p", { key: "label", className: "text-sm font-semibold" }, label),
                h("p", { key: "state", className: "flex items-center gap-1 text-xs opacity-75" }, [
                  h(Activity, { key: "pulse", size: 12, className: active ? "animate-pulse" : "" }),
                  active ? "searching" : "idle"
                ])
              ])
            ])
          );
        })
      ),
      h(
        "p",
        { key: "note", className: "mt-5 text-xs leading-5 text-zinc-500 dark:text-zinc-400" },
        "Agent activity is simulated from prompt triggers. Use words like search, latest, source, or research to activate all agents."
      )
    ]
  );
}
