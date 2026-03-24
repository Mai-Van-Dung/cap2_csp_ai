/** @type {import('tailwindcss').Config} */
export default {
  darkMode: "class",
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        primary: "#FF8C00",
        background: "#1E1E26",
        surface: "#2A2A35",
        danger: "#FF4D4D",
      },
    },
  },
  plugins: [],
};
