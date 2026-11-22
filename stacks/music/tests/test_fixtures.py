"""Pruebas locales del generador y del manejador de audio, sin abrir puertos."""
from array import array
import importlib.util
from io import BytesIO
import json
import math
from pathlib import Path
import shutil
import subprocess
import sys
from unittest.mock import Mock
from urllib.parse import urlsplit
import wave

import pytest

FIXTURES = Path(__file__).resolve().parent / "fixtures"


@pytest.fixture(scope="module")
def generated(tmp_path_factory):
    root = tmp_path_factory.mktemp("music")
    scripts = root / "tests/fixtures"
    scripts.mkdir(parents=True)
    generator = shutil.copy2(FIXTURES / "prepare_audio.py", scripts)
    subprocess.run([sys.executable, generator], cwd=root, check=True, capture_output=True)
    return root / "runtime/fixtures"


@pytest.mark.parametrize(("name", "hz"), [("one.wav", 220), ("two.wav", 330)])
def test_generated_pcm_and_ranges(generated, name, hz, monkeypatch):
    with wave.open(str(generated / name)) as wav:
        assert (wav.getnchannels(), wav.getsampwidth(), wav.getframerate(), wav.getnframes()) == (1, 2, 16000, 544000)
        pcm = array("h", wav.readframes(wav.getnframes()))
    if sys.byteorder != "little":
        pcm.byteswap()
    assert all(sample == int(1500 * math.sin(2 * math.pi * hz * i / 16000)) for i, sample in enumerate(pcm))

    monkeypatch.setenv("FIXTURES_DIR", str(generated))
    spec = importlib.util.spec_from_file_location("range_server", FIXTURES / "range_server.py")
    server = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(server)
    raw = (generated / name).read_bytes()
    for headers, status, body in [({}, 200, raw), ({"Range": "bytes=44-63"}, 206, raw[44:64])]:
        request = Mock(path="/" + name, headers=headers, wfile=BytesIO())
        server.Handler.do_GET(request)
        request.send_response.assert_called_once_with(status)
        assert request.wfile.getvalue() == body


def test_catalog_uses_the_two_generated_wavs(generated):
    records = json.loads((generated / "sources.json").read_text())
    assert set(records) == {"authorized_http:" + name for name in ("one", "two", "three", "four")}
    urls = [urlsplit(item["url"]) for item in records.values()]
    assert all((u.scheme, u.netloc) == ("http", "fixtures:8100") for u in urls)
    assert {u.path for u in urls} == {"/one.wav", "/two.wav"}
    assert all((generated / u.path[1:]).is_file() for u in urls)
