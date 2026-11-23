import io
import wave

import numpy as np
import pytest
from fastapi.testclient import TestClient

from ai_singer.audio_analysis import AudioInputError, analyze_audio, decode_audio
from ai_singer.main import app

client = TestClient(app)
RATE = 16_000


def sine(frequency: float, seconds: float, amplitude: float = 0.3) -> np.ndarray:
    t = np.arange(int(seconds * RATE)) / RATE
    return (amplitude * np.sin(2 * np.pi * frequency * t)).astype(np.float32)


def wav_bytes(samples: np.ndarray) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as writer:
        writer.setnchannels(1)
        writer.setsampwidth(2)
        writer.setframerate(RATE)
        writer.writeframes((np.clip(samples, -1, 1) * 32767).astype("<i2").tobytes())
    return buffer.getvalue()


def test_decode_valid_wav() -> None:
    samples = decode_audio(wav_bytes(sine(220, 1.5)))
    assert samples.size == 24_000
    assert np.max(np.abs(samples)) > 0.1


def test_analysis_tracks_constant_a3() -> None:
    result = analyze_audio(sine(220, 2))
    voiced = [frame["frequency_hz"] for frame in result["pitch_track"] if frame["frequency_hz"]]
    assert len(voiced) > 50
    assert np.median(voiced) == pytest.approx(220, abs=3)
    assert any(note["midi_note"] == 57 for note in result["note_events"])


def test_analysis_tracks_note_change_and_silence() -> None:
    recorded = np.concatenate((sine(220, 1), np.zeros(RATE // 4, dtype=np.float32), sine(330, 1)))
    result = analyze_audio(recorded)
    observed = {note["midi_note"] for note in result["note_events"]}
    assert {57, 64}.issubset(observed)
    assert any(0.9 < p["start_seconds"] < 1.3 for p in result["quiet_intervals"])


def test_analysis_rejects_uncertain_noise() -> None:
    rng = np.random.default_rng(100)
    result = analyze_audio((rng.normal(0, 0.08, RATE * 2)).astype(np.float32))
    assert not result["note_events"]
    assert any("No reliable" in warning for warning in result["warnings"])


def test_analysis_reports_unvoiced_silence() -> None:
    result = analyze_audio(np.zeros(RATE * 2, dtype=np.float32))
    assert not result["note_events"]
    assert all(point["frequency_hz"] is None for point in result["pitch_track"])


@pytest.mark.parametrize("data", [b"", b"bad wav data", b"x" * (10 * 1024 * 1024 + 1)])
def test_invalid_audio_is_rejected(data: bytes) -> None:
    with pytest.raises(AudioInputError):
        decode_audio(data)


@pytest.mark.parametrize("duration", [0.6, 15.5])
def test_duration_bounds(duration: float) -> None:
    with pytest.raises(AudioInputError, match="between 1 and 15"):
        decode_audio(wav_bytes(sine(220, duration)))


def test_api_upload_returns_pitch_track() -> None:
    response = client.post("/analyze", files={"file": ("voice.wav", wav_bytes(sine(220, 2)), "audio/wav")})
    assert response.status_code == 200, response.text
    assert response.json()["note_events"]
    assert response.json()["sample_rate_hz"] == RATE
    assert response.json()["duration_seconds"] == 2.0


def test_api_invalid_input_returns_422() -> None:
    response = client.post("/analyze", files={"file": ("invalid.wav", b"xyz", "audio/wav")})
    assert response.status_code == 422
    assert "Cannot decode" in response.json()["detail"]


def test_api_missing_ffmpeg_returns_503(monkeypatch) -> None:
    import ai_singer.audio_analysis as module
    def missing(*args, **kwargs):
        raise FileNotFoundError("ffmpeg")
    monkeypatch.setattr(module.subprocess, "run", missing)
    response = client.post("/analyze", files={"file": ("voice.wav", b"abc", "audio/wav")})
    assert response.status_code == 503
    assert "FFmpeg" in response.json()["detail"]


def test_silence_intervals_do_not_exceed_recording_length() -> None:
    result = analyze_audio(np.zeros(RATE * 2, dtype=np.float32))
    assert result["quiet_intervals"]
    assert max(p["end_seconds"] for p in result["quiet_intervals"]) <= 2.0


def test_api_rejects_oversized_upload() -> None:
    response = client.post(
        "/analyze",
        files={"file": ("oversized.wav", b"x" * (10 * 1024 * 1024 + 1), "audio/wav")},
    )
    assert response.status_code == 422
    assert "10 MB" in response.json()["detail"]


def test_api_requires_audio_upload() -> None:
    response = client.post("/analyze")
    assert response.status_code == 422
