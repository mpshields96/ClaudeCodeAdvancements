# /cca-slides — Generate CCA Presentation Slides

Generate a professional 16:9 PDF slide deck for ClaudeCodeAdvancements using Typst.

## Usage
```
/cca-slides              # Generate with auto-detected session number
/cca-slides 46           # Generate for specific session
/cca-slides "My Title"   # Generate with custom title
```

## What It Does
1. Collects current project data (tests, modules, findings, session state)
2. Builds a slide deck with title, summary, metrics, frontiers, and module status
3. Renders a professional 16:9 PDF via Typst
4. Saves to project root as `CCA_SLIDES_YYYY-MM-DD.pdf`

## Execution

Determine the session number from SESSION_STATE.md or from the argument.
Then run:

```bash
cd /Users/matthewshields/Projects/ClaudeCodeAdvancements
python3 design-skills/slide_generator.py generate \
  --output "CCA_SLIDES_$(date +%Y-%m-%d).pdf" \
  --session $SESSION_NUMBER \
  $ARGUMENTS
```

Then tell the user the PDF was generated and its file size.

## Requirements
- Typst must be installed (`brew install typst`)
- Must be in the CCA project directory
