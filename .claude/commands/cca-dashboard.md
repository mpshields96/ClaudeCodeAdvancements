# /cca-dashboard — Generate Interactive HTML Dashboard

Generate a self-contained HTML dashboard showing CCA project status.
Opens in browser automatically.

## Usage

Run this command to generate and open the dashboard:

```bash
python3 /Users/matthewshields/Projects/ClaudeCodeAdvancements/design-skills/dashboard_generator.py generate --output /tmp/cca-dashboard.html && open /tmp/cca-dashboard.html
```

For demo data (testing the template):
```bash
python3 /Users/matthewshields/Projects/ClaudeCodeAdvancements/design-skills/dashboard_generator.py generate --output /tmp/cca-dashboard.html --demo && open /tmp/cca-dashboard.html
```

## What It Shows

- Metric cards: total tests, module count
- Module grid with status indicators (COMPLETE/ACTIVE)
- Master task priority table with score bars
- Responsive layout — works on mobile and desktop
- Self-contained: no external CSS/JS, single HTML file

## Design

Follows `design-skills/design-guide.md`:
- Color palette: primary (#1a1a2e), accent (#0f3460), success (#16c79a), highlight (#e94560)
- Typography: Source Sans 3 / Helvetica Neue fallback
- Layout: responsive grid, clean minimal style
- XSS-safe: all text is HTML-escaped
