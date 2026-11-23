"""Generate a known-pitch audio fixture and optionally score both estimators."""

import argparse
import io
import json
from pathlib import Path
import wave

import numpy as np

from ai_singer.audio_analysis import SAMPLE_RATE
from ai_singer.pitch_validation import score_pitch
from ai_singer.storage import StorageConfigurationError, configured_storage_root

DURATION_SECONDS = 7.55
NOTE_FREQUENCIES = {57: 220.0, 60: 261.625565, 62: 293.664768}

# Deliberately leave transitions, note edges and the continuous slide unscored.
REFERENCE_SEGMENTS = [
    {"start_seconds": 0.05, "end_seconds": 0.25, "midi_note": None},
    {"start_seconds": 0.50, "end_seconds": 1.50, "midi_note": 57},
    {"start_seconds": 1.80, "end_seconds": 1.95, "midi_note": None},
    {"start_seconds": 2.25, "end_seconds": 3.15, "midi_note": 60},
    {"start_seconds": 4.35, "end_seconds": 5.30, "midi_note": 62},
    {"start_seconds": 5.60, "end_seconds": 5.75, "midi_note": None},
    {"start_seconds": 6.05, "end_seconds": 7.05, "midi_note": 57},
    {"start_seconds": 7.30, "end_seconds": 7.45, "midi_note": None},
]


class CalibrationError(RuntimeError):
    """A calibration artifact cannot be created at the configured destination."""


def generate_calibration() -> tuple[np.ndarray, dict]:
    """Synthesize four held notes, rests and one C4-to-D4 glide."""
    count = int(round(DURATION_SECONDS * SAMPLE_RATE))
    frequency = np.zeros(count, dtype=np.float64)

    def constant(start: float, stop: float, note: int) -> None:
        frequency[round(start * SAMPLE_RATE):round(stop * SAMPLE_RATE)] = NOTE_FREQUENCIES[note]

    constant(0.35, 1.65, 57)
    constant(2.10, 3.35, 60)
    begin, end = round(3.35 * SAMPLE_RATE), round(4.20 * SAMPLE_RATE)
    # An equal-tempered slide rises linearly in musical semitones, not Hz.
    midi = 60 + 2 * np.arange(end - begin, dtype=np.float64) / (end - begin)
    frequency[begin:end] = 440 * np.power(2.0, (midi - 69) / 12)
    constant(4.20, 5.45, 62)
    constant(5.90, 7.20, 57)

    phase = 2 * np.pi * np.cumsum(frequency) / SAMPLE_RATE
    harmonics = 0.40 * np.sin(phase) + 0.12 * np.sin(2 * phase) + 0.05 * np.sin(3 * phase)
    envelope = np.zeros(count, dtype=np.float64)
    fade = round(0.025 * SAMPLE_RATE)
    for start, end in [(0.35, 1.65), (2.10, 5.45), (5.90, 7.20)]:
        a, b = round(start * SAMPLE_RATE), round(end * SAMPLE_RATE)
        envelope[a:b] = 1.0
        envelope[a:a + fade] = np.linspace(0, 1, fade, endpoint=False)
        envelope[b - fade:b] = np.linspace(1, 0, fade, endpoint=False)

    samples = (harmonics * envelope).astype(np.float32)
    reference = {
        "description": "Synthetic calibration only: A3, rest, C4, C4-to-D4 slide, D4, rest, A3. Not a human singing test.",
        "duration_seconds": DURATION_SECONDS,
        "sample_rate_hz": SAMPLE_RATE,
        "slide_unscored_seconds": [3.35, 4.20],
        "segments": [dict(segment) for segment in REFERENCE_SEGMENTS],
    }
    return samples, reference


def wave_bytes(samples: np.ndarray) -> bytes:
    """Write standard signed 16-bit mono PCM, playable in Pitch Lab."""
    with io.BytesIO() as output:
        with wave.open(output, "wb") as handle:
            handle.setnchannels(1)
            handle.setsampwidth(2)
            handle.setframerate(SAMPLE_RATE)
            handle.writeframes((np.clip(samples, -1, 1) * 32767).astype("<i2").tobytes())
        return output.getvalue()


def calibration_directory() -> Path:
    """Resolve Seagate output from existing storage configuration; never fall back to C:."""
    try:
        return configured_storage_root() / "outputs" / "previews" / "calibration"
    except StorageConfigurationError as exc:
        raise CalibrationError(str(exc)) from exc


def write_calibration_files(destination: Path, *, overwrite: bool = False) -> tuple[Path, Path]:
    """Create the audio/reference pair without overwriting existing data by default."""
    if not destination.is_absolute():
        raise CalibrationError("Calibration output directory must be an absolute path.")
    wav_path = destination / "known-pitch-calibration.wav"
    ref_path = destination / "known-pitch-reference.json"
    if not overwrite and (wav_path.exists() or ref_path.exists()):
        raise CalibrationError("Calibration files already exist. Use --overwrite to regenerate them.")
    samples, reference = generate_calibration()
    destination.mkdir(parents=True, exist_ok=True)
    wav_path.write_bytes(wave_bytes(samples))
    ref_path.write_text(json.dumps(reference, indent=2) + "\n", encoding="utf-8")
    return wav_path, ref_path


def compare_calibration(wav_path: Path, ref_path: Path) -> dict:
    """Use the same benchmark and scoring functions as real-recording evaluation."""
    from ai_singer.pitch_benchmark import benchmark_audio

    report = benchmark_audio(wav_path.read_bytes())
    reference = json.loads(ref_path.read_text(encoding="utf-8"))
    scores = {name: score_pitch(report[name], reference) for name in ("yin", "rmvpe")}
    output = wav_path.parent
    (output / "known-pitch-comparison.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    (output / "known-pitch-scores.json").write_text(json.dumps(scores, indent=2) + "\n", encoding="utf-8")
    return scores


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compare", action="store_true", help="Run YIN and RMVPE and score known intervals")
    parser.add_argument("--overwrite", action="store_true", help="Explicitly replace existing calibration files")
    args = parser.parse_args()
    try:
        output = calibration_directory()
        audio_path = output / "known-pitch-calibration.wav"
        reference_path = output / "known-pitch-reference.json"
        if not audio_path.exists() or not reference_path.exists() or args.overwrite:
            audio_path, reference_path = write_calibration_files(output, overwrite=args.overwrite)
        print(f"Calibration audio: {audio_path}")
        print(f"Known-pitch reference: {reference_path}")
        if args.compare:
            result = compare_calibration(audio_path, reference_path)
            print(json.dumps(result, indent=2))
            print(f"Comparison and scores saved to {output}")
    except (CalibrationError, OSError, ValueError, RuntimeError) as exc:
        parser.exit(1, f"Calibration failed: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
