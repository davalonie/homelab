#!/usr/bin/env python3
"""Prepara las dos cuentas ficticias en el proyecto Compose del laboratorio."""
import argparse
import subprocess
import sys
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--lab", required=True, action="store_true")
parser.add_argument("--project", required=True, help="Nombre del proyecto de laboratorio")
parser.add_argument("--docker-config", type=Path)
args = parser.parse_args()
command = [sys.executable, str(Path(__file__).with_name("bootstrap.py")),
           "--project", args.project, "--users", "alice", "bob"]
if args.docker_config:
    command.extend(["--docker-config", str(args.docker_config)])
subprocess.run(command, check=True)
