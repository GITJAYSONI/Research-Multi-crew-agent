import React from "https://esm.sh/react@18.3.1";
import { Moon, Sun } from "https://esm.sh/lucide-react@0.468.0";

const h = React.createElement;

export default function ThemeToggle({ theme, onToggle }) {
  return h(
    "button",
    {
      onClick: onToggle,
      className:
        "rounded-full border border-zinc-200 bg-white p-2 text-zinc-700 transition hover:bg-zinc-100 dark:border-app-border dark:bg-app-secondary dark:text-zinc-200 dark:hover:bg-white/10",
      "aria-label": "Toggle theme"
    },
    theme === "dark" ? h(Sun, { size: 18 }) : h(Moon, { size: 18 })
  );
}
