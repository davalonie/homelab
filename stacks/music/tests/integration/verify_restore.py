"""Comprueba las cuentas y los datos de una restauración en funcionamiento."""
import argparse
from contextlib import closing
import json
from pathlib import Path
import sqlite3

from restauracion import account, open_restore


def verify(target, url):
    restored, users = open_restore(target, url)
    config = json.loads((restored / "secrets/integrations.json").read_text())
    database = (restored / "runtime/music-app/music.db").as_uri() + "?mode=ro"
    with closing(sqlite3.connect(database, uri=True)) as connection:
        assert connection.execute("PRAGMA integrity_check").fetchone() == ("ok",)
        for name in users["_users"]:
            with account(url, name, users) as (client, owner):
                assert owner in config["users"]
                lists = client.get("/api/mixed-playlists").raise_for_status().json()["playlists"]
                rows = connection.execute("SELECT id FROM playlists WHERE owner = ?", (owner,))
                assert {item["id"] for item in lists} == {row[0] for row in rows}
                client.get("/api/listening/top/artists").raise_for_status()
                client.get("/api/discover/flows").raise_for_status()
    print("Verificadas las cuentas, las listas, la integridad de SQLite, Koito, Aurral y el cierre de sesión.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", required=True, type=Path)
    parser.add_argument("--url", required=True)
    args = parser.parse_args()
    verify(args.target, args.url)
