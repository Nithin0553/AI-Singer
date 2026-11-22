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

**Original baseline:** `main` only, initial commit `b863383`, root `README.md` only.

**Now present:**
- `README.md`: project overview and backend quick start.
- `PROJECT_CONTEXT.md`: persistent, verified handoff.
- `.gitignore`: local secrets, model, dataset, cache, and generated asset exclusions.
- `.env.example`: intentionally blank external-storage root for local configuration.
- `backend/pyproject.toml`: minimal Python project metadata and development dependencies.
- `backend/ai_singer/main.py`: FastAPI `/health` and `/ready` routes.
- `backend/ai_singer/storage.py`: safe validation of `AI_SINGER_STORAGE_ROOT` with no silent internal-disk fallback.
- `backend/ai_singer/__init__.py`: package marker.
- `backend/tests/test_api.py`, `backend/tests/test_storage.py`: backend tests.

Folders such as `frontend/`, `models/`, and `datasets/` **do not exist in Git** and should be created only when needed. Model/data directories belong on configured external storage.

## 6. Development Progress

**Completed:**
- Located and inspected GitHub repository and initial history.
- Established repository handoff documentation and exclusions; pushed `9eb2048`.
- Reviewed user-provided Windows OS, disk, GPU and tool-version reports (not directly verified on the laptop).
- Added minimal FastAPI liveness and external-storage readiness checks with 9 tests; implementation tested in isolated development container.

**In progress / blocked pending device confirmation:**
- Identify which disk/volume is the Seagate HDD; reported `D:` volume is 2 TB (exFAT), not the described 1 TB device.
- Confirm FFmpeg availability and whether the intended external model root exists.
- Run the backend and tests on the actual Windows laptop.

**Not implemented:** Frontend, audio capture, pitch or note detection, structured performance, singing generation, agent orchestration, music-memory, fine-tuning, dataset processing, or deployment.

## 7. Technical Decisions

- Continue in the existing GitHub repo; no new repo.
- Keep `main` stable; commit directly for small reviewed changes; isolate risky work only when needed. No force-push or destructive Git actions.
- Update this file whenever code, tests, architecture, risks or priorities materially change, and at the end of sessions.
- Store datasets/models and generated output off Git, with paths supplied by environment configuration.
- Build a **turn-based** singing agent: listen first, respond after recording ends.
- First validate musical listening and pitch/timing representation. Then benchmark voice conversion before attempting costly custom Telugu training.
- Model, agent and storage proposals are not confirmations of functioning code.
- Do not install dependencies or configure hardware-dependent paths before getting the real local inventory.

## 8. Known Issues

- The backend performs only process liveness and configured storage-readiness checks; there is no musical feature yet.
- Seagate disk identity is **unconfirmed**. Windows shows `D:` labeled `Dimpu`, around 2 TB, exFAT. This may or may not be the Seagate device; do not place large assets there until confirmed.
- `C:` has only ~41 GB free (decimal), limiting on-SSD working sets. NVIDIA RTX 3050 Ti has 4 GiB VRAM; larger models/training may need GPU rental or smaller configurations.
- FFmpeg not checked, CUDA toolkit and actual PyTorch compatibility not verified. `nvidia-smi` reporting CUDA version 13.3 indicates driver support, **not** that CUDA toolkit is installed.
- `/ready` checks for a configured, existing, writable folder; it does not create storage paths or verify real device identity. `os.access` is a basic writability hint, not a complete physical write test.
- Candidate singing model quality, Telugu transcription, latency, pitch accuracy, dataset rights, and synthesis are untested.
- Initial packaging install in the isolated container required `--no-build-isolation` because the container has no outbound access; normal Windows installation has **not been tested**.

## 9. Testing and Verification

**Performed in isolated development container (Python 3.13.5, not the user laptop):**
- `python -m compileall -q ai_singer` succeeded.
- `PYTHONPATH=. pytest -q`: **9 passed**. Tests cover `/health`, `/ready`, missing/disconnected storage, relative paths, and valid directories.
- `python -m pip install -e . --no-build-isolation --no-deps` succeeded using already-installed dependencies; `python -m pytest -q` again yielded **9 passed**.
- The isolated container could not resolve package-index hosts for a normal build-isolation install, so this does **not** verify fresh dependency installation.
- GitHub branch and changed-file readback should be checked after this commit.

**Not performed:** Windows-local startup/install, FFmpeg checks, actual HDD access, GPU/PyTorch model tests, audio inference, singing tests, fine-tuning.

**Future changes:** Review the diff, run applicable tests, check secrets/large assets, and verify the pushed commit and branch head.

## 10. Development Environment

**Reported by the user from their Windows laptop on 2026-11-22 (not directly inspected):**

| Item | Reported value |
| --- | --- |
| OS | Microsoft Windows 11 Home, build `10.0.26300` |
| GPU | NVIDIA GeForce RTX 3050 Ti Laptop GPU, 4 GiB VRAM; Intel UHD integrated graphics |
| NVIDIA | driver `610.60`; `nvidia-smi` shows CUDA UMD support `13.3` (CUDA toolkit unverified) |
| Git | `2.51.0.windows.1` |
| Python | `3.12.10` |
| Node.js | `24.11.0` |
| C: | NTFS, ~335 GB capacity, ~41 GB free |
| B: | NTFS, `New Volume`, ~152 GB capacity, ~101 GB free |
| D: | exFAT, `Dimpu`, ~2 TB capacity, ~1.66 TB free |

Other NTFS volumes shown without letters appear to be small system/recovery partitions; do not use them for project storage.

**Critical gap:** User described a Seagate **1 TB** external HDD, but the shown `D:` volume has ~2 TB capacity. Identify the actual Seagate physical disk and its mounted partition(s), without revealing serial numbers or changing/formatting drives. Use read-only PowerShell:

```powershell
Get-Disk | Select-Object Number, FriendlyName, BusType, Size
Get-Partition -DriveLetter D | Get-Disk | Select-Object Number, FriendlyName, BusType, Size
Get-Partition -DriveLetter B | Get-Disk | Select-Object Number, FriendlyName, BusType, Size
ffmpeg -version
```

**Backend quick start for Windows (not yet verified on laptop):**

```powershell
git clone https://github.com/Nithin0553/AI-Singer.git
cd AI-Singer/backend
python -m venv .venv
.\\.venv\\Scripts\\python -m pip install -e ".[dev]"
.\\.venv\\Scripts\\python -m pytest -q
.\\.venv\\Scripts\\python -m uvicorn ai_singer.main:app --reload
```

`GET /health` should return `{"status":"ok"}` even when the drive is disconnected. `GET /ready` returns HTTP 503 until `AI_SINGER_STORAGE_ROOT` points to an existing writable directory; this is intentional. Windows commands and dependency installation require verification on the actual laptop.

No model downloads or machine-specific HDD folders have been created.

## 11. Model and Storage Configuration

**External storage root remains UNSELECTED** until a read-only physical disk-to-volume check confirms which drive is the Seagate HDD. Do not assume `D:` is correct or initialize/format anything.

**Proposed structure, not created:**

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

The backend uses `AI_SINGER_STORAGE_ROOT`. With the variable missing, relative, or pointing at a nonexistent directory, storage readiness fails clearly with HTTP 503; the app never silently defaults to an internal drive. `.env.example` intentionally leaves the value empty and does not auto-load it. After drive identification, set it explicitly in the Windows process environment.

When selecting model libraries, configure `HF_HOME` and `TORCH_HOME` under this root, verify that each respects the cache setting, and avoid repeated downloads. Keep source and latency-sensitive temporary work on internal SSD where space permits; HDD is slower. Maintain separate backups of irreplaceable recordings, annotations, and rights/consent metadata.

## 12. Next Steps

1. **Confirm Seagate HDD physical identity and mount** with read-only PowerShell `Get-Disk` / `Get-Partition` commands above. Check `ffmpeg -version`.
2. **Run minimal FastAPI backend on Windows** using the tested steps above; record Python 3.12 installation and pytest results. The `/health` endpoint is independent of the external drive.
3. **Create external folders and configure `AI_SINGER_STORAGE_ROOT` only after confirming correct drive.** Verify that `/ready` transitions from 503 to 200; check disconnect behavior.
4. Build a focused 5–15-second upload/recording → musical pitch/time/pauses → structured JSON experiment with explicit uncertainty.
5. Validate on permissioned sample audio, then benchmark male/female singing voice conversion against original pitch and duration.
6. Implement the conversational music-director agent, approved takes/revisions and two creativity modes.
7. Build a rights-cleared Telugu dataset pipeline and investigate advanced synthesis/fine-tuning when justified by measurement and hardware cost.

## 13. Latest Development Session

**Date:** 2026-11-22. **Base GitHub commit:** `9eb2048` on `main` (initial documentation).

**User-provided inventory:** Windows 11 Home, Git 2.51, Python 3.12.10, Node 24.11, RTX 3050 Ti / 4 GiB, driver 610.60. Volumes: `C:` ~41 GB free, `B:` ~101 GB, `D:` ~1.66 TB. Seagate volume identity unresolved because the user described a 1 TB HDD but `D:` is ~2 TB.

**Implementation:** Minimal FastAPI backend with `/health` and storage-aware `/ready`, explicit storage root validation, starter `pyproject.toml`, sample environment variable, and 9 tests.

**Verification:** Python 3.13 isolated container: compileall succeeded, pytest 9/9 passed, editable installation succeeded without build isolation using pre-existing dependencies. Standard isolated install failed only because container package-index access is unavailable. **Not yet verified on the user laptop.**

**Commit:** This GitHub commit (see Git history; the file cannot include its own SHA).

**Stop point:** Remote repository foundations in place; waiting for the disk-to-volume mapping and Windows-local backend test. No large models or datasets downloaded; no Windows disk modifications performed.
