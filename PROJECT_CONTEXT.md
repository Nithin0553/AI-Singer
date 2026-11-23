# AI Singer — Project Context

> **Persistent handoff:** Read this file at the beginning of each development session. Then inspect current source files and recent Git commits; this document is not a substitute for verification.
>
> **Last reviewed:** 2026-11-22 | **Repo:** [Nithin0553/AI-Singer](https://github.com/Nithin0553/AI-Singer) | **Status:** Minimal backend scaffold and storage-readiness checks implemented; musical analysis and singing are not implemented.
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

The minimal API backend is implemented with Python and FastAPI; all other technologies remain proposals.

| Layer | Current choice or candidate | Current status |
| --- | --- | --- |
| UI | Next.js / React / TypeScript / Tailwind | Planned, not installed |
| Backend | Python 3.12+ / FastAPI / Pydantic / Uvicorn | Minimal health and readiness endpoints implemented |
| Agent | LangGraph + evaluated GPT API or Qwen | Research proposal; not implemented |
| Speech instructions | faster-whisper or another multilingual ASR | Not selected or tested for Telugu |
| Audio | FFmpeg, NumPy, SciPy, librosa | Planned; FFmpeg installation unverified |
| Pitch | RMVPE and/or torchcrepe | Planned comparative evaluation |
| First singing experiment | RVC-style voice conversion | Not implemented |
| Controlled synthesis candidate | DiffSinger | Not implemented |
| Dataset work | Vocal-separation and OpenVPI tools | Not implemented |
| Runtime/training | PyTorch, supported NVIDIA CUDA | Not installed/tested on user laptop |
| Persistence later | PostgreSQL and configured media storage | Not implemented |
| Testing | pytest, FastAPI TestClient / httpx | 9 backend tests passed in development container |

NVIDIA PersonaPlex remains a possible research candidate for speech interaction, not an accepted singing model. The RTX 3050 Ti has 4 GiB VRAM, so avoid assuming large models/fine-tuning will run locally.

## 4. System Architecture

**Proposed, not implemented:**

```text
Studio recorder + spoken/text instructions
                  |
       FastAPI session/backend
                  |
    Preprocess + musical measurements
                  |
   Structured performance representation
                  |
   Reasoning agent + revision/version state
                  |
     Singing conversion / synthesis
                  |
  Objective comparison + listenable audio
                  |
    Director feedback -> new version
```

The LLM interprets user intent; analysis tools measure notes and time; singing models render audio. The agent cannot claim a successful match without independent measurement or human confirmation. Keep user-approved takes immutable unless explicitly superseded.

## 5. Repository Structure

**Original baseline:** `main` only, initial commit `b863383` with a single README.

**Current repository files:**
- `README.md`: project overview, Windows quick start and Seagate storage setup.
- `PROJECT_CONTEXT.md`: persistent handoff, verified and proposed state.
- `.gitignore`: excludes local secrets, large models, datasets, caches and generated assets.
- `.env.example`: non-secret external-storage configuration placeholder; not auto-loaded.
- `scripts/Initialize-Storage.ps1`: Windows-local, label-based storage initializer with preview mode; no hardcoded drive letters.
- `backend/pyproject.toml`: Python runtime/test dependencies.
- `backend/ai_singer/main.py`: FastAPI `/health` and `/ready`.
- `backend/ai_singer/storage.py`: validation of the configured absolute storage directory.
- `backend/ai_singer/__init__.py`: Python package marker.
- `backend/tests/test_api.py`, `backend/tests/test_storage.py`: 9 automated tests.

No `frontend/`, singing model, music analysis engine or dataset pipeline exists. Storage directories are created **locally on demand**, not in Git.

## 6. Development Progress

**Completed in GitHub:**
- Audited the existing repository; established version-control conventions and a persistent handoff.
- Implemented minimal FastAPI liveness and storage-readiness routes with 9 passing tests in the isolated development workspace.
- Recorded user-provided Windows, disk, GPU and toolchain inventory.
- **User confirmed that the Seagate device is the 2 TB `D:` volume labeled `Dimpu`.**
- Added a PowerShell script that discovers the volume by its label, previews or creates project subdirectories, and configures session-only storage/model cache variables.

**Verified from user-provided PowerShell execution:** The repository was cloned successfully to the user's computer, the script's `-Preview` resolved `Dimpu` to `D:\`, and the non-preview run reported `Storage directories created or verified.` The session then printed `AI_SINGER_STORAGE_ROOT = D:\AI_Singer`. These are reported local execution results, not independent filesystem inspection by the assistant.

**Verified from user-provided Windows test/server logs:** `python -m pytest -q` reports **9 passed, 1 warning in 0.70 seconds**. Uvicorn started, completed application startup, and served `GET /health` and `GET /ready` with HTTP 200. The readiness success is evidence that the configured storage directory passed the backend's basic readiness validation at that moment.

**Not yet verified on laptop:** Detailed disk write/read behavior, model cache paths, FFmpeg installation, model/GPU runtime, or actual audio processing. The GitHub connection cannot directly inspect the laptop.

**Not implemented:** Audio recording, frontend, pitch/timing analysis, singing generation, conversation agent, model downloads, training, dataset pipeline or deployment.

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

- No singing model, audio understanding, or frontend is implemented yet. API currently provides only health and configured storage-readiness checks.
- User ran the storage initializer on Windows and it reported successful directory creation/verification. However, folder contents and HDD read/write behavior have not been independently checked; model cache and exFAT compatibility remain unverified.
- `Get-Volume` volume-label lookup is Windows-specific; it intentionally fails on missing or ambiguous labels rather than writing to an unintended drive.
- Because `D:` uses **exFAT**, some model caches or tools may have limitations with symlinks and permissions. Confirm compatibility and model loading before major downloads.
- `C:` has ~41 GB free, and GPU is RTX 3050 Ti with 4 GiB VRAM. Large models or training may require smaller configurations or cloud compute.
- Actual FFmpeg installation, CUDA toolkit and PyTorch runtime are unverified. `nvidia-smi` CUDA support does not verify toolkit installation.
- `/ready` currently checks an existing absolute writable folder and does not independently prove physical drive identity; rerun the label-based script after reconnecting the HDD, and never rely on an old path.
- Windows pytest reported one `StarletteDeprecationWarning`: importing `fastapi.testclient` warns that `httpx` with `starlette.testclient` is deprecated and suggests `httpx2`. This is nonfatal; inspect actual versions and upstream guidance before changing dependencies.
- An incidental `GET /favicon.ico` returned HTTP 404 while browsing API endpoints; there is no frontend/favicon yet, and it is not a failed API health check.
- End-to-end audio quality, expressive singing, Telugu interpretation, model compatibility, dataset rights and latency remain untested.

## 9. Testing and Verification

**Performed in isolated development workspace (not on the user laptop):**
- `python -m compileall -q ai_singer` succeeded.
- `PYTHONPATH=. python -m pytest -q`: **9 passed** (re-run during this storage-setup session), testing API readiness and storage errors.
- A previous editable installation with preinstalled dependencies passed; fresh dependency installation on the user's Windows environment remains untested.
- Label-based PowerShell initializer reviewed for non-destructive operations, explicit preview, and session-only environment settings. **It cannot be executed or functionally tested on Windows from this environment** because no Windows PowerShell runtime or attached Seagate drive is available.

**Reported successful by user from Windows PowerShell:** Clone, storage preview, actual storage initializer, and current-session `AI_SINGER_STORAGE_ROOT` value. Python 3.12 virtual-environment backend pytest run: **9 passed, 1 warning in 0.70 seconds**; Uvicorn started successfully at `http://127.0.0.1:8000`, with `GET /health` **200** and `GET /ready` **200** in server logs. The test warning originates in FastAPI TestClient / Starlette and does not fail tests. **Not performed/verified:** independent HDD file write/read, FFmpeg, real GPU/model load, singing test, or training. HTTP response bodies were not included in the shared logs.

## 10. Development Environment

**Reported from the user's Windows PowerShell output (2026-11-22):**

| Item | Reported value |
| --- | --- |
| OS | Windows 11 Home, `10.0.26300` |
| GPU | NVIDIA GeForce RTX 3050 Ti Laptop GPU, 4 GiB VRAM; Intel UHD |
| NVIDIA driver | `610.60`; `nvidia-smi` CUDA version `13.3` (driver support only) |
| Git | `2.51.0.windows.1` |
| Python | `3.12.10` |
| Node.js | `24.11.0` |
| `C:` | NTFS; ~41 GB available |
| `B:` | NTFS; ~101 GB available |
| `D:` | exFAT, `Dimpu`; ~2 TB capacity, ~1.66 TB available; **user-confirmed Seagate HDD** |

**Windows storage setup completed according to user-supplied local PowerShell transcript:** Cloned repository and ran:

```powershell
.\scripts\Initialize-Storage.ps1 -VolumeLabel 'Dimpu' -Preview
.\scripts\Initialize-Storage.ps1 -VolumeLabel 'Dimpu'
$env:AI_SINGER_STORAGE_ROOT
$env:HF_HOME
$env:TORCH_HOME
```

The first command only displays a preview; the second creates folders and sets three variables for the **current PowerShell session**. It does not change global machine/user environment variables, format the drive, or download models.

**Backend (tested successfully on user's Windows laptop, per user-provided logs):**

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python -m pip install -e ".[dev]"
.\.venv\Scripts\python -m pytest -q
.\.venv\Scripts\python -m uvicorn ai_singer.main:app --reload
```

In a separate terminal, `Invoke-RestMethod http://127.0.0.1:8000/health` should show `ok`, and `Invoke-RestMethod http://127.0.0.1:8000/ready` should show `ready` when the drive folder is available.

Windows pytest, Uvicorn startup, and both endpoint HTTP 200 statuses have been reported successfully. Check `ffmpeg -version` next. New PowerShell terminals require rerunning `Initialize-Storage.ps1` (even if folders already exist).

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

1. **Next:** Confirm `ffmpeg -version` and inspect the Windows test warning's installed package versions if it persists. Avoid needless upgrades while the current backend is working.
2. Confirm `$env:HF_HOME` and `$env:TORCH_HOME` in the configured shell; optionally validate a small temporary file read/write on Seagate without downloading models. Record actual exFAT cache behavior before large downloads.
3. Implement a focused, safe 5–15-second completed-audio input → pitch, timing and pause estimates → structured JSON and diagnostic output experiment; design low-confidence/invalid-input handling and tests.
4. Validate the analyzer on short, consented known-reference audio and record measured errors.
5. Evaluate licensed male/female singing voice-conversion candidates with the 4 GiB GPU constraints, reporting quality, latency and resource use.
6. Build the conversational music-director agent, targeted revisions, approved-take memory and Director/Collaborative modes.
7. Prepare a rights-cleared Telugu dataset and experiment with controllable synthesis/fine-tuning only when justified by measurements.

## 13. Latest Development Session

**Date:** 2026-11-22. **Starting commit:** `0b68f26` on `main`.

**Windows verification reported by user:** Backend tests ran in `C:\Users\nithi\AI-Singer\backend`: `9 passed, 1 warning in 0.70s`. Uvicorn `--reload` launched on `127.0.0.1:8000`, server startup completed, and requests to `/health` and `/ready` both returned **HTTP 200**. No HTTP response bodies were supplied. The reported storage-readiness 200 means the current backend validator accepted the configured storage path at request time.

**Warning:** `StarletteDeprecationWarning` from `fastapi.testclient` suggesting `httpx2` in place of `httpx`. Nonfatal; investigate package compatibility before changing dependency pins. An automatic `/favicon.ico` request returned 404; expected for an API without a website icon.

**Changes this session:** Documentation-only update to reflect Windows-local backend success. No application code, dependency versions or assets were changed. GitHub commit is the revision containing this file (see Git history).

**Not yet verified:** FFmpeg, physical HDD read/write tests, actual model cache creation, GPU inference, singing audio, or musical analysis.

**Stop point / exact next task:** Confirm FFmpeg and optional cache locations, then implement the first measured musical-understanding/audio-input experiment with tests. The prior backend foundation and storage setup are now user-verified; don't repeat setup unnecessarily.
