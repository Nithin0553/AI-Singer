"""AI Singer API: health, external storage readiness, and vocal phrase analysis."""

from typing import Literal

from pathlib import Path

from fastapi import Body, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response

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
