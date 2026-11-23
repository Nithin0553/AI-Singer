# AI Singer — Project Context

> **Persistent handoff:** Read this file at the beginning of each development session. Then inspect current source files and recent Git commits; this document is not a substitute for verification.
>
> **Last reviewed:** 2026-11-22 | **Repo:** [Nithin0553/AI-Singer](https://github.com/Nithin0553/AI-Singer) | **Status:** Stage 1 CPU-only musical analysis endpoint implemented and tested with synthetic audio; no user-voice or singing model evaluation yet.
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

**Implemented today:**

```text
Finished short vocal file (WAV/MP3/WebM etc. supported by FFmpeg)
            |
    POST /analyze (FastAPI)
            |
   Size + duration validation
            |
 FFmpeg -> 16 kHz mono float PCM (in memory)
            |
 librosa YIN fundamental pitch estimate
 RMS silence check + periodicity gate
            |
 Frame-by-frame pitch & MIDI values
 Candidate steady notes + quiet intervals
            |
        JSON response
```

Audio duration must be 1–15 seconds, upload payload <=10 MiB. Decode is capped at 16 seconds and has a 30-second subprocess timeout. No AI weights or GPU required. The source audio is not intentionally saved to project storage by the endpoint (request handling may use framework temporary files).

**Future, unimplemented:** Browser capture, agent reasoning, sung-lyrics recognition, music-aware correction, singing voice conversion/synthesis, fidelity comparisons, take history and studio UI. The LLM must not replace audio measurements; approved takes must remain reversible.

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

**Implemented and verified in development container:**
- Existing `main` foundation retained; 9 original tests preserved.
- CPU-only `POST /analyze` implemented. Uses FFmpeg to decode a completed 1–15-second clip to 16 kHz mono, rejects invalid input, calculates frame-level pitch, candidate notes, quiet intervals, and warnings.
- Automated tests: **25 passed** in isolated Linux Python 3.13 development environment, including API-level WAV upload tests, generated note frequencies, silence, noise, decoder failure, and upload size/duration errors.
- Editable installation (`--no-build-isolation --no-deps` with dependencies already present) and `compileall` succeeded.

**Confirmed by user on Windows:** Seagate `Dimpu` volume initialized as `D:\AI_Singer`; Python 3.12.10; previous 9 backend tests passed and `/health`/`/ready` returned HTTP 200. Fresh Windows PowerShell successfully ran **FFmpeg 9.1 and ffprobe 9.1** and reran storage initializer.

**Awaiting Windows verification:** Installing new dependencies from `pyproject.toml`, running the new 25-test suite and loading short real microphone recordings through `/docs`.

**Not implemented:** Voice synthesis, model evaluation/training, natural-language feedback, lyrics/phoneme alignment, interactive studio UI, or conversational agent.

## 7. Technical Decisions

- Continue in the existing repository with a simple `main` workflow; no unnecessary branches, destructive updates or force-pushes.
- Update this file alongside meaningful implementation, test, design and session changes.
- Keep models, datasets, checkpoints, caches and rendered audio outside Git.
- **Storage selection is user-confirmed:** Seagate exFAT volume labeled `Dimpu` currently at `D:`; planned project root `D:\AI_Singer`.
- Do **not hardcode drive letters** in application logic. The setup script resolves by volume label each time, so it can find the disk after drive-letter reassignment.
- The script must be run locally in each PowerShell session that will run models/API; its `AI_SINGER_STORAGE_ROOT`, `HF_HOME` and `TORCH_HOME` variables apply only to that shell, avoiding global effects on other projects.
- Use a non-destructive, idempotent initialization script: preview first, create only project folders on explicit execution; never format or clear the disk.
- Prefer a turn-based listen → analyze → sing → correct workflow and independent pitch/time evaluation before costly training.
- Keep application source/virtual environments on faster internal storage when practical, larger assets on the Seagate HDD.

## 8. Known Issues

- Audio analysis is a **baseline experiment**, not a verified musical transcription. YIN and stability thresholds can miss vibrato, short notes, ornaments, slides, soft singing, overlapping sounds and noisy recordings.
- Quiet intervals represent low measured RMS, not necessarily semantic or musical rests. Timing is frame-based and approximate (20 ms steps, ~128 ms window).
- No beat-level tempo inference, Telugu lyrics, voice identity, singing synthesis, emotions or creative musical suggestions are implemented.
- `POST /analyze` handles one completed 1–15 s upload (<=10 MiB); it decodes via an FFmpeg subprocess and does **not** save takes or generate a rendered pitch plot. The JSON pitch track can later power plotting in the studio UI.
- Real singer recordings, microphone formats (WebM/MP3), peak memory use, first-run latency, and Windows dependency installation still need validation. Tests currently exercise WAV and generated signals only.
- Windows `D:` Seagate exFAT remains slower than internal SSD and may not support symlink-intensive model caches.
- Windows earlier emitted one nonfatal `StarletteDeprecationWarning` from `fastapi.testclient` regarding httpx/httpx2; don't upgrade libraries blindly.
- RTX 3050 Ti has 4 GiB VRAM; larger singing and training models may need cloud resources or carefully reduced configurations.

## 9. Testing and Verification

**Development workspace tests (Linux Python 3.13.5, not user's Windows):**
- `python -m compileall -q ai_singer tests`: passed.
- `PYTHONPATH=. python -m pytest -q`: **25 passed**.
- `python -m pip install -e . --no-deps --no-build-isolation`: succeeded using preinstalled dependencies; `python -m pytest -q` still **25 passed**.
- Two-tone sample (220 and 330 Hz), steady 220 Hz note, quiet interval, white noise and silent recordings exercised. API upload returns structured JSON; bad and oversized uploads rejected.
- Manual analysis benchmark in the container: a 15-second 220 Hz reference produced 751 pitch frames and a steady A3 candidate; does not establish real-world latency guarantees or musical accuracy.
- Source files and documentation reviewed; the generated Git tree should be read back after the commit.

**User-reported Windows verification before this change:** Existing 9 tests passed (1 warning), Uvicorn started, and `/health` and `/ready` returned HTTP 200. Newly opened PowerShell successfully executed `ffmpeg -version` and `ffprobe -version`, both **9.1**, and the Seagate setup script reported success.

**Not yet tested:** New analyzer on Windows/Python 3.12, user singing, consumer microphone/WebM/MP3 clips, GPU or model inference, voice quality or training.

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

1. **Next: Windows acceptance check.** Fast-forward local checkout, initialize `Dimpu` in that shell, install updated backend dependencies and run pytest. Confirm 25 tests pass on Python 3.12.10; report warnings or dependency issues.
2. Upload an original/consented 1–15-second **clear solo vocal WAV** via `/docs` → `POST /analyze`. Inspect the pitch contour, candidate note events, pauses and limitations. Do not mark musical fidelity verified until compared with the recording.
3. Add diagnostic plotting in studio UI or generated report, and quantify measured note/pitch/timing error on reference clips.
4. Improve voicing and pitch methods with RMVPE/torchcrepe comparison only if the baseline has documented shortcomings.
5. Evaluate licensed male/female singing voice-conversion models with 4 GiB VRAM constraints; record quality, resource use and latency.
6. Implement the LLM-orchestrated director/creative musical agent, targeted corrections and versioned approved takes.
7. Prepare rights-cleared Telugu vocal datasets and consider controlled synthesis/fine-tuning when necessary.

## 13. Latest Development Session

**Date:** 2026-11-22. **Base commit:** `38231c0` on `main`.

**User-confirmed local environment:** Windows FFmpeg and FFprobe both **9.1** ran successfully after a PowerShell restart; Seagate setup script again selected `Dimpu` at `D:\AI_Singer`. The previous Windows backend had **9 passing tests**, and `/health` plus `/ready` returned HTTP 200.

**Implementation in this development session:** Added `POST /analyze` for short uploaded audio, bounded FFmpeg decode, pitch estimation using librosa YIN with periodicity + RMS rejection, candidate MIDI note events and quiet intervals, clear limitations, and new dependencies/tests. No model weights or recorded user audio stored.

**Verification:** Isolated Linux Python 3.13.5 container: **25 tests passed**, compileall passed, editable install using preinstalled packages passed. Generated sine-wave note/silence tests pass. **Windows installation and genuine singing performance remain untested.**

**Changed files:** `backend/pyproject.toml`, `backend/ai_singer/main.py`, new `backend/ai_singer/audio_analysis.py`, new `backend/tests/test_audio_analysis.py`, `README.md`, this context file. No unrelated files changed. Check Git history for commit hash.

**Stop point:** Ready for user to `git pull --ff-only`, install updated dependencies, run pytest, and submit a short recorded vocal clip in Swagger `/docs`. Only after verifying actual singing may the pitch model be called effective in practice.
