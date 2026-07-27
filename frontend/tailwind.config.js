/** @type {import('tailwindcss').Config} */
module.exports = {
    darkMode: ["class"],
    content: [
    "./src/**/*.{js,jsx,ts,tsx}",
    "./public/index.html"
  ],
  theme: {
    extend: {
      fontFamily: {
        heading: ['Inter', 'system-ui', '-apple-system', 'sans-serif'],
        body: ['"Open Sans"', 'system-ui', '-apple-system', 'sans-serif'],
        sans: ['"Open Sans"', 'system-ui', '-apple-system', 'sans-serif'],
      },
      letterSpacing: {
        tightest: '-0.045em',
      },

      /*
       * ── TYPE SCALE ────────────────────────────────────────────────────────
       *
       * Semantic tokens, not raw sizes. Each bakes in its own line-height and
       * tracking, so a heading can never end up with body line-height or a
       * display size with loose tracking. Use these instead of text-sm / text-4xl
       * etc. so the whole site scales from one place.
       *
       *   text-display   hero focal statement. ONE per page, maximum
       *   text-title-1   page <h1>
       *   text-title-2   section <h2>
       *   text-title-3   subsection / large card heading
       *   text-title-4   card heading
       *   text-lead      intro paragraph under a title
       *   text-body      default paragraph
       *   text-body-sm   secondary / supporting copy
       *   text-meta      metadata, bylines, dates, counts
       *   text-label     uppercase eyebrow labels (tracking is part of the token)
       *   text-micro     numeric ticks, badges, the smallest legible text
       *
       * The fluid tokens use clamp() so they scale with the viewport without
       * needing a breakpoint variant at every call site.
       */
      fontSize: {
        display: ['clamp(2.75rem, 10.5vw, 8rem)', { lineHeight: '1.06', letterSpacing: '-0.04em' }],
        'title-1': ['clamp(1.75rem, 4.2vw, 3.25rem)', { lineHeight: '1.05', letterSpacing: '-0.035em' }],
        'title-2': ['clamp(1.375rem, 2.8vw, 2.125rem)', { lineHeight: '1.12', letterSpacing: '-0.03em' }],
        'title-3': ['clamp(1.125rem, 1.8vw, 1.5rem)', { lineHeight: '1.2', letterSpacing: '-0.025em' }],
        'title-4': ['1.0625rem', { lineHeight: '1.3', letterSpacing: '-0.02em' }],
        lead: ['1rem', { lineHeight: '1.62', letterSpacing: '0' }],
        body: ['0.875rem', { lineHeight: '1.66', letterSpacing: '0' }],
        'body-sm': ['0.8125rem', { lineHeight: '1.6', letterSpacing: '0' }],
        meta: ['0.75rem', { lineHeight: '1.45', letterSpacing: '0.005em' }],
        label: ['0.6875rem', { lineHeight: '1.2', letterSpacing: '0.2em' }],
        micro: ['0.625rem', { lineHeight: '1.2', letterSpacing: '0.08em' }],
      },

      /*
       * Vertical rhythm for section spacing. Paired with the type scale so the
       * gap between a heading and its content is consistent site-wide.
       */
      spacing: {
        'gap-title': '1.25rem', // title -> its lead paragraph
        'gap-block': '2.5rem', // heading block -> content
        'gap-section': '5rem', // between stacked blocks inside a section
      },
      /*
       * Radius scale is intentionally collapsed. Every rounded-* utility maps to a
       * 0-3px value so the whole UI reads as sharp regardless of which token a
       * component reached for. `rounded-full` is deliberately NOT circular --
       * use `rounded-circle` for the few genuinely round elements (avatars,
       * chakra marks, progress rails).
       */
      borderRadius: {
        none: '0px',
        sm: '1px',
        DEFAULT: '2px',
        md: '2px',
        lg: '3px',
        xl: '3px',
        '2xl': '3px',
        '3xl': '3px',
        full: '2px',
        circle: '9999px',
      },
      /*
       * Every shadow utility resolves to `none`. The classes are also stripped from
       * source, but this makes a regression impossible -- depth is communicated with
       * borders and background steps instead.
       */
      boxShadow: {
        none: 'none',
        sm: 'none',
        DEFAULT: 'none',
        md: 'none',
        lg: 'none',
        xl: 'none',
        '2xl': 'none',
        inner: 'none',
      },
      dropShadow: {
        none: 'none',
        sm: 'none',
        DEFAULT: 'none',
        md: 'none',
        lg: 'none',
        xl: 'none',
        '2xl': 'none',
      },
      colors: {
        background: 'hsl(var(--background))',
        foreground: 'hsl(var(--foreground))',
        card: {
          DEFAULT: 'hsl(var(--card))',
          foreground: 'hsl(var(--card-foreground))'
        },
        popover: {
          DEFAULT: 'hsl(var(--popover))',
          foreground: 'hsl(var(--popover-foreground))'
        },
        primary: {
          DEFAULT: 'hsl(var(--primary))',
          foreground: 'hsl(var(--primary-foreground))'
        },
        secondary: {
          DEFAULT: 'hsl(var(--secondary))',
          foreground: 'hsl(var(--secondary-foreground))'
        },
        muted: {
          DEFAULT: 'hsl(var(--muted))',
          foreground: 'hsl(var(--muted-foreground))'
        },
        accent: {
          DEFAULT: 'hsl(var(--accent))',
          foreground: 'hsl(var(--accent-foreground))'
        },
        destructive: {
          DEFAULT: 'hsl(var(--destructive))',
          foreground: 'hsl(var(--destructive-foreground))'
        },
        border: 'hsl(var(--border))',
        input: 'hsl(var(--input))',
        ring: 'hsl(var(--ring))',
        chakra: 'hsl(var(--chakra))',
        saffron: 'hsl(var(--saffron))',
        'india-green': 'hsl(var(--india-green))',
        chart: {
          '1': 'hsl(var(--chart-1))',
          '2': 'hsl(var(--chart-2))',
          '3': 'hsl(var(--chart-3))',
          '4': 'hsl(var(--chart-4))',
          '5': 'hsl(var(--chart-5))'
        }
      },
      keyframes: {
        'accordion-down': {
          from: { height: '0' },
          to: { height: 'var(--radix-accordion-content-height)' }
        },
        'accordion-up': {
          from: { height: 'var(--radix-accordion-content-height)' },
          to: { height: '0' }
        }
      },
      animation: {
        'accordion-down': 'accordion-down 0.2s ease-out',
        'accordion-up': 'accordion-up 0.2s ease-out'
      }
    }
  },
  plugins: [require("tailwindcss-animate")],
};
