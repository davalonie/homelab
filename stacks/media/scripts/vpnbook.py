"""Prepara los archivos de VPNBook y aplica cambios al túnel activo de Media."""

import fcntl
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import sys
import tempfile
from urllib.request import Request, urlopen


STACK = Path(__file__).resolve().parents[1]
STATE = STACK / "secrets/vpnbook"
LOGIN_URL = "https://www.vpnbook.com/freevpn/openvpn"


def download(url):
    request = Request(url, headers={"User-Agent": "homelab-media-vpnbook/1.0"})
    with urlopen(request, timeout=25) as response:
        return response.read(1024 * 1024).decode("utf-8")


def credentials(page):
    # La FAQ del proveedor incluye el usuario y la contraseña pública en JSON-LD.
    passwords = set(re.findall(r"\bUsername:\s*vpnbook\.\s*Password:\s*([A-Za-z0-9]{5,32})\.", page))
    if len(passwords) != 1:
        raise ValueError("VPNBook no publica una contraseña inequívoca en su FAQ.")
    return passwords.pop()


def client_profile(source, server, address):
    if not re.search(rf"^remote[ \t]+{re.escape(server)}[ \t]+443[ \t]*$", source, re.MULTILINE):
        raise ValueError("El perfil recibido no corresponde al servidor VPNBook elegido.")

    # Construimos las directivas localmente. Del proveedor sólo se importan los PEM.
    profile = (
        f"client\ndev tun0\nproto tcp-client\nremote {address} 443\nnobind\n"
        "persist-key\npersist-tun\nauth-user-pass\nremote-cert-tls server\n"
        "auth SHA256\ndata-ciphers AES-256-GCM:AES-128-GCM\nredirect-gateway def1\n"
    )
    for tag, label in (("ca", "CERTIFICATE"), ("cert", "CERTIFICATE"), ("key", "(?:(?:RSA|EC) )?PRIVATE KEY")):
        blocks = re.findall(rf"<{tag}>\s*(.*?)\s*</{tag}>", source, re.DOTALL)
        pem = rf"-----BEGIN ({label})-----\n[A-Za-z0-9+/=\n]+\n-----END \1-----"
        if len(blocks) != 1 or not re.fullmatch(pem, blocks[0]):
            raise ValueError(f"Bloque PEM inválido en el perfil de VPNBook ({tag}).")
        profile += f"<{tag}>\n{blocks[0]}\n</{tag}>\n"
    return profile


def fetch(server):
    if not re.fullmatch(r"[a-z]{2}[0-9]+\.vpnbook\.com", server):
        raise ValueError("MEDIA_VPNBOOK_SERVER debe ser un servidor del catálogo de VPNBook.")
    password = credentials(download(LOGIN_URL))
    source = download(f"https://www.vpnbook.com/api/openvpn?hostname={server}&protocol=tcp443").replace("\r\n", "\n")
    records = socket.getaddrinfo(server, 443, socket.AF_INET, socket.SOCK_STREAM)
    addresses = {ipaddress.IPv4Address(record[4][0]) for record in records}
    public = sorted(address for address in addresses if address.is_global)
    if not public:
        raise ValueError("El DNS del servidor VPN no devuelve una IPv4 pública.")
    return client_profile(source, server, public[0]), password


def stage(state, profile, password):
    digest = hashlib.sha256((profile + "\0" + password).encode()).hexdigest()
    name = f"rev-{digest}"
    if not (state / name).exists():
        with tempfile.TemporaryDirectory(dir=state) as tmp:
            directory = Path(tmp)
            (directory / "profile.ovpn").write_text(profile)
            (directory / "password").write_text(password + "\n")
            (directory / "generation.env").write_text(f"VPNBOOK_REVISION={digest}\n")
            directory.rename(state / name)
    return name


def point(link, name):
    if link.is_symlink() and os.readlink(link) == name:
        return
    pending = link.with_suffix(".next")
    pending.unlink(missing_ok=True)
    pending.symlink_to(name)
    pending.replace(link)


def compose(*args, capture=False):
    result = subprocess.run(["docker", "compose", *args], cwd=STACK, check=True,
                            text=True, stdout=subprocess.PIPE if capture else None)
    return result.stdout


def deployment():
    config = json.loads(compose("config", "--format", "json", "gluetun", capture=True))
    settings = config["services"]["gluetun"]
    mounts = {v["target"]: v["source"] for v in settings.get("volumes", [])}
    if settings["environment"].get("VPN_TYPE") != "openvpn" or mounts.get("/vpnbook") != str(STATE / "current"):
        raise ValueError("Selecciona compose.yaml:compose.vpnbook.yaml en COMPOSE_FILE del .env.")

    rows = compose("ps", "--all", "--format", "json", "gluetun", "qbittorrent", capture=True).strip()
    containers = json.loads(rows) if rows.startswith("[") else [json.loads(line) for line in rows.splitlines()]
    states = {c["Service"]: c["State"] for c in containers}
    live = {"running", "restarting"}
    services = []
    if states.get("gluetun") in live:
        services.append("gluetun")
    if states.get("qbittorrent") in live or (services and states.get("qbittorrent") == "created"):
        services = ["gluetun", "qbittorrent"]
    return settings["labels"]["homelab.vpnbook.server"], services


def apply(services):
    compose("up", "-d", "--wait", "--wait-timeout", "90", "--pull", "never", *services)


def refresh(state, server, services):
    current = state / "current"
    confirmed = state / "confirmed"
    pending = state / "pending.json"
    previous = os.readlink(current) if current.is_symlink() else None
    fallback = os.readlink(confirmed) if confirmed.is_symlink() else previous
    if pending.exists():
        transaction = json.loads(pending.read_text())
        services = transaction["services"]
        fallback = transaction["fallback"]
    try:
        candidate = stage(state, *fetch(server))
    except (OSError, ValueError):
        if pending.exists() and fallback:
            point(current, fallback)
            apply(services)
            pending.unlink()
        raise
    if services:
        # Compose puede haber detenido ambos contenedores cuando se interrumpe una rotación.
        temp = pending.with_suffix(".next")
        temp.write_text(json.dumps({"services": services, "fallback": fallback}))
        temp.replace(pending)
    point(current, candidate)
    if services:
        try:
            # Compose compara VPNBOOK_REVISION incluso tras una interrupción del proceso.
            apply(services)
        except subprocess.CalledProcessError:
            if fallback and fallback != candidate:
                print("Falló el túnel nuevo. Recuperando la configuración anterior.", file=sys.stderr, flush=True)
                point(current, fallback)
                apply(services)
                pending.unlink()
            raise
        point(confirmed, candidate)
        pending.unlink()

    keep = {candidate, previous, fallback}
    for directory in state.glob("rev-*"):
        if directory.name not in keep and re.fullmatch(r"rev-[a-f0-9]{64}", directory.name):
            shutil.rmtree(directory)
    print("VPNBook actualizado." if previous != candidate else "VPNBook sin cambios.")


def main():
    os.umask(0o077)
    STATE.mkdir(mode=0o700, parents=True, exist_ok=True)
    with (STATE / ".lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        refresh(STATE, *deployment())


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        sys.exit(f"VPNBook: {error}")
