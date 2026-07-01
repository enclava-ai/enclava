/** @type {import('tailwindcss').Config} */
const withA = (value) => `hsl(var(${value}) / <alpha-value>)`

module.exports = {
  darkMode: ["class"],
  content: [
    './pages/**/*.{ts,tsx}',
    './components/**/*.{ts,tsx}',
    './app/**/*.{ts,tsx}',
    './src/**/*.{ts,tsx}',
  ],
  prefix: "",
  theme: {
    container: {
      center: true,
      padding: "2rem",
      screens: {
        "2xl": "1400px",
      },
    },
    extend: {
      fontFamily: {
        sans: ['var(--font-sans)'],
        display: ['var(--font-display)'],
        mono: ['var(--font-mono)'],
      },
      colors: {
        border: withA("--border"),
        input: withA("--input"),
        ring: withA("--ring"),
        "border-strong": withA("--border-strong"),
        faint: withA("--faint"),
        background: withA("--background"),
        foreground: withA("--foreground"),
        primary: {
          DEFAULT: withA("--primary"),
          foreground: withA("--primary-foreground"),
        },
        secondary: {
          DEFAULT: withA("--secondary"),
          foreground: withA("--secondary-foreground"),
        },
        destructive: {
          DEFAULT: withA("--destructive"),
          foreground: withA("--destructive-foreground"),
        },
        muted: {
          DEFAULT: withA("--muted"),
          foreground: withA("--muted-foreground"),
        },
        accent: {
          DEFAULT: withA("--accent"),
          foreground: withA("--accent-foreground"),
        },
        "accent-soft": withA("--accent-soft"),
        popover: {
          DEFAULT: withA("--popover"),
          foreground: withA("--popover-foreground"),
        },
        card: {
          DEFAULT: withA("--card"),
          foreground: withA("--card-foreground"),
        },
        success: {
          DEFAULT: withA("--success"),
          foreground: withA("--success-foreground"),
          soft: withA("--success-soft"),
          "soft-foreground": withA("--success-soft-foreground"),
          border: withA("--success-border"),
        },
        warning: {
          DEFAULT: withA("--warning"),
          foreground: withA("--warning-foreground"),
          soft: withA("--warning-soft"),
          "soft-foreground": withA("--warning-soft-foreground"),
          border: withA("--warning-border"),
        },
        danger: {
          DEFAULT: withA("--danger"),
          foreground: withA("--danger-foreground"),
          soft: withA("--danger-soft"),
          "soft-foreground": withA("--danger-soft-foreground"),
          border: withA("--danger-border"),
        },
        info: {
          DEFAULT: withA("--info"),
          foreground: withA("--info-foreground"),
          soft: withA("--info-soft"),
          "soft-foreground": withA("--info-soft-foreground"),
          border: withA("--info-border"),
        },
        chart: {
          1: withA("--chart-1"),
          2: withA("--chart-2"),
          3: withA("--chart-3"),
          4: withA("--chart-4"),
          5: withA("--chart-5"),
        },
        // Enclava brand colors (cyan/teal palette matching website)
        enclava: {
          50: '#ecfeff',
          100: '#cffafe',
          200: '#a5f3fc',
          300: '#67e8f9',
          400: '#22d3ee',
          500: '#14b8a6', // primary cyan
          600: '#0d9488',
          700: '#0f766e',
          800: '#115e59',
          900: '#134e4a',
        },
        // Legacy alias
        empire: {
          gold: '#22d3ee',
          dark: '#0f172a',
          darker: '#020617',
          50: '#ecfeff',
          100: '#cffafe',
          200: '#a5f3fc',
          300: '#67e8f9',
          400: '#22d3ee',
          500: '#14b8a6',
          600: '#0d9488',
          700: '#0f766e',
          800: '#115e59',
          900: '#134e4a',
        },
      },
      borderRadius: {
        lg: "var(--radius)",
        md: "calc(var(--radius) - 2px)",
        sm: "calc(var(--radius) - 4px)",
      },
      keyframes: {
        "accordion-down": {
          from: { height: "0" },
          to: { height: "var(--radix-accordion-content-height)" },
        },
        "accordion-up": {
          from: { height: "var(--radix-accordion-content-height)" },
          to: { height: "0" },
        },
        "pulse-glow": {
          "0%, 100%": { opacity: "0.6", filter: "brightness(1)" },
          "50%": { opacity: "1", filter: "brightness(1.2)" },
        },
        "float": {
          "0%": { transform: "translateY(0px)" },
          "50%": { transform: "translateY(-20px)" },
          "100%": { transform: "translateY(0px)" },
        },
      },
      animation: {
        "accordion-down": "accordion-down 0.2s ease-out",
        "accordion-up": "accordion-up 0.2s ease-out",
        "pulse-glow": "pulse-glow 3s cubic-bezier(0.4, 0, 0.6, 1) infinite",
        "float": "float 6s ease-in-out infinite",
      },
    },
  },
  plugins: [require("tailwindcss-animate"), require("@tailwindcss/typography")],
}
