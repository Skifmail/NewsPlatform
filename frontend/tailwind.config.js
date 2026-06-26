/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{vue,js}'],
  theme: {
    extend: {
      colors: {
        panel: {
          bg: 'rgb(var(--panel-bg-rgb) / <alpha-value>)',
          surface: 'rgb(var(--panel-surface-rgb) / <alpha-value>)',
          elevated: 'rgb(var(--panel-elevated-rgb) / <alpha-value>)',
          hover: 'rgb(var(--panel-hover-rgb) / <alpha-value>)',
          border: 'rgb(var(--panel-border-rgb) / <alpha-value>)',
          muted: 'rgb(var(--panel-muted-rgb) / <alpha-value>)',
        },
        accent: {
          DEFAULT: 'rgb(var(--accent-rgb) / <alpha-value>)',
          dark: 'rgb(var(--accent-dark-rgb) / <alpha-value>)',
          muted: 'var(--accent-muted)',
        },
        danger: 'rgb(var(--danger-rgb) / <alpha-value>)',
        info: 'rgb(var(--info-rgb) / <alpha-value>)',
        tag: {
          purple: 'rgb(var(--purple-rgb) / <alpha-value>)',
        },
      },
      fontFamily: {
        sans: ['"Plus Jakarta Sans"', 'system-ui', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'ui-monospace', 'monospace'],
      },
      borderRadius: {
        panel: '12px',
        pill: '9999px',
      },
      boxShadow: {
        panel: 'var(--shadow-panel)',
        glow: 'var(--shadow-glow)',
      },
    },
  },
  plugins: [],
}
