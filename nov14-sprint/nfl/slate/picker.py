"""Sunday picker entry point. Score with the issued engine; add separately dated evidence."""
import copy
import sys
from pathlib import Path

SLATE_DIR = Path(__file__).resolve().parent
sys.path.append(str(SLATE_DIR))  # -I deliberately omits the script directory.
import issued_picker_20261115 as issued
import selection_release


def freeze_inputs():
    """Resolve historical manifest names to the original bytes actually used for scoring."""
    files = {"picker.py": Path(issued.__file__),
             "selection_decisions.py": Path(issued.decisions.issued.__file__),
             "selection_markets.py": Path(issued.markets.__file__)}
    return {name: issued.sha256_file(path) for name, path in files.items()}


# Install presentation hooks once, before the issued command's ordinary locking,
# idempotent writes and archive checks. Keep the complete original module reproducible.
if not hasattr(issued, "_issued_run_slate"):
    issued._issued_run_slate = issued.run_slate
    issued._issued_slate_blocks = issued.slate_blocks


def run_slate(args):
    saved = SLATE_DIR / "release_data/sunday-odds.json"
    if not args.lines and not args.odds and saved.is_file():
        args = copy.copy(args)
        args.odds = str(saved)
    return selection_release.attach(issued._issued_run_slate(args))


def slate_blocks(doc):
    return selection_release.report_blocks(doc, issued._issued_slate_blocks(doc))


issued.freeze_inputs = freeze_inputs
issued.run_slate = run_slate
issued.slate_blocks = slate_blocks


def __getattr__(name):
    return getattr(issued, name)


if __name__ == "__main__":
    sys.exit(issued.main())
