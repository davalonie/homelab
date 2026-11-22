#!/usr/bin/env python3
"""First-install bootstrap for the selected local Compose project. Uses upstream APIs only.
Requires the prepared, locally built Compose project. Never prints credentials.
Generated passwords are stored privately; no credentials are printed.
"""
import argparse
import json
import os
import secrets
import subprocess
from pathlib import Path

import httpx

parser = argparse.ArgumentParser()
parser.add_argument('--project', required=True)
parser.add_argument('--users', nargs='+', required=True, help='One to three new application usernames; stable order')
parser.add_argument('--docker-config', type=Path)
args = parser.parse_args()
import re
if not 1 <= len(args.users) <= 3 or len(set(args.users)) != len(args.users):
    parser.error('Choose one to three different users')
if any(not re.fullmatch(r'[a-z][a-z0-9_-]{1,31}', name) or name == 'admin' for name in args.users):
    parser.error('Usernames must be 2-32 lowercase letters/digits, underscore or hyphen; admin is reserved')
root = Path(__file__).resolve().parents[1]
os.umask(0o077)
statefile = root / 'secrets' / 'bootstrap-users.json'
slots = dict(zip(args.users, ('alice','bob','carol')))
if statefile.exists():
    state = json.loads(statefile.read_text())
    if state.get('_users') != args.users:
        parser.error('Existing bootstrap has different users/order; refusing to reassign identities')
else:
    state = {name: secrets.token_urlsafe(32) for name in ['admin'] + args.users}
    state['_users'] = args.users
    with statefile.open('x') as out:
        json.dump(state, out)


def client(service, port):
    docker = ['docker'] + (['--config', str(args.docker_config)] if args.docker_config else [])
    ids = subprocess.check_output(docker + ['ps','--filter','label=com.docker.compose.project='+args.project,
        '--filter','label=com.docker.compose.service='+service,'-q'],text=True).split()
    if len(ids) != 1:
        raise RuntimeError('Expected one running '+service+' container (third user needs --profile third-user)')
    info = json.loads(subprocess.check_output(docker + ['inspect', ids[0]], text=True))[0]
    if Path(info['Config']['Labels']['com.docker.compose.project.working_dir']).resolve() != root:
        raise RuntimeError('Selected project belongs to another directory')
    address = next(n['IPAddress'] for n in info['NetworkSettings']['Networks'].values() if n['IPAddress'])
    headers = {'Host': service} if service.startswith('koito') else {}
    return httpx.Client(base_url=f'http://{address}:{port}', headers=headers, timeout=20, trust_env=False, follow_redirects=False)


def check(response, codes=(200, 201, 204)):
    if response.status_code not in codes:
        raise RuntimeError(f'{response.request.method} {response.request.url.path}: HTTP {response.status_code}')
    return response.json() if response.content else None


nd = client('navidrome', 4533)
r = nd.post('/auth/createAdmin', json={'username': 'homelab-admin', 'password': state['admin']})
if r.status_code == 403:
    r = nd.post('/auth/login', json={'username': 'homelab-admin', 'password': state['admin']})
admin = check(r)
nd.headers['x-nd-authorization'] = 'Bearer ' + admin['token']
ndusers = check(nd.get('/api/user'))
libraries = check(nd.get('/api/library'))
ids = {}
for name, slot in slots.items():
    user = next((u for u in ndusers if u['userName'] == name), None)
    if user is None:
        user = check(nd.post('/api/user', json={'userName': name, 'name': name.title(), 'password': state[name], 'isAdmin': False}))
    else:
        # Never reassign the libraries of an unrelated account with the same name.
        check(nd.post('/auth/login', json={'username': name, 'password': state[name]}))
        if user.get('isAdmin'):
            raise RuntimeError('Refusing to repurpose an administrator account')
    ids[name] = user['id']
    library = next((lib for lib in libraries if lib['path'] == '/music/' + slot), None)
    if library is None:
        library = check(nd.post('/api/library', json={'name': name.title() + ' private',
            'path': '/music/' + slot, 'defaultNewUsers': False}))
    # POST native CRUD returns a string id; GET returns a numeric id.
    check(nd.put('/api/user/' + user['id'] + '/library', json={'libraryIds': [int(library['id'])]}))
print('Navidrome: non-admin application users provisioned through API')

ar = client('aurral', 3001)
adminpass = (root / 'secrets/aurral-admin.password').read_text().strip()
ar.headers['X-API-Key'] = (root / 'secrets/aurral.key').read_text().strip()
r = ar.post('/api/onboarding/complete', json={'authUser': 'homelab-admin', 'authPassword': adminpass,
    'security': {'localNetworkBypass': {'enabled': False}}, 'downloadFolderPath': '/config/library'})
check(r, codes=(200, 403))
admin = check(ar.post('/api/auth/login', json={'username': 'homelab-admin', 'password': adminpass}))
del ar.headers['X-API-Key']
ar.headers['Authorization'] = 'Bearer ' + admin['token']
users = check(ar.get('/api/users/'))
config = json.loads((root / 'secrets/integrations.json').read_text())
for name, slot in slots.items():
    remote = next((u for u in users if u['username'] == name), None)
    if remote is None:
        remote = check(ar.post('/api/users/', json={'username': name, 'password': state[name], 'role': 'user',
            'permissions': {'accessFlow': True, 'addArtist': False, 'addAlbum': False, 'deleteArtist': False,
                            'deleteAlbum': False, 'deleteTrack': False, 'changeMonitoring': False}}))
    else:
        own = check(ar.post('/api/auth/login', json={'username': name, 'password': state[name]}))
        check(ar.post('/api/auth/logout', headers={'Authorization': 'Bearer ' + own['token']}))
    kc = client('koito-' + slot, 4110)
    password = (root / 'secrets' / ('koito-' + slot + '.password')).read_text().strip()
    check(kc.post('/apis/web/v1/login', json={'username': slot, 'password': password}))
    tokenfile = root / 'secrets' / ('koito-' + slot + '.token')
    if not tokenfile.read_text().strip():
        key = check(kc.post('/apis/web/v1/user/apikeys', json={'label': 'Music Homelab private delivery'}))
        tokenfile.write_text(key['key'] + '\n')
    check(kc.post('/apis/web/v1/logout'))
    previous = config['users'].get(ids[name], {})
    config['users'][ids[name]] = {'aurral_user_id': remote['id'], 'koito_url': 'http://koito-' + slot + ':4110',
        'koito_token_file': '/run/secrets/koito_' + slot + '_token',
        'bridge_key': previous.get('bridge_key', secrets.token_urlsafe(32))}
    kc.close()
(root / 'secrets/integrations.json').write_text(json.dumps(config, indent=2))
print('Aurral: separate ordinary accounts with flow permission; Koito: separate credentials and instances')
check(ar.post('/api/auth/logout'))
ar.close()
nd.close()
print('Provisioning complete. Generated credentials remain only in secrets/bootstrap-users.json. Link each Aurral account in the application.')
