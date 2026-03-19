# /cca-report — Generate Professional CCA Status Report

Generate a comprehensive, Apple-style PDF status report for ClaudeCodeAdvancements using Typst.

## Usage
```
/cca-report              # Generate with auto-detected session number
/cca-report 52           # Generate for specific session
```

## What It Does
1. Collects data from PROJECT_INDEX.md, MASTER_TASKS.md, FINDINGS_LOG.md, papers.jsonl, SESSION_STATE.md
2. Scans codebase for LOC, file counts, and module statistics
3. Parses master tasks into complete/active/pending groups with deliverables and next steps
4. Renders a 12-14 page professional PDF with:
   - Cover page with hero metrics
   - Executive summary + project health dashboard
   - Module deep-dives (tests, LOC, components, next actions)
   - Master tasks grouped by status with deliverables
   - Live hook infrastructure table
   - Intelligence & research stats (Reddit findings + self-learning)
   - Architecture decisions
   - Risks & blockers with severity badges
   - Next priorities
   - Closing status page
5. Saves to project root as `CCA_STATUS_REPORT_YYYY-MM-DD.pdf`

## Execution

Run this command:
```bash
cd /Users/matthewshields/Projects/ClaudeCodeAdvancements
python3 design-skills/report_generator.py generate \
  --output "CCA_STATUS_REPORT_$(date +%Y-%m-%d).pdf" \
  $ARGUMENTS
```

Then tell the user the PDF was generated, its file size, and page count.

## EOD Report Usage
This report is designed as an end-of-day overview. Run it at session wrap to capture current state. The template and data collector will evolve over time — update the Typst template for visual improvements, update the Python collector for richer data extraction.

## Requirements
- Typst must be installed (`brew install typst`)
- Must be in the CCA project directory
