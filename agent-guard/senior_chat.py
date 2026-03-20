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
import json
import os
import sys
import urllib.request
import urllib.error
from dataclasses import dataclass, field

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


def build_system_prompt(ctx: ReviewContext) -> str:
    """Build a system prompt that gives the LLM full review context.

    This is the persistent context for the conversation — the LLM acts as a
    senior developer who has already reviewed the file.

    Args:
        ctx: ReviewContext with file content and review data.

    Returns:
        System prompt string.
    """
    r = ctx.review_result
    verdict = r.get("verdict", "unknown")
    concerns = r.get("concerns", [])
    suggestions = r.get("suggestions", [])
    metrics = r.get("metrics", {})

    lines = []
    lines.append("You are a senior software developer. You have just reviewed the following file "
                 "and produced a detailed analysis. Answer the developer's questions about this code "
                 "based on your review. Be specific, cite line numbers when relevant, and give "
                 "actionable advice.")
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
        parts = []
        for key in ("loc", "quality_score", "quality_grade", "effort_score",
                     "satd_total", "satd_high", "blast_radius", "relevant_adrs"):
            if key in metrics:
                parts.append(f"{key}={metrics[key]}")
        if parts:
            lines.append(f"Metrics: {', '.join(parts)}")
            lines.append("")

    # Include file content (truncated for very large files)
    content = ctx.content
    if len(content) > 10000:
        content = content[:10000] + "\n... [truncated at 10000 chars]"

    lines.append("File content:")
    lines.append("```")
    lines.append(content)
    lines.append("```")

    return "\n".join(lines)


_ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
_ANTHROPIC_VERSION = "2023-06-01"
_DEFAULT_MODEL = "claude-sonnet-4-20250514"
_DEFAULT_MAX_TOKENS = 4096


class LLMClient:
    """Anthropic Messages API client with conversation history.

    Uses stdlib urllib only — no external dependencies. Maintains multi-turn
    conversation history for follow-up questions.
    """

    def __init__(self, api_key: str = None, model: str = None, max_tokens: int = None):
        """Initialize the LLM client.

        Args:
            api_key: Anthropic API key. Falls back to ANTHROPIC_API_KEY env var.
            model: Model ID. Defaults to claude-sonnet-4-20250514.
            max_tokens: Max response tokens. Defaults to 4096.

        Raises:
            ValueError: If no API key is provided or found in environment.
        """
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError(
                "No API key provided. Set ANTHROPIC_API_KEY environment variable "
                "or pass api_key= to LLMClient."
            )
        self.model = model or _DEFAULT_MODEL
        self.max_tokens = max_tokens or _DEFAULT_MAX_TOKENS
        self.history: list = []
        self.total_input_tokens: int = 0
        self.total_output_tokens: int = 0

    def ask(self, question: str, system: str = "") -> str:
        """Send a question and get a response, maintaining conversation history.

        Args:
            question: The user's question.
            system: System prompt (used on every call for context).

        Returns:
            The assistant's response text, or an error message on failure.
        """
        messages = self.history + [{"role": "user", "content": question}]

        try:
            response = self._call_api(messages, system=system)
        except Exception as e:
            return f"Error calling API: {e}"

        # Extract text from response
        text = ""
        for block in response.get("content", []):
            if block.get("type") == "text":
                text += block.get("text", "")

        # Update history with successful exchange
        self.history.append({"role": "user", "content": question})
        self.history.append({"role": "assistant", "content": text})

        # Track token usage
        usage = response.get("usage", {})
        self.total_input_tokens += usage.get("input_tokens", 0)
        self.total_output_tokens += usage.get("output_tokens", 0)

        return text

    def _call_api(self, messages: list, system: str = "") -> dict:
        """Make a raw API call to Anthropic Messages endpoint.

        Args:
            messages: Conversation messages list.
            system: System prompt.

        Returns:
            Parsed JSON response dict.

        Raises:
            Exception: On HTTP errors or network failures.
        """
        body = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "messages": messages,
        }
        if system:
            body["system"] = system

        data = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(
            _ANTHROPIC_API_URL,
            data=data,
            headers={
                "Content-Type": "application/json",
                "X-API-Key": self.api_key,
                "Anthropic-Version": _ANTHROPIC_VERSION,
            },
            method="POST",
        )

        with urllib.request.urlopen(req, timeout=120) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def reset(self):
        """Clear conversation history and token counters."""
        self.history = []
        self.total_input_tokens = 0
        self.total_output_tokens = 0


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
    parser.add_argument("--model", default=_DEFAULT_MODEL,
                        help=f"LLM model ID (default: {_DEFAULT_MODEL})")
    parser.add_argument("--no-llm", action="store_true", default=False,
                        help="Disable LLM calls — just show generated prompts")

    return parser.parse_args(argv)


def _init_llm_client(model: str = None, no_llm: bool = False) -> "LLMClient | None":
    """Try to initialize an LLM client. Returns None if disabled or no key.

    Args:
        model: Model ID override.
        no_llm: If True, skip LLM initialization entirely.

    Returns:
        LLMClient instance or None.
    """
    if no_llm:
        return None
    try:
        return LLMClient(model=model)
    except ValueError:
        return None


def run_interactive(ctx: ReviewContext, llm: "LLMClient | None" = None):
    """Run the interactive REPL loop.

    Displays the initial review, then accepts follow-up questions.
    If an LLM client is provided, questions get real AI responses.
    Type 'quit', 'exit', or Ctrl+D to exit.

    Args:
        ctx: ReviewContext from build_review_context.
        llm: Optional LLMClient for AI-powered follow-ups.
    """
    # Display initial review
    print(format_initial_review(ctx))

    if ctx.review_result.get("verdict") == "error":
        return

    system = build_system_prompt(ctx)

    if llm:
        print(f"LLM active ({llm.model}). Ask follow-up questions. Type 'quit' to exit.")
    else:
        print("No LLM (set ANTHROPIC_API_KEY or remove --no-llm). Showing prompts only.")
        print("Type 'quit' to exit.")
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
            if llm:
                print(f"\nSession ended. Tokens used: {llm.total_input_tokens} in / "
                      f"{llm.total_output_tokens} out")
            else:
                print("Session ended.")
            break

        if llm:
            response = llm.ask(question, system=system)
            print(f"\nSenior Dev: {response}")
        else:
            prompt = format_followup_prompt(ctx, question)
            print(f"\n[Prompt generated — {len(prompt)} chars]")
            print("(No LLM configured — set ANTHROPIC_API_KEY for live responses)")


def main():
    """CLI entry point."""
    args = parse_args()

    # Build review context
    ctx = build_review_context(args.file_path, project_root=args.project_root)

    # Try to initialize LLM
    llm = _init_llm_client(model=args.model, no_llm=args.no_llm)

    if args.question:
        # Non-interactive: show review + answer one question
        print(format_initial_review(ctx))
        if llm:
            system = build_system_prompt(ctx)
            response = llm.ask(args.question, system=system)
            print(f"\nSenior Dev: {response}")
            print(f"\n[Tokens: {llm.total_input_tokens} in / {llm.total_output_tokens} out]")
        else:
            prompt = format_followup_prompt(ctx, args.question)
            print(f"[Prompt ready — {len(prompt)} chars for LLM]")
    else:
        # Interactive REPL
        run_interactive(ctx, llm=llm)


if __name__ == "__main__":
    main()
