"""Bounded, non-destructive DSP for explicit Director Mode passage changes.

This is NOT natural-language interpretation or new vocal synthesis. A director
selects an existing take, time interval, operation and numeric amount. Only
samples within the selected interval are changed; transitions are blended
inside that interval to preserve sample values outside it.
"""
from __future__ import annotations

from io import BytesIO
import math
import wave

import numpy as np


class PassageEditError(ValueError):
    """Invalid edit, time selection, or source recording."""


MAX_WAV_BYTES = 25 * 1024 * 1024
MIN_PASSAGE_SECONDS = 0.35
MAX_PITCH_SECONDS = 8.0
CROSSFADE_SECONDS = 0.045


def _number(value: object, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise PassageEditError(f"{name} must be a finite number.")
    value = float(value)
    if not math.isfinite(value):
        raise PassageEditError(f"{name} must be a finite number.")
    return value


def _read_wav(data: bytes) -> tuple[np.ndarray, int]:
    if not isinstance(data, bytes) or len(data) > MAX_WAV_BYTES:
        raise PassageEditError("Take must be a valid WAV no larger than 25 MiB.")
    try:
        with wave.open(BytesIO(data), "rb") as source:
            if (source.getcomptype() != "NONE" or source.getnchannels() != 1
                    or source.getsampwidth() != 2 or not 8000 <= source.getframerate() <= 96000):
                raise PassageEditError("Take must be mono 16-bit PCM WAV (8–96 kHz).")
            sr = source.getframerate()
            n = source.getnframes()
            if not 0.5 <= n / sr <= 18.0:
                raise PassageEditError("Take duration must be between 0.5 and 18 seconds.")
            frames = source.readframes(n)
            if len(frames) != n * 2:
                raise PassageEditError("Source WAV is truncated.")
    except (wave.Error, EOFError) as exc:
        raise PassageEditError("Source is not a readable PCM WAV.") from exc
    return np.frombuffer(frames, dtype="<i2").copy(), sr


def _write_wav(samples: np.ndarray, sr: int) -> bytes:
    output = BytesIO()
    with wave.open(output, "wb") as dest:
        dest.setnchannels(1)
        dest.setsampwidth(2)
        dest.setframerate(sr)
        dest.writeframes(samples.astype("<i2", copy=False).tobytes())
    return output.getvalue()


def edit_passage(
    wav_bytes: bytes, *, start_seconds: float, end_seconds: float,
    operation: str, value: float,
) -> tuple[bytes, dict]:
    """Return a candidate full-length take, never modify the input bytes.

    'pitch' is a uniform time-preserving pitch shift in semitones, not note-
    aware singing synthesis. 'gain' changes dB level. All outside-interval PCM
    samples remain *exactly* identical, with a raised-cosine blend inside.
    """
    original, sr = _read_wav(wav_bytes)
    start = _number(start_seconds, "Start time")
    end = _number(end_seconds, "End time")
    amount = _number(value, "Edit amount")
    duration = len(original) / sr
    if not 0 <= start < end <= duration + 1e-7:
        raise PassageEditError("Edit range must be within the selected take.")
    if end - start < MIN_PASSAGE_SECONDS:
        raise PassageEditError("Select a passage of at least 0.35 seconds.")
    if operation == "pitch":
        if not 0 < abs(amount) <= 3:
            raise PassageEditError("Pitch change must be between -3 and +3 semitones, excluding zero.")
        if end - start > MAX_PITCH_SECONDS:
            raise PassageEditError("Pitch edits are limited to 8 seconds per passage.")
    elif operation == "gain":
        if not 0 < abs(amount) <= 9:
            raise PassageEditError("Gain change must be between -9 and +9 dB, excluding zero.")
    else:
        raise PassageEditError("Supported edits are 'pitch' (semitones) and 'gain' (dB).")

    # Use ceil/floor so no samples outside the user's requested interval change.
    lo = math.ceil(start * sr)
    hi = math.floor(end * sr)
    if hi - lo < int(MIN_PASSAGE_SECONDS * sr) - 2:
        raise PassageEditError("Selected interval is too short at this sample rate.")
    src = original[lo:hi].astype(np.float32) / 32768.0
    if operation == "gain":
        modified = src * (10.0 ** (amount / 20.0))
    else:
        import librosa
        try:
            modified = librosa.effects.pitch_shift(src, sr=sr, n_steps=amount)
        except (ValueError, RuntimeError) as exc:
            raise PassageEditError("Pitch adjustment failed on this passage.") from exc
        if modified.size != src.size:
            # Libraries can pad or trim internally; never shift global timing.
            modified = np.pad(modified[:src.size], (0, max(0, src.size - modified.size)))
    if modified.shape != src.shape or not np.isfinite(modified).all():
        raise PassageEditError("The DSP edit produced invalid audio samples.")

    # The fade is fully *inside* the selected region. Original PCM samples
    # before lo and after hi are copied verbatim, including approved sections.
    width = len(src)
    ramp = min(int(sr * CROSSFADE_SECONDS), width // 4)
    weights = np.ones(width, dtype=np.float32)
    if ramp > 1:
        t = np.linspace(0.0, 1.0, ramp, endpoint=True, dtype=np.float32)
        fade = (1.0 - np.cos(np.pi * t)) * 0.5
        weights[:ramp] = fade
        weights[-ramp:] = fade[::-1]
    combined = src * (1.0 - weights) + modified * weights
    result = original.copy()
    result[lo:hi] = np.rint(np.clip(combined * 32768.0, -32768, 32767)).astype("<i2")
    detail = {
        "operation": operation, "value": round(amount, 3),
        "unit": "semitones" if operation == "pitch" else "dB",
        "start_seconds": round(start, 3), "end_seconds": round(end, 3),
        "fade_ms": int(round(CROSSFADE_SECONDS * 1000)),
    }
    return _write_wav(result, sr), detail
