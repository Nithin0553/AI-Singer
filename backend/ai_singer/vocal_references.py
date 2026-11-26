"""Milestone 3.1: explicitly captured sung references, not automatic edits."""
from __future__ import annotations

from io import BytesIO
import json
import math
from pathlib import Path
import shutil
import tempfile
from uuid import uuid4
import wave

import numpy as np
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response

from ai_singer.audio_analysis import (
    MAX_UPLOAD_BYTES, AudioDecoderUnavailable, AudioInputError, analyze_audio, decode_audio,
)
from ai_singer.director_sessions import (
    DirectorInputError, DirectorLimitError, _ID, _LOCK, _now, _original_extension,
    _ORIGINAL_TYPES, _path, take_audio,
)
from ai_singer.storage import StorageConfigurationError
from ai_singer.rmvpe_pitch import RMVPEUnavailable

router = APIRouter()
MAX_REFERENCES = 12
MAX_REPORT_BYTES = 1024 * 1024
BASE = "/director/sessions/{session_id}/vocal-references"


def passage_wav(session_id: str, take_id: str, start: float, end: float) -> bytes:
    """Crop native PCM to a validated interval, without changing the saved take."""
    path = take_audio(session_id, take_id)
    with wave.open(str(path), "rb") as src:
        rate = src.getframerate()
        duration = src.getnframes() / rate
        if (not math.isfinite(start) or not math.isfinite(end)
                or start < 0 or end > duration + 0.000001 or not 1 <= end - start <= 15):
            raise DirectorInputError("Choose a 1–15 second interval within the selected take.")
        first, last = round(start * rate), min(src.getnframes(), round(end * rate))
        src.setpos(first)
        frames = src.readframes(last - first)
        params = src.getparams()
    out = BytesIO()
    with wave.open(out, "wb") as dest:
        dest.setparams(params)
        dest.writeframes(frames)
    return out.getvalue()


def compare_contours(target: dict, demo: dict) -> dict:
    """Compare equally spaced normalized-time frames; never infer a correction command."""
    def sampled(analysis):
        frames = analysis["pitch_track"]
        indices = np.rint(np.linspace(0, len(frames) - 1, 101)).astype(int)
        midi = np.array([np.nan if frames[i]["midi_note"] is None
                         else frames[i]["midi_note"] for i in indices], dtype=float)
        voiced = np.isfinite(midi)
        center = float(np.median(midi[voiced])) if voiced.any() else None
        relative = midi - center if center is not None else midi
        return midi, voiced, center, relative

    a, av, ac, ar = sampled(target)
    b, bv, bc, br = sampled(demo)
    common = av & bv
    overlap = int(common.sum())
    shape_error = None
    if overlap >= 10:
        shape_error = round(float(np.median(np.abs(ar[common] - br[common])) * 100), 1)
    warnings = [
        "Uniform time normalization only: local timing differences can be misaligned.",
        "Pitch and voicing are estimates; this does not measure lyrics, emotion, or singing quality.",
        "No edit or neural resynthesis is inferred from these measurements.",
    ]
    if overlap < 10:
        warnings.append("Too few jointly voiced points for a reliable contour comparison.")
    if target.get("octave_jump_candidates") or demo.get("octave_jump_candidates"):
        warnings.append("Possible octave excursions require listening review.")
    return {
        "alignment_method": "uniform_normalized_time_101_points",
        "target_duration_seconds": target["duration_seconds"],
        "demo_duration_seconds": demo["duration_seconds"],
        "duration_difference_seconds": round(demo["duration_seconds"] - target["duration_seconds"], 3),
        "target_voiced_points": int(av.sum()),
        "demo_voiced_points": int(bv.sum()),
        "jointly_voiced_points": overlap,
        "voicing_mismatch_points": int(np.count_nonzero(av != bv)),
        "register_difference_semitones": round(bc - ac, 2) if ac is not None and bc is not None else None,
        "relative_contour_median_difference_cents": shape_error,
        "target_relative_midi": [round(float(x), 2) if np.isfinite(x) else None for x in ar],
        "demo_relative_midi": [round(float(x), 2) if np.isfinite(x) else None for x in br],
        "warnings": warnings,
    }


def _reference_root(session_id: str) -> Path:
    session = _path(session_id)
    root = session / "vocal_references"
    if root.is_symlink() or not root.resolve().is_relative_to(session.resolve()):
        raise DirectorInputError("Invalid vocal reference storage.")
    if root.exists() and not root.is_dir():
        raise DirectorInputError("Vocal reference storage is unavailable.")
    return root


def _reference_path(session_id: str, reference_id: str) -> Path:
    if not _ID.fullmatch(reference_id):
        raise DirectorInputError("Invalid vocal reference ID.")
    root = _reference_root(session_id)
    path = root / reference_id
    if path.is_symlink() or not path.is_dir() or not path.resolve().is_relative_to(root.resolve()):
        raise DirectorInputError("Vocal reference not found.")
    return path


def _read_report(path: Path) -> dict:
    report = path / "report.json"
    if report.is_symlink() or not report.is_file() or report.stat().st_size > MAX_REPORT_BYTES:
        raise DirectorInputError("Vocal reference report unavailable.")
    try:
        data = json.loads(report.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or data.get("id") != path.name:
            raise ValueError("Invalid reference ID")
        return data
    except (OSError, UnicodeError, ValueError) as exc:
        raise DirectorInputError("Invalid vocal reference report.") from exc


def analyze_reference(session_id, take_id, start, end, recording, *,
                      estimator="yin", save=False, authorized=False):
    if save and not authorized:
        raise DirectorInputError("Confirm permission before saving the vocal reference.")
    if estimator not in ("yin", "rmvpe"):
        raise DirectorInputError("Unsupported pitch estimator.")
    target = analyze_audio(decode_audio(passage_wav(session_id, take_id, start, end)), estimator=estimator)
    demo = analyze_audio(decode_audio(recording), estimator=estimator)
    report = {
        "id": None, "session_id": session_id, "take_id": take_id,
        "start_seconds": start, "end_seconds": end, "estimator": estimator,
        "target_analysis": target, "demo_analysis": demo,
        "comparison": compare_contours(target, demo),
        "status": "analysis_only",
    }
    if not save:
        return report
    extension = _original_extension(recording)
    with _LOCK:
        # Resolve again before writing; existing original, takes and metadata are untouched.
        take_audio(session_id, take_id)
        root = _reference_root(session_id)
        root.mkdir(exist_ok=True)
        if sum(p.is_dir() and bool(_ID.fullmatch(p.name)) for p in root.iterdir()) >= MAX_REFERENCES:
            raise DirectorLimitError("Vocal reference limit reached (12 per session).")
        reference_id = uuid4().hex
        report.update(id=reference_id, created_at=_now(), original_extension=extension,
                      status="saved_reference")
        encoded = json.dumps(report, ensure_ascii=False, allow_nan=False).encode("utf-8")
        if len(encoded) > MAX_REPORT_BYTES:
            raise DirectorLimitError("Vocal reference report is too large.")
        stage = Path(tempfile.mkdtemp(prefix=".reference-", dir=root))
        try:
            (stage / ("demo." + extension)).write_bytes(recording)
            (stage / "report.json").write_bytes(encoded)
            stage.rename(root / reference_id)
        finally:
            if stage.exists():
                shutil.rmtree(stage)
    return report


def _http(exc):
    if isinstance(exc, (StorageConfigurationError, AudioDecoderUnavailable, RMVPEUnavailable)):
        return HTTPException(503, str(exc))
    if isinstance(exc, DirectorLimitError):
        return HTTPException(409, str(exc))
    return HTTPException(422, str(exc))


_ERRORS = (StorageConfigurationError, AudioDecoderUnavailable, RMVPEUnavailable,
           DirectorInputError, AudioInputError)


@router.get("/director/vocal-reference", include_in_schema=False)
def reference_page():
    return FileResponse(Path(__file__).parent / "static" / "vocal_reference.html", media_type="text/html")


@router.get(BASE + "/passage")
def preview_passage(session_id: str, take_id: str, start_seconds: float, end_seconds: float):
    try:
        audio = passage_wav(session_id, take_id, start_seconds, end_seconds)
        return Response(audio, media_type="audio/wav", headers={"Cache-Control": "no-store"})
    except _ERRORS as exc:
        raise _http(exc) from exc


@router.post(BASE)
def submit_reference(session_id: str, file: UploadFile = File(...),
                     take_id: str = Form(...), start_seconds: float = Form(...),
                     end_seconds: float = Form(...), estimator: str = Form("yin"),
                     save_reference: bool = Form(False), authorized_use: bool = Form(False)):
    try:
        if save_reference and not authorized_use:
            raise HTTPException(403, "Confirm permission to save the recording.")
        data = file.file.read(MAX_UPLOAD_BYTES + 1)
        return analyze_reference(session_id, take_id, start_seconds, end_seconds, data,
                                 estimator=estimator, save=save_reference, authorized=authorized_use)
    except _ERRORS as exc:
        raise _http(exc) from exc
    finally:
        file.file.close()


@router.get(BASE)
def list_references(session_id: str):
    try:
        root = _reference_root(session_id)
        entries = []
        if root.exists():
            for child in root.iterdir():
                if _ID.fullmatch(child.name) and child.is_dir() and not child.is_symlink():
                    data = _read_report(child)
                    entries.append({k: data[k] for k in (
                        "id", "take_id", "start_seconds", "end_seconds", "created_at", "estimator")})
        return {"references": sorted(entries, key=lambda x: x["created_at"], reverse=True)}
    except _ERRORS as exc:
        raise _http(exc) from exc


@router.get(BASE + "/{reference_id}")
def get_reference(session_id: str, reference_id: str):
    try:
        return _read_report(_reference_path(session_id, reference_id))
    except _ERRORS as exc:
        raise _http(exc) from exc


@router.get(BASE + "/{reference_id}/audio")
def reference_audio(session_id: str, reference_id: str):
    try:
        path = _reference_path(session_id, reference_id)
        extension = _read_report(path).get("original_extension")
        if extension not in _ORIGINAL_TYPES:
            raise DirectorInputError("Invalid reference audio type.")
        audio = path / ("demo." + extension)
        if audio.is_symlink() or not audio.is_file():
            raise DirectorInputError("Vocal reference audio unavailable.")
        return FileResponse(audio, media_type=_ORIGINAL_TYPES[extension],
                            headers={"Cache-Control": "no-store"})
    except _ERRORS as exc:
        raise _http(exc) from exc
