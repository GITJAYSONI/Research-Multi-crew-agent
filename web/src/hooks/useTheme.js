import { useEffect, useState } from "https://esm.sh/react@18.3.1";

export function useTheme() {
  const [theme, setTheme] = useState(() => localStorage.getItem("theme") || "dark");

  useEffect(() => {
    document.documentElement.classList.toggle("dark", theme === "dark");
    localStorage.setItem("theme", theme);
  }, [theme]);

  return {
    theme,
    toggleTheme: () => setTheme((value) => (value === "dark" ? "light" : "dark"))
  };
}
