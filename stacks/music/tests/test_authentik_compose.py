"""Check the OIDC trust boundary after Compose merges the production overlays."""
import ipaddress
import json
import os
from pathlib import Path
import shutil
import subprocess

import pytest

STACK = Path(__file__).resolve().parents[1]


def test_optional_oidc_keeps_the_base_networks_and_secrets(tmp_path):
    if not shutil.which("docker") or subprocess.run(
        ["docker", "compose", "version"], capture_output=True
    ).returncode:
        pytest.skip("requires Docker Compose v2")
    files = ["compose.yaml", "compose.phone.local.yaml", "compose.metadata.yaml", "compose.authentik.yaml"]
    for filename in files:
        shutil.copyfile(STACK / filename, tmp_path / filename)
    shutil.copyfile(STACK / ".env.example", tmp_path / ".env")
    env = {k: v for k, v in os.environ.items() if not k.startswith(("MUSIC_", "COMPOSE_"))}

    def render(overlays):
        command = ["docker", "compose", "--profile", "third-user"]
        for filename in overlays:
            command.extend(["-f", filename])
        output = subprocess.check_output(command + ["config", "--format", "json"], cwd=tmp_path, env=env)
        return json.loads(output)

    base = render(files[:-1])
    assert "MUSIC_OIDC_ISSUER" not in base["services"]["music"]["environment"]
    assert "ND_EXTAUTH_TRUSTEDSOURCES" not in base["services"]["navidrome"]["environment"]
    assert "oidc_client_secret" not in base["secrets"]

    env.update(MUSIC_OIDC_ISSUER="https://identity.example.org/application/o/armonia/", MUSIC_OIDC_CLIENT_ID="example")
    model = render(files)
    assert model["services"].keys() == base["services"].keys()
    music = model["services"]["music"]
    original = base["services"]["music"]
    assert music["networks"].keys() == original["networks"].keys()
    assert {s["source"] for s in music["secrets"]} == {s["source"] for s in original["secrets"]} | {"oidc_client_secret"}
    assert music["environment"]["MUSIC_OIDC_SECRET_FILE"] == "/run/secrets/oidc_client_secret"
    library = model["networks"]["library"]
    assert library["internal"]
    config, = library["ipam"]["config"]
    proxy = ipaddress.ip_address(music["networks"]["library"]["ipv4_address"])
    assert proxy in ipaddress.ip_network(config["subnet"])
    assert proxy not in ipaddress.ip_network(config["ip_range"])
    nd = model["services"]["navidrome"]
    assert nd["environment"]["ND_EXTAUTH_TRUSTEDSOURCES"] == f"{proxy}/32"
    assert nd["environment"]["ND_EXTAUTH_USERHEADER"] == "X-Armonia-User"
    assert not nd.get("ports")
    for service in base["services"].keys() - {"music", "navidrome"}:
        assert model["services"][service] == base["services"][service]
