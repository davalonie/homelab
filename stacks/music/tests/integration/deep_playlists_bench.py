"""Mide la lectura del índice de listas sobre una base temporal con metadatos sintéticos."""
import json
import os
from pathlib import Path
import resource
import sys
import tempfile
import time
from uuid import uuid4

STACK = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(STACK / "scripts"))
from runtime_path import runtime_dir

APP = Path(os.environ.get("ARMONIA_REPO", STACK.parents[2] / "armonia"))
sys.path.insert(0, str(APP / "middleware"))

import db
from homelab import store


def measure():
    track = {
        "source": "navidrome", "source_id": "fixture", "title": "T" * 250,
        "artist": "A" * 250, "album": "B" * 250, "duration": 180,
        "artist_mbids": [], "recording_mbid": None, "isrc": None,
    }
    items = json.dumps([{"id": str(uuid4()), "track": track} for _ in range(500)])
    with tempfile.TemporaryDirectory() as temp:
        db.DB_PATH = Path(temp) / "armonia.db"
        store.init()
        with store.connection(write=True) as conn:
            conn.executemany(
                "INSERT INTO playlists (id, owner, name, revision, items, updated) VALUES (?, ?, ?, ?, ?, ?)",
                ((str(uuid4()), "fixture", f"Lista {n}", 1, items, 123) for n in range(200)),
            )
        start = time.perf_counter()
        summaries = store.playlists("fixture")
        elapsed = time.perf_counter() - start
    assert len(summaries) == 200 and all(row["item_count"] == 500 for row in summaries)
    return {
        "playlists": len(summaries), "entries_per_playlist": 500,
        "metadata_bytes": len(json.dumps(summaries).encode()), "list_seconds": elapsed,
        "process_max_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
    }


if __name__ == "__main__":
    result = json.dumps(measure(), indent=2)
    output = runtime_dir(STACK) / "mediciones"
    output.mkdir(parents=True, exist_ok=True)
    (output / "playlists-bench.json").write_text(result + "\n")
    print(result)
