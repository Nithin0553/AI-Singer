from pathlib import Path

import numpy as np
import pytest

from ai_singer.rmvpe_pitch import RMVPEUnavailable, estimate_rmvpe, model_file
from ai_singer.pitch_benchmark import compare_results


def test_missing_external_storage_blocks_model_access(monkeypatch) -> None:
    monkeypatch.delenv("AI_SINGER_STORAGE_ROOT", raising=False)
    monkeypatch.delenv("AI_SINGER_RMVPE_MODEL", raising=False)
    with pytest.raises(RMVPEUnavailable, match="not configured"):
        model_file()


def test_missing_weights_are_not_downloaded(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AI_SINGER_STORAGE_ROOT", str(tmp_path))
    monkeypatch.delenv("AI_SINGER_RMVPE_MODEL", raising=False)
    with pytest.raises(RMVPEUnavailable, match="not installed"):
        model_file()
    assert not list(tmp_path.rglob("*.onnx"))


def test_model_override_must_be_absolute(monkeypatch) -> None:
    monkeypatch.setenv("AI_SINGER_RMVPE_MODEL", "relative/rmvpe.onnx")
    with pytest.raises(RMVPEUnavailable, match="absolute"):
        model_file()


def test_rmvpe_frames_align_with_yin_grid(monkeypatch, tmp_path: Path) -> None:
    import ai_singer.rmvpe_pitch as module
    checkpoint = tmp_path / "rmvpe.onnx"
    checkpoint.write_bytes(b"test-placeholder")
    monkeypatch.setenv("AI_SINGER_RMVPE_MODEL", str(checkpoint))

    class FakeModel:
        def predict(self, samples, sr):
            assert sr == 16000
            return (np.array([0.0, 0.01, 0.02, 0.03, 0.04]),
                    np.array([220., 220., 330., 330., 440.]),
                    np.array([0.8, 0.8, 0.8, 0.02, 0.8]), None)

    monkeypatch.setattr(module, "_load_model", lambda path: FakeModel())
    values = estimate_rmvpe(np.zeros(3200, dtype=np.float32), 4, 16000, 320)
    assert values[0] == 220
    assert values[1] == 330
    assert values[2] == 440
    assert np.isnan(values[3])


def test_rmvpe_rejects_invalid_model_timeline(monkeypatch, tmp_path: Path) -> None:
    import ai_singer.rmvpe_pitch as module
    checkpoint = tmp_path / "rmvpe.onnx"
    checkpoint.write_bytes(b"test-placeholder")
    monkeypatch.setenv("AI_SINGER_RMVPE_MODEL", str(checkpoint))

    class FakeModel:
        def predict(self, samples, sr):
            return np.array([0.1, 0.0]), np.array([220., 240.]), np.array([0.9, 0.9]), None

    monkeypatch.setattr(module, "_load_model", lambda path: FakeModel())
    with pytest.raises(RMVPEUnavailable, match="invalid pitch timeline"):
        estimate_rmvpe(np.zeros(16000, dtype=np.float32), 2, 16000, 320)


def test_cannot_compare_unaligned_frames() -> None:
    yin = {"pitch_track": [{"time_seconds": 0, "midi_note": 57}]}
    rmvpe = {"pitch_track": [{"time_seconds": 0.02, "midi_note": 57}]}
    with pytest.raises(ValueError, match="timestamps"):
        compare_results(yin, rmvpe)


def test_comparison_reports_agreement_not_accuracy() -> None:
    yin = {"pitch_track": [
        {"time_seconds": 0, "midi_note": 57},
        {"time_seconds": .02, "midi_note": 60},
        {"time_seconds": .04, "midi_note": None},
    ]}
    rmvpe = {"pitch_track": [
        {"time_seconds": 0, "midi_note": 57.1},
        {"time_seconds": .02, "midi_note": 72},
        {"time_seconds": .04, "midi_note": 60},
    ]}
    result = compare_results(yin, rmvpe)
    assert result["frame_count"] == 3
    assert result["overlapping_voiced_frames"] == 2
    assert result["octave_like_disagreement_frames"] == 1
    assert result["median_absolute_disagreement_cents"] == pytest.approx(605)


def test_no_shared_pitch_results_in_null_median() -> None:
    a = {"pitch_track": [{"time_seconds": 0, "midi_note": None}]}
    b = {"pitch_track": [{"time_seconds": 0, "midi_note": 57}]}
    assert compare_results(a, b)["median_absolute_disagreement_cents"] is None


def test_api_rejects_rmvpe_until_weights_are_configured(monkeypatch, tmp_path: Path) -> None:
    from fastapi.testclient import TestClient
    from ai_singer.main import app
    from test_audio_analysis import sine, wav_bytes

    monkeypatch.setenv("AI_SINGER_STORAGE_ROOT", str(tmp_path))
    monkeypatch.delenv("AI_SINGER_RMVPE_MODEL", raising=False)
    response = TestClient(app).post(
        "/analyze?estimator=rmvpe",
        files={"file": ("sung.wav", wav_bytes(sine(220, 2)), "audio/wav")},
    )
    assert response.status_code == 503
    assert "not installed" in response.json()["detail"]


def test_api_accepts_mock_rmvpe_without_changing_yin(monkeypatch, tmp_path: Path) -> None:
    from fastapi.testclient import TestClient
    from ai_singer.main import app
    from test_audio_analysis import sine, wav_bytes
    import ai_singer.rmvpe_pitch as module

    weight_path = tmp_path / "rmvpe.onnx"
    weight_path.write_bytes(b"mock only")
    monkeypatch.setenv("AI_SINGER_RMVPE_MODEL", str(weight_path))

    class FakeModel:
        def predict(self, audio, sr):
            t = np.arange(201) * 0.01
            return t, np.full(len(t), 220), np.full(len(t), 0.95), None

    monkeypatch.setattr(module, "_load_model", lambda path: FakeModel())
    clip = wav_bytes(sine(220, 2))
    rmvpe = TestClient(app).post(
        "/analyze?estimator=rmvpe", files={"file": ("song.wav", clip, "audio/wav")},
    )
    yin = TestClient(app).post(
        "/analyze", files={"file": ("song.wav", clip, "audio/wav")},
    )
    assert rmvpe.status_code == 200, rmvpe.text
    assert yin.status_code == 200, yin.text
    assert rmvpe.json()["estimator"] == "rmvpe"
    assert yin.json()["estimator"] == "yin"
    assert any(item["midi_note"] == 57 for item in rmvpe.json()["note_events"])


def test_benchmark_works_with_mock_neural_model(monkeypatch, tmp_path: Path) -> None:
    from ai_singer.pitch_benchmark import benchmark_audio
    from test_audio_analysis import sine, wav_bytes
    import ai_singer.rmvpe_pitch as module

    model = tmp_path / "rmvpe.onnx"
    model.write_bytes(b"mock only")
    monkeypatch.setenv("AI_SINGER_RMVPE_MODEL", str(model))

    class FakeModel:
        def predict(self, audio, sr):
            times = np.arange(201) * 0.01
            return times, np.full(len(times), 220.), np.full(len(times), 0.9), None

    monkeypatch.setattr(module, "_load_model", lambda path: FakeModel())
    result = benchmark_audio(wav_bytes(sine(220, 2)))
    assert result["agreement"]["frame_count"] == 101
    assert result["agreement"]["overlapping_voiced_frames"] > 50
    assert result["rmvpe"]["estimator"] == "rmvpe"


def test_checkpoint_hash_mismatch_is_rejected(monkeypatch, tmp_path: Path) -> None:
    import ai_singer.rmvpe_pitch as module
    model = tmp_path / "rmvpe.onnx"
    model.write_bytes(b"invalid-weight-file")
    module._load_model.cache_clear()
    with pytest.raises(RMVPEUnavailable, match="SHA-256"):
        module._load_model(str(model))
