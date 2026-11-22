"""Rutas y cuentas de una restauración aislada del stack de música."""
from contextlib import contextmanager
import json
from pathlib import Path
from urllib.parse import urlsplit

import httpx

STACK = Path(__file__).resolve().parents[2]


def open_restore(target, url):
    folder = target.resolve()
    if not folder.is_relative_to(STACK / "restores") or not (folder / "backup-manifest.json").is_file():
        raise ValueError("Indica una restauración en restores/ con su manifiesto.")
    origin = urlsplit(url)
    if (origin.scheme != "http" or origin.hostname != "127.0.0.1" or origin.username
            or origin.password or origin.port in (None, 18400) or origin.path not in ("", "/")
            or origin.query or origin.fragment):
        raise ValueError("Indica el puerto de bucle local dedicado a la restauración.")
    state = json.loads((folder / "secrets/bootstrap-users.json").read_text())
    return folder, state



@contextmanager
def account(url, name, state):
    with httpx.Client(base_url=url, trust_env=False, timeout=20) as client:
        auth = client.post("/api/login", json={"username": name, "password": state[name]})
        auth.raise_for_status()
        identity = auth.json()
        client.headers.update({"X-Session-Id": identity["sessionId"], "X-Music-Owner": identity["userId"]})
        try:
            yield client, identity["userId"]
        finally:
            client.post("/api/logout").raise_for_status()
        assert client.get("/api/me").status_code == 401
