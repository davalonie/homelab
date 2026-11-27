"""Allow direct imports of the stack's administrative scripts in tests."""
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))


@pytest.fixture(scope="session", autouse=True)
def isolate_runtime():
    # A deployment environment must never redirect fixtures or backups to live data.
    with pytest.MonkeyPatch.context() as env:
        env.delenv("MUSIC_RUNTIME_DIR", raising=False)
        yield
