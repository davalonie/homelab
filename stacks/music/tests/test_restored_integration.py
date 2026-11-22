"""Verifica que el ensayo utiliza las cuentas y rutas de la restauración elegida."""
from contextlib import closing
import json
from pathlib import Path
import sqlite3
import sys

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent / "integration"))
import deep_restore_snapshot
import restauracion
import verify_restore


def test_reports_use_the_restored_accounts_and_content(tmp_path, monkeypatch):
    monkeypatch.setattr(restauracion, "STACK", tmp_path)
    clone = tmp_path / "restores/ensayo"
    for directory in ("secrets", "runtime/music", "runtime/music-app", "config"):
        (clone / directory).mkdir(parents=True)
    (clone / "backup-manifest.json").write_text("{}")
    (clone / "secrets/bootstrap-users.json").write_text(json.dumps({"_users": ["carol"], "carol": "ficticia"}))
    (clone / "secrets/integrations.json").write_text(json.dumps({"users": {"fixture": {}}}))
    with closing(sqlite3.connect(clone / "runtime/music-app/music.db")) as db:
        db.execute("CREATE TABLE playlists (id TEXT, owner TEXT)")
        db.execute("INSERT INTO playlists VALUES ('lista', 'fixture')")
        db.commit()

    def response(request):
        path = request.url.path
        if path == "/api/login":
            assert json.loads(request.content)["username"] == "carol"
            return httpx.Response(200, json={"sessionId": "fixture", "userId": "fixture"})
        assert request.headers["X-Music-Owner"] == "fixture"
        endpoints = {
            "/api/mixed-playlists": {"playlists": [{"id": "lista"}]},
            "/api/mixed-playlists/lista": {"id": "lista", "items": []},
            "/api/listening/top/artists": [], "/api/discover/flows": [], "/api/logout": {},
        }
        if path == "/api/me":
            return httpx.Response(401)
        return httpx.Response(200, json=endpoints[path])

    client = httpx.Client
    monkeypatch.setattr(restauracion.httpx, "Client", lambda **kw: client(transport=httpx.MockTransport(response), **kw))
    url = "http://127.0.0.1:19400"
    verify_restore.verify(clone, url)
    baseline = deep_restore_snapshot.fingerprints(clone, url)
    assert deep_restore_snapshot.fingerprints(clone, url) == baseline
    (clone / "runtime/music/pista").write_bytes(b"fixture")
    after = deep_restore_snapshot.fingerprints(clone, url)
    assert {k for k in baseline if baseline[k] != after[k]} == {"music"}
    with pytest.raises(ValueError):
        restauracion.open_restore(clone, "http://127.0.0.1:18400")
    with pytest.raises(ValueError):
        restauracion.open_restore(tmp_path, url)
