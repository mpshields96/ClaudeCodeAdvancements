# /cca-website — Generate CCA Website Pages

Generate self-contained HTML pages for the CCA project — landing page and documentation pages.
Opens in browser automatically.

## Landing Page (default)

Generate a live landing page from real CCA project data:
```bash
python3 /Users/matthewshields/Projects/ClaudeCodeAdvancements/design-skills/website_generator.py --type landing --output /tmp/cca-landing.html && open /tmp/cca-landing.html
```

For demo data (testing the template):
```bash
python3 /Users/matthewshields/Projects/ClaudeCodeAdvancements/design-skills/website_generator.py --type landing --demo --output /tmp/cca-landing.html && open /tmp/cca-landing.html
```

## Docs Page

Generate a documentation page:
```bash
python3 /Users/matthewshields/Projects/ClaudeCodeAdvancements/design-skills/website_generator.py --type docs --output /tmp/cca-docs.html && open /tmp/cca-docs.html
```

## What It Shows

### Landing Page
- Hero section with title, tagline, and CTA button
- Metrics strip (total tests, modules, sessions)
- Features grid — one card per CCA module
- Sticky navigation bar with GitHub link
- Footer

### Docs Page
- Sticky sidebar with section navigation
- Content sections with code blocks
- Responsive layout (mobile-friendly)

## Design

Follows `design-skills/design-guide.md`:
- Color palette: primary (#1a1a2e), accent (#0f3460), highlight (#e94560), success (#16c79a)
- Typography: system-ui / SF Mono
- Layout: responsive grid, sticky nav, 240px sidebar for docs
- XSS-safe: all user content HTML-escaped
- Self-contained: no external CSS/JS, single HTML file
