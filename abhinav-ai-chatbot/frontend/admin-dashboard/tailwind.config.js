/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        primary: {
          DEFAULT: '#1a2f5a',
          50: '#e8ecf4',
          100: '#c5cfe3',
          200: '#9eafd0',
          300: '#778fbd',
          400: '#5a77b0',
          500: '#3d5fa3',
          600: '#355796',
          700: '#2b4c86',
          800: '#214177',
          900: '#1a2f5a',
        },
        accent: {
          DEFAULT: '#d4a017',
          50: '#fdf8e8',
          100: '#faeec6',
          200: '#f7e3a0',
          300: '#f4d87a',
          400: '#f1cf5f',
          500: '#eec644',
          600: '#e8bb3d',
          700: '#dfad33',
          800: '#d6a029',
          900: '#d4a017',
        },
        background: '#f8f9fa',
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'sans-serif'],
      },
    },
  },
  plugins: [],
}
