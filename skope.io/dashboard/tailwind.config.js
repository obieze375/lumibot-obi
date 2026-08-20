/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        background: "#09090B",
        foreground: "#FAFAFA",
        muted: "#27272A",
        "muted-foreground": "#A1A1AA",
        accent: "#DFE104",
        "accent-foreground": "#000000",
        border: "#3F3F46",
      },
      fontFamily: {
        display: ['"Space Grotesk"', "Inter", "sans-serif"],
      },
    },
  },
  plugins: [],
};
