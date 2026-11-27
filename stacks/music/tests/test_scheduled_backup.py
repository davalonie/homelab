"""The scheduled copy on a disposable installation: fictitious data, no Docker, nothing stopped."""
import base64
import fcntl
import importlib.util
import json
import os
import sqlite3
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
spec = importlib.util.spec_from_file_location("scheduled_backup", SCRIPTS / "scheduled_backup.py")
copia = importlib.util.module_from_spec(spec)
spec.loader.exec_module(copia)


@pytest.fixture
def lab(tmp_path):
    root, dest = tmp_path / "instalacion", tmp_path / "disco"
    (root / "runtime/music/user-a/Lúa Norte").mkdir(parents=True)
    (root / "runtime/music/user-a/Lúa Norte/Bajamar.m4a").write_bytes(b"audio ficticio 1")
    (root / "runtime/music/user-a/Lúa Norte/Cristal.m4a").write_bytes(b"audio ficticio 22")
    (root / "runtime/cache").mkdir()
    (root / "runtime/cache/portada").write_bytes(b"cache")
    (root / "runtime/navidrome/cache").mkdir(parents=True)
    (root / "runtime/navidrome/cache/imagen").write_bytes(b"cache")
    (root / "runtime/music-app").mkdir()
    (root / "secrets").mkdir()
    (root / "secrets/backup.key").write_bytes(base64.urlsafe_b64encode(os.urandom(32)))
    (root / "secrets/credential_key").write_text("secreto ficticio")
    (root / "compose.yaml").write_text("services: {}\n")
    dest.mkdir()
    # A live database in WAL mode with a writer still connected, as in the running service.
    writer = sqlite3.connect(root / "runtime/music-app/music.db")
    writer.execute("PRAGMA journal_mode=WAL")
    writer.execute("CREATE TABLE playlists(name TEXT)")
    writer.execute("INSERT INTO playlists VALUES ('Para conducir de noche')")
    writer.commit()
    yield root, dest, writer
    writer.close()


def make(root, dest, when=None, **options):
    return copia.run(root, dest, root / "secrets/backup.key", allow_same_disk=True, now=when, **options)


def restore(root, archive, target):
    subprocess.run([sys.executable, str(SCRIPTS / "backup.py"), "restore", str(archive), "--target", str(target),
                    "--key", str(root / "secrets/backup.key")], check=True, capture_output=True)


def test_state_is_restorable_with_the_existing_tool_and_music_is_mirrored(lab, tmp_path):
    root, dest, writer = lab
    (root / "compose.authentik.yaml").write_text("services: {}")
    (root / "secrets/oidc-client-secret").write_text("synthetic")
    extra = tmp_path / "firma.jks"
    extra.write_bytes(b"clave de firma ficticia")
    report = make(root, dest, extras=[extra])
    archive = dest / "estado" / report["state"]["archive"]
    assert report["ok"] and report["state"]["databases"] == 1 and report["key_included"] is False
    assert report["music"] == {"files_in_library": 2, "files_copied": 2, "bytes_copied": 33, "only_in_mirror_kept": 0}
    assert (dest / "musica/user-a/Lúa Norte/Bajamar.m4a").read_bytes() == b"audio ficticio 1"
    assert json.loads((dest / "ultimo-informe.json").read_text())["state"]["sha256"] == report["state"]["sha256"]

    restored = tmp_path / "restaurada"
    restore(root, archive, restored)
    assert not list(restored.rglob("*-wal")), "a snapshot is one whole file, not a database plus its log"
    rows = sqlite3.connect(restored / "runtime/music-app/music.db").execute("SELECT name FROM playlists").fetchall()
    assert rows == [("Para conducir de noche",)], "the snapshot includes what was still in the write-ahead log"
    assert (restored / "secrets/credential_key").read_text() == "secreto ficticio"
    assert (restored / "compose.authentik.yaml").read_text() == "services: {}"
    assert (restored / "secrets/oidc-client-secret").read_text() == "synthetic"
    assert (restored / "extras/firma.jks").read_bytes() == b"clave de firma ficticia"
    assert not (restored / "secrets/backup.key").exists(), "the key never travels with what it protects"
    assert not (restored / "runtime/music").exists() and not (restored / "runtime/navidrome/cache").exists()
    # The source was only read.
    assert writer.execute("SELECT count(*) FROM playlists").fetchone() == (1,)


def test_the_second_run_only_copies_what_changed_and_never_deletes_from_the_mirror(lab):
    root, dest, writer = lab
    make(root, dest, datetime(2026, 11, 17, 3, 0, 0))
    (root / "runtime/music/user-a/Lúa Norte/Bajamar.m4a").unlink()
    (root / "runtime/music/user-a/Lúa Norte/Luz de enero.m4a").write_bytes(b"audio ficticio 333")
    writer.execute("INSERT INTO playlists VALUES ('Domingo')")
    writer.commit()
    report = make(root, dest, datetime(2026, 11, 18, 3, 0, 0))
    assert report["music"]["files_copied"] == 1 and report["music"]["only_in_mirror_kept"] == 1
    assert (dest / "musica/user-a/Lúa Norte/Bajamar.m4a").exists(), "a song deleted by mistake survives in the mirror"
    assert len(list((dest / "estado").glob("*.mhb"))) == 2


def test_old_state_archives_are_pruned_but_foreign_files_are_left_alone(lab):
    root, dest, _ = lab
    (dest / "estado").mkdir()
    (dest / "estado/notas.txt").write_text("no es una copia")
    for day in range(1, 6):
        make(root, dest, datetime(2026, 11, day, 3, 0, 0), keep=3)
    names = sorted(p.name for p in (dest / "estado").iterdir())
    assert names == ["armonia-20261103-030000.mhb", "armonia-20261104-030000.mhb", "armonia-20261105-030000.mhb", "notas.txt"]


def test_a_damaged_archive_or_a_wrong_key_is_detected(lab):
    root, dest, _ = lab
    archive = dest / "estado" / make(root, dest)["state"]["archive"]
    key = copia.read_key(root / "secrets/backup.key")
    assert copia.verify(archive, key)["databases"] == 1
    with pytest.raises(copia.Refused):
        copia.verify(archive, os.urandom(32))
    raw = bytearray(archive.read_bytes())
    raw[len(raw) // 2] ^= 1
    archive.write_bytes(raw)
    with pytest.raises(copia.Refused):
        copia.verify(archive, key)


def test_refusals(lab, tmp_path):
    root, dest, _ = lab
    key = root / "secrets/backup.key"
    with pytest.raises(copia.Refused, match="mismo disco"):
        copia.run(root, dest, key)
    with pytest.raises(copia.Refused, match="no existe"):
        copia.run(root, tmp_path / "sin-montar", key, allow_same_disk=True)
    inside = root / "copias"
    inside.mkdir()
    with pytest.raises(copia.Refused, match="dentro"):
        copia.run(root, inside, key, allow_same_disk=True)
    (root / "runtime/music-app/enlace").symlink_to(key)
    with pytest.raises(copia.Refused, match="enlaces"):
        make(root, dest)
    assert not list(dest.rglob("*.mhb")), "nothing half-made is left behind"


def test_it_waits_its_turn_when_a_deployment_or_another_copy_holds_the_lock(lab, capsys):
    root, dest, _ = lab
    with open(root / ".backup.lock", "w") as held:
        fcntl.flock(held, fcntl.LOCK_EX)
        code = copia.main(["run", "--root", str(root), "--dest", str(dest), "--allow-same-disk"])
    assert code == copia.BUSY and not (dest / "estado").exists()
    assert copia.main(["run", "--root", str(root), "--dest", str(dest), "--allow-same-disk"]) == 0


def test_external_runtime_mirror_and_state(lab, tmp_path, monkeypatch):
    root, dest, writer = lab
    writer.close()
    runtime = tmp_path / "separate disk"
    (root / "runtime").rename(runtime)
    monkeypatch.setenv("MUSIC_RUNTIME_DIR", str(runtime))
    with pytest.raises(copia.Refused, match="dentro"):
        make(root, runtime)
    report = make(root, dest)
    assert report["music"]["files_copied"] == 2
    assert report["state"]["databases"] == 1
    restored = tmp_path / "clone"
    restore(root, dest / "estado" / report["state"]["archive"], restored)
    assert (restored / "runtime/music-app/music.db").is_file()
    assert not (restored / "runtime/music").exists()
