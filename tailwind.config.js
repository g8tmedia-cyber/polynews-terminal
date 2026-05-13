/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        terminal: {
          bg: '#0a0e17',
          panel: '#111827',
          border: '#1e2d40',
          header: '#0d1926',
          green: '#00ff88',
          amber: '#ffb800',
          red: '#ff4757',
          blue: '#00bfff',
          text: '#e0e8f0',
          muted: '#4a6572',
        }
      },
      fontFamily: {
        mono: ['JetBrains Mono', 'Fira Code', 'Courier New', 'monospace'],
      }
    },
  },
  plugins: [],
}