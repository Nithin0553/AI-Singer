"""Explicitly saved local singing takes and review notes on external storage.

No recordings are retained by the normal /render-voice preview. Director
sessions are opt-in, immutable audio takes with atomic JSON metadata updates.
This store is intended for one localhost Uvicorn worker, not a multi-user server.
"""
from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO
import json
import math
import os
from pathlib import Path
import re
import shutil
import tempfile
import threading
from uuid import uuid4
import wave

from ai_singer.audio_analysis import decode_audio
from ai_singer.passage_edits import PassageEditError, edit_passage, suggest_audible_passage
from ai_singer.storage import configured_storage_root
from ai_singer.voice_render import MAX_OUTPUT_BYTES, _pcm_wav, _select_profile, render_voice

_LOCK = threading.RLock()
_ID = re.compile(r"^[0-9a-f]{32}$")
_ORIGINAL_TYPES = {
    "wav": "audio/wav", "m4a": "audio/mp4", "mp3": "audio/mpeg",
    "webm": "audio/webm", "ogg": "audio/ogg", "flac": "audio/flac",
}


def _original_extension(raw: bytes) -> str:
    """Identify playable upload type from bytes, never user-provided filenames."""
    if raw.startswith(b"RIFF") and raw[8:12] == b"WAVE":
        return "wav"
    if len(raw) >= 12 and raw[4:8] == b"ftyp":
        return "m4a"
    if raw.startswith(b"ID3") or (len(raw) > 2 and raw[0] == 255 and raw[1] & 224 == 224):
        return "mp3"
    if raw.startswith(bytes.fromhex("1a45dfa3")):
        return "webm"
    if raw.startswith(b"OggS"):
        return "ogg"
    if raw.startswith(b"fLaC"):
        return "flac"
    raise DirectorInputError("Unsupported source audio container for saved sessions.")

MAX_SESSIONS = 30
MAX_TAKES = 12
MAX_FEEDBACK = 100
MAX_METADATA_BYTES = 128 * 1024


class DirectorInputError(ValueError):
    """Invalid user data, reference or saved session."""


class DirectorLimitError(DirectorInputError):
    """A local session/take/note limit was reached."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _base() -> Path:
    root = configured_storage_root().resolve()
    base = root / "outputs" / "director_sessions"
    if not base.resolve().is_relative_to(root):
        raise DirectorInputError("Director storage points outside the configured external drive.")
    return base


def _path(session_id: str) -> Path:
    if not isinstance(session_id, str) or not _ID.fullmatch(session_id):
        raise DirectorInputError("Invalid session ID.")
    base = _base()
    directory = base / session_id
    if not directory.is_dir() or directory.is_symlink() or not directory.resolve().is_relative_to(base.resolve()):
        raise DirectorInputError("Saved session not found.")
    return directory


def _read(session_id: str) -> dict:
    directory = _path(session_id)
    meta = directory / "session.json"
    if meta.is_symlink() or not meta.is_file() or meta.stat().st_size > MAX_METADATA_BYTES:
        raise DirectorInputError("Saved session metadata is unavailable.")
    try:
        data = json.loads(meta.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError) as exc:
        raise DirectorInputError("Saved session metadata cannot be read.") from exc
    if not isinstance(data, dict) or data.get("id") != session_id:
        raise DirectorInputError("Saved session metadata is invalid.")
    if not isinstance(data.get("takes"), list) or not isinstance(data.get("feedback"), list):
        raise DirectorInputError("Saved session metadata is incomplete.")
    return data


def _atomic_json(path: Path, data: dict) -> None:
    encoded = (json.dumps(data, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if len(encoded) > MAX_METADATA_BYTES:
        raise DirectorLimitError("Session metadata limit reached.")
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".metadata-", suffix=".tmp",
                                         delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _audio_file(session_id: str, name: str) -> Path:
    directory = _path(session_id)
    if not (name in {"original." + ext for ext in _ORIGINAL_TYPES} or
            (name.startswith("take_") and name.endswith(".wav") and _ID.fullmatch(name[5:-4]))):
        raise DirectorInputError("Unknown audio file.")
    audio = directory / name
    if audio.is_symlink() or not audio.is_file() or not audio.resolve().is_relative_to(directory.resolve()):
        raise DirectorInputError("Saved recording is unavailable.")
    return audio


def _wav_seconds(data: bytes) -> float:
    if len(data) > MAX_OUTPUT_BYTES:
        raise DirectorInputError("Converted WAV exceeds 25 MiB.")
    try:
        with wave.open(BytesIO(data), "rb") as wav:
            if wav.getcomptype() != "NONE" or wav.getnchannels() != 1 or wav.getsampwidth() != 2:
                raise DirectorInputError("Converted WAV must be mono, uncompressed 16-bit PCM.")
            if not 8000 <= wav.getframerate() <= 96000:
                raise DirectorInputError("Unsupported converted WAV sample rate.")
            duration = wav.getnframes() / wav.getframerate()
            if not 0.5 <= duration <= 18.0:
                raise DirectorInputError("Converted WAV must be between 0.5 and 18 seconds.")
            # Reject truncated or malformed files, not just valid-looking headers.
            if len(wav.readframes(wav.getnframes())) != wav.getnframes() * 2:
                raise DirectorInputError("Converted WAV is incomplete.")
    except (wave.Error, EOFError) as exc:
        raise DirectorInputError("Converted file must be a valid PCM WAV.") from exc
    return duration


def _validate_pair(original_wav: bytes, converted_wav: bytes) -> float:
    with wave.open(BytesIO(original_wav), "rb") as wav:
        duration = wav.getnframes() / wav.getframerate()
    if abs(_wav_seconds(converted_wav) - duration) > 1.5:
        raise DirectorInputError("Converted recording timing differs too much from the original.")
    return round(duration, 3)


def _require_voice(voice_id: str, authorized: bool) -> None:
    if authorized is not True:
        raise DirectorInputError("Confirm the original recording and voice model are authorized.")
    _select_profile(voice_id)


def create_session(source: bytes, preview: bytes, voice_id: str, *, authorized: bool) -> dict:
    """Only an explicit Save action persists the original and converted WAV."""
    _require_voice(voice_id, authorized)
    extension = _original_extension(source)
    original_pcm = _pcm_wav(decode_audio(source))
    duration = _validate_pair(original_pcm, preview)
    with _LOCK:
        base = _base()
        base.mkdir(parents=True, exist_ok=True)
        sessions = [p for p in base.iterdir() if p.is_dir() and _ID.fullmatch(p.name)]
        if len(sessions) >= MAX_SESSIONS:
            raise DirectorLimitError("Director Mode holds at most 30 sessions. Export older work first.")
        session_id, take_id = uuid4().hex, uuid4().hex
        stage = base / (".pending-" + session_id)
        stage.mkdir()
        try:
            (stage / ("original." + extension)).write_bytes(source)
            (stage / f"take_{take_id}.wav").write_bytes(preview)
            data = {
                "id": session_id, "created_at": _now(), "duration_seconds": duration,
                "original_name": "Original singing", "original_extension": extension, "voice_id": voice_id,
                "approved_take_id": None, "feedback": [],
                "takes": [{"id": take_id, "voice_id": voice_id,
                           "created_at": _now(), "label": "Take 1"}],
            }
            _atomic_json(stage / "session.json", data)
            stage.rename(base / session_id)
        finally:
            if stage.exists():
                shutil.rmtree(stage)
        return data


def get_session(session_id: str) -> dict:
    with _LOCK:
        return _read(session_id)


def list_sessions() -> list[dict]:
    with _LOCK:
        base = _base()
        if not base.is_dir():
            return []
        result = []
        for folder in base.iterdir():
            if not folder.is_dir() or folder.is_symlink() or not _ID.fullmatch(folder.name):
                continue
            try:
                entry = _read(folder.name)
            except DirectorInputError:
                continue
            result.append({
                "id": entry["id"], "created_at": entry["created_at"],
                "duration_seconds": entry["duration_seconds"],
                "voice_id": entry["voice_id"],
                "approved_take_id": entry["approved_take_id"],
                "take_count": len(entry["takes"]),
            })
        return sorted(result, key=lambda e: e["created_at"], reverse=True)[:MAX_SESSIONS]


def original_audio(session_id: str) -> tuple[Path, str]:
    data = _read(session_id)
    extension = data.get("original_extension")
    if extension not in _ORIGINAL_TYPES:
        raise DirectorInputError("Unsupported saved source format.")
    return _audio_file(session_id, "original." + extension), _ORIGINAL_TYPES[extension]


def take_audio(session_id: str, take_id: str) -> Path:
    with _LOCK:
        data = _read(session_id)
        if not isinstance(take_id, str) or not _ID.fullmatch(take_id) or not any(t["id"] == take_id for t in data["takes"]):
            raise DirectorInputError("Take not found.")
        return _audio_file(session_id, f"take_{take_id}.wav")


def approve_take(session_id: str, take_id: str) -> dict:
    with _LOCK:
        data = _read(session_id)
        if not isinstance(take_id, str) or not _ID.fullmatch(take_id) or not any(t["id"] == take_id for t in data["takes"]):
            raise DirectorInputError("Take not found.")
        data["approved_take_id"] = take_id
        _atomic_json(_path(session_id) / "session.json", data)
        return data


def add_feedback(session_id: str, take_id: str, start: float, end: float, instruction: str) -> dict:
    with _LOCK:
        data = _read(session_id)
        if not isinstance(take_id, str) or not _ID.fullmatch(take_id) or not any(t["id"] == take_id for t in data["takes"]):
            raise DirectorInputError("Take not found.")
        if len(data["feedback"]) >= MAX_FEEDBACK:
            raise DirectorLimitError("This session already has 100 correction notes.")
        duration = float(data["duration_seconds"])
        if (isinstance(start, bool) or isinstance(end, bool)
            or not isinstance(start, (float, int)) or not isinstance(end, (float, int))
            or not math.isfinite(start) or not math.isfinite(end)
            or not 0 <= start < end <= duration):
            raise DirectorInputError("Correction times must be within the original recording.")
        if not isinstance(instruction, str) or not 1 <= len(instruction.strip()) <= 300:
            raise DirectorInputError("Write a correction note between 1 and 300 characters.")
        note = {"id": uuid4().hex, "take_id": take_id,
                "start_seconds": round(start, 3), "end_seconds": round(end, 3),
                "instruction": instruction.strip(), "created_at": _now(),
                "status": "pending_review"}
        data["feedback"].append(note)
        _atomic_json(_path(session_id) / "session.json", data)
        return note


def render_next_take(session_id: str, voice_id: str, *, authorized: bool) -> dict:
    """Re-run the full source with RVC. Feedback is recorded, NOT interpreted."""
    _require_voice(voice_id, authorized)
    with _LOCK:
        current = _read(session_id)
        if len(current["takes"]) >= MAX_TAKES:
            raise DirectorLimitError("This session holds at most 12 takes.")
        original = original_audio(session_id)[0].read_bytes()
    preview = render_voice(original, voice_id, authorized_use=True)
    _validate_pair(_pcm_wav(decode_audio(original)), preview)
    with _LOCK:
        current = _read(session_id)
        if len(current["takes"]) >= MAX_TAKES:
            raise DirectorLimitError("This session holds at most 12 takes.")
        new_id = uuid4().hex
        target = _path(session_id) / f"take_{new_id}.wav"
        temporary = target.with_suffix(".part")
        try:
            temporary.write_bytes(preview)
            os.replace(temporary, target)
            current["takes"].append({
                "id": new_id, "voice_id": voice_id, "created_at": _now(),
                "label": f"Take {len(current['takes']) + 1}",
            })
            _atomic_json(_path(session_id) / "session.json", current)
        except Exception:
            # The metadata is the durable commit point. Avoid orphaned takes.
            target.unlink(missing_ok=True)
            raise
        finally:
            temporary.unlink(missing_ok=True)
        return current


def audible_passage_hint(session_id: str, take_id: str) -> dict:
    """Expose a read-only loudness-based interval suggestion for one saved take."""
    with _LOCK:
        path = take_audio(session_id, take_id)
        return suggest_audible_passage(path.read_bytes())


def edit_take(
    session_id: str, take_id: str, start_seconds: float, end_seconds: float,
    operation: str, value: float,
) -> dict:
    """Apply an explicitly selected DSP operation; append a new, unapproved take.

    Text feedback is NOT interpreted or executed here. The director chooses
    both the region and numeric adjustment. Originals/approved takes stay
    immutable and unaffected segments remain sample-exact.
    """
    with _LOCK:
        current = _read(session_id)
        if not isinstance(take_id, str) or not _ID.fullmatch(take_id):
            raise DirectorInputError("Take not found.")
        selected = next((t for t in current["takes"] if t["id"] == take_id), None)
        if selected is None:
            raise DirectorInputError("Take not found.")
        if len(current["takes"]) >= MAX_TAKES:
            raise DirectorLimitError("This session holds at most 12 takes.")
        source = _audio_file(session_id, f"take_{take_id}.wav").read_bytes()
        # Avoid editing portions beyond the original performance even if a
        # prior RVC output includes some extra tail silence.
        if (isinstance(end_seconds, bool) or not isinstance(end_seconds, (float, int))
                or not math.isfinite(end_seconds)
                or end_seconds > float(current["duration_seconds"])):
            raise DirectorInputError("Edit interval exceeds the original performance.")

    # CPU DSP can take time. Do not block readers/approvals while it runs.
    candidate, details = edit_passage(
        source, start_seconds=start_seconds, end_seconds=end_seconds,
        operation=operation, value=value,
    )
    with _LOCK:
        latest = _read(session_id)
        if len(latest["takes"]) >= MAX_TAKES:
            raise DirectorLimitError("This session holds at most 12 takes.")
        if not any(t["id"] == take_id for t in latest["takes"]):
            raise DirectorInputError("Source take no longer exists.")
        new_id = uuid4().hex
        target = _path(session_id) / f"take_{new_id}.wav"
        temporary = target.with_suffix(".part")
        n = len(latest["takes"]) + 1
        unit = "st" if operation == "pitch" else "dB"
        label = f"Take {n} · {operation} {details['value']:+g} {unit}"
        try:
            temporary.write_bytes(candidate)
            os.replace(temporary, target)
            latest["takes"].append({
                "id": new_id, "voice_id": selected["voice_id"],
                "created_at": _now(), "label": label,
                "source_take_id": take_id, "edit": details,
            })
            _atomic_json(_path(session_id) / "session.json", latest)
        except Exception:
            target.unlink(missing_ok=True)
            raise
        finally:
            temporary.unlink(missing_ok=True)
        return latest
