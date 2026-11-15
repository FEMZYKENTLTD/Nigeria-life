/** @type {import('tailwindcss').Config} */
// Premium palette: "Midnight & Copper" — deep midnight-blue base, ivory text,
// restrained copper accents. Deliberately not the near-black + gold cliché.
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#0d1322",
        charcoal: "#121a2e",
        panel: "#151e33",
        panel2: "#1b2540",
        line: "#283453",
        // token names kept (copper is the accent)
        gold: {
          DEFAULT: "#c17d4f",
          soft: "#e3ab84",
          dim: "#8f5f3d",
        },
        ivory: "#ece7db",
        muted: "#97a3c0",
        faint: "#5e6a8a",
        good: "#43d692",
        warn: "#f2b23e",
        bad: "#ef6a6a",
        info: "#6fb1ff",
      },
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "Segoe UI", "Roboto", "Helvetica Neue", "sans-serif"],
        mono: ["ui-monospace", "SFMono-Regular", "Menlo", "Consolas", "monospace"],
      },
    },
  },
  plugins: [],
};
