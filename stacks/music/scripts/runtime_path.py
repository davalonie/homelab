"""Resolve the runtime like Compose, relative to the installation directory."""
import json
import os
from pathlib import Path
import subprocess


def runtime_dir(root):
    value = os.environ.get("MUSIC_RUNTIME_DIR")
    if value is None and (root / ".env").is_file():
        # Let Compose apply its own quoting, expansion and precedence rules.
        # This model emits only the path and needs neither images nor a daemon.
        model = 'services: {paths: {image: scratch, labels: {runtime: "${MUSIC_RUNTIME_DIR:-./runtime}"}}}'
        result = subprocess.run(
            ["docker", "compose", "-p", "paths", "--env-file", ".env", "-f", "-",
             "config", "--format", "json"], cwd=root, input=model,
            text=True, check=True, stdout=subprocess.PIPE,
        )
        value = json.loads(result.stdout)["services"]["paths"]["labels"]["runtime"]
    path = (root / (value or "./runtime")).resolve()
    checkout = next((p for p in (root, *root.parents) if (p / ".git").exists()), root)
    if path != root / "runtime" and (path.is_relative_to(checkout) or checkout.is_relative_to(path)):
        raise ValueError("Choose ./runtime or a dedicated data directory outside the checkout")
    return path


def check_runtime_mount(container, runtime):
    """Refuse to operate on live state from a different Compose configuration."""
    service = container["Config"]["Labels"]["com.docker.compose.service"]
    directories = {"music": ("music-app", "/app/data"), "navidrome": ("navidrome", "/data"),
                   "aurral": ("aurral", "/config")}
    if service.startswith("koito-"):
        directory, target = service, "/etc/koito"
    elif service in directories:
        directory, target = directories[service]
    else:
        return
    source = next((m["Source"] for m in container["Mounts"] if m["Destination"] == target), None)
    if source is None or Path(source).resolve() != runtime / directory:
        raise RuntimeError("Running service uses a different runtime; check MUSIC_RUNTIME_DIR")
