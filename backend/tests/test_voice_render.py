"""Offline voice-output contract tests; no third-party RVC model is loaded."""
import json
import logging
import os
from pathlib import Path
import sys
import wave
from io import BytesIO

import numpy as np
import pytest
from fastapi.testclient import TestClient

from ai_singer.main import app
from ai_singer.voice_render import (
    VoiceConfigurationError, VoiceBusyError, VoiceRenderError, _model_under_base,
    _pcm_wav, list_voices, render_voice,
)


def sample_wav(seconds=2.0):
    sr = 16000
    samples = (0.25 * np.sin(2*np.pi*220*np.arange(int(seconds*sr))/sr)).astype("float32")
    return _pcm_wav(samples)


@pytest.fixture
def installed(monkeypatch, tmp_path):
    storage = tmp_path / "external"
    base = storage / "models" / "voice_conversion"
    model = base / "my-voice" / "model.pth"
    model.parent.mkdir(parents=True)
    model.write_bytes(b"fake-model-NOT-A-REAL-VOICE")
    manifest = base / "voices.json"
    manifest.write_text(json.dumps({"voices": [{"id": "my-voice", "label": "Licensed singer",
                                               "model": "my-voice/model.pth", "rights_confirmed": True,
                                               "enabled": True, "speaker_id": 0}]}))
    runtime = tmp_path / "rvc-runtime"
    cli = runtime / "infer" / "cli.py"
    cli.parent.mkdir(parents=True)
    # Exercise the same absolute package imports used by real RVC conversion.
    (cli.parent / "_launch_contract.py").write_text("launch_mode = 'infer'\n")
    # Fake third-party CLI for testing the real subprocess/WAV boundary.
    cli.write_text("""import argparse, shutil
from infer._launch_contract import launch_mode
assert launch_mode == 'infer'
assert __package__ == 'infer'
p=argparse.ArgumentParser()
for flag in ('model','speaker-id','input','output','pitch','f0-method','index-rate'):
    p.add_argument('--'+flag, required=True)
a=p.parse_args()
assert a.pitch == '0'
assert a.f0_method == 'rmvpe'
assert a.index_rate == '0'
shutil.copyfile(a.input,a.output)
""")
    monkeypatch.setenv("AI_SINGER_STORAGE_ROOT", str(storage))
    monkeypatch.setenv("AI_SINGER_RVC_ROOT", str(runtime))
    monkeypatch.setenv("AI_SINGER_RVC_PYTHON", sys.executable)
    return storage, manifest, model, runtime


def test_no_manifest_lists_no_voices(monkeypatch, tmp_path):
    monkeypatch.setenv("AI_SINGER_STORAGE_ROOT", str(tmp_path))
    assert list_voices() == []
    assert TestClient(app).get("/voices").json() == {"voices": []}


def test_manifest_requires_rights_and_enabled(installed):
    _, manifest, _, _ = installed
    rows = json.loads(manifest.read_text())
    rows["voices"][0]["rights_confirmed"] = False
    manifest.write_text(json.dumps(rows))
    assert list_voices() == []
    with pytest.raises(VoiceConfigurationError, match="not enabled"):
        render_voice(sample_wav(), "my-voice", authorized_use=True)


def test_voices_returns_profile_without_exposing_model_path(installed):
    client = TestClient(app)
    response = client.get("/voices")
    assert response.status_code == 200
    assert response.json()["voices"] == [{"id": "my-voice", "label": "Licensed singer", "ready": True}]
    assert "external" not in response.text
    assert "model.pth" not in response.text


def test_missing_approved_weight_listed_as_not_ready(installed):
    _, _, model, _ = installed
    model.unlink()
    assert list_voices()[0]["ready"] is False
    with pytest.raises(VoiceConfigurationError, match="missing"):
        render_voice(sample_wav(), "my-voice", authorized_use=True)


@pytest.mark.parametrize("path", ["../private/model.pth", "../../model.pth", "/etc/model.pth",
                                   "C:/Users/model.pth", "foo\\bar.pth", "../good.pth", "model.pt"],
                         ids=["traversal", "deep-traversal", "absolute", "windows-drive", "backslash",
                              "parent", "wrong-extension"])
def test_unsafe_model_path_rejected(tmp_path, path):
    with pytest.raises(VoiceConfigurationError):
        _model_under_base(tmp_path, path)


def test_symlink_escape_rejected(installed, tmp_path):
    storage, manifest, _, _ = installed
    destination = tmp_path / "private.pth"
    destination.write_bytes(b"unsafe")
    shortcut = storage / "models" / "voice_conversion" / "evil.pth"
    try:
        shortcut.symlink_to(destination)
    except OSError:
        pytest.skip("Creating symlinks is restricted on this machine")
    data = json.loads(manifest.read_text())
    data["voices"][0]["model"] = "evil.pth"
    manifest.write_text(json.dumps(data))
    with pytest.raises(VoiceConfigurationError, match="inside"):
        list_voices()


def test_duplicate_voice_id_rejected(installed):
    _, manifest, _, _ = installed
    data = json.loads(manifest.read_text())
    data["voices"].append(dict(data["voices"][0]))
    manifest.write_text(json.dumps(data))
    with pytest.raises(VoiceConfigurationError, match="unique"):
        list_voices()


def test_missing_rvc_is_actionable(installed, monkeypatch):
    monkeypatch.delenv("AI_SINGER_RVC_PYTHON")
    with pytest.raises(VoiceConfigurationError, match="AI_SINGER_RVC_ROOT and AI_SINGER_RVC_PYTHON"):
        render_voice(sample_wav(), "my-voice", authorized_use=True)


def test_render_requires_authorization(installed):
    with pytest.raises(VoiceConfigurationError, match="Confirm"):
        render_voice(sample_wav(), "my-voice", authorized_use=False)
    response = TestClient(app).post("/render-voice", data={"voice_id": "my-voice"},
                                    files={"file": ("vocal.wav", sample_wav(), "audio/wav")})
    assert response.status_code == 403


def test_real_subprocess_boundary_outputs_valid_wav_and_cleans_temp(installed):
    storage, _, _, _ = installed
    client = TestClient(app)
    response = client.post("/render-voice", data={"voice_id": "my-voice", "authorized_use": "true"},
                           files={"file": ("vocal.wav", sample_wav(), "audio/wav")})
    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("audio/wav")
    assert response.headers["cache-control"] == "no-store"
    assert response.content[:4] == b"RIFF"
    with wave.open(BytesIO(response.content), "rb") as f:
        assert abs(f.getnframes()/f.getframerate()-2.0) < 0.05
    assert not list((storage / "cache" / "voice_previews").iterdir())


def test_input_duration_limit_is_applied_before_subprocess(installed):
    response = TestClient(app).post("/render-voice", data={"voice_id": "my-voice", "authorized_use": "true"},
                                    files={"file": ("vocal.wav", sample_wav(.5), "audio/wav")})
    assert response.status_code == 422


def test_busy_is_reported_as_429(installed):
    import ai_singer.voice_render as module
    module._RENDER_LOCK.acquire()
    try:
        response = TestClient(app).post("/render-voice", data={"voice_id": "my-voice", "authorized_use": "true"},
                                        files={"file": ("vocal.wav", sample_wav(), "audio/wav")})
        assert response.status_code == 429
    finally:
        module._RENDER_LOCK.release()


def test_renderer_failure_is_502_not_500(installed):
    _, _, _, runtime = installed
    (runtime / "infer" / "cli.py").write_text("raise RuntimeError('example inference error')\n")
    response = TestClient(app).post("/render-voice", data={"voice_id": "my-voice", "authorized_use": "true"},
                                    files={"file": ("vocal.wav", sample_wav(), "audio/wav")})
    assert response.status_code == 502
    assert "example inference error" not in response.text


def test_voice_lab_contains_controls_and_local_fetch_only():
    response = TestClient(app).get("/voice-lab")
    assert response.status_code == 200
    for term in ['id="sourceFile"','id="voice"','id="authorized"','id="render"',
                 'id="original"','id="converted"','"/voices"','"/render-voice"']:
        assert term in response.text
    assert 'src="http' not in response.text

def test_renderer_local_diagnostics_require_explicit_opt_in(installed, monkeypatch, caplog):
    _, _, _, runtime = installed
    (runtime / "infer" / "cli.py").write_text(
        "import sys\nprint('secret trace on stdout')\n"
        "print('example inference error', file=sys.stderr)\nsys.exit(7)\n"
    )
    client = TestClient(app)

    def submit():
        return client.post("/render-voice",
                           data={"voice_id": "my-voice", "authorized_use": "true"},
                           files={"file": ("vocal.wav", sample_wav(), "audio/wav")})

    monkeypatch.delenv("AI_SINGER_RVC_DEBUG", raising=False)
    with caplog.at_level(logging.WARNING, logger="ai_singer.voice_render"):
        first = submit()
    assert first.status_code == 502
    assert "secret trace" not in first.text
    assert "example inference error" not in first.text
    assert "code 7" in caplog.text
    assert "secret trace" not in caplog.text
    assert "example inference error" not in caplog.text

    caplog.clear()
    monkeypatch.setenv("AI_SINGER_RVC_DEBUG", "1")
    with caplog.at_level(logging.WARNING, logger="ai_singer.voice_render"):
        second = submit()
    assert second.status_code == 502
    assert "secret trace" not in second.text
    assert "example inference error" not in second.text
    assert "code 7" in caplog.text
    assert "secret trace on stdout" in caplog.text
    assert "example inference error" in caplog.text


def test_diagnostic_excerpt_bounds_output_and_handles_bad_bytes():
    from ai_singer.voice_render import _diagnostic_excerpt
    ending = b"very last error"
    blob = b"Z" * 10000 + bytes([255]) + ending
    excerpt = _diagnostic_excerpt(blob)
    assert excerpt.endswith("very last error")
    assert len(excerpt) <= 2500
    assert "\ufffd" in excerpt

def test_rvc_infer_package_import_with_dedicated_python(installed, monkeypatch, tmp_path):
    """Regression: direct infer/cli.py execution fails to import infer.*.

    Ensure it works without depending on PYTHONPATH or a developer checkout.
    """
    monkeypatch.setenv("PYTHONPATH", str(tmp_path / "unrelated"))
    response = TestClient(app).post(
        "/render-voice",
        data={"voice_id": "my-voice", "authorized_use": "true"},
        files={"file": ("vocal.wav", sample_wav(), "audio/wav")},
    )
    assert response.status_code == 200, response.text
    assert response.content[:4] == b"RIFF"
