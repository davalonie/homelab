"""Comprueba tres contratos en el middleware del clon hermano, con datos temporales."""
import os
from pathlib import Path
import subprocess
import sys

stack = Path(__file__).resolve().parents[2]
app = Path(os.environ.get("ARMONIA_REPO", stack.parents[2] / "armonia"))
suite = "tests/test_deep_failures.py::"
contracts = [
    "test_same_user_duplicate_reservation_is_atomic_but_users_are_independent",
    "test_stream_url_cache_is_bounded_and_discards_expired_entries",
    "test_truncated_oversized_or_mismatched_ranges_are_not_spliced",
]
if __name__ == "__main__":
    command = [sys.executable, "-m", "pytest", "-q", *(suite + case for case in contracts)]
    raise SystemExit(subprocess.run(command, cwd=app / "middleware").returncode)
