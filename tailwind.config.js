export default {
  content: [
  './index.html',
  './src/**/*.{js,ts,jsx,tsx}'
],
  theme: {
    extend: {
      colors: {
        ink: {
          950: '#08090A',
          900: '#0D0F10',
          850: '#131617',
          800: '#191D1F',
          700: '#242A2C',
          600: '#343B3E',
          500: '#4B5457',
        },
        chalk: {
          DEFAULT: '#F1F4F0',
          dim: '#A5ADA7',
          faint: '#6D7772',
        },
        signal: {
          DEFAULT: '#CBFF4D',
          dark: '#A9DE22',
          deep: '#141A05',
        },
        ember: '#FF8A4C',
        sky: {
          soft: '#7FD3E8',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'sans-serif'],
        display: ['"Instrument Sans"', 'Inter', 'system-ui', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'ui-monospace', 'SFMono-Regular', 'monospace'],
      },
      letterSpacing: {
        tightest: '-0.04em',
      },
      keyframes: {
        'pulse-ring': {
          '0%': { transform: 'scale(0.85)', opacity: '0.7' },
          '100%': { transform: 'scale(1.6)', opacity: '0' },
        },
        marquee: {
          '0%': { transform: 'translateX(0)' },
          '100%': { transform: 'translateX(-50%)' },
        },
      },
      animation: {
        'pulse-ring': 'pulse-ring 2.4s ease-out infinite',
        marquee: 'marquee 32s linear infinite',
      },
    },
  },
  plugins: [],
};
