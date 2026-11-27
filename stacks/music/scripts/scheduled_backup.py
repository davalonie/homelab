#!/usr/bin/env python3
"""Copia programada sin parar los servicios: estado cifrado + espejo incremental de la música.

    scheduled_backup.py run --dest /ruta/al/disco/externo [--keep 14] [--extra archivo ...]
    scheduled_backup.py verify /ruta/estado/armonia-AAAAMMDD-HHMMSS.mhb

Qué guarda en el destino:

  estado/armonia-<fecha>.mhb   Archivo cifrado (mismo formato que backup.py, se restaura con
                               `backup.py restore`): una instantánea coherente de cada base de
                               datos SQLite tomada con la API de copia en línea, más secretos,
                               configuración, compose y los archivos sueltos pasados con --extra
                               (por ejemplo la clave de firma de la APK). Sin música ni cachés.
  musica/                      Espejo de runtime/music. Solo se copian archivos nuevos o
                               cambiados; nunca se borra nada del espejo.
  ultimo-informe.json          Recuentos de la última ejecución (sin nombres de canciones).

La clave de cifrado (secrets/backup.key) NUNCA se copia: sin ella el estado no se puede leer.
Guárdala aparte. Las bases se leen en modo de solo lectura; no se detiene ningún servicio.
"""
import argparse
import base64
import fcntl
import hashlib
import io
import json
import os
import re
import shutil
import sqlite3
import sys
import tarfile
import tempfile
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from runtime_path import runtime_dir

MAGIC = b"MUSIC-HOMELAB-1\n"  # backup.py's format: MAGIC + nonce + AES-256-GCM(tar.gz) + tag
INCLUDED = ("runtime", "secrets", "config", "tests/fixtures", "scripts", "compose.yaml", "compose.dev.yaml", "compose.lab.yaml",
            "compose.phone.local.yaml", "compose.metadata-test.yaml", "compose.gateway-test.yaml",
            "compose.metadata.yaml", ".env", "versions.lock")
# Never in the state archive: the music has its own mirror, caches are rebuilt.
SKIPPED_DIRS = (("runtime", "music"), ("runtime", "cache"), ("runtime", "navidrome", "cache"))
ARCHIVE_NAME = re.compile(r"armonia-\d{8}-\d{6}\.mhb")
SQLITE_HEADER = b"SQLite format 3\x00"
BUSY, FAILED = 75, 1


class Refused(Exception):
    """The copy was not attempted or not completed; the message says why."""


class _Encrypted:
    def __init__(self, stream, cipher):
        self.stream, self.cipher = stream, cipher

    def write(self, data):
        self.stream.write(self.cipher.update(data))
        return len(data)

    def flush(self):
        self.stream.flush()


@contextmanager
def installation_lock(root):
    """The lock backup.py and the deployments use: only one capture per installation."""
    fd = os.open(root / ".backup.lock", os.O_CREAT | os.O_RDWR | os.O_CLOEXEC | os.O_NOFOLLOW, 0o600)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise Refused("busy") from error
        yield
    finally:
        os.close(fd)


def read_key(path):
    key = base64.urlsafe_b64decode(Path(path).read_bytes().strip())
    if len(key) != 32:
        raise Refused("la clave de copia debe contener 32 bytes aleatorios (base64)")
    return key


def is_sqlite(path):
    try:
        with path.open("rb") as handle:
            return handle.read(16) == SQLITE_HEADER
    except OSError:
        return False


def snapshot(database, folder):
    """A consistent copy of a live database, taken through SQLite itself and then checked."""
    target = Path(folder) / hashlib.sha256(str(database).encode()).hexdigest()
    source = sqlite3.connect(database.as_uri() + "?mode=ro", uri=True, timeout=30)
    try:
        copy = sqlite3.connect(target)
        try:
            source.backup(copy)
            verdict = copy.execute("PRAGMA integrity_check").fetchone()[0]
        finally:
            copy.close()
    finally:
        source.close()
    if verdict != "ok":
        raise Refused(f"la instantánea de {database.name} no supera la comprobación de integridad")
    return target


def state_files(root, runtime, key_path):
    """Every file of the state archive as (path, name inside the archive)."""
    for name in INCLUDED:
        source = runtime if name == "runtime" else root / name
        if not source.exists():
            continue
        for item in ([source] + sorted(source.rglob("*")) if source.is_dir() else [source]):
            rel = Path(name) / item.relative_to(source)
            if any(rel.parts[:len(skip)] == skip for skip in SKIPPED_DIRS) or item == key_path:
                continue
            if "__pycache__" in rel.parts or item.name.endswith(("-wal", "-shm", "-journal")):
                continue
            if item.is_symlink():
                raise Refused("la copia no admite enlaces simbólicos en el estado")
            if item.is_file():
                yield item, str(rel)


def write_state(root, runtime, key, key_path, archive, extras):
    databases = 0
    archive.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".copia-", dir=archive.parent) as staging:
        partial = Path(staging) / "archive"
        with partial.open("xb") as out:
            nonce = os.urandom(12)
            cipher = Cipher(algorithms.AES(key), modes.GCM(nonce)).encryptor()
            out.write(MAGIC + nonce)
            manifest = json.dumps({"created": datetime.now(UTC).isoformat(), "kind": "scheduled",
                                   "music": "mirrored separately", "services_stopped": False}, indent=2).encode()
            with tarfile.open(fileobj=_Encrypted(out, cipher), mode="w|gz") as tar:
                info = tarfile.TarInfo("backup-manifest.json")
                info.size, info.mode = len(manifest), 0o600
                tar.addfile(info, io.BytesIO(manifest))
                for item, name in state_files(root, runtime, key_path):
                    if is_sqlite(item):
                        tar.add(snapshot(item, staging), arcname=name, recursive=False)
                        databases += 1
                    else:
                        tar.add(item, arcname=name, recursive=False)
                for extra in extras:
                    if extra in (key_path, root / "secrets/backup.key"):
                        raise Refused("la clave de copia debe guardarse aparte")
                    if not extra.is_file() or extra.is_symlink():
                        raise Refused(f"--extra debe ser un archivo normal: {extra.name}")
                    tar.add(extra, arcname=f"extras/{extra.name}", recursive=False)
            out.write(cipher.finalize())
            out.write(cipher.tag)
            out.flush()
            os.fsync(out.fileno())
        os.replace(partial, archive)
    return databases


def verify(archive, key):
    """Authenticate the whole archive and list it. Raises when it is damaged or the key is wrong."""
    size = archive.stat().st_size - len(MAGIC) - 12 - 16
    if size < 0:
        raise Refused("archivo truncado")
    with archive.open("rb") as source, tempfile.TemporaryFile() as clear:
        if source.read(len(MAGIC)) != MAGIC:
            raise Refused("formato de copia no reconocido")
        nonce = source.read(12)
        source.seek(-16, 2)
        tag = source.read(16)
        cipher = Cipher(algorithms.AES(key), modes.GCM(nonce, tag)).decryptor()
        source.seek(len(MAGIC) + 12)
        while size > 0:
            chunk = source.read(min(size, 1024 ** 2))
            if not chunk:
                raise Refused("archivo truncado")
            size -= len(chunk)
            clear.write(cipher.update(chunk))
        try:
            clear.write(cipher.finalize())
        except Exception as error:
            raise Refused("el archivo no se autentica: dañado o clave equivocada") from error
        clear.seek(0)
        with tarfile.open(fileobj=clear, mode="r:gz") as tar:
            names = tar.getnames()
    return {"files": len(names), "databases": sum(n.endswith(".db") for n in names),
            "extras": sum(n.startswith("extras/") for n in names)}


def pending_music(source, mirror):
    """Files to copy (new, or different in size or time) and what the mirror has that the source lost."""
    todo, present = [], set()
    if source.is_dir():
        for item in sorted(source.rglob("*")):
            if item.is_symlink() or not item.is_file():
                continue
            rel = item.relative_to(source)
            present.add(rel)
            info, copy = item.stat(), mirror / rel
            try:
                kept = copy.stat()
            except FileNotFoundError:
                kept = None
            if kept is None or kept.st_size != info.st_size or int(kept.st_mtime) != int(info.st_mtime):
                todo.append((item, copy, info))
    only_in_mirror = 0
    if mirror.is_dir():
        only_in_mirror = sum(1 for item in mirror.rglob("*")
                             if item.is_file() and not item.name.startswith(".parcial-")
                             and item.relative_to(mirror) not in present)
    return todo, len(present), only_in_mirror


def copy_music(todo):
    copied = 0
    for item, copy, info in todo:
        copy.parent.mkdir(parents=True, exist_ok=True)
        partial = copy.parent / f".parcial-{copy.name}"
        with item.open("rb") as source, partial.open("wb") as target:
            shutil.copyfileobj(source, target, 1024 ** 2)
            target.flush()
            os.fsync(target.fileno())
        if partial.stat().st_size != info.st_size:
            partial.unlink()
            raise Refused("un archivo de música cambió mientras se copiaba; repite la copia")
        os.utime(partial, (info.st_atime, info.st_mtime))
        os.replace(partial, copy)
        copied += info.st_size
    return copied


def prune(folder, keep):
    archives = sorted(p for p in folder.iterdir() if p.is_file() and ARCHIVE_NAME.fullmatch(p.name))
    removed = archives[:-keep] if keep > 0 else []
    for old in removed:
        old.unlink()
    return len(removed)


def run(root, dest, key_path, keep=14, extras=(), allow_same_disk=False, now=None):
    root, dest, key_path = Path(root).resolve(), Path(dest).resolve(), Path(key_path).resolve()
    key = read_key(key_path)
    if not dest.is_dir():
        raise Refused("el destino no existe o no está montado")
    runtime = runtime_dir(root)
    if not (runtime / "music").is_dir():
        raise Refused("falta runtime/music; verifica el montaje de datos")
    if dest.is_relative_to(root) or dest.is_relative_to(runtime) or runtime.is_relative_to(dest):
        raise Refused("el destino no puede estar dentro de la instalación")
    if dest.stat().st_dev in (root.stat().st_dev, runtime.stat().st_dev) and not allow_same_disk:
        raise Refused("el destino está en el mismo disco que la instalación: no protege de un fallo del disco")
    stamp = (now or datetime.now()).strftime("%Y%m%d-%H%M%S")
    with installation_lock(root):
        todo, songs, only_in_mirror = pending_music(runtime / "music", dest / "musica")
        needed = sum(info.st_size for _, _, info in todo)
        state_size = sum(item.stat().st_size for item, _ in state_files(root, runtime, key_path))
        free = shutil.disk_usage(dest).free
        if needed + state_size + 64 * 1024 ** 2 > free:
            raise Refused(f"no hay espacio en el destino: hacen falta {(needed + state_size) // 1024 ** 2} MB "
                          f"y quedan {free // 1024 ** 2} MB")
        archive = dest / "estado" / f"armonia-{stamp}.mhb"
        if archive.exists():
            raise Refused("ya existe una copia con esta fecha y hora")
        databases = write_state(root, runtime, key, key_path, archive, [Path(e).resolve() for e in extras])
        checked = verify(archive, key)
        copied = copy_music(todo)
        removed = prune(archive.parent, keep)
        with archive.open("rb") as source:
            digest = hashlib.file_digest(source, "sha256").hexdigest()
    report = {
        "finished": datetime.now(UTC).isoformat(), "ok": True,
        "state": {"archive": archive.name, "sha256": digest, "bytes": archive.stat().st_size,
                  "databases": databases, "verified": checked, "old_archives_removed": removed},
        "music": {"files_in_library": songs, "files_copied": len(todo), "bytes_copied": copied,
                  "only_in_mirror_kept": only_in_mirror},
        "key_included": False, "services_stopped": False,
    }
    (dest / "ultimo-informe.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


def main(argv=None):
    os.umask(0o077)
    here = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    make = commands.add_parser("run")
    make.add_argument("--dest", type=Path, required=True)
    make.add_argument("--keep", type=int, default=14)
    make.add_argument("--extra", type=Path, action="append", default=[])
    make.add_argument("--root", type=Path, default=here)
    make.add_argument("--key", type=Path)
    make.add_argument("--allow-same-disk", action="store_true")
    check = commands.add_parser("verify")
    check.add_argument("archive", type=Path)
    check.add_argument("--key", type=Path, default=here / "secrets/backup.key")
    args = parser.parse_args(argv)
    try:
        if args.command == "verify":
            print(json.dumps({"authenticated": True, **verify(args.archive, read_key(args.key))}))
        else:
            print(json.dumps(run(args.root, args.dest, args.key or args.root / "secrets/backup.key",
                                 args.keep, args.extra, args.allow_same_disk), indent=2))
    except Refused as refused:
        if str(refused) == "busy":
            print("Otra copia o un despliegue está en curso; se reintentará en la próxima ejecución.", file=sys.stderr)
            return BUSY
        print(f"Copia no realizada: {refused}", file=sys.stderr)
        return FAILED
    return 0


if __name__ == "__main__":
    sys.exit(main())
