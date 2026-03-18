# /cca-report — Generate Professional CCA Status Report

Generate a professional PDF status report for ClaudeCodeAdvancements using Typst.

## Usage
```
/cca-report              # Generate with auto-detected session number
/cca-report 41           # Generate for specific session
```

## What It Does
1. Collects data from PROJECT_INDEX.md, MASTER_TASKS.md, FINDINGS_LOG.md, papers.jsonl, SESSION_STATE.md
2. Renders a professional PDF with metrics, module status, master task progress, and next priorities
3. Saves to project root as `CCA_STATUS_REPORT_YYYY-MM-DD.pdf`

## Execution

Run this command:
```bash
cd /Users/matthewshields/Projects/ClaudeCodeAdvancements
python3 design-skills/report_generator.py generate \
  --output "CCA_STATUS_REPORT_$(date +%Y-%m-%d).pdf" \
  $ARGUMENTS
```

Then tell the user the PDF was generated and its file size.

## Requirements
- Typst must be installed (`brew install typst`)
- Must be in the CCA project directory
