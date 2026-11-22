"""Restore failure paths use synthetic archives and never invoke Docker."""
import base64
import io
import os
from pathlib import Path
import subprocess
import sys
import tarfile

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/backup.py'


def archive(tmp_path, name='runtime/music/song.txt', symlink=False):
    key = os.urandom(32)
    keyfile = tmp_path / 'key'
    keyfile.write_bytes(base64.urlsafe_b64encode(key))
    data = io.BytesIO()
    with tarfile.open(fileobj=data, mode='w:gz') as tar:
        entry = tarfile.TarInfo(name)
        if symlink:
            entry.type = tarfile.SYMTYPE
            entry.linkname = '/etc/passwd'
        else:
            entry.size = 7
        tar.addfile(entry, None if symlink else io.BytesIO(b'fixture'))
    nonce = os.urandom(12)
    file = tmp_path / 'copy.mhb'
    file.write_bytes(b'MUSIC-HOMELAB-1\n' + nonce + AESGCM(key).encrypt(nonce, data.getvalue(), None))
    return file, keyfile


def restore(file, key, dest):
    return subprocess.run([sys.executable, str(SCRIPT), 'restore', str(file), '--key', str(key), '--target', str(dest)],
                          capture_output=True, timeout=10)


def test_valid_archive_and_existing_target_protection(tmp_path):
    file, key = archive(tmp_path)
    dest = tmp_path / 'restore'
    assert restore(file, key, dest).returncode == 0
    assert (dest / 'runtime/music/song.txt').read_bytes() == b'fixture'
    assert restore(file, key, dest).returncode != 0
    assert (dest / 'runtime/music/song.txt').read_bytes() == b'fixture'


def test_altered_or_truncated_archive_never_creates_target(tmp_path):
    file, key = archive(tmp_path)
    content = bytearray(file.read_bytes())
    content[-1] ^= 1
    file.write_bytes(content)
    dest = tmp_path / 'restore'
    assert restore(file, key, dest).returncode != 0 and not dest.exists()
    file.write_bytes(content[:25])
    assert restore(file, key, dest).returncode != 0 and not dest.exists()


def test_wrong_key_never_creates_target(tmp_path):
    file, key = archive(tmp_path)
    key.write_bytes(base64.urlsafe_b64encode(os.urandom(32)))
    dest = tmp_path / 'restore'
    assert restore(file, key, dest).returncode != 0 and not dest.exists()


def test_traversal_and_symbolic_links_rejected_even_with_valid_authentication(tmp_path):
    for name, symlink in [('../outside', False), ('/absolute', False), ('link', True)]:
        file, key = archive(tmp_path, name, symlink)
        dest = tmp_path / 'restore'
        assert restore(file, key, dest).returncode != 0 and not dest.exists()
