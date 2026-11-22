"""Compara el contenido lógico de una misma restauración antes y después de un cambio."""
import argparse
import hashlib
import json
from pathlib import Path

from restauracion import STACK, account, open_restore


def fingerprints(target, url):
    restored, users = open_restore(target, url)
    snapshot = {"users": {}, "music": {}, "config": {}}
    for name in users["_users"]:
        with account(url, name, users) as (client, owner):
            lists = client.get("/api/mixed-playlists").raise_for_status().json()["playlists"]
            details = [client.get("/api/mixed-playlists/" + p["id"]).raise_for_status().json() for p in lists]
            artists = client.get("/api/listening/top/artists", params={"period": "all_time"})
            snapshot["users"][name] = {
                "id": owner, "playlists": sorted(details, key=lambda p: p["id"]),
                "artists": artists.raise_for_status().json(),
            }
            client.get("/api/discover/flows").raise_for_status()

    for group, path in (("music", "runtime/music"), ("config", "config")):
        folder = restored / path
        for file in sorted(folder.rglob("*")):
            if file.is_file():
                with file.open("rb") as source:
                    snapshot[group][str(file.relative_to(folder))] = hashlib.file_digest(source, "sha256").hexdigest()
    return {group: hashlib.sha256(json.dumps(items, sort_keys=True).encode()).hexdigest()
            for group, items in snapshot.items()}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("label")
    parser.add_argument("--target", type=Path, required=True)
    parser.add_argument("--url", required=True)
    parser.add_argument("--compare", type=Path, help="Instantánea de esta campaña para la comparación")
    args = parser.parse_args()
    if not args.label.replace("-", "").isalnum():
        parser.error("Etiqueta inválida.")
    report = fingerprints(args.target, args.url)
    if args.compare and report != json.loads(args.compare.read_text()):
        raise SystemExit("El contenido de la restauración ha cambiado.")
    folder = STACK / "runtime/mediciones"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{args.label}.json").write_text(json.dumps(report, indent=2))
    print("Verificadas las huellas de las cuentas, listas, escuchas, música y configuración del clon.")
