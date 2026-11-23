"""Regression checks for the reproducible known-pitch reference fixture."""

import io
import json
from pathlib import Path
import wave

import numpy as np
import pytest

from ai_singer.audio_analysis import analyze_audio, decode_audio
from ai_singer.calibration import (
    CalibrationError,
    calibration_directory,
    compare_calibration,
    generate_calibration,
    main,
    wave_bytes,
    write_calibration_files,
)
from ai_singer.pitch_validation import score_pitch, validate_reference


def test_calibration_has_exact_known_intervals() -> None:
    samples, reference = generate_calibration()
    assert len(samples) == 120800  # 7.55 sec at 16 kHz
    assert len(reference["segments"]) == 8
    validate_reference(reference, 7.55)
    assert [x["midi_note"] for x in reference["segments"]] == [None, 57, None, 60, 62, None, 57, None]
    assert reference["slide_unscored_seconds"] == [3.35, 4.20]


def test_calibration_is_quiet_on_annotated_rests() -> None:
    samples, reference = generate_calibration()
    for segment in reference["segments"]:
        if segment["midi_note"] is None:
            a = round(segment["start_seconds"] * 16000)
            b = round(segment["end_seconds"] * 16000)
            assert np.max(abs(samples[a:b])) == 0


def test_calibration_wave_round_trip() -> None:
    original, _ = generate_calibration()
    encoded = wave_bytes(original)
    with wave.open(io.BytesIO(encoded), "rb") as reader:
        assert reader.getnchannels() == 1
        assert reader.getframerate() == 16000
        assert reader.getsampwidth() == 2
    decoded = decode_audio(encoded)
    assert np.max(np.abs(decoded - original)) < 0.0001


def test_known_pitch_scores_yin_against_actual_reference() -> None:
    samples, reference = generate_calibration()
    result = analyze_audio(samples)
    score = score_pitch(result, reference)
    assert score["labeled_pitch_frames"] > 100
    assert score["median_absolute_pitch_error_cents"] < 20
    assert score["within_50_cents_fraction"] > 0.95
    assert score["octave_error_frames"] == 0


def test_write_creates_pair_only_under_selected_directory(tmp_path: Path) -> None:
    output = tmp_path / "calibration"
    wav_path, ref_path = write_calibration_files(output)
    assert wav_path.is_file() and ref_path.is_file()
    assert json.loads(ref_path.read_text())["segments"]
    with pytest.raises(CalibrationError, match="already exist"):
        write_calibration_files(output)
    new_wav, _ = write_calibration_files(output, overwrite=True)
    assert new_wav == wav_path


def test_reject_relative_output(tmp_path: Path) -> None:
    with pytest.raises(CalibrationError, match="absolute"):
        write_calibration_files(Path("relative"))


def test_default_output_requires_configured_external_root(monkeypatch) -> None:
    monkeypatch.delenv("AI_SINGER_STORAGE_ROOT", raising=False)
    with pytest.raises(CalibrationError, match="not configured"):
        calibration_directory()


def test_default_output_is_under_configured_root(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AI_SINGER_STORAGE_ROOT", str(tmp_path))
    assert calibration_directory() == tmp_path / "outputs" / "previews" / "calibration"


def test_cli_creates_known_files_no_model_needed(monkeypatch, tmp_path: Path) -> None:
    import sys
    monkeypatch.setenv("AI_SINGER_STORAGE_ROOT", str(tmp_path))
    monkeypatch.setattr(sys, "argv", ["calibration"])
    assert main() == 0
    assert main() == 0  # Reuse existing files on subsequent invocation
    assert (calibration_directory() / "known-pitch-calibration.wav").is_file()


def test_comparison_generates_saved_scored_reports(monkeypatch, tmp_path: Path) -> None:
    import ai_singer.pitch_benchmark as module
    path, ref = write_calibration_files(tmp_path)
    def fake_benchmark(encoded: bytes) -> dict:
        result = analyze_audio(decode_audio(encoded))
        return {"yin": result, "rmvpe": dict(result, estimator="rmvpe")}
    monkeypatch.setattr(module, "benchmark_audio", fake_benchmark)
    scores = compare_calibration(path, ref)
    assert scores["yin"]["within_50_cents_fraction"] > 0.95
    assert scores["rmvpe"]["within_50_cents_fraction"] > 0.95
    assert (tmp_path / "known-pitch-comparison.json").exists()
    assert (tmp_path / "known-pitch-scores.json").exists()


def test_reference_slide_is_progressive_and_not_labeled_as_fixed_note() -> None:
    samples, reference = generate_calibration()
    track = analyze_audio(samples)["pitch_track"]
    def at(second: float) -> float:
        return next(point["midi_note"] for point in track if abs(point["time_seconds"] - second) < 0.001)
    assert 60 < at(3.46) < at(3.86) < 62
    for span in reference["segments"]:
        assert span["end_seconds"] <= 3.35 or span["start_seconds"] >= 4.20


def test_synthetic_calibration_event_grouping_keeps_c4_and_d4():
    """Regression for the previously merged C4 -> glide -> D4 passage."""
    samples, _ = generate_calibration()
    result = analyze_audio(samples)
    mids = [event["midi_note"] for event in result["note_events"]]
    assert mids == [57, 60, 62, 57]
    assert any(item["classification"] == "glide_candidate"
               and item["start_seconds"] < 3.8 < item["end_seconds"]
               for item in result["pitch_transitions"])
