"""Opt-in, local RVC voice preview. This module does not install or download models.

RVC is an untrusted external executable/checkpoint. Use only a locally reviewed
installation and a voice model whose training/inference rights you have verified.
"""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import threading
import wave

import numpy as np

from ai_singer.audio_analysis import SAMPLE_RATE, decode_audio
from ai_singer.storage import StorageConfigurationError, configured_storage_root

VOICE_ID = re.compile(r"^[a-z][a-z0-9_-]{0,39}$")
MANIFEST_NAME = "voices.json"
MAX_MANIFEST_BYTES = 64 * 1024
MAX_OUTPUT_BYTES = 25 * 1024 * 1024
RENDER_TIMEOUT_SECONDS = 240
_RENDER_LOCK = threading.Lock()


class VoiceConfigurationError(RuntimeError):
    """An explicitly configured voice or local RVC installation is unavailable."""


class VoiceRenderError(RuntimeError):
    """A configured RVC renderer could not produce an audio preview."""


class VoiceBusyError(RuntimeError):
    """Another render is already running in this server process."""


@dataclass(frozen=True)
class VoiceProfile:
    id: str
    label: str
    model_path: Path
    speaker_id: int


def _voice_base() -> Path:
    try:
        return configured_storage_root().resolve() / "models" / "voice_conversion"
    except StorageConfigurationError as exc:
        raise VoiceConfigurationError(str(exc)) from exc


def _model_under_base(base: Path, relative: str) -> Path:
    """Reject drive paths, traversal, symlinks escaping the trusted model directory."""
    if not isinstance(relative, str) or not relative or "\\" in relative or ":" in relative:
        raise VoiceConfigurationError("Voice model must use a relative forward-slash path.")
    target = Path(relative)
    if target.is_absolute() or any(p in ("..", ".") for p in relative.split("/")):
        raise VoiceConfigurationError("Voice model path must remain inside the voice model directory.")
    resolved = (base / target).resolve()
    if not resolved.is_relative_to(base.resolve()) or resolved.suffix.lower() != ".pth":
        raise VoiceConfigurationError("Voice checkpoint must be a .pth file inside the voice model directory.")
    return resolved


def _manifest_rows() -> tuple[Path, list[dict]]:
    base = _voice_base()
    file = base / MANIFEST_NAME
    if not file.is_file():
        return base, []
    if file.stat().st_size > MAX_MANIFEST_BYTES:
        raise VoiceConfigurationError("Voice manifest is too large (64 KiB maximum).")
    try:
        parsed = json.loads(file.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise VoiceConfigurationError("Cannot read voice manifest JSON.") from exc
    if not isinstance(parsed, dict) or not isinstance(parsed.get("voices"), list) or len(parsed["voices"]) > 20:
        raise VoiceConfigurationError("Voice manifest must contain at most 20 voice entries.")
    return base, parsed["voices"]


def _profiles() -> list[VoiceProfile]:
    base, rows = _manifest_rows()
    result = []
    seen = set()
    for row in rows:
        if not isinstance(row, dict):
            raise VoiceConfigurationError("Each voice entry must be an object.")
        voice_id, label = row.get("id"), row.get("label")
        if not isinstance(voice_id, str) or not VOICE_ID.fullmatch(voice_id) or voice_id in seen:
            raise VoiceConfigurationError("Voice ID must be unique, lowercase and use letters/numbers/-/_.")
        seen.add(voice_id)
        if not isinstance(label, str) or not (1 <= len(label.strip()) <= 70):
            raise VoiceConfigurationError("Voice label must be between 1 and 70 characters.")
        speaker = row.get("speaker_id", 0)
        if isinstance(speaker, bool) or not isinstance(speaker, int) or not 0 <= speaker <= 109:
            raise VoiceConfigurationError("Voice speaker_id must be an integer between 0 and 109.")
        if row.get("enabled") is not True or row.get("rights_confirmed") is not True:
            continue  # An unapproved or disabled checkpoint cannot be selected.
        path = _model_under_base(base, row.get("model"))
        result.append(VoiceProfile(voice_id, label.strip(), path, speaker))
    return result


def list_voices() -> list[dict]:
    """Expose only identifiers and readiness, never local paths or checkpoint bytes."""
    return [{"id": p.id, "label": p.label, "ready": p.model_path.is_file()}
            for p in _profiles()]


def _select_profile(voice_id: str) -> VoiceProfile:
    selected = next((p for p in _profiles() if p.id == voice_id), None)
    if selected is None:
        raise VoiceConfigurationError("Voice is not enabled or does not have confirmed usage rights.")
    if not selected.model_path.is_file():
        raise VoiceConfigurationError("The approved voice checkpoint is missing from the external drive.")
    return selected


def _rvc_runtime() -> tuple[Path, Path]:
    raw_root = os.environ.get("AI_SINGER_RVC_ROOT", "").strip()
    raw_python = os.environ.get("AI_SINGER_RVC_PYTHON", "").strip()
    if not raw_root or not raw_python:
        raise VoiceConfigurationError("Set AI_SINGER_RVC_ROOT and AI_SINGER_RVC_PYTHON for a reviewed local RVC installation.")
    root, python = Path(raw_root).expanduser(), Path(raw_python).expanduser()
    if not root.is_absolute() or not python.is_absolute():
        raise VoiceConfigurationError("RVC installation and Python paths must be absolute.")
    if not root.is_dir() or not (root / "infer" / "cli.py").is_file() or not python.is_file():
        raise VoiceConfigurationError("RVC runtime was not found. Check its root and dedicated Python path.")
    return root.resolve(), python.resolve()


def _pcm_wav(samples: np.ndarray) -> bytes:
    audio = np.clip(samples, -1.0, 1.0)
    with BytesIO() as stream:
        with wave.open(stream, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(SAMPLE_RATE)
            w.writeframes((audio * 32767).astype("<i2").tobytes())
        return stream.getvalue()


def _output_duration(path: Path) -> float:
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
            capture_output=True, text=True, timeout=15, check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        raise VoiceRenderError("FFprobe is required to check the converted audio.") from exc
    if result.returncode:
        raise VoiceRenderError("Cannot verify converted audio duration.")
    try:
        duration = float(result.stdout.strip())
    except ValueError as exc:
        raise VoiceRenderError("Converted audio duration is invalid.") from exc
    if not np.isfinite(duration):
        raise VoiceRenderError("Converted audio duration is not finite.")
    return duration


def render_voice(recording: bytes, voice_id: str, *, authorized_use: bool) -> bytes:
    """Return one unpersisted WAV preview; preserve the sung pitch (RVC --pitch 0)."""
    if authorized_use is not True:
        raise VoiceConfigurationError("Confirm the uploaded recording and selected voice are authorized for this use.")
    profile = _select_profile(voice_id)
    root, python = _rvc_runtime()
    # Decode once and check the 1–15-second/10-MiB API input limits.
    samples = decode_audio(recording)
    original_duration = len(samples) / SAMPLE_RATE
    if not _RENDER_LOCK.acquire(blocking=False):
        raise VoiceBusyError("A voice render is already in progress. Try again when it finishes.")
    try:
        storage = configured_storage_root().resolve()
        work = storage / "cache" / "voice_previews"
        work.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="ai_singer_rvc_", dir=work) as folder:
            source = Path(folder) / "source.wav"
            output = Path(folder) / "converted.wav"
            source.write_bytes(_pcm_wav(samples))
            cmd = [str(python), str(root / "infer" / "cli.py"),
                   "--model", str(profile.model_path),
                   "--speaker-id", str(profile.speaker_id),
                   "--input", str(source), "--output", str(output),
                   "--pitch", "0", "--f0-method", "rmvpe", "--index-rate", "0"]
            env = os.environ.copy()
            env["HF_HUB_OFFLINE"] = "1"
            env["TRANSFORMERS_OFFLINE"] = "1"
            env["PYTHONNOUSERSITE"] = "1"
            try:
                task = subprocess.run(cmd, cwd=root, env=env,
                                      capture_output=True, timeout=RENDER_TIMEOUT_SECONDS,
                                      check=False)
            except subprocess.TimeoutExpired as exc:
                raise VoiceRenderError("RVC rendering timed out; try a shorter phrase or CPU runtime.") from exc
            except OSError as exc:
                raise VoiceConfigurationError("Unable to start the configured RVC Python executable.") from exc
            if task.returncode != 0:
                # Third-party logs may contain local paths/private data; don't expose them to the browser.
                raise VoiceRenderError("RVC conversion failed. Inspect your local RVC installation and model compatibility.")
            if not output.is_file() or not 44 <= output.stat().st_size <= MAX_OUTPUT_BYTES:
                raise VoiceRenderError("RVC did not produce a valid-size WAV preview.")
            converted_duration = _output_duration(output)
            if not (0.5 <= converted_duration <= 18.0 and abs(converted_duration - original_duration) <= 1.5):
                raise VoiceRenderError("Rendered output duration differs too much from the original phrase.")
            return output.read_bytes()
    finally:
        _RENDER_LOCK.release()
