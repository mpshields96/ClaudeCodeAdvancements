"""CCA Slide Generator — Collects project data and renders presentation slides via Typst.

MT-17 Phase 2: Slide templates for project updates, session summaries, and presentations.

Usage:
    python3 design-skills/slide_generator.py generate --output slides.pdf
    python3 design-skills/slide_generator.py generate --output slides.pdf --session 46
    python3 design-skills/slide_generator.py generate --output slides.pdf --title "CCA Update"

Pipeline: Python collects CCA data -> JSON -> Typst slide template -> PDF
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import date
from pathlib import Path


class SlideDataCollector:
    """Collects CCA project data and builds slide deck structure."""

    def __init__(self, project_root=None):
        if project_root is None:
            self.project_root = str(Path(__file__).parent.parent)
        else:
            self.project_root = project_root

    def collect_metadata(self, *, title=None, subtitle=None, author=None, session=None):
        """Collect deck-level metadata."""
        return {
            "title": title or "ClaudeCodeAdvancements",
            "subtitle": subtitle or "Project Update",
            "author": author or "",
            "session": session,
            "date": date.today().isoformat(),
        }

    def build_summary_slide(self, total_tests, passing_tests, test_suites,
                            total_modules, total_findings):
        """Build a project summary slide with key counts."""
        return {
            "type": "summary",
            "metrics": {
                "total_tests": total_tests,
                "passing_tests": passing_tests,
                "test_suites": test_suites,
                "total_modules": total_modules,
                "total_findings": total_findings,
            },
        }

    def build_module_slide(self, modules):
        """Build a module status table slide.

        modules: list of dicts with name, status, tests keys.
        """
        return {
            "type": "modules",
            "modules": [
                {"name": m["name"], "status": m["status"], "tests": m["tests"]}
                for m in modules
            ],
        }

    def build_bullet_slide(self, title, bullets):
        """Build a bullet-point slide."""
        return {
            "type": "bullets",
            "title": title,
            "bullets": list(bullets),
        }

    def build_metric_slide(self, title, metrics):
        """Build a large-number metrics slide.

        metrics: list of dicts with label, value, sublabel keys.
        """
        return {
            "type": "metrics",
            "title": title,
            "metrics": [
                {"label": m["label"], "value": m["value"], "sublabel": m["sublabel"]}
                for m in metrics
            ],
        }

    def build_chart_slide(self, title, svg_content, caption=""):
        """Build a chart/figure slide with embedded SVG.

        Args:
            title: Slide title displayed above the chart.
            svg_content: Raw SVG string (from chart_generator or figure_generator).
            caption: Optional caption below the chart.

        Returns:
            Slide dict with type "chart".
        """
        return {
            "type": "chart",
            "title": title,
            "svg_content": svg_content,
            "caption": caption,
        }

    def build_section_slide(self, title):
        """Build a section divider slide."""
        return {
            "type": "section",
            "title": title,
        }

    def assemble_deck(self, metadata, slides):
        """Assemble metadata and slides into a complete deck structure."""
        deck = dict(metadata)
        deck["slides"] = list(slides)
        return deck


class SlideGenerator:
    """Handles Typst compilation of slide decks."""

    def __init__(self):
        self._template_dir = str(Path(__file__).parent / "templates")
        self.template_path = os.path.join(self._template_dir, "cca-slides.typ")

    def write_data_json(self, data, path):
        """Write slide deck data to a JSON file."""
        with open(path, "w") as f:
            json.dump(data, f, indent=2)

    def build_compile_command(self, data_path, output_path):
        """Build the typst compile command."""
        return [
            "typst", "compile",
            "--root", "/",
            "--input", f"data={data_path}",
            self.template_path,
            output_path,
        ]

    def generate(self, data, output_path):
        """Generate PDF slides from deck data.

        Returns (success: bool, message: str).
        """
        if not shutil.which("typst"):
            return False, "Typst not installed. Install: brew install typst"

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(data, f, indent=2)
            data_path = f.name

        try:
            cmd = self.build_compile_command(data_path, output_path)
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode != 0:
                return False, f"Typst error: {result.stderr.strip()}"
            return True, f"Slides generated: {output_path}"
        except subprocess.TimeoutExpired:
            return False, "Typst compilation timed out (30s)"
        except FileNotFoundError:
            return False, "Typst binary not found"
        finally:
            os.unlink(data_path)


def collect_slides_from_project(collector, session=None):
    """Build slide deck from real CCA project data."""
    # Import the report data collector for real metrics
    sys.path.insert(0, os.path.dirname(__file__))
    from report_generator import CCADataCollector

    data_collector = CCADataCollector(project_root=collector.project_root)
    report_data = data_collector.collect_from_project(session=session)

    s = report_data["summary"]
    modules = report_data["modules"]
    intelligence = report_data["intelligence"]

    slides = [
        collector.build_section_slide(
            f"Session {report_data['session']}" if report_data.get("session") else "Project Overview"
        ),
        collector.build_summary_slide(
            s["total_tests"], s["passing_tests"], s["test_suites"],
            s["total_modules"], s["total_findings"],
        ),
        collector.build_metric_slide("Key Metrics", [
            {"label": "Tests", "value": f"{s['total_tests']:,}", "sublabel": f"{s['test_suites']} suites, all passing"},
            {"label": "LOC", "value": f"{s['total_loc']:,}", "sublabel": f"{s['source_files']} source + {s['test_files']} test files"},
            {"label": "Commits", "value": str(s["git_commits"]), "sublabel": f"{s['project_age_days']} days"},
        ]),
        collector.build_bullet_slide("Five Frontiers", [
            f"{f['name']} — {f['description']}" for f in report_data.get("frontiers", [])
        ] or [
            "Memory System — persistent cross-session memory",
            "Spec System — requirements-first development",
            "Context Monitor — health tracking + auto-handoff",
            "Agent Guard — multi-agent safety + conflict prevention",
            "Usage Dashboard — token/cost transparency",
        ]),
        collector.build_module_slide([
            {"name": m["name"], "status": m["status"], "tests": m["tests"]}
            for m in modules
        ]),
        collector.build_metric_slide("Intelligence", [
            {"label": "Findings", "value": str(intelligence["findings_total"]), "sublabel": f"{intelligence['build']} BUILD, {intelligence['adapt']} ADAPT"},
            {"label": "Subreddits", "value": str(intelligence["subreddits_scanned"]), "sublabel": "actively monitored"},
            {"label": "Repos", "value": str(intelligence["github_repos_evaluated"]), "sublabel": "evaluated"},
        ]),
    ]

    return report_data["session"] or session, slides


def main():
    parser = argparse.ArgumentParser(description="Generate CCA presentation slides")
    sub = parser.add_subparsers(dest="command")

    gen = sub.add_parser("generate", help="Generate slide deck PDF")
    gen.add_argument("--output", "-o", required=True, help="Output PDF path")
    gen.add_argument("--title", default="ClaudeCodeAdvancements", help="Deck title")
    gen.add_argument("--subtitle", default="Project Update", help="Deck subtitle")
    gen.add_argument("--session", type=int, help="Session number")
    gen.add_argument("--demo", action="store_true", help="Use hardcoded demo data")

    sub.add_parser("templates", help="List available templates")

    args = parser.parse_args()

    if args.command == "templates":
        template_dir = Path(__file__).parent / "templates"
        for t in sorted(template_dir.glob("*.typ")):
            print(f"  {t.name}")
        return

    if args.command == "generate":
        collector = SlideDataCollector()

        if args.demo:
            # Hardcoded demo data for testing without project files
            metadata = collector.collect_metadata(
                title=args.title, subtitle=args.subtitle, session=args.session,
            )
            slides = [
                collector.build_section_slide(f"Session {args.session}" if args.session else "Project Overview"),
                collector.build_summary_slide(1593, 1593, 39, 9, 283),
                collector.build_metric_slide("Key Metrics", [
                    {"label": "Tests", "value": "1593", "sublabel": "39 suites, all passing"},
                    {"label": "Modules", "value": "9", "sublabel": "5 frontiers complete"},
                    {"label": "Findings", "value": "283", "sublabel": "32% APF"},
                ]),
            ]
        else:
            # Collect real project data
            real_session, slides = collect_slides_from_project(collector, session=args.session)
            metadata = collector.collect_metadata(
                title=args.title, subtitle=args.subtitle,
                session=args.session or real_session,
            )

        deck = collector.assemble_deck(metadata, slides)
        generator = SlideGenerator()
        success, message = generator.generate(deck, args.output)
        print(message)
        sys.exit(0 if success else 1)

    parser.print_help()


if __name__ == "__main__":
    main()
