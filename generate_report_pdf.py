#!/usr/bin/env python3
"""Generate a clean, Apple-style PDF from the CCA status report text file.

Design principles: generous whitespace, restrained color, typographic hierarchy,
no heavy boxes or gimmicks. Let content breathe.
"""

import re
from fpdf import FPDF

# -- Minimal palette (Apple-inspired) --
BLACK     = (28, 28, 30)      # near-black
DARK      = (58, 58, 60)      # primary body text
MID       = (99, 99, 102)     # secondary text
LIGHT     = (142, 142, 147)   # tertiary / captions
FAINT     = (209, 209, 214)   # hairline dividers
WASH      = (242, 242, 247)   # subtle background tint
BLUE      = (0, 122, 255)     # iOS blue — used sparingly
WHITE     = (255, 255, 255)

MARGIN_L  = 22
MARGIN_R  = 22
CONTENT_W = 216 - MARGIN_L - MARGIN_R  # usable width


def san(text):
    """Sanitize text for latin-1 encoding (built-in Helvetica limitation)."""
    reps = {
        '\u2014': ' -- ', '\u2013': '-', '\u2018': "'", '\u2019': "'",
        '\u201c': '"', '\u201d': '"', '\u2022': '-', '\u2026': '...',
        '\u2192': '->', '\u00a0': ' ', '\u2011': '-', '\u2212': '-',
    }
    for o, n in reps.items():
        text = text.replace(o, n)
    return text.encode('latin-1', errors='replace').decode('latin-1')


class ApplePDF(FPDF):

    def __init__(self):
        super().__init__('P', 'mm', 'letter')
        self.set_auto_page_break(True, 25)
        self.set_margins(MARGIN_L, 20, MARGIN_R)

    # ── Page chrome ──────────────────────────────────────────────

    def header(self):
        if self.page_no() <= 1:
            return
        self.set_y(10)
        self.set_font('Helvetica', '', 6.5)
        self.set_text_color(*LIGHT)
        self.cell(CONTENT_W / 2, 4, 'ClaudeCodeAdvancements')
        self.cell(CONTENT_W / 2, 4, 'Status Report  /  2026-03-17', align='R')
        self.set_y(20)

    def footer(self):
        if self.page_no() <= 1:
            return
        self.set_y(-18)
        self.set_draw_color(*FAINT)
        self.line(MARGIN_L, self.get_y(), 216 - MARGIN_R, self.get_y())
        self.set_font('Helvetica', '', 6.5)
        self.set_text_color(*LIGHT)
        self.cell(0, 10, str(self.page_no() - 1), align='C')

    # ── Cover ────────────────────────────────────────────────────

    def cover(self):
        self.add_page()
        self.set_fill_color(*WHITE)
        self.rect(0, 0, 216, 280, 'F')

        # Thin top accent line
        self.set_fill_color(*BLACK)
        self.rect(0, 0, 216, 0.8, 'F')

        # Title — high on the page, lots of air below
        self.set_y(72)
        self.set_font('Helvetica', '', 11)
        self.set_text_color(*LIGHT)
        self.cell(0, 6, 'Project Status Report', align='C', new_x='LMARGIN', new_y='NEXT')

        self.ln(6)
        self.set_font('Helvetica', 'B', 36)
        self.set_text_color(*BLACK)
        self.cell(0, 15, 'ClaudeCode', align='C', new_x='LMARGIN', new_y='NEXT')
        self.cell(0, 15, 'Advancements', align='C', new_x='LMARGIN', new_y='NEXT')

        # Thin rule
        self.ln(8)
        rule_w = 40
        self.set_draw_color(*FAINT)
        self.set_line_width(0.3)
        self.line(108 - rule_w/2, self.get_y(), 108 + rule_w/2, self.get_y())

        # Subtitle
        self.ln(10)
        self.set_font('Helvetica', '', 10)
        self.set_text_color(*MID)
        self.cell(0, 6, 'Comprehensive overview of all modules, tests,', align='C', new_x='LMARGIN', new_y='NEXT')
        self.cell(0, 6, 'infrastructure, and development progress.', align='C', new_x='LMARGIN', new_y='NEXT')

        # Key stats — clean horizontal row, no boxes
        self.ln(28)
        stats = [
            ('1,525', 'tests passing'),
            ('30,925', 'lines of code'),
            ('38', 'sessions'),
            ('129', 'commits'),
        ]
        col_w = CONTENT_W / 4
        y = self.get_y()
        for i, (val, label) in enumerate(stats):
            x = MARGIN_L + i * col_w
            self.set_xy(x, y)
            self.set_font('Helvetica', 'B', 22)
            self.set_text_color(*BLACK)
            self.cell(col_w, 10, val, align='C')
            self.set_xy(x, y + 11)
            self.set_font('Helvetica', '', 7.5)
            self.set_text_color(*LIGHT)
            self.cell(col_w, 5, label, align='C')

        # Hairline separators between stats
        self.set_draw_color(*FAINT)
        self.set_line_width(0.2)
        for i in range(1, 4):
            x = MARGIN_L + i * col_w
            self.line(x, y + 2, x, y + 14)

        # Bottom of cover
        self.set_y(240)
        self.set_font('Helvetica', '', 8)
        self.set_text_color(*LIGHT)
        self.cell(0, 5, 'March 17, 2026', align='C', new_x='LMARGIN', new_y='NEXT')
        self.set_font('Helvetica', '', 7)
        self.cell(0, 5, 'github.com/mpshields96/ClaudeCodeAdvancements', align='C', new_x='LMARGIN', new_y='NEXT')

        # Bottom accent
        self.set_fill_color(*BLACK)
        self.rect(0, 278.2, 216, 0.8, 'F')

    # ── Table of Contents ────────────────────────────────────────

    def toc(self, items):
        self.add_page()
        self.set_font('Helvetica', '', 8)
        self.set_text_color(*LIGHT)
        self.cell(0, 5, 'CONTENTS', new_x='LMARGIN', new_y='NEXT')
        self.ln(4)
        self.set_draw_color(*FAINT)
        self.line(MARGIN_L, self.get_y(), MARGIN_L + 20, self.get_y())
        self.ln(6)

        for i, title in enumerate(items, 1):
            self.set_font('Helvetica', '', 8)
            self.set_text_color(*LIGHT)
            self.cell(10, 7, f'{i:02d}')
            self.set_font('Helvetica', '', 10)
            self.set_text_color(*DARK)
            self.cell(0, 7, san(title), new_x='LMARGIN', new_y='NEXT')

    # ── Content primitives ───────────────────────────────────────

    def section(self, num, title):
        if self.get_y() > 220:
            self.add_page()
        else:
            self.ln(8)

        # Section number + title
        self.set_font('Helvetica', '', 8)
        self.set_text_color(*BLUE)
        self.cell(0, 5, f'{num:02d}', new_x='LMARGIN', new_y='NEXT')
        self.set_font('Helvetica', 'B', 17)
        self.set_text_color(*BLACK)
        self.cell(0, 9, san(title), new_x='LMARGIN', new_y='NEXT')
        # Hairline
        self.ln(3)
        self.set_draw_color(*FAINT)
        self.set_line_width(0.2)
        self.line(MARGIN_L, self.get_y(), 216 - MARGIN_R, self.get_y())
        self.ln(5)

    def subsection(self, title):
        if self.get_y() > 240:
            self.add_page()
        self.ln(4)
        self.set_font('Helvetica', 'B', 11)
        self.set_text_color(*BLACK)
        self.cell(0, 7, san(title), new_x='LMARGIN', new_y='NEXT')
        self.ln(2)

    def body(self, text):
        self.set_font('Helvetica', '', 9)
        self.set_text_color(*DARK)
        self.multi_cell(CONTENT_W, 4.8, san(text.rstrip()), new_x='LMARGIN', new_y='NEXT')
        self.ln(1.5)

    def mono(self, text):
        lines = san(text.rstrip()).split('\n')
        line_h = 3.8
        total_h = len(lines) * line_h + 5
        if self.get_y() + total_h > 250:
            self.add_page()
        y0 = self.get_y()
        # Subtle wash background
        self.set_fill_color(*WASH)
        self.rect(MARGIN_L, y0, CONTENT_W, total_h, 'F')
        self.set_font('Courier', '', 7)
        self.set_text_color(*DARK)
        self.set_xy(MARGIN_L + 4, y0 + 2.5)
        for line in lines:
            self.set_x(MARGIN_L + 4)
            self.cell(0, line_h, line, new_x='LMARGIN', new_y='NEXT')
        self.ln(3)

    def kv(self, key, value, highlight=False):
        self.set_x(MARGIN_L)
        self.set_font('Helvetica', '', 8)
        self.set_text_color(*LIGHT)
        kw = max(self.get_string_width(san(key)) + 4, 44)
        self.cell(kw, 5.5, san(key))
        self.set_font('Helvetica', '', 9)
        if highlight:
            self.set_text_color(*BLUE)
        else:
            self.set_text_color(*DARK)
        # Handle long values with multi_cell
        remaining = CONTENT_W - kw
        if self.get_string_width(san(value)) > remaining:
            self.multi_cell(remaining, 5.5, san(value), new_x='LMARGIN', new_y='NEXT')
        else:
            self.cell(remaining, 5.5, san(value), new_x='LMARGIN', new_y='NEXT')

    def bullet(self, text):
        self.set_x(MARGIN_L + 3)
        self.set_font('Helvetica', '', 8)
        self.set_text_color(*MID)
        self.cell(5, 4.8, '-')
        self.set_text_color(*DARK)
        self.multi_cell(CONTENT_W - 8, 4.8, san(text), new_x='LMARGIN', new_y='NEXT')

    def closing_page(self):
        self.add_page()
        self.set_y(100)
        # Centered, minimal
        self.set_font('Helvetica', '', 8)
        self.set_text_color(*LIGHT)
        self.cell(0, 5, 'STATUS', align='C', new_x='LMARGIN', new_y='NEXT')
        self.ln(4)
        self.set_font('Helvetica', 'B', 20)
        self.set_text_color(*BLACK)
        self.cell(0, 10, 'All Systems Operational', align='C', new_x='LMARGIN', new_y='NEXT')
        self.ln(8)
        # Thin rule
        rule_w = 40
        self.set_draw_color(*FAINT)
        self.set_line_width(0.3)
        self.line(108 - rule_w/2, self.get_y(), 108 + rule_w/2, self.get_y())
        self.ln(8)
        self.set_font('Helvetica', '', 9)
        self.set_text_color(*MID)
        self.cell(0, 6, '1,525 tests   /   30,925 LOC   /   38 sessions   /   129 commits', align='C', new_x='LMARGIN', new_y='NEXT')
        self.ln(3)
        self.cell(0, 6, '7 of 7 modules complete   /   0 stubs   /   0 syntax errors', align='C', new_x='LMARGIN', new_y='NEXT')


def build_pdf(txt_path, out_path):
    pdf = ApplePDF()

    with open(txt_path) as f:
        content = f.read()

    toc_items = [
        'Executive Summary', 'Project Metrics at a Glance',
        'Codebase Statistics by Module', 'Frontier Module Deep-Dive',
        'Support Module Deep-Dive', 'Live Hook Architecture',
        'Master-Level Tasks', 'Self-Learning System Status',
        'Reddit Intelligence Status', 'Severity-Tracked Learnings',
        'Git & Commit History', 'Full Session History',
        'Next Priorities & Open Work', 'Known Risks & Blockers',
        'Architecture Decisions Log',
    ]

    pdf.cover()
    pdf.toc(toc_items)

    # Parse and render content
    lines = content.split('\n')
    i = 0
    mono_buf = []
    current_section = 0
    skip_title_block = True

    def flush(pdf, buf):
        if buf:
            pdf.mono('\n'.join(buf))
            buf.clear()

    while i < len(lines):
        line = lines[i]
        s = line.strip()

        # Skip decorative ===== lines
        if re.match(r'^={20,}$', s):
            flush(pdf, mono_buf)
            i += 1
            continue

        # Skip title block and TOC at top of file
        if skip_title_block:
            if re.match(r'^\d+\.\s+[A-Z]', s):
                skip_title_block = False  # Found first section header
            else:
                i += 1
                continue

        # Section headers: "1. EXECUTIVE SUMMARY"
        m = re.match(r'^(\d+)\.\s+(.+)$', s)
        if m:
            flush(pdf, mono_buf)
            current_section = int(m.group(1))
            pdf.section(current_section, m.group(2))
            i += 1
            continue

        # Subsection: dashed border pattern
        if re.match(r'^-{10,}$', s):
            flush(pdf, mono_buf)
            if i + 1 < len(lines) and lines[i+1].strip() and not re.match(r'^-{10,}$', lines[i+1].strip()):
                pdf.subsection(lines[i+1].strip())
                i += 2
                if i < len(lines) and re.match(r'^-{10,}$', lines[i].strip()):
                    i += 1
                continue
            i += 1
            continue

        # "---------- COMPLETED (6/17) ----------" headers
        dm = re.match(r'^-{5,}\s+(.+?)\s+-{5,}$', s)
        if dm:
            flush(pdf, mono_buf)
            pdf.subsection(dm.group(1))
            i += 1
            continue

        # Empty lines
        if not s:
            flush(pdf, mono_buf)
            i += 1
            continue

        # Table separator rows (+----- or ---+---)
        if re.match(r'^.*[-+]{5,}.*$', s) and ('+-' in s or '-+' in s):
            flush(pdf, mono_buf)
            i += 1
            continue

        # Key-value aligned rows: "  Label              Value"
        if re.match(r'^\s{2,}\S.*\s{3,}\S', line) and not s.startswith('-'):
            parts = re.split(r'\s{3,}', s, maxsplit=1)
            if len(parts) == 2:
                flush(pdf, mono_buf)
                hl = any(kw in parts[1] for kw in ['COMPLETE', 'ALL PASSING', '1,525', '30,925'])
                pdf.kv(parts[0], parts[1], highlight=hl)
                i += 1
                continue

        # Bullet: "  - something"
        bm = re.match(r'^\s{2,}-\s+(.+)$', line)
        if bm and not re.match(r'^\s{2,}-{5,}', line):
            flush(pdf, mono_buf)
            pdf.bullet(bm.group(1))
            i += 1
            continue

        # Deeply indented content -> mono block
        if re.match(r'^\s{4,}\S', line):
            mono_buf.append(line.rstrip())
            i += 1
            continue

        # "  Label: Value" pattern
        lm = re.match(r'^\s{2}(\w[\w\s]*?):\s+(.+)$', line)
        if lm:
            flush(pdf, mono_buf)
            hl = 'COMPLETE' in lm.group(2)
            pdf.kv(lm.group(1) + ':', lm.group(2), highlight=hl)
            i += 1
            continue

        # Body paragraph text
        flush(pdf, mono_buf)
        para = [s]
        i += 1
        while i < len(lines):
            ns = lines[i].strip()
            if not ns or re.match(r'^={20,}$', ns) or re.match(r'^-{10,}$', ns) or \
               re.match(r'^\d+\.\s', ns) or re.match(r'^\s{2,}-\s', lines[i]) or \
               re.match(r'^\s{2}\w[\w\s]*?:\s+', lines[i]):
                break
            para.append(ns)
            i += 1
        pdf.body(' '.join(para))

    flush(pdf, mono_buf)
    pdf.closing_page()
    pdf.output(out_path)
    return out_path


if __name__ == '__main__':
    txt = '/Users/matthewshields/Projects/ClaudeCodeAdvancements/CCA_STATUS_REPORT_2026-03-17.txt'
    out = '/Users/matthewshields/Projects/ClaudeCodeAdvancements/CCA_STATUS_REPORT_2026-03-17.pdf'
    build_pdf(txt, out)
    print(f'Done: {out}')
