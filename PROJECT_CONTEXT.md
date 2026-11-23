# AI Singer — Project Context

> **Persistent handoff:** Read this file at the beginning of each development session. Then inspect current source files and recent Git commits; this document is not a substitute for verification.
>
> **Last reviewed:** 2026-11-23 | **Repo:** [Nithin0553/AI-Singer](https://github.com/Nithin0553/AI-Singer) | **Status:** Optional RMVPE ONNX integration and YIN comparison CLI implemented. Real ONNX inference on Windows remains unverified.
>
> **Verification boundary:** Repository contents/history were checked through GitHub. Hardware and tool versions below are from **user-provided Windows PowerShell output**; no direct access to or verification on the laptop or external disk.

## 1. Project Overview

Build a human-directed, interactive AI singing collaborator. The human sings a phrase; **the agent waits until the phrase is finished** and then analyzes and tries to reproduce it with its own selected male or female singing voice. It accepts feedback, makes precise corrections, keeps approved takes, and optionally suggests musical alternatives like a professional singer working with a music director. Telugu songs and Telugu/English instructions are priorities.

## 2. Requirements and Scope

**Confirmed requirements:**
- Listen until completion rather than singing simultaneously. Offer a manual **Done Singing** control and optional silence detection tuned not to cut off musical rests.
- Extract and reproduce melody, pitch movement, timing, pauses and expression as faithfully as models permit; select a consistent male or female AI singing voice.
- Understand Telugu and English conversational corrections and support iterative listen → sing → feedback → revise.
- Provide **Director Mode** for strict instruction following and **Collaborative Mode** for optional suggestions and distinct alternative takes.
- Preserve approved sections; revise only the requested part when possible; keep version history and restoration.
- Explore fine-tuning on rights-cleared Telugu vocal recordings with aligned lyrics, timing and pitch.
- Maintain repo continuity and keep large AI assets outside Git.

**Initial experiment (proposed):** Short, solo vocal phrases (approximately 5–15 seconds), explicit end of recording, one target voice per rendering. Real-time duets, full song production, and arbitrary voice imitation are outside initial scope.

**Unresolved:** Specific model/provider choices, actual Telugu quality, numerical accuracy targets, real device performance, voice/data rights, production hosting, and acceptable latency. These require evidence.

**Data rights:** Use licensed or consented voices and recordings. Vocal separation does not create permission to train on copyrighted commercial songs.

## 3. Technology Stack

**Implemented:** Python/FastAPI, FFmpeg decoder, YIN/librosa baseline, optional `rmvpe-onnx` with CPU ONNX Runtime, and YIN/RMVPE comparison CLI.

| Layer | Technology | Verified state |
| --- | --- | --- |
| Backend | Python >=3.12, FastAPI, Uvicorn | Existing API plus `POST /analyze?estimator=yin|rmvpe` |
| Decode and classical pitch | FFmpeg, librosa YIN, NumPy, SciPy | First real Windows recording analyzed successfully with YIN |
| Learned pitch | `rmvpe-onnx` (0.2.3 series) and ONNX Runtime CPU | Optional, source adapter and mock integration tests passed; real model **not loaded** |
| Comparison | `python -m ai_singer.pitch_benchmark` | Benchmarks two estimators on one recording; results are disagreements, not ground truth |
| Frontend | React, Next.js, TypeScript | Not implemented |
| Agent | LangGraph + evaluated LLM | Not implemented |
| Singing engine | Authorized RVC-type conversion, DiffSinger | Not implemented |

The user's RTX 3050 Ti has 4 GiB VRAM. CPU ONNX is the first experimental path to avoid requiring a large CUDA/PyTorch install. The upstream API and SHA were reviewed at https://github.com/NewComer00/rmvpe-onnx.

## 4. System Architecture

```text
Audio upload (1–15 s, max 10 MiB)
  -> short-lived, seekable FFmpeg input -> mono 16 kHz PCM
  -> YIN (default) OR optional RMVPE ONNX CPU
  -> align to 20 ms pitch grid; RMS / confidence / candidate-note processing
  -> JSON pitch track, note candidates, quiet intervals and warnings

python -m ai_singer.pitch_benchmark original.m4a [--output report.json]
  -> decode once -> run both estimators -> compare pitch, voicing and runtime
```

The RMVPE adapter requires a manually supplied, SHA-256 verified weight file under `AI_SINGER_STORAGE_ROOT/models/audio_analysis/rmvpe.onnx` or at absolute `AI_SINGER_RMVPE_MODEL`. It never calls automatic checkpoint downloading. A missing model/dependency returns HTTP 503. Benchmark JSON is only saved when the CLI user requests an output path. No real model was downloaded by ChatGPT. No AI voice generation, lyrics, editing UI or musical agent has been implemented.

## 5. Repository Structure

- `backend/ai_singer/audio_analysis.py`: unchanged YIN default plus optional RMVPE pitch values and common post-processing.
- `backend/ai_singer/rmvpe_pitch.py`: optional CPU ONNX integration, checksum, model-storage policy and 10 ms to 20 ms alignment.
- `backend/ai_singer/pitch_benchmark.py`: comparison CLI and YIN/RMVPE disagreement metrics.
- `backend/ai_singer/main.py`: `/health`, `/ready`, `POST /analyze?estimator=yin|rmvpe`.
- `backend/pyproject.toml`: normal API requirements and opt-in `[rmvpe]` extra.
- `backend/tests/test_rmvpe_pitch.py`: RMVPE path, prediction, API, benchmark and security tests (mock model).
- `backend/tests/test_audio_analysis.py`, `test_storage.py`, `test_api.py`: existing 29 tests.
- `scripts/Initialize-Storage.ps1`: volume-label storage initializer.
- `README.md`, `PROJECT_CONTEXT.md`, `.env.example`, `.gitignore`: setup, handoff and Git exclusions.

## 6. Development Progress

**Implemented and tested locally:** Optional RMVPE ONNX CPU adapter, query-parameter selection and benchmark script with elapsed runtime, shared-voiced count, median absolute pitch disagreement and octave-like differences. The default YIN branch remains available. No model downloads. Mirrored repository test suite: **41 passed**, including 29 existing tests and 12 new RMVPE/benchmark tests using mocked model predictions, with Python compilation and editable package installation successful in isolated Python 3.13 workspace.

**Previously user-verified Windows:** Seagate `Dimpu` setup, FFmpeg/ffprobe 9.1, YIN `POST /analyze` HTTP 200 with a 9.195-second recording and 460 analysis frames. 36 candidate notes and an apparent late octave drop require listening/ground truth verification. Windows pytest after the short test-ID fix has not yet been reported.

**Not verified:** Real RMVPE model weights, optional package installed on the user's Windows computer, CPU inference time/accuracy and comparison against original recording. The singing agent, frontend, voice models and training are unimplemented.

## 7. Technical Decisions

- Keep YIN as default; RMVPE must be explicitly chosen via API parameter or local benchmark CLI.
- Use CPU ONNX first on a 4 GiB VRAM laptop; do not install PyTorch/CUDA as a prerequisite for the benchmark.
- Require an existing, SHA-256 verified canonical `rmvpe.onnx` at the Seagate storage root; allow an explicit absolute override. Never auto-download checkpoints or store large assets in Git.
- Match the model's ~10 ms output to the existing 20 ms timeline to compare both estimators consistently.
- Never call **inter-model agreement** accuracy: require annotated reference clips to measure actual pitch error.
- Keep the architecture modest and separate singing generation, musical directions and model inference authority.

## 8. Known Issues

- Real RMVPE checkpoint inference and install are still **pending**. Mock-based integration success is not evidence that RMVPE is accurate or even runs successfully on the user's machine.
- The canonical weight SHA-256 is `5370e71ac80af8b4b7c793d27efd51fd8bf962de3a7ede0766dac0befa3660fd` (per third-party package). Review license and rights for commercial use before relying on this checkpoint.
- Thresholds (0.03 model confidence, 80–900 Hz) and 20 ms time-grid downsampling are provisional. Pitch glide over-segmentation and an octave-like artifact remain in YIN's first recording.
- Windows pytest previously failed because huge parameter IDs exceeded `PYTEST_CURRENT_TEST` variable limit; shortened test IDs committed, but full Windows acceptance result not yet provided.
- User-provided YIN JSON confirms first real recording processing, not note transcription correctness. Original audio bytes not uploaded to ChatGPT.
- Seagate is exFAT, may cause symlink/cache challenges. CPU inference latency and memory use on Windows unmeasured. One nonfatal Starlette TestClient warning was reported.

## 9. Testing and Verification

**Isolated Linux Python 3.13 (not the user's Windows):** **41 tests passed**, comprising 29 prior tests and 12 new RMVPE/benchmark tests, with `python -m compileall -q ai_singer tests` and local editable install (without downloading new dependencies) successful. Tests cover model root/missing file/absolute override, no automatic download, alignment/voicing, invalid prediction timeline, SHA mismatch, mocked API RMVPE selection, mocked benchmark, comparison frames/median error and existing WAV/M4A behavior. The ONNX model and package **were not installed or loaded**, so real model inference is pending.

**User Windows verified previously:** FFmpeg/ffprobe 9.1, external `Dimpu` drive configuration and successful YIN `POST /analyze` HTTP 200 with a 9.195 s real recording (460 frames). User has not supplied a subsequent full Windows pytest result after short-ID fix.

**Not tested:** `rmvpe-onnx` dependency installation on Windows, real checkpoint loading, measured neural accuracy and performance on actual singing, singing audio generation and multilingual agent.

## 10. Development Environment

**User hardware:** Windows 11 Home, Python 3.12.10, RTX 3050 Ti Laptop GPU (4 GiB), FFmpeg 9.1, Seagate `Dimpu` at `D:\AI_Singer` (drive letter may change). Storage script sets `AI_SINGER_STORAGE_ROOT`, `HF_HOME` and `TORCH_HOME` in the active PowerShell session.

**Next Windows installation:**

```powershell
cd C:\Users\nithi\AI-Singer
git pull --ff-only
.\scripts\Initialize-Storage.ps1 -VolumeLabel 'Dimpu'
cd backend
.\.venv\Scripts\python -m pip install -e ".[dev,rmvpe]"
.\.venv\Scripts\python -m pytest -q
```

To explicitly obtain the canonical RMVPE checkpoint (after verifying license and permissions), run in **that same PowerShell window**:

```powershell
$model = Join-Path $env:AI_SINGER_STORAGE_ROOT 'models\audio_analysis\rmvpe.onnx'
if (-not (Test-Path $model)) {
    Invoke-WebRequest -Uri 'https://huggingface.co/lj1995/VoiceConversionWebUI/resolve/main/rmvpe.onnx?download=true' -OutFile $model
}
(Get-FileHash -Algorithm SHA256 $model).Hash.ToLower()
```

Expected digest: `5370e71ac80af8b4b7c793d27efd51fd8bf962de3a7ede0766dac0befa3660fd`. The adapter checks the hash and refuses mismatches. Neither the user nor ChatGPT has reported a successful weights download.

**Benchmark original recording:**

```powershell
$clip = 'C:\path\to\Test 1.m4a'  # Replace with actual recording path
$report = Join-Path $env:AI_SINGER_STORAGE_ROOT 'outputs\previews\yin-rmvpe-comparison.json'
.\.venv\Scripts\python -m ai_singer.pitch_benchmark "$clip" --output "$report"
```

Alternatively use `POST /analyze?estimator=rmvpe` in Swagger after the model has been installed. Omitting the query parameter continues to use YIN.

## 11. Model and Storage Configuration

**Model storage:** The confirmed external drive is Seagate volume `Dimpu`, currently `D:\AI_Singer`. The optional neural checkpoint belongs at `<AI_SINGER_STORAGE_ROOT>/models/audio_analysis/rmvpe.onnx`. Benchmark JSON should be stored under `<AI_SINGER_STORAGE_ROOT>/outputs/previews/` if requested. The model requires an existing verified file and will not download automatically. An absolute `AI_SINGER_RMVPE_MODEL` override is supported, but the canonical SHA is still required. Other models, datasets, outputs and checkpoints remain outside Git. Runtime source/virtualenv stays on local SSD.

## 12. Next Steps

1. **Windows integration check:** Fast-forward the existing clone, initialize `Dimpu` in the current terminal, install optional RMVPE dependencies, run pytest and report whether all **41 tests pass** (possible nonfatal Starlette warning).
2. **Explicit model setup:** After reviewing model rights, download `rmvpe.onnx` directly to the Seagate `models/audio_analysis` folder; verify canonical SHA-256 before inference. Do not commit weights or duplicate model downloads.
3. **Real benchmark:** Run the CLI on the original 9.195 s recording, save JSON to `outputs/previews`, and report CPU latency, voiced overlap, pitch disagreement and octave-like mismatches. Do not claim RMVPE is more accurate until verified against known reference pitches.
4. Compare both estimators on several permissioned annotated clips, visualize their pitch curves, tune voicing thresholds and resolve glide over-segmentation/octave errors with measurement.
5. Only then choose a main pitch estimator and progress to authorized singing voice conversion and later musical-director agent intelligence.

## 13. Latest Development Session

**Date:** 2026-11-23. **Starting repository head:** `432d535` on `main` (first real audio analysis recorded).

**Goal:** Implement next milestone: optional learned RMVPE pitch estimator and comparison with existing YIN on the same recording.

**Implemented:** CPU-capable ONNX integration via optional `rmvpe-onnx` dependency, no automatic weights download, checksum-verified Seagate model path, `POST /analyze?estimator=rmvpe`, 10 ms-to-20 ms pitch alignment and side-by-side benchmark CLI comparing pitch/voicing disagreements, octave-like differences and runtime. Default YIN behavior is preserved. No song generation, training or LLM added.

**Tests:** In isolated Linux Python 3.13 environment, a mirrored backend suite passed **41 tests** (29 existing + 12 new). `compileall` and offline editable packaging passed. The neural checkpoint, `rmvpe-onnx`, real inference and Windows Py3.12 acceptance are **not tested** in that environment.

**Previous Windows validation:** User verified FFmpeg and `Dimpu`, and `POST /analyze` returned HTTP 200 for a 9.195-second real recording, 460 pitch frames and 36 approximate notes. This is not evidence of correct note count; full Windows pytest after test-ID fix still unreported.

**Changed files:** `backend/ai_singer/audio_analysis.py`, `main.py`, `pyproject.toml`, new `rmvpe_pitch.py`, `pitch_benchmark.py`, `tests/test_rmvpe_pitch.py`, plus this handoff and `README.md`. See git history for resulting commit.

**Stop point:** Windows dependency installation, explicit model weight acquisition on HDD, SHA check and first genuine YIN/RMVPE benchmark remain to be done by user. No model weights downloaded or committed by the assistant.
