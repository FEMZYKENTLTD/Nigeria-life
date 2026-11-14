/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#0a0a0c",
        charcoal: "#131318",
        panel: "#17171e",
        panel2: "#1d1d26",
        line: "#26262f",
        gold: {
          DEFAULT: "#c9a227",
          soft: "#e6c96a",
          dim: "#8a6d1a",
        },
        muted: "#9a97a3",
        faint: "#6b6875",
        good: "#4ade80",
        warn: "#facc15",
        bad: "#f87171",
        info: "#7dd3fc",
      },
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "Segoe UI", "Roboto", "Helvetica Neue", "sans-serif"],
        mono: ["ui-monospace", "SFMono-Regular", "Menlo", "Consolas", "monospace"],
      },
    },
  },
  plugins: [],
};
