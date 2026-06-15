/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        display: ['"Syne"', 'sans-serif'],
        body: ['"DM Sans"', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'monospace'],
      },
      colors: {
        bg: {
          primary: '#040812',
          secondary: '#080f1e',
          card: '#0d1628',
          border: '#1a2540',
        },
        signal: {
          buy: '#00d97e',
          neutral: '#f5a623',
          sell: '#ff4757',
        },
        accent: '#3b82f6',
        muted: '#4a5568',
      },
    },
  },
  plugins: [],
}
