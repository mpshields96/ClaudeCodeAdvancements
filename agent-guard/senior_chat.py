#!/usr/bin/env python3
"""Senior Dev Chat — MT-20 Phase 8: Interactive senior developer CLI chat.

Reviews a file using the full senior_review pipeline, displays the verdict,
then enters a REPL where you can ask follow-up questions about the code.

The chat mode uses the review context (verdict, concerns, metrics, file content)
to provide informed answers about the code — like pair-programming with a senior
developer who has already read and analyzed the file.

Usage:
    # Interactive mode (REPL)
    python3 senior_chat.py path/to/file.py --project-root .

    # Single question mode (no REPL)
    python3 senior_chat.py path/to/file.py --question "What should I refactor first?"

    # Pipe-friendly (non-interactive)
    echo "What are the main concerns?" | python3 senior_chat.py path/to/file.py
"""

import argparse
import os
import sys
from dataclasses import dataclass

_MODULE_DIR = os.path.dirname(os.path.abspath(__file__))
if _MODULE_DIR not in sys.path:
    sys.path.insert(0, _MODULE_DIR)

from senior_review import review_file


@dataclass
class ReviewContext:
    """Holds everything needed for follow-up conversation about a file."""
    file_path: str
    content: str
    review_result: dict


def build_review_context(file_path: str, project_root: str = "") -> ReviewContext:
    """Run senior review and build a conversation context.

    Args:
        file_path: Path to the file to review.
        project_root: Optional project root for coherence/ADR checks.

    Returns:
        ReviewContext with file content and review results.
    """
    # Read file content
    content = ""
    if os.path.isfile(file_path):
        try:
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
        except (OSError, IOError):
            pass

    # Run the full review
    result = review_file(file_path, project_root=project_root)

    return ReviewContext(
        file_path=file_path,
        content=content,
        review_result=result,
    )


# Verdict display styling
_VERDICT_DISPLAY = {
    "approve": "APPROVE — Clean code, no blocking issues",
    "conditional": "CONDITIONAL — Issues found, fix before merging",
    "rethink": "RETHINK — Structural problems, needs redesign",
    "error": "ERROR — Could not review file",
}


def format_initial_review(ctx: ReviewContext) -> str:
    """Format the initial review for terminal display.

    Args:
        ctx: ReviewContext from build_review_context.

    Returns:
        Formatted string for display.
    """
    r = ctx.review_result
    verdict = r.get("verdict", "error")
    metrics = r.get("metrics", {})

    lines = []
    lines.append(f"Senior Review: {os.path.basename(ctx.file_path)}")
    lines.append("=" * 60)
    lines.append("")

    # Verdict
    verdict_text = _VERDICT_DISPLAY.get(verdict, verdict.upper())
    lines.append(f"Verdict: {verdict_text}")
    lines.append("")

    # Metrics summary
    loc = metrics.get("loc", 0)
    quality = metrics.get("quality_score", 0)
    grade = metrics.get("quality_grade", "?")
    effort = metrics.get("effort_score", 0)
    effort_label = metrics.get("effort_label", "?")
    satd = metrics.get("satd_total", 0)
    satd_high = metrics.get("satd_high", 0)
    blast = metrics.get("blast_radius", 0)
    adrs = metrics.get("relevant_adrs", 0)

    lines.append(f"Metrics:")
    lines.append(f"  LOC: {loc} | Quality: {quality} ({grade}) | Effort: {effort}/5 ({effort_label})")
    lines.append(f"  SATD: {satd} total ({satd_high} high) | Blast radius: {blast} | ADRs: {adrs}")
    lines.append("")

    # Concerns
    concerns = r.get("concerns", [])
    if concerns:
        lines.append(f"Concerns ({len(concerns)}):")
        for i, c in enumerate(concerns, 1):
            lines.append(f"  {i}. {c}")
        lines.append("")

    # Suggestions
    suggestions = r.get("suggestions", [])
    if suggestions:
        lines.append(f"Suggestions ({len(suggestions)}):")
        for i, s in enumerate(suggestions, 1):
            lines.append(f"  {i}. {s}")
        lines.append("")

    # Error
    error = r.get("error", "")
    if error:
        lines.append(f"Error: {error}")
        lines.append("")

    return "\n".join(lines)


def format_followup_prompt(ctx: ReviewContext, question: str) -> str:
    """Format a follow-up question with full review context for an LLM.

    This produces a self-contained prompt that includes the file content,
    review results, and the user's question — suitable for sending to an LLM.

    Args:
        ctx: ReviewContext with file content and review data.
        question: The user's follow-up question.

    Returns:
        Formatted prompt string.
    """
    r = ctx.review_result
    verdict = r.get("verdict", "unknown")
    concerns = r.get("concerns", [])
    suggestions = r.get("suggestions", [])
    metrics = r.get("metrics", {})

    lines = []
    lines.append("You are a senior developer reviewing code. You have already analyzed this file.")
    lines.append("")
    lines.append(f"File: {ctx.file_path}")
    lines.append(f"Verdict: {verdict}")
    lines.append("")

    if concerns:
        lines.append("Your concerns:")
        for c in concerns:
            lines.append(f"  - {c}")
        lines.append("")

    if suggestions:
        lines.append("Your suggestions:")
        for s in suggestions:
            lines.append(f"  - {s}")
        lines.append("")

    if metrics:
        lines.append(f"Metrics: LOC={metrics.get('loc', '?')}, Quality={metrics.get('quality_score', '?')}, "
                      f"SATD={metrics.get('satd_total', 0)}, Blast={metrics.get('blast_radius', 0)}")
        lines.append("")

    # Include file content (truncated for very large files)
    content = ctx.content
    if len(content) > 8000:
        content = content[:8000] + "\n... [truncated at 8000 chars]"

    lines.append("File content:")
    lines.append("```")
    lines.append(content)
    lines.append("```")
    lines.append("")
    lines.append(f"Developer question: {question}")

    return "\n".join(lines)


def parse_args(argv: list = None) -> argparse.Namespace:
    """Parse CLI arguments.

    Args:
        argv: Argument list (defaults to sys.argv[1:]).

    Returns:
        Parsed arguments namespace.
    """
    parser = argparse.ArgumentParser(
        description="Senior Dev Chat — interactive code review conversation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("file_path", help="Path to the file to review")
    parser.add_argument("--project-root", default="", help="Project root for coherence/ADR checks")
    parser.add_argument("--question", "-q", default=None,
                        help="Single question (non-interactive mode)")

    return parser.parse_args(argv)


def run_interactive(ctx: ReviewContext):
    """Run the interactive REPL loop.

    Displays the initial review, then accepts follow-up questions.
    Type 'quit', 'exit', or Ctrl+D to exit.

    Args:
        ctx: ReviewContext from build_review_context.
    """
    # Display initial review
    print(format_initial_review(ctx))

    if ctx.review_result.get("verdict") == "error":
        return

    print("Ask follow-up questions about this code. Type 'quit' to exit.")
    print("-" * 60)

    while True:
        try:
            question = input("\nYou: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nSession ended.")
            break

        if not question:
            continue
        if question.lower() in ("quit", "exit", "q"):
            print("Session ended.")
            break

        # Format the prompt (for now, display it — LLM integration is future work)
        prompt = format_followup_prompt(ctx, question)
        print(f"\n[Senior Dev prompt generated — {len(prompt)} chars]")
        print("(LLM integration pending — prompt is ready for API call)")


def main():
    """CLI entry point."""
    args = parse_args()

    # Build review context
    ctx = build_review_context(args.file_path, project_root=args.project_root)

    if args.question:
        # Non-interactive: show review + answer one question
        print(format_initial_review(ctx))
        prompt = format_followup_prompt(ctx, args.question)
        print(f"[Prompt ready — {len(prompt)} chars for LLM]")
    else:
        # Interactive REPL
        run_interactive(ctx)


if __name__ == "__main__":
    main()
