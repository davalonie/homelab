#!/usr/bin/env python3
"""Create local directories/secrets only when absent. Never replace existing values."""
import base64
import json
import os
import secrets
from pathlib import Path

root = Path(__file__).resolve().parents[1]
os.umask(0o077)
for name in ('music-app', 'music', 'navidrome', 'koito-alice', 'koito-bob', 'koito-carol', 'aurral', 'cache'):
    (root / 'runtime' / name).mkdir(parents=True, exist_ok=True)
for name in ('shared', 'alice', 'bob', 'carol'):
    (root / 'runtime/music' / name).mkdir(parents=True, exist_ok=True)
(root / 'secrets').mkdir(exist_ok=True, mode=0o700)
values = {'credential.key': base64.urlsafe_b64encode(secrets.token_bytes(32)).decode(),
          'backup.key': base64.urlsafe_b64encode(secrets.token_bytes(32)).decode(),
          'integrations.json': json.dumps({'aurral_url': 'http://aurral:3001', 'bridge_origin': 'http://music:8001', 'users': {}})}
for name in ('koito-alice.password', 'koito-bob.password', 'koito-carol.password', 'aurral-admin.password', 'aurral.key', 'metadata-proxy.key'):
    values[name] = secrets.token_urlsafe(40)
for name in ('koito-alice.token', 'koito-bob.token', 'koito-carol.token', 'lastfm-api.key'):
    values[name] = ''  # Rellenar durante el aprovisionamiento de Koito o el registro en Last.fm.
for name, value in values.items():
    path = root / 'secrets' / name
    try:
        with path.open('x') as f:
            f.write(value + '\n')
    except FileExistsError:
        pass
print('Local directories and missing secret files prepared; no services started.')
catalog = root / 'config/sources.json'
if not catalog.exists():
    with catalog.open('x') as out:
        out.write((root / 'config/sources.example.json').read_text())
