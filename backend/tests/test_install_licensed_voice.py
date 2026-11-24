"""Offline checks for the publisher-checksummed, opt-in voice installer."""
import hashlib
import json
from pathlib import Path
import pytest
import ai_singer.install_licensed_voice as installer


@pytest.fixture
def storage(monkeypatch, tmp_path):
    root = tmp_path / "external"
    root.mkdir()
    monkeypatch.setenv("AI_SINGER_STORAGE_ROOT", str(root))
    return root


def test_refuses_without_license(storage):
    with pytest.raises(installer.VoiceInstallError, match="Accept"):
        installer.install(accept_noncommercial_license=False)
    assert not (storage / "models").exists()


def test_install_download_checksum_registry_and_idempotence(storage, monkeypatch):
    payload = b"fake-voice-checkpoint-for-checksum"
    monkeypatch.setattr(installer, "EXPECTED_SHA256", hashlib.sha256(payload).hexdigest())
    calls = []
    class Remote:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def read(self, _size):
            if calls: return b""
            calls.append(True)
            return payload
    monkeypatch.setattr(installer, "urlopen", lambda *_a, **_kw: Remote())
    manifest = storage / "models" / "voice_conversion" / "voices.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(json.dumps({"voices": [{"id":"another-voice", "enabled": False}]}))
    first = installer.install(accept_noncommercial_license=True)
    assert first["reused_existing"] is False
    assert installer.check()["voice_lab_ready"]
    assert first["model_path"].startswith(str(storage))
    voices = json.loads(manifest.read_text())["voices"]
    assert len(voices) == 2
    assert voices[1]["license"].startswith("CC BY-NC")
    assert voices[1]["attribution"] == "Voice model: Shadowww"
    second = installer.install(accept_noncommercial_license=True)
    assert second["reused_existing"] is True
    assert len(json.loads(manifest.read_text())["voices"]) == 2
    assert not list(manifest.parent.glob("*.part"))


def test_bad_digest_does_not_register_or_keep_partial(storage, monkeypatch):
    class Remote:
        def __init__(self): self.count = 0
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def read(self, n):
            self.count += 1
            return b"bad-model" if self.count == 1 else b""
    monkeypatch.setattr(installer, "urlopen", lambda *_a, **_kw: Remote())
    with pytest.raises(installer.VoiceInstallError, match="SHA-256"):
        installer.install(accept_noncommercial_license=True)
    folder = storage / "models" / "voice_conversion"
    assert not (folder / "voices.json").exists()
    assert not list(folder.rglob("*.pth"))
    assert not list(folder.rglob("*.part"))


def test_existing_wrong_checksum_not_overwritten(storage):
    target = storage / "models" / "voice_conversion" / "shadowww-t02" / "shadowww-t02.pth"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"not-verified")
    with pytest.raises(installer.VoiceInstallError, match="wrong SHA"):
        installer.install(accept_noncommercial_license=True)
    assert target.read_bytes() == b"not-verified"


def test_malformed_manifest_preserved(storage):
    manifest = storage / "models" / "voice_conversion" / "voices.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text("invalid json", encoding="utf-8")
    with pytest.raises(installer.VoiceInstallError, match="not valid JSON"):
        installer.install(accept_noncommercial_license=True)
    assert manifest.read_text() == "invalid json"


def test_conflicting_existing_voice_not_modified(storage):
    manifest = storage / "models" / "voice_conversion" / "voices.json"
    manifest.parent.mkdir(parents=True)
    original = {"voices": [{"id": installer.VOICE_ID, "model": "other/checkpoint.pth"}]}
    manifest.write_text(json.dumps(original))
    with pytest.raises(installer.VoiceInstallError, match="different profile"):
        installer.install(accept_noncommercial_license=True)
    assert json.loads(manifest.read_text()) == original


def test_offline_check_without_manifest(storage):
    result = installer.check()
    assert result["voice_lab_ready"] is False
    assert result["verified_checkpoint"] is False
    assert result["rvc_runtime_installed"] == "not_checked"


def test_path_symlink_escape_refused(storage, tmp_path):
    models = storage / "models"
    models.mkdir()
    escape = tmp_path / "elsewhere"
    escape.mkdir()
    try:
        (models / "voice_conversion").symlink_to(escape, target_is_directory=True)
    except OSError:
        pytest.skip("Symlinks restricted")
    with pytest.raises(installer.VoiceInstallError, match="escapes external storage"):
        installer.check()


def test_bounded_model_download(storage, monkeypatch):
    monkeypatch.setattr(installer, "MAX_MODEL_BYTES", 6)
    class Remote:
        def __init__(self): self.called=False
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def read(self, n):
            if self.called: return b""
            self.called=True
            return b"too many bytes"
    monkeypatch.setattr(installer, "urlopen", lambda *_a, **_kw: Remote())
    with pytest.raises(installer.VoiceInstallError, match="80 MiB safety"):
        installer.install(accept_noncommercial_license=True)
    assert not list((storage / "models" / "voice_conversion").rglob("*.part"))
