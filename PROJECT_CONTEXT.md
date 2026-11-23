# AI Singer — Project Context

> **Persistent handoff:** Read this file at the beginning of each development session. Then inspect current source files and recent Git commits; this document is not a substitute for verification.
>
> **Last reviewed:** 2026-11-22 | **Repo:** [Nithin0553/AI-Singer](https://github.com/Nithin0553/AI-Singer) | **Status:** Stage 1 analyzer implemented; M4A decoding improved and tested with generated files; the actual user M4A recording remains unverified.
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

**Implemented:** Python FastAPI backend, external-storage readiness, FFmpeg audio decoding, NumPy/librosa/SciPy pitch-baseline processing, and automated pytest checks.

| Layer | Current choice / candidate | Status |
| --- | --- | --- |
| UI | Next.js, React, TypeScript, Tailwind | Not implemented; use FastAPI Swagger `/docs` to submit trial recordings |
| API | Python >=3.12, FastAPI, Uvicorn, python-multipart | `/health`, `/ready`, `POST /analyze` implemented |
| Decode | FFmpeg CLI | 9.1/ffprobe 9.1 verified running in fresh Windows PowerShell |
| Pitch prototype | NumPy, librosa YIN, SciPy median filter | CPU-only implementation; tests use generated tones, silence and noise |
| Agent | LangGraph + GPT or Qwen | Later evaluation; not implemented |
| Spoken corrections | Multilingual ASR, possibly faster-whisper | Not implemented or benchmarked for Telugu |
| Advanced audio | RMVPE / torchcrepe | Later pitch comparison, not installed |
| Voice conversion | Permissioned RVC-type singing voices | Later experiment, not implemented |
| Controlled singing | DiffSinger candidate | Later experiment, not implemented |
| Data/training | PyTorch, permitted vocals, alignment and dataset tools | Not implemented |
| Persistence | Versioned takes, PostgreSQL and external media storage | Not implemented |

The Windows GPU is RTX 3050 Ti with 4 GiB VRAM. This prototype is CPU-only and does not download model weights.

## 4. System Architecture

**Implemented:**

```text
Finished 1–15 s recording (WAV, M4A, MP3, WebM, as decodable)
    |
POST /analyze; bound uploaded bytes to <=10 MiB
    |
Short-lived local temporary file with seekable FFmpeg input
    |
FFmpeg -> 16 kHz mono float PCM in memory
    |
librosa YIN pitch + RMS + periodicity checks
    |
Time-stamped pitch, candidate notes, quiet intervals and warnings
    |
JSON response; temporary input file deleted
```

FFmpeg is invoked without a shell; original user-supplied filenames are never used as a local path. Temporary files use the OS temporary directory (normally an internal disk), not the Seagate model/dataset storage. Files are automatically deleted after decode success or failure; this is ordinary filesystem deletion, not secure erasure. Duration is bounded at 1–15 seconds, decode at 16 seconds, max payload 10 MiB, and subprocess timeout 30 seconds.

**Not implemented:** Record/Done button, streaming, musical score editor, lyric recognition, agent intelligence, singing conversion/synthesis, audio exports or persistent take history.

## 5. Repository Structure

- `README.md`: project overview, Windows storage/API setup, and first analyzer trial.
- `PROJECT_CONTEXT.md`: handoff, verified state and next actions.
- `.gitignore`, `.env.example`: local secrets, models, caches and drive configuration.
- `scripts/Initialize-Storage.ps1`: discovers Seagate `Dimpu` by volume label and sets current-shell paths.
- `backend/pyproject.toml`: backend dependencies; adds `python-multipart`, NumPy, SciPy and librosa.
- `backend/ai_singer/main.py`: `GET /health`, `GET /ready`, `POST /analyze`.
- `backend/ai_singer/audio_analysis.py`: FFmpeg decode, pitch and RMS analysis, candidate note/quiet intervals.
- `backend/ai_singer/storage.py`: external storage path validation.
- `backend/tests/test_api.py`, `backend/tests/test_storage.py`: original 9 API/storage tests.
- `backend/tests/test_audio_analysis.py`: synthetic pitch, notes, silence/noise, duration/size, invalid upload and decoder-failure tests.

No `frontend/`, music model weights or data assets are committed.

## 6. Development Progress

**Completed and tested in isolated Linux development environment:**
- Existing backend and musical pitch analysis API retained.
- Replaced non-seekable FFmpeg stdin upload decoding with a seekable, disposable temporary input file. This addresses a common MP4/M4A decoding constraint without assuming the exact cause of the user's error.
- Regression tests now include a real FFmpeg-generated AAC/M4A upload with filename `Test 1.m4a`, decoding via the library function, API-level upload, file cleanup on success and failure, WAV and existing analysis checks.
- **29 tests passed** (9 original API/storage + 20 audio tests) using Python 3.13.5, FFmpeg 7.1.x, with compileall passing. No GPU or model weights required.

**Verified by user on Windows:** FFmpeg and FFprobe **9.1** both ran; Seagate `Dimpu` set to `D:\AI_Singer`. Earlier backend tests were 9 passed and `/health` / `/ready` HTTP 200.

**New user report:** Swagger `POST /analyze` with `Test 1.m4a` returned HTTP **422**, `Cannot decode the recording. Try WAV, MP3, or WebM audio.` A separate `GET /analyze` returned **405**, which is expected because the route only accepts POST.

**Pending on Windows:** Update checkout, rerun 29 tests, retry the same recording. The original M4A file was **not supplied** for inspection, so the exact cause and successful resolution for that recording are unverified.

## 7. Technical Decisions

- Preserve existing GitHub repository and minimal `main` workflow; maintain this handoff with real implementation and test state.
- Keep large models/datasets off Git, with Seagate `Dimpu` as configurable external storage; never hardcode a drive letter in application code.
- Use a small, **seekable temporary file** for inbound audio formats such as M4A/MP4. Do not depend on the request's filename, shell command interpolation or saving recordings into long-term dataset storage. Delete input temp files after decoding.
- Keep the same 10 MiB upload and 1–15 s duration limits while investigating format compatibility. Keep the output PCM in memory.
- Do not assume that changing FFmpeg input mechanics resolves every M4A issue; validate with actual user recordings and inspect with `ffprobe` if failures persist.
- The first analyzer is a CPU-only heuristic; measured pitch, candidate notes and quiet intervals are not validated musical meaning or a generated singing performance.

## 8. Known Issues

- **Real user file still unverified:** Screenshot shows an M4A upload rejected by the old non-seekable decoder with HTTP 422. The new seekable-file implementation passed generated M4A tests, but the exact `Test 1.m4a` was not provided. If it still fails, inspect its FFprobe metadata and playback. Corrupt/incomplete/protected files and unusual codecs may remain unsupported.
- `GET /analyze` returns HTTP 405 by design; use `POST /analyze` multipart upload in `/docs`.
- Heuristic YIN pitch extraction can miss vibrato, ornaments, slides, short notes, soft singing and noisy vocals; no end-to-end voice fidelity demonstrated.
- Silence intervals are RMS-based rather than semantically classified rests. No tempo inference, lyric alignment, visual score, voice generation, editing UI or speaking agent yet.
- Temp files use OS default temporary space (typically C:), bounded to 10 MiB each; simultaneous uploads may consume temporary disk. Files are deleted normally after processing but not securely overwritten.
- Model/HDD cache behavior and real Windows audio-processing latency remain unmeasured. ExFAT may not support some cache symlink strategies.
- Windows Starlette/httpx TestClient deprecation warning remains nonfatal; do not upgrade unrelated libraries without assessment.

## 9. Testing and Verification

**Isolated Linux Python 3.13.5 development environment, not Windows:**
- `python -m pytest -q`: **29 passed**, including existing 9 backend checks, original WAV/analysis tests and four M4A/temp-file regressions.
- `python -m compileall -q ai_singer tests`: passed.
- Real AAC-in-MP4 generated by FFmpeg 7.1.x and decoded successfully from a seekable input file. API accepted `Test 1.m4a` with `audio/x-m4a` as HTTP 200, returning pitch and note candidates.
- Tests verify that the temporary source is accessible during FFmpeg execution and is deleted on success or failure.
- Existing 10 MiB limit, 1–15 s duration, invalid audio, absent FFmpeg and storage-readiness behaviors remain tested.

**Previously user-reported Windows checks:** FFmpeg/FFprobe 9.1 available, Seagate `Dimpu` configured, existing 9 backend tests passed, API `/health` and `/ready` returned HTTP 200. The user also reported one failed M4A `POST /analyze` (422) and expected `GET /analyze` (405) with the prior decoder.

**Not yet tested:** New fix with FFmpeg 9.1 on Windows/Python 3.12; exact user's M4A recording, singer pitch accuracy, performance, GPU, or AI models.

## 10. Development Environment

**Reported by user from Windows 11 Home (build `10.0.26300`):** Git 2.51, Python 3.12.10, Node 24.11, NVIDIA RTX 3050 Ti Laptop GPU (4 GiB), NVIDIA driver 610.60, Seagate `Dimpu` exFAT 2 TB volume mounted `D:`, `C:` ~41 GB free.

**Audio tools (now verified by user):** FFmpeg `9.1-full_build-www.gyan.dev` and FFprobe `9.1-full_build-www.gyan.dev` both ran successfully with fresh PowerShell and exited normally. `winget` installed Gyan.FFmpeg. The new PowerShell session reran `scripts/Initialize-Storage.ps1 -VolumeLabel 'Dimpu'`, reporting `D:\AI_Singer` configured.

**Next Windows setup (same terminal after updating repository):**

```powershell
cd C:\Users\nithi\AI-Singer
git pull --ff-only
.\scripts\Initialize-Storage.ps1 -VolumeLabel 'Dimpu'
cd backend
.\.venv\Scripts\python -m pip install -e ".[dev]"
.\.venv\Scripts\python -m pytest -q
.\.venv\Scripts\python -m uvicorn ai_singer.main:app --reload
```

Open `http://127.0.0.1:8000/docs` in browser, expand **POST /analyze**, click **Try it out**, choose a 1–15-second solo vocal WAV, then **Execute**. Results include time-stamped pitch and candidate note events. Existing `/health` and `/ready` endpoints are unchanged. Stop a previous Uvicorn process with Ctrl+C before starting a new one on port 8000. Some imports (librosa/numba) may be slower on first call.

If the storage initializer is not run in the same shell, `/ready` will report 503, even though `/analyze` currently does not persist recordings.

## 11. Model and Storage Configuration

**Configured destination (per user and local PowerShell output):** Seagate `Dimpu` exFAT volume currently at `D:`, project root `D:\AI_Singer`. The initializer reported directory creation/verification; direct folder listing and write tests have not yet been supplied.

**Folder layout created by the script only when run locally:**

```text
<AI_SINGER_STORAGE_ROOT>/
  models/
    voice_conversion/
    singing_synthesis/
    audio_analysis/
  datasets/
    raw/
    processed/
    annotations/
  cache/
    huggingface/
    torch/
  outputs/
    previews/
    renders/
  training/
    checkpoints/
    logs/
```

Use `scripts/Initialize-Storage.ps1 -VolumeLabel 'Dimpu'` rather than embedding `D:` into Python. The script discovers the current drive letter via `Get-Volume` and sets `AI_SINGER_STORAGE_ROOT`, `HF_HOME`, `TORCH_HOME` for its PowerShell process. These variables are intentionally **not persisted globally**, and model libraries' use of these caches must be verified before large downloads.

The API refuses storage readiness if the configured root is missing or not writable. Keep model weights, checkpoints, recordings and datasets on the HDD; retain the source, Python virtual environment and performance-sensitive temporary files on a faster internal drive when space permits. Avoid duplicate weights and separately back up irreplaceable licensed data. exFAT may not support symlink-intensive caches.

## 12. Next Steps

1. **Windows acceptance:** Stop running Uvicorn (`Ctrl+C`), `git pull --ff-only`, rerun pytest and verify **29 passed**. Relaunch with `uvicorn ... --reload`.
2. In `http://127.0.0.1:8000/docs` retry **POST /analyze** with the original `Test 1.m4a` (1–15 seconds, <=10 MiB). Record the actual HTTP response. Do not use browser navigation to `GET /analyze`.
3. If the same M4A fails, confirm it plays locally and run `ffprobe -v error -show_format -show_streams 'path-to-Test 1.m4a'` (share relevant codec/duration/errors, not private metadata), or convert a copy to WAV. The original file has not been uploaded to ChatGPT, so do not speculate about its codec or integrity.
4. Once the upload succeeds, inspect pitches/notes/pauses and evaluate against a consented known reference. Add visual diagnostic plotting and quantify errors.
5. Compare advanced pitch models only if baseline fails demonstrated accuracy needs, then evaluate authorized voice conversion on suitable compute.
6. Continue with director/creative agent, versioned take memory and licensed Telugu singing data after audio validation.

## 13. Latest Development Session

**Date:** 2026-11-22 to 2026-11-23. **Starting GitHub commit:** `37e3406` on `main`.

**User report:** Uploaded `Test 1.m4a` using Swagger `POST /analyze` (MIME `audio/x-m4a`) and received HTTP 422 with generic FFmpeg decode error. A separate browser request `GET /analyze` returned HTTP 405; only POST is implemented.

**Investigation:** Existing decoder passed uploaded bytes to FFmpeg through `pipe:0` (non-seekable). MP4/M4A may require seeking; this is a plausible compatibility issue, not confirmed as the exact reason for this file's failure because the actual audio was not provided.

**Implementation:** Changed FFmpeg decoding to use a bounded, seekable file in `tempfile.TemporaryDirectory`, with automatic deletion. Improved decode error to mention M4A. Added regression tests for FFmpeg-generated AAC/M4A, HTTP M4A upload, temp-file lifetime on successful decode and failure. No change to `POST /analyze` API shape or large storage configuration.

**Verified:** **29 tests passed** and Python compilation succeeded in an isolated Linux/Python 3.13.5 environment using FFmpeg 7.1.x. The generated AAC/M4A request passed, but the user's actual recording and Windows FFmpeg 9.1 are still untested with the fix.

**Changed:** `backend/ai_singer/audio_analysis.py`, `backend/tests/test_audio_analysis.py`, `README.md`, and `PROJECT_CONTEXT.md`. See Git history for this session's new commit.

**Next task:** User fetches updated `main`, runs 29 tests, restarts Uvicorn, retries the same `Test 1.m4a`, and reports the result.
