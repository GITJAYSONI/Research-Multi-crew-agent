/** @type {import('tailwindcss').Config} */
export default {
  darkMode: "class",
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        app: {
          bg: "#0a0a0a",
          secondary: "#111111",
          border: "#222222",
          muted: "#8a8a8a"
        },
        accent: {
          400: "#818cf8",
          500: "#6366f1",
          600: "#4f46e5"
        }
      },
      boxShadow: {
        soft: "0 18px 50px rgba(0,0,0,0.28)"
      }
    }
  },
  plugins: []
};
