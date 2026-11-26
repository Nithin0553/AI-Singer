"""AI Singer API: health, external storage readiness, and vocal phrase analysis."""

from typing import Literal

from pathlib import Path

from fastapi import Body, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response

from ai_singer.director_sessions import (
    DirectorInputError, DirectorLimitError, add_feedback, approve_take,
    audible_passage_hint, create_session, edit_take, get_session, list_sessions,
    original_audio, render_next_take, take_audio,
)
from ai_singer.passage_edits import PassageEditError
from ai_singer.audio_analysis import (
    MAX_UPLOAD_BYTES,
    AudioDecoderUnavailable,
    AudioInputError,
    analyze_audio,
    decode_audio,
)
from ai_singer.annotation_review import score_annotations
from ai_singer.pitch_benchmark import benchmark_audio
from ai_singer.rmvpe_pitch import RMVPEUnavailable
from ai_singer.storage import StorageConfigurationError, configured_storage_root

app = FastAPI(title="AI Singer API", version="0.1.0")


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness is independent of model downloads and connected drives."""
    return {"status": "ok"}


@app.get("/ready")
def ready() -> dict[str, str]:
    """Reject storage-dependent work when the configured drive is absent."""
    try:
        configured_storage_root()
    except StorageConfigurationError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    return {"status": "ready", "storage": "available"}


@app.post("/analyze")
def analyze(file: UploadFile = File(...), estimator: Literal["yin", "rmvpe"] = "yin") -> dict:
    """Analyze a finished 1–15-second phrase without storing the uploaded audio."""
    try:
        recording = file.file.read(MAX_UPLOAD_BYTES + 1)
        samples = decode_audio(recording)
        return analyze_audio(samples, estimator=estimator)
    except AudioInputError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except (AudioDecoderUnavailable, RMVPEUnavailable) as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    finally:
        file.file.close()

@app.post("/compare")
def compare(file: UploadFile = File(...)) -> dict:
    """Compare two estimators on one recording; results are not ground truth."""
    try:
        recording = file.file.read(MAX_UPLOAD_BYTES + 1)
        return benchmark_audio(recording)
    except AudioInputError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except (AudioDecoderUnavailable, RMVPEUnavailable) as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    finally:
        file.file.close()


@app.get("/pitch-lab", include_in_schema=False)
def pitch_lab() -> FileResponse:
    """Local visual comparison page; uploaded audio is not saved permanently."""
    return FileResponse(Path(__file__).parent / "static" / "pitch_lab.html", media_type="text/html")


@app.post("/score-reference")
def score_reference(payload: dict = Body(...)) -> dict:
    """Score a manually labeled reference without persisting audio or labels."""
    try:
        return score_annotations(payload.get("analysis"), payload.get("reference"))
    except (ValueError, KeyError, TypeError, OverflowError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.get("/voices")
def voices() -> dict:
    """List locally authorized voice profiles (no filesystem paths exposed)."""
    from ai_singer.voice_render import VoiceConfigurationError, list_voices
    try:
        return {"voices": list_voices()}
    except VoiceConfigurationError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


@app.get("/voice-lab", include_in_schema=False)
def voice_lab() -> FileResponse:
    """Local-only voice conversion preview; it does not install any model."""
    return FileResponse(Path(__file__).parent / "static" / "voice_lab.html", media_type="text/html")


@app.post("/render-voice")
def render_voice_preview(
    file: UploadFile = File(...),
    voice_id: str = Form(...),
    authorized_use: bool = Form(False),
) -> Response:
    """Convert a short solo vocal using a user-provided, licensed local RVC voice."""
    from ai_singer.voice_render import (
        VoiceBusyError, VoiceConfigurationError, VoiceRenderError, render_voice,
    )
    try:
        if not authorized_use:
            raise HTTPException(status_code=403, detail="Confirm permission to use the recording and voice model.")
        data = file.file.read(MAX_UPLOAD_BYTES + 1)
        preview = render_voice(data, voice_id, authorized_use=True)
        return Response(
            content=preview, media_type="audio/wav",
            headers={"Content-Disposition": 'attachment; filename="ai-singer-voice-preview.wav"',
                     "Cache-Control": "no-store"},
        )
    except AudioInputError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except AudioDecoderUnavailable as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except VoiceBusyError as error:
        raise HTTPException(status_code=429, detail=str(error)) from error
    except VoiceConfigurationError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except VoiceRenderError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error
    finally:
        file.file.close()


@app.get("/director", include_in_schema=False)
def director_page() -> FileResponse:
    """Local Director Mode take and feedback interface."""
    return FileResponse(Path(__file__).parent / "static" / "director.html", media_type="text/html")


@app.get("/director/sessions")
def director_list() -> dict:
    try:
        return {"sessions": list_sessions()}
    except StorageConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except DirectorInputError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/director/sessions", status_code=201)
def director_save(
    source: UploadFile = File(...),
    preview: UploadFile = File(...),
    voice_id: str = Form(...),
    authorized_use: bool = Form(False),
) -> dict:
    """Persist only after the user explicitly saves the session."""
    from ai_singer.voice_render import VoiceConfigurationError
    try:
        if not authorized_use:
            raise HTTPException(status_code=403, detail="Confirm permission to save the original and voice model.")
        original_bytes = source.file.read(MAX_UPLOAD_BYTES + 1)
        preview_bytes = preview.file.read(25 * 1024 * 1024 + 1)
        return create_session(original_bytes, preview_bytes, voice_id, authorized=True)
    except AudioInputError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except (AudioDecoderUnavailable, StorageConfigurationError, VoiceConfigurationError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except DirectorLimitError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except DirectorInputError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    finally:
        source.file.close()
        preview.file.close()


@app.get("/director/sessions/{session_id}")
def director_session(session_id: str) -> dict:
    try:
        return get_session(session_id)
    except StorageConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except DirectorInputError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/director/sessions/{session_id}/original")
def director_original(session_id: str) -> FileResponse:
    try:
        saved_path, media_type = original_audio(session_id)
        return FileResponse(saved_path, media_type=media_type,
                            headers={"Cache-Control": "no-store"})
    except StorageConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except DirectorInputError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/director/sessions/{session_id}/takes/{take_id}.wav")
def director_take(session_id: str, take_id: str) -> FileResponse:
    try:
        return FileResponse(take_audio(session_id, take_id), media_type="audio/wav",
                            headers={"Cache-Control": "no-store"})
    except StorageConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except DirectorInputError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/director/sessions/{session_id}/approve")
def director_approve(session_id: str, payload: dict = Body(...)) -> dict:
    try:
        return approve_take(session_id, payload.get("take_id"))
    except StorageConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except DirectorInputError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/director/sessions/{session_id}/feedback", status_code=201)
def director_feedback(session_id: str, payload: dict = Body(...)) -> dict:
    try:
        return add_feedback(session_id, payload.get("take_id"),
                            payload.get("start_seconds"), payload.get("end_seconds"),
                            payload.get("instruction"))
    except StorageConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except DirectorLimitError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except DirectorInputError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/director/sessions/{session_id}/render")
def director_render(session_id: str, payload: dict = Body(...)) -> dict:
    """Render a new full-phrase take, not an automated region edit."""
    from ai_singer.voice_render import (
        VoiceBusyError, VoiceConfigurationError, VoiceRenderError,
    )
    try:
        if payload.get("authorized_use") is not True:
            raise HTTPException(status_code=403, detail="Confirm permission to use the original and target voice.")
        return render_next_take(session_id, payload.get("voice_id"), authorized=True)
    except AudioInputError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except (AudioDecoderUnavailable, StorageConfigurationError, VoiceConfigurationError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except VoiceBusyError as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc
    except VoiceRenderError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except DirectorLimitError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except DirectorInputError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/director/sessions/{session_id}/edit", status_code=201)
def director_edit(session_id: str, payload: dict = Body(...)) -> dict:
    """Apply explicit bounded DSP pitch/gain to a selected take, saving a candidate."""
    try:
        return edit_take(
            session_id, payload.get("take_id"), payload.get("start_seconds"),
            payload.get("end_seconds"), payload.get("operation"),
            payload.get("value"),
        )
    except StorageConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except DirectorLimitError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except (DirectorInputError, PassageEditError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/director/sessions/{session_id}/takes/{take_id}/audible-passage")
def director_audible_passage(session_id: str, take_id: str) -> dict:
    """Recommend a non-silent region for audition; not a singing classifier."""
    try:
        return audible_passage_hint(session_id, take_id)
    except StorageConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except DirectorInputError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PassageEditError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


# Sung demonstration routes are independent of existing take editing.
from ai_singer.vocal_references import router as vocal_reference_router

app.include_router(vocal_reference_router)
