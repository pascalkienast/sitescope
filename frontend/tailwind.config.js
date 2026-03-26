/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        risk: {
          high: "#DC2626",
          "high-bg": "#FEE2E2",
          medium: "#F59E0B",
          "medium-bg": "#FEF3C7",
          low: "#10B981",
          "low-bg": "#D1FAE5",
          none: "#6B7280",
          "none-bg": "#F3F4F6",
        },
      },
    },
  },
  plugins: [],
};
