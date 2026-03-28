#!/usr/bin/env python3
"""Generate a bounded Codex-native autoloop prompt for CCA.

This is the desktop-app analogue of CCA's autoloop flow. It does not try to
spawn fresh Codex sessions. Instead, it emits one bounded prompt that composes:

1. init
2. focused auto work
3. wrap

Usage:
  python3 codex_autoloop.py
  python3 codex_autoloop.py --task "Build codex_autoloop.py"
  python3 codex_autoloop.py --max-deliverables 2
  python3 codex_autoloop.py --write CODEX_AUTOLOOP_PROMPT.md
"""

from __future__ import annotations

import argparse
import os
import sys

from codex_auto import build_auto_prompt
from codex_init import DEFAULT_REPO_ROOT, build_init_prompt, collect_snapshot, normalize_cli_root
from codex_wrap import build_wrap_prompt, collect_snapshot as collect_wrap_snapshot


DEFAULT_OUTPUT_FILE = "CODEX_AUTOLOOP_PROMPT.md"


def build_autoloop_prompt(
    root: str,
    snapshot,
    task_override: str | None = None,
    max_deliverables: int = 1,
    wrap_prompt: str | None = None,
) -> str:
    if max_deliverables < 1:
        max_deliverables = 1

    init_prompt = build_init_prompt(root, snapshot)
    auto_prompt = build_auto_prompt(
        root,
        snapshot,
        task_override=task_override,
        max_deliverables=max_deliverables,
    )
    if wrap_prompt is None:
        wrap_prompt = build_wrap_prompt(root, collect_wrap_snapshot(root))
    deliverable_word = "deliverable" if max_deliverables == 1 else "deliverables"

    lines = [
        f"Use $cca-desktop-workflow in autoloop mode for {root}.",
        "",
        "Autoloop plan:",
        f"- Run one bounded cycle only inside the current Codex chat.",
        f"- Stop after {max_deliverables} meaningful {deliverable_word}, a validation blocker, or muddy context.",
        "- Do not try to respawn desktop sessions or emulate Claude's shell loop literally.",
        "- Use CCA comms directly if coordination matters.",
        "",
        "Init phase prompt:",
        "```text",
        init_prompt.rstrip(),
        "```",
        "",
        "Auto phase prompt:",
        "```text",
        auto_prompt.rstrip(),
        "```",
        "",
        "Wrap phase prompt:",
        "```text",
        wrap_prompt.rstrip(),
        "```",
    ]
    return "\n".join(lines).strip() + "\n"


def write_prompt(path: str, content: str) -> None:
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(content)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate a Codex autoloop prompt for CCA.")
    parser.add_argument("--root", default=DEFAULT_REPO_ROOT, help="Repo root to inspect.")
    parser.add_argument("--task", default=None, help="Explicit task override for the auto phase.")
    parser.add_argument(
        "--max-deliverables",
        type=int,
        default=1,
        help="Upper bound for meaningful deliverables inside this autoloop cycle.",
    )
    parser.add_argument(
        "--write",
        nargs="?",
        const=DEFAULT_OUTPUT_FILE,
        help="Write the generated prompt to a file instead of only printing it.",
    )
    args = parser.parse_args(argv)

    root, override_notice = normalize_cli_root(args.root)
    if override_notice:
        print(override_notice, file=sys.stderr)
    snapshot = collect_snapshot(root)
    prompt = build_autoloop_prompt(
        root,
        snapshot,
        task_override=args.task,
        max_deliverables=args.max_deliverables,
    )

    if args.write:
        out_path = args.write
        if not os.path.isabs(out_path):
            out_path = os.path.join(root, out_path)
        write_prompt(out_path, prompt)
        print(out_path)
        return 0

    sys.stdout.write(prompt)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
