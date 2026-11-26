"""Director Mode persists opt-in original/takes and review notes on external storage."""
from io import BytesIO
import json
import os
from pathlib import Path
import wave
import numpy as np
import pytest
from fastapi.testclient import TestClient

import ai_singer.director_sessions as director
from ai_singer.main import app


@pytest.fixture
def setup(monkeypatch, tmp_path):
    root = tmp_path / "Dimpu"
    root.mkdir()
    monkeypatch.setenv("AI_SINGER_STORAGE_ROOT", str(root))
    monkeypatch.setattr(director, "_select_profile", lambda voice_id: {"id": voice_id})
    return root, TestClient(app)


def wav(seconds=2.0, rate=16000):
    samples = np.arange(int(rate * seconds), dtype=np.float32)
    pcm = (0.15 * np.sin(2 * np.pi * 220 * samples / rate) * 32767).astype("<i2")
    buffer = BytesIO()
    with wave.open(buffer, "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(rate)
        audio.writeframes(pcm.tobytes())
    return buffer.getvalue()


def save(client, source=None, output=None, authorized=True):
    return client.post(
        "/director/sessions",
        data={"voice_id": "my-voice", "authorized_use": str(authorized).lower()},
        files={
            "source": ("source.wav", source if source is not None else wav(), "audio/wav"),
            "preview": ("converted.wav", output if output is not None else wav(rate=48000), "audio/wav"),
        },
    )


def test_preview_not_saved_until_explicit_post(setup):
    root, client = setup
    assert client.get("/director/sessions").json() == {"sessions": []}
    assert not (root / "outputs").exists()
    rejected = save(client, authorized=False)
    assert rejected.status_code == 403
    assert not (root / "outputs").exists()


def test_save_persists_original_and_take_with_no_exposed_paths(setup):
    root, client = setup
    created = save(client)
    assert created.status_code == 201, created.text
    session = created.json()
    assert len(session["id"]) == 32
    assert len(session["takes"]) == 1
    assert session["approved_take_id"] is None
    assert session["feedback"] == []
    assert "Dimpu" not in created.text
    saved = root / "outputs" / "director_sessions" / session["id"]
    assert (saved / "original.wav").is_file()
    assert (saved / ("take_" + session["takes"][0]["id"] + ".wav")).is_file()
    reread = client.get("/director/sessions/" + session["id"])
    assert reread.status_code == 200
    assert reread.json() == session
    listing = client.get("/director/sessions")
    assert listing.status_code == 200
    assert listing.json()["sessions"][0]["take_count"] == 1
    original = client.get("/director/sessions/" + session["id"] + "/original")
    output = client.get("/director/sessions/" + session["id"] + "/takes/" + session["takes"][0]["id"] + ".wav")
    assert original.status_code == 200 and output.status_code == 200
    assert original.headers["cache-control"] == "no-store"
    assert original.content[:4] == output.content[:4] == b"RIFF"
    with wave.open(BytesIO(original.content), "rb") as player:
        assert player.getframerate() == 16000
        assert player.getnchannels() == 1
    with wave.open(BytesIO(output.content), "rb") as player:
        assert player.getframerate() == 48000


def test_approval_and_feedback_are_immutable_audio_metadata_only(setup):
    root, client = setup
    session = save(client).json()
    sid = session["id"]
    tid = session["takes"][0]["id"]
    folder = root / "outputs" / "director_sessions" / sid
    audio = folder / f"take_{tid}.wav"
    before = audio.read_bytes()
    approved = client.post(f"/director/sessions/{sid}/approve", json={"take_id": tid})
    assert approved.status_code == 200, approved.text
    assert approved.json()["approved_take_id"] == tid
    note = client.post(f"/director/sessions/{sid}/feedback", json={
        "take_id": tid, "start_seconds": 0.7, "end_seconds": 1.2,
        "instruction": "Keep the glide softer here / ఇక్కడ మృదువుగా పాడు",
    })
    assert note.status_code == 201, note.text
    assert note.json()["status"] == "pending_review"
    assert client.get(f"/director/sessions/{sid}").json()["feedback"][0]["instruction"].startswith("Keep")
    assert audio.read_bytes() == before


@pytest.mark.parametrize("start,end,text", [
    (-1, 1, "bad"), (0.8, 0.8, "bad"), (1.5, 4, "bad"),
    (0.1, 0.5, ""), (0.1, 0.5, "x" * 301),
], ids=["negative","zero","past-duration","empty","too-long"])
def test_bad_feedback_rejected_without_modifying_state(setup, start, end, text):
    _, client = setup
    session = save(client).json()
    url = f"/director/sessions/{session['id']}/feedback"
    res = client.post(url, json={"take_id": session["takes"][0]["id"],
                                  "start_seconds": start, "end_seconds": end,
                                  "instruction": text})
    assert res.status_code in (422, 400)
    assert client.get(f"/director/sessions/{session['id']}").json()["feedback"] == []


def test_invalid_take_and_session_paths_rejected(setup):
    _, client = setup
    session = save(client).json()
    sid = session["id"]
    for path in [
        "/director/sessions/ffffffffffffffffffffffffffffffff",
        f"/director/sessions/{sid}/takes/ffffffffffffffffffffffffffffffff.wav",
        "/director/sessions/not-a-valid-id",
    ]:
        assert client.get(path).status_code == 404
    assert client.post(f"/director/sessions/{sid}/approve",
                       json={"take_id": "ffffffffffffffffffffffffffffffff"}).status_code == 422


def test_reject_bad_output_and_mismatched_duration(setup):
    root, client = setup
    assert save(client, output=b"not wav").status_code == 422
    assert save(client, output=wav(seconds=8, rate=48000)).status_code == 422
    assert client.get("/director/sessions").json()["sessions"] == []
    directory = root / "outputs" / "director_sessions"
    assert not directory.exists() or not any(directory.iterdir())


def test_render_new_take_preserves_approved_take(setup, monkeypatch):
    root, client = setup
    initial = save(client).json()
    sid, tid = initial["id"], initial["takes"][0]["id"]
    client.post(f"/director/sessions/{sid}/approve", json={"take_id": tid})
    original = client.get(f"/director/sessions/{sid}/original").content
    monkeypatch.setattr(director, "render_voice",
                        lambda source, voice, authorized_use: wav(rate=48000))
    rejected = client.post(f"/director/sessions/{sid}/render",
                           json={"voice_id": "my-voice", "authorized_use": False})
    assert rejected.status_code == 403
    result = client.post(f"/director/sessions/{sid}/render",
                         json={"voice_id": "my-voice", "authorized_use": True})
    assert result.status_code == 200, result.text
    final = result.json()
    assert len(final["takes"]) == 2
    assert final["approved_take_id"] == tid
    assert client.get(f"/director/sessions/{sid}/original").content == original
    assert final["takes"][0]["id"] == tid
    assert final["takes"][1]["label"] == "Take 2"


def test_failed_render_does_not_append_take(setup, monkeypatch):
    _, client = setup
    session = save(client).json()
    def fail(*a, **kw):
        from ai_singer.voice_render import VoiceRenderError
        raise VoiceRenderError("Simulated RVC failure")
    monkeypatch.setattr(director, "render_voice", fail)
    response = client.post(f"/director/sessions/{session['id']}/render",
                           json={"voice_id": "my-voice", "authorized_use": True})
    assert response.status_code == 502
    assert len(client.get(f"/director/sessions/{session['id']}").json()["takes"]) == 1


def test_take_cap_preserves_existing_files(setup, monkeypatch):
    root, client = setup
    session = save(client).json()
    monkeypatch.setattr(director, "MAX_TAKES", 1)
    response = client.post(f"/director/sessions/{session['id']}/render",
                           json={"voice_id": "my-voice", "authorized_use": True})
    assert response.status_code == 409
    folder = root / "outputs" / "director_sessions" / session["id"]
    assert len(list(folder.glob("take_*.wav"))) == 1


def test_external_storage_symlink_escape_blocked(setup, tmp_path):
    root, client = setup
    destination = tmp_path / "private"
    destination.mkdir()
    (root / "outputs").mkdir()
    try:
        (root / "outputs" / "director_sessions").symlink_to(destination, target_is_directory=True)
    except OSError:
        pytest.skip("Creating symlinks is restricted on this machine")
    response = save(client)
    assert response.status_code == 422
    assert not list(destination.iterdir())


def test_director_html_page_and_voice_lab_entry(setup):
    _, client = setup
    page = client.get("/director")
    assert page.status_code == 200
    for label in ('id="sessionSelect"', 'id="takesList"', 'id="originalPlayer"',
                  'id="takePlayer"', 'id="approveTake"', 'id="feedbackText"',
                  'id="renderAgain"', 'id="gainDb"'):
        assert label in page.text
    voice = client.get("/voice-lab")
    assert 'id="saveDirector"' in voice.text
    assert 'href="/director"' in voice.text


def test_preserves_exact_uploaded_m4a_bytes_when_available(setup):
    """Original file must not be silently replaced with a 16-kHz analysis copy."""
    import shutil
    import subprocess
    if shutil.which("ffmpeg") is None:
        pytest.skip("FFmpeg not found")
    _, client = setup
    encoded = subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-f", "lavfi",
         "-i", "sine=frequency=230:duration=2", "-c:a", "aac",
         "-movflags", "+frag_keyframe+empty_moov", "-f", "mp4", "pipe:1"],
        capture_output=True, check=True
    ).stdout
    response = save(client, source=encoded)
    assert response.status_code == 201, response.text
    session = response.json()
    sid = session["id"]
    assert session["original_extension"] == "m4a"
    read = client.get(f"/director/sessions/{sid}/original")
    assert read.status_code == 200
    assert read.content == encoded
    assert read.headers["content-type"].startswith("audio/mp4")


def test_passage_edit_creates_unapproved_take_and_preserves_original(setup):
    root, client = setup
    first = save(client).json()
    sid, tid = first["id"], first["takes"][0]["id"]
    assert client.post(f"/director/sessions/{sid}/approve",
                       json={"take_id": tid}).status_code == 200
    original_before = client.get(f"/director/sessions/{sid}/original").content
    parent = client.get(f"/director/sessions/{sid}/takes/{tid}.wav").content
    response = client.post(f"/director/sessions/{sid}/edit", json={
        "take_id": tid, "start_seconds": 0.5, "end_seconds": 1.5,
        "operation": "gain", "value": 6,
    })
    assert response.status_code == 201, response.text
    session = response.json()
    assert len(session["takes"]) == 2
    assert session["approved_take_id"] == tid
    assert session["takes"][1]["source_take_id"] == tid
    assert session["takes"][1]["edit"]["operation"] == "gain"
    assert session["takes"][1]["edit"]["fade_ms"] == 45
    new_id = session["takes"][1]["id"]
    child = client.get(f"/director/sessions/{sid}/takes/{new_id}.wav").content
    assert client.get(f"/director/sessions/{sid}/takes/{tid}.wav").content == parent
    assert client.get(f"/director/sessions/{sid}/original").content == original_before
    def samples(wav_data):
        with wave.open(BytesIO(wav_data)) as w:
            return np.frombuffer(w.readframes(w.getnframes()), dtype="<i2").copy(), w.getframerate()
    a, rate = samples(parent)
    b, rate2 = samples(child)
    assert rate == rate2 == 48000
    assert np.array_equal(a[:int(0.5 * rate)], b[:int(0.5 * rate)])
    assert np.array_equal(a[int(1.5 * rate):], b[int(1.5 * rate):])
    assert np.any(a[int(0.65 * rate):int(1.35 * rate)] !=
                  b[int(0.65 * rate):int(1.35 * rate)])
    assert len(list((root / "outputs" / "director_sessions" / sid).glob("take_*.wav"))) == 2


@pytest.mark.parametrize("change", [
    {"value": 0}, {"value": 10}, {"operation": "autonomous_singing"},
    {"end_seconds": 4.0}, {"start_seconds": -1},
    {"start_seconds": 0.9, "end_seconds": 1.0}, {"value": "louder"},
    {"take_id": "f" * 32}, {"start_seconds": None},
], ids=["zero","excessive","unsupported","out-of-range","negative",
        "too-short","text-value","unknown-take","missing-start"])
def test_invalid_passage_edit_never_creates_audio(setup, change):
    root, client = setup
    saved = save(client).json()
    sid, tid = saved["id"], saved["takes"][0]["id"]
    payload = {
        "take_id": tid, "start_seconds": 0.5, "end_seconds": 1.5,
        "operation": "gain", "value": 5,
    }
    payload.update(change)
    response = client.post(f"/director/sessions/{sid}/edit", json=payload)
    assert response.status_code == 422, response.text
    assert len(client.get(f"/director/sessions/{sid}").json()["takes"]) == 1
    assert len(list((root / "outputs" / "director_sessions" / sid).glob("take_*.wav"))) == 1


def test_passage_edit_cap_and_atomic_rollback(setup, monkeypatch):
    root, client = setup
    first = save(client).json()
    sid, tid = first["id"], first["takes"][0]["id"]
    payload = {
        "take_id": tid, "start_seconds": 0.5, "end_seconds": 1.5,
        "operation": "gain", "value": -4,
    }
    monkeypatch.setattr(director, "MAX_TAKES", 1)
    blocked = client.post(f"/director/sessions/{sid}/edit", json=payload)
    assert blocked.status_code == 409
    monkeypatch.setattr(director, "MAX_TAKES", 12)
    before = client.get(f"/director/sessions/{sid}").json()
    with monkeypatch.context() as m:
        m.setattr(director, "_atomic_json",
                  lambda *a, **k: (_ for _ in ()).throw(OSError("forced failure")))
        with pytest.raises(OSError, match="forced failure"):
            director.edit_take(sid, tid, 0.5, 1.5, "gain", -4)
    after = client.get(f"/director/sessions/{sid}").json()
    assert before == after
    assert len(list((root / "outputs" / "director_sessions" / sid).glob("take_*.wav"))) == 1
