#!/usr/bin/env python3
"""Consistent encrypted backups; restore only into a new project directory.

Requires Python cryptography. The backup key is NEVER included in its archive.
No database is edited directly. All application writers are stopped for capture.
"""
import argparse
import base64
from contextlib import contextmanager
import fcntl
import hashlib
import io
import json
import os
import signal
import stat
from pathlib import Path
import subprocess
import tarfile
import tempfile
from datetime import datetime, timezone

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from runtime_path import check_runtime_mount, runtime_dir

ROOT=Path(__file__).resolve().parents[1]
MAGIC=b'MUSIC-HOMELAB-1\n'
os.umask(0o077)
p=argparse.ArgumentParser()
p.add_argument('operation',choices=('create','restore'))
p.add_argument('archive',type=Path)
p.add_argument('--target',type=Path)
p.add_argument('--key',type=Path,default=ROOT/'secrets/backup.key')
p.add_argument('--project',default='music-homelab')
p.add_argument('--docker-config',type=Path)
a=p.parse_args()
key=base64.urlsafe_b64decode(a.key.read_bytes().strip())
if len(key)!=32:raise SystemExit('Backup key must contain 32 random bytes (base64).')
archive=a.archive.resolve()


def docker(*args):
    cmd=['docker']
    if a.docker_config:cmd+=['--config',str(a.docker_config)]
    return subprocess.check_output(cmd+list(args),text=True,stderr=subprocess.STDOUT,timeout=120)


class EncryptedWriter:
    def __init__(self,stream,cipher):self.stream=stream;self.cipher=cipher
    def write(self,data):self.stream.write(self.cipher.update(data));return len(data)
    def flush(self):self.stream.flush()


def interrupted(signum, frame):
    raise KeyboardInterrupt('Backup interrupted')


@contextmanager
def project_backup_lock():
    # One installation may have several Compose project aliases. Keep the lock
    # outside the captured directories and never unlink it: another process may
    # already have opened the inode. Closing the descriptor releases flock.
    fd=os.open(ROOT/'.backup.lock',os.O_CREAT|os.O_RDWR|os.O_CLOEXEC|os.O_NOFOLLOW,0o600)
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise RuntimeError('Backup lock must be a regular file')
        try:
            fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise RuntimeError('A backup is already running for this installation') from error
        yield
    finally:
        os.close(fd)


if a.operation=='create':
    signal.signal(signal.SIGTERM, interrupted)
    included = ('runtime','secrets','config','tests/fixtures','scripts','compose.yaml','compose.dev.yaml','compose.authentik.yaml','compose.lab.yaml',
                'compose.phone.local.yaml','compose.metadata.yaml','compose.metadata-test.yaml','compose.gateway-test.yaml','.env','versions.lock')
    runtime = runtime_dir(ROOT)
    if not (runtime / "music").is_dir():
        raise ValueError("Missing runtime/music; check the data mount")
    sources = {name: runtime if name == 'runtime' else ROOT / name for name in included}
    if any(archive.is_relative_to(path.resolve()) for path in sources.values()):
        raise ValueError('Backup destination must be outside the source directories')
    if archive.exists():
        raise FileExistsError('Backup already exists')
    archive.parent.mkdir(parents=True,exist_ok=True)
    # Publish a complete authenticated archive atomically; never replace a backup.
    with project_backup_lock(), tempfile.TemporaryDirectory(prefix='.music-backup-', dir=archive.parent) as staging:
        with (Path(staging) / 'archive').open('xb') as out:
            nonce=os.urandom(12)
            enc=Cipher(algorithms.AES(key),modes.GCM(nonce)).encryptor()
            out.write(MAGIC+nonce)
            ids = docker('ps', '--filter', 'label=com.docker.compose.project=' + a.project, '-q').split()
            if not ids:
                raise RuntimeError('No running containers found for the selected project; verify the project name.')
            containers = json.loads(docker('inspect', *ids))
            if any(Path(c['Config']['Labels']['com.docker.compose.project.working_dir']).resolve() != ROOT for c in containers):
                raise RuntimeError('Selected project belongs to another directory')
            for container in containers:
                check_runtime_mount(container, runtime)
            try:
                docker('stop', *ids)
                refs={c['Config']['Labels']['com.docker.compose.service']: c['Image'] for c in containers}
                manifest=json.dumps({'created':datetime.now(timezone.utc).isoformat(),'images':refs},indent=2).encode()
                with tarfile.open(fileobj=EncryptedWriter(out,enc),mode='w|gz', dereference=True) as tar:
                    info=tarfile.TarInfo('backup-manifest.json');info.size=len(manifest);info.mode=0o600
                    tar.addfile(info,io.BytesIO(manifest))
                    for name, src in sources.items():
                        if not src.exists():continue
                        paths=[src]+sorted(src.rglob('*')) if src.is_dir() else [src]
                        for item in paths:
                            rel=Path(name) / item.relative_to(src)
                            if item==a.key.resolve() or rel.parts[:2]==('runtime','cache'):continue
                            if item.is_symlink():raise RuntimeError('Backup refuses symbolic links; use real dedicated music directories.')
                            if not (stat.S_ISREG(item.stat().st_mode) or item.is_dir()):
                                raise RuntimeError('Backup accepts only regular files and directories')
                            tar.add(item,arcname=str(rel),recursive=False)
                out.write(enc.finalize());out.write(enc.tag);out.flush();os.fsync(out.fileno())
            finally:
                docker('start', *ids)  # Preserve which containers were running, including optional profiles.
        os.link(Path(staging) / 'archive', archive)
        fd = os.open(archive.parent, os.O_RDONLY | os.O_DIRECTORY)
        try: os.fsync(fd)
        finally: os.close(fd)
    with archive.open('rb') as source:
        digest=hashlib.file_digest(source,'sha256').hexdigest()
    print(json.dumps({'archive':str(archive),'sha256':digest,'consistent':True}))
else:
    if not a.target:raise SystemExit('--target is required for restore')
    dest=a.target.resolve()
    if dest.exists():raise SystemExit('Restore target must not exist; existing installations are never overwritten.')
    with archive.open('rb') as src,tempfile.TemporaryFile() as clear:
        if archive.stat().st_size < len(MAGIC)+12+16:
            raise SystemExit('Truncated backup')
        if src.read(len(MAGIC))!=MAGIC:raise SystemExit('Unsupported backup format')
        nonce=src.read(12)
        src.seek(-16,2);tag=src.read(16);size=src.tell()-len(MAGIC)-12-16
        dec=Cipher(algorithms.AES(key),modes.GCM(nonce,tag)).decryptor()
        src.seek(len(MAGIC)+12)
        while size>0:
            chunk=src.read(min(size,1024**2))
            if not chunk:raise SystemExit('Truncated backup')
            size-=len(chunk);clear.write(dec.update(chunk))
        clear.write(dec.finalize()) # Authenticate completely before touching target.
        clear.seek(0)
        with tarfile.open(fileobj=clear,mode='r:gz') as tar:
            for member in tar.getmembers():
                rel=Path(member.name)
                if rel.is_absolute() or '..' in rel.parts or not (member.isfile() or member.isdir()):
                    raise RuntimeError('Unsafe archive member')
            dest.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory(prefix='.music-restore-', dir=dest.parent) as staging:
                complete = Path(staging) / 'complete'
                complete.mkdir(mode=0o700)
                tar.extractall(complete, filter='data')
                (complete/'runtime/cache').mkdir(parents=True, exist_ok=True)
                # Restored projects must never inherit a live absolute data path.
                env = complete / ".env"
                if env.exists():
                    with env.open("a") as out:
                        out.write("\nMUSIC_RUNTIME_DIR=./runtime\n")
                # Reserve a new destination; never replace an existing directory.
                dest.mkdir(mode=0o700)
                try:
                    os.replace(complete, dest)
                except BaseException:
                    dest.rmdir()  # only the empty directory just reserved above
                    raise
    print(json.dumps({'restored':str(dest),'authenticated':True,'services_started':False}))
