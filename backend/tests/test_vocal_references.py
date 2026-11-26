"""Regression coverage for the sung-demonstration workflow."""
from io import BytesIO
import wave

import numpy as np
import pytest
from fastapi.testclient import TestClient

from ai_singer import director_sessions as director
from ai_singer import vocal_references as refs
from ai_singer.main import app


def wav(frequency=220, seconds=2, rate=16000):
    t = np.arange(round(seconds * rate)) / rate
    data = (0.15 * np.sin(2 * np.pi * frequency * t) * 32767).astype("<i2")
    out = BytesIO()
    with wave.open(out, "wb") as f:
        f.setparams((1, 2, rate, 0, "NONE", "not compressed"))
        f.writeframes(data.tobytes())
    return out.getvalue()


def contour(values, seconds=2):
    return {"duration_seconds": seconds,
            "pitch_track": [{"midi_note": n} for n in values],
            "octave_jump_candidates": []}


def test_normalized_contours_preserve_relative_shape_across_register_and_duration():
    result = refs.compare_contours(contour([60, 62, 64, 62]),
                                   contour([72, 74, 76, 74], 3))
    assert result["register_difference_semitones"] == 12
    assert result["relative_contour_median_difference_cents"] == 0
    assert result["duration_difference_seconds"] == 1
    assert result["jointly_voiced_points"] == 101


def test_silence_and_different_shape_not_mislabeled_as_equivalent():
    quiet = refs.compare_contours(contour([60] * 4), contour([None] * 4))
    assert quiet["relative_contour_median_difference_cents"] is None
    assert quiet["register_difference_semitones"] is None
    assert quiet["voicing_mismatch_points"] == 101
    opposite = refs.compare_contours(contour([60, 62, 64, 66]),
                                      contour([66, 64, 62, 60]))
    assert opposite["relative_contour_median_difference_cents"] > 0


def test_pause_mismatch_visible():
    result = refs.compare_contours(contour([60, 60, None, 62, 62]),
                                   contour([72, 72, 72, 74, 74]))
    assert result["voicing_mismatch_points"] > 0
    assert result["target_voiced_points"] < result["demo_voiced_points"]


@pytest.fixture
def session(tmp_path, monkeypatch):
    root = tmp_path / "Dimpu"
    root.mkdir()
    monkeypatch.setenv("AI_SINGER_STORAGE_ROOT", str(root))
    monkeypatch.setattr(director, "_select_profile", lambda voice_id: {"id": voice_id})
    client = TestClient(app)
    source, take = wav(), wav(rate=48000)
    response = client.post("/director/sessions",
                           data={"voice_id": "test", "authorized_use": "true"},
                           files={"source": ("source.wav", source, "audio/wav"),
                                  "preview": ("take.wav", take, "audio/wav")})
    assert response.status_code == 201, response.text
    sid = response.json()["id"]
    tid = response.json()["takes"][0]["id"]
    approved = client.post(f"/director/sessions/{sid}/approve", json={"take_id": tid})
    assert approved.status_code == 200
    return client, root, sid, tid, source, take, approved.json()


def post(session, **changes):
    client, _, sid, tid, *_ = session
    data = {"take_id": tid, "start_seconds": "0.5", "end_seconds": "1.5"}
    data.update(changes)
    return client.post(f"/director/sessions/{sid}/vocal-references", data=data,
                       files={"file": ("demo.wav", wav(440), "audio/wav")})


def test_preview_and_explicit_save_preserve_original_approved_take_and_metadata(session):
    client, root, sid, tid, source, take, before = session
    endpoint = f"/director/sessions/{sid}/vocal-references"
    folder = root / "outputs" / "director_sessions" / sid / "vocal_references"
    cropped = client.get(endpoint + "/passage",
                         params={"take_id": tid, "start_seconds": 0.5, "end_seconds": 1.5})
    assert cropped.status_code == 200
    with wave.open(BytesIO(cropped.content), "rb") as f:
        assert f.getframerate() == 48000
        assert f.getnframes() == 48000
    rejected = post(session, save_reference="true", authorized_use="false")
    assert rejected.status_code == 403
    assert not folder.exists()
    analyzed = post(session)
    assert analyzed.status_code == 200, analyzed.text
    assert analyzed.json()["id"] is None
    assert analyzed.json()["comparison"]["jointly_voiced_points"] >= 10
    assert not folder.exists()
    saved = post(session, save_reference="true", authorized_use="true")
    assert saved.status_code == 200, saved.text
    report = saved.json()
    rid = report["id"]
    assert report["status"] == "saved_reference"
    assert client.get(endpoint + "/" + rid).json() == report
    assert client.get(endpoint + "/" + rid + "/audio").content == wav(440)
    assert len(client.get(endpoint).json()["references"]) == 1
    assert client.get(f"/director/sessions/{sid}").json() == before
    assert client.get(f"/director/sessions/{sid}/original").content == source
    assert client.get(f"/director/sessions/{sid}/takes/{tid}.wav").content == take


@pytest.mark.parametrize("change", [
    {"start_seconds": "-1"}, {"end_seconds": "3"}, {"end_seconds": "0.75"},
    {"take_id": "f" * 32}, {"estimator": "unsupported"}, {"start_seconds": "nan"},
])
def test_invalid_selection_does_not_save(session, change):
    _, root, sid, *_ = session
    result = post(session, save_reference="true", authorized_use="true", **change)
    assert result.status_code == 422
    assert not (root / "outputs" / "director_sessions" / sid / "vocal_references").exists()


def test_page_integration(session):
    client = session[0]
    director_page = client.get("/director")
    assert 'id="recordVocalCorrection"' in director_page.text
    page = client.get("/director/vocal-reference")
    assert page.status_code == 200
    for label in ('id="record"', 'id="done"', 'id="demoPlayer"', 'id="save"', 'id="contour"'):
        assert label in page.text


def test_reference_cap_and_symlink_guard(session, monkeypatch, tmp_path):
    _, root, sid, *_ = session
    folder = root / "outputs" / "director_sessions" / sid / "vocal_references"
    monkeypatch.setattr(refs, "MAX_REFERENCES", 0)
    limited = post(session, save_reference="true", authorized_use="true")
    assert limited.status_code == 409
    assert not any(folder.iterdir())
    folder.rmdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    try:
        folder.symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("Symlinks are restricted on this machine")
    assert post(session, save_reference="true", authorized_use="true").status_code == 422
    assert not any(outside.iterdir())
