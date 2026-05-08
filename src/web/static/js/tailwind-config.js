if (typeof tailwind !== 'undefined') {
    tailwind.config = {
        theme: {
            extend: {
                colors: {
                    bg: 'var(--c-bg)',
                    'bg-secondary': 'var(--c-bg-secondary)',
                    card: 'var(--c-card)',
                    up: 'var(--c-up)',
                    down: 'var(--c-down)',
                    accent: 'var(--c-accent)',
                    'accent-hover': 'var(--c-accent-hover)',
                    txt: 'var(--c-text)',
                    muted: 'var(--c-muted)',
                    gold: 'var(--c-gold)',
                    border: 'var(--c-border)',
                },
                fontFamily: {
                    sans: ['var(--font-sans)'],
                    mono: ['var(--font-mono)'],
                },
                borderRadius: {
                    sm: 'var(--radius-sm)',
                    md: 'var(--radius-md)',
                    lg: 'var(--radius-lg)',
                    xl: 'var(--radius-xl)',
                    '2xl': 'var(--radius-2xl)',
                    full: 'var(--radius-full)',
                },
                boxShadow: {
                    sm: 'var(--shadow-sm)',
                    md: 'var(--shadow-md)',
                    lg: 'var(--shadow-lg)',
                    xl: 'var(--shadow-xl)',
                    glow: 'var(--shadow-glow)',
                    'glow-lg': 'var(--shadow-glow-lg)',
                },
                transitionDuration: {
                    fast: '150ms',
                    normal: '200ms',
                    slow: '300ms',
                },
                transitionTimingFunction: {
                    bounce: 'cubic-bezier(0.34, 1.56, 0.64, 1)',
                },
            }
        }
    };
}
