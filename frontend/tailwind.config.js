/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './src/pages/**/*.{js,ts,jsx,tsx,mdx}',
    './src/components/**/*.{js,ts,jsx,tsx,mdx}',
    './src/app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        'vinuni-navy': '#0A2B57',
        'vinuni-red': '#C72127',
        'vinuni-burgundy': '#941616',
        'vinuni-secondary-navy': '#134D8B',
        'vinuni-cyan': '#2599DC',
      },
      fontFamily: {
        sans: ['Roboto', 'sans-serif'],
      },
    },
  },
  plugins: [],
  corePlugins: {
    preflight: false, // Prevent Tailwind from conflicting with MUI styles
  },
};
