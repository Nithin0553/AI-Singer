"""Small, CPU-only baseline for listening to a completed vocal phrase."""

from dataclasses import dataclass
import math
from pathlib import Path
import subprocess
import tempfile

import librosa
import numpy as np
from scipy.ndimage import median_filter

SAMPLE_RATE = 16_000
HOP_LENGTH = 320
FRAME_LENGTH = 2_048
MIN_DURATION_SECONDS = 1.0
MAX_DURATION_SECONDS = 15.0
MAX_UPLOAD_BYTES = 10 * 1024 * 1024
MAX_DECODE_SECONDS = 16


class AudioInputError(ValueError):
    """The submitted audio cannot be analyzed reliably."""


class AudioDecoderUnavailable(RuntimeError):
    """FFmpeg is missing from the backend process PATH."""


@dataclass(frozen=True)
class VoiceFrame:
    time_seconds: float
    frequency_hz: float | None
    midi_note: float | None
    rms: float


def decode_audio(data: bytes) -> np.ndarray:
    """Decode the first audio stream from a seekable, short-lived temporary file."""
    if not data:
        raise AudioInputError("The audio recording is empty.")
    if len(data) > MAX_UPLOAD_BYTES:
        raise AudioInputError("Recording exceeds the 10 MB upload limit.")

    # Some MP4/M4A files require seeking to locate metadata or audio samples.
    # Don't pass the uploaded filename to FFmpeg, and always remove the file.
    with tempfile.TemporaryDirectory(prefix="ai_singer_audio_") as temporary_dir:
        source_path = Path(temporary_dir) / "recording"
        source_path.write_bytes(data)
        command = [
            "ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error",
            "-threads", "1", "-i", str(source_path), "-map", "0:a:0",
            "-vn", "-ac", "1", "-ar", str(SAMPLE_RATE),
            "-t", str(MAX_DECODE_SECONDS), "-f", "f32le", "pipe:1",
        ]
        try:
            decoded = subprocess.run(command, capture_output=True, timeout=30, check=False)
        except FileNotFoundError as exc:
            raise AudioDecoderUnavailable("FFmpeg is not available in the server PATH.") from exc
        except subprocess.TimeoutExpired as exc:
            raise AudioInputError("Audio decoding timed out.") from exc

    if decoded.returncode or not decoded.stdout:
        raise AudioInputError(
            "Cannot decode the recording. Verify that the audio file plays and try WAV, M4A, MP3, or WebM."
        )
    if len(decoded.stdout) % 4:
        raise AudioInputError("The decoded audio is incomplete.")

    samples = np.frombuffer(decoded.stdout, dtype="<f4").copy()
    duration = samples.size / SAMPLE_RATE
    if not MIN_DURATION_SECONDS <= duration <= MAX_DURATION_SECONDS:
        raise AudioInputError("Record between 1 and 15 seconds of singing.")
    if not np.isfinite(samples).all():
        raise AudioInputError("The recording contains invalid audio samples.")
    return np.clip(samples, -1.0, 1.0)

def _periodicity(frame: np.ndarray, frequency: float) -> float:
    """Check whether a proposed fundamental actually repeats in the waveform."""
    lag = round(SAMPLE_RATE / frequency)
    if lag < 1 or lag >= frame.size // 2:
        return 0.0
    left, right = frame[:-lag], frame[lag:]
    denominator = math.sqrt(float(left @ left) * float(right @ right))
    return float((left @ right) / denominator) if denominator > 1e-10 else 0.0


def _segments(
    mask: np.ndarray, frame_step: float, min_frames: int, duration: float
) -> list[dict[str, float]]:
    """Group consecutive true frames into approximate time intervals."""
    intervals = []
    start = None
    for i in range(len(mask) + 1):
        active = bool(mask[i]) if i < len(mask) else False
        if active and start is None:
            start = i
        if not active and start is not None:
            if i - start >= min_frames:
                intervals.append({
                    "start_seconds": round(min(start * frame_step, duration), 3),
                    "end_seconds": round(min(i * frame_step, duration), 3),
                })
            start = None
    return intervals


def analyze_audio(samples: np.ndarray, estimator: str = "yin") -> dict:
    """Estimate vocal pitch, steady notes, and quiet intervals; no lyric transcription."""
    y = np.asarray(samples, dtype=np.float32)
    if y.ndim != 1 or y.size == 0:
        raise AudioInputError("Expected one non-empty mono audio channel.")

    duration_seconds = y.size / SAMPLE_RATE
    rms = librosa.feature.rms(
        y=y, frame_length=FRAME_LENGTH, hop_length=HOP_LENGTH, center=True,
    )[0]
    if estimator == "yin":
        f0 = librosa.yin(
            y, sr=SAMPLE_RATE, fmin=80, fmax=900,
            frame_length=FRAME_LENGTH, hop_length=HOP_LENGTH, center=True,
        )
    elif estimator == "rmvpe":
        from ai_singer.rmvpe_pitch import estimate_rmvpe
        f0 = estimate_rmvpe(y, len(rms), SAMPLE_RATE, HOP_LENGTH)
    else:
        raise ValueError(f"Unknown pitch estimator: {estimator}")

    if len(f0) != len(rms):
        raise RuntimeError("Audio feature lengths do not match.")

    padded = np.pad(y, FRAME_LENGTH // 2)
    frame_step = HOP_LENGTH / SAMPLE_RATE
    # Silence and periodicity are independent checks. YIN reports frequencies even for noise.
    silence_threshold = max(0.002, float(np.max(rms)) * 0.06)
    quiet = rms < silence_threshold
    voiced = np.zeros(len(f0), dtype=bool)
    for index, frequency in enumerate(f0):
        if not quiet[index] and math.isfinite(float(frequency)):
            if estimator == "rmvpe":
                voiced[index] = True  # Neural confidence filtering is applied by the adapter.
            else:
                frame = padded[index * HOP_LENGTH:index * HOP_LENGTH + FRAME_LENGTH]
                voiced[index] = _periodicity(frame, float(frequency)) >= 0.72

    midi = np.full(len(f0), np.nan)
    midi[voiced] = librosa.hz_to_midi(f0[voiced])
    frames = [
        VoiceFrame(
            time_seconds=round(index * frame_step, 3),
            frequency_hz=round(float(f0[index]), 2) if voiced[index] else None,
            midi_note=round(float(midi[index]), 2) if voiced[index] else None,
            rms=round(float(rms[index]), 5),
        ).__dict__
        for index in range(len(f0))
    ]

    # Candidate notes require stability; rapid slides intentionally remain in the pitch contour.
    notes: list[dict] = []
    quantized = np.full(len(midi), -1, dtype=int)
    for interval in _segments(voiced, frame_step, min_frames=4, duration=duration_seconds):
        begin = round(interval["start_seconds"] / frame_step)
        end = round(interval["end_seconds"] / frame_step)
        quantized[begin:end] = median_filter(np.rint(midi[begin:end]).astype(int), size=5)
    distinct = np.concatenate(([True], quantized[1:] != quantized[:-1], [True]))
    changes = np.flatnonzero(distinct)
    for begin, end in zip(changes[:-1], changes[1:]):
        if quantized[begin] >= 0 and end - begin >= 4:
            notes.append({
                "start_seconds": float(round(begin * frame_step, 3)),
                "end_seconds": float(round(min(end * frame_step, duration_seconds), 3)),
                "midi_note": int(quantized[begin]),
                "frequency_hz": round(float(librosa.midi_to_hz(quantized[begin])), 2),
            })

    warnings = ["Pitch and note boundaries are estimates, not a verified transcription."]
    if not np.any(voiced):
        warnings.append("No reliable voiced pitch detected. Try a clear solo vocal recording.")
    return {
        "estimator": estimator,
        "duration_seconds": round(y.size / SAMPLE_RATE, 3),
        "sample_rate_hz": SAMPLE_RATE,
        "hop_seconds": frame_step,
        "pitch_track": frames,
        "note_events": notes,
        "quiet_intervals": _segments(quiet, frame_step, min_frames=4, duration=duration_seconds),
        "warnings": warnings,
    }
