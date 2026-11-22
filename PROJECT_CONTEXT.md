# AI Singer — Project Context

> **Persistent handoff:** Read this file at the beginning of each development session. Then inspect current source files and recent Git commits; this document is not a substitute for verification.
>
> **Last reviewed:** 2026-11-22 | **Repo:** [Nithin0553/AI-Singer](https://github.com/Nithin0553/AI-Singer) | **Status:** Documentation-only baseline.
>
> **Verification boundary:** Repository contents/history were checked through GitHub. The developer's actual laptop, Seagate HDD, drive capacity, OS, GPU and installed tooling **have not been inspected**.

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

These are **candidates, not installed or implemented integrations**:

| Layer | Candidate | Why |
| --- | --- | --- |
| UI | Next.js / React / TypeScript / Tailwind | Recorder, playback, revision controls |
| Backend | Python / FastAPI / Pydantic | Validated APIs and audio workflow |
| Agent | LangGraph + evaluated GPT API or Qwen | Understand instructions; plan tool calls and revisions |
| Speech instructions | faster-whisper or another multilingual ASR | Transcribe Telugu/English speech, subject to validation |
| Audio | FFmpeg, NumPy, SciPy, librosa | Process files and measure timing/rhythm |
| Pitch | RMVPE and/or torchcrepe | Measure singing pitch and contours |
| Singing experiment 1 | RVC-style voice conversion | Attempt to preserve the sung melody in a selected voice |
| Controlled synthesis candidate | DiffSinger | Later note/phoneme/duration-based edits |
| Dataset work | Separation tools and OpenVPI dataset utilities | Prepare permitted vocals, lyrics and annotations |
| Runtime and training | PyTorch, CUDA if available | Models and possible fine-tuning |
| Persistence later | PostgreSQL plus configured file/object storage | Sessions, takes, audio references |
| Tests | pytest, frontend tests, CI as code appears | Prevent regressions |

NVIDIA PersonaPlex is an optional speech interaction research candidate, **not** a proven singing model. Do not choose or download large models until actual hardware, model licenses and evaluation criteria are confirmed.

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

**Verified before setup:** `main` branch only; one initial commit `b863383` (“Initial commit”); one file `README.md` containing `# AI-Singer`. There was no app code, dependency manifest, test, CI configuration, or `PROJECT_CONTEXT.md`.

**Setup commit files:**
- `README.md`: concise introduction and handoff instructions.
- `PROJECT_CONTEXT.md`: verified/projected state, architecture, decisions, and next actions.
- `.gitignore`: excludes credentials, local state, downloaded models, and training/generated artifacts.

Directories like `backend/`, `frontend/` and `tests/` are planned **only**, not currently present.

## 6. Development Progress

**Verified:** Existing GitHub repo identified; write permissions, root listing, sole branch, initial commit, and initial README inspected. Documentation and safe Git ignores prepared for the initial setup commit.

**Pending environmental verification:** Local OS/version, internal free space, Seagate HDD location/capacity, NVIDIA GPU/VRAM, tool availability.

**Not implemented:** Backend, UI, recording, audio analysis, pitch extraction, singing conversion, model training, dataset pipeline, conversational intelligence, integration tests, deployment.

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

- No runnable code exists, so no implementation can yet be tested.
- Actual Windows/other OS version, free disk space, Seagate drive letters, filesystem, GPU and installed tooling are not yet accessible through this session.
- Pitch detection can be wrong on slides, vibrato, rests, noisy recordings or unvoiced segments.
- Telugu singing transcription, expressive quality, model suitability, and low latency remain unproven.
- No confirmed rights-cleared dataset or authorized voice models.
- A disconnected external HDD or changing drive letter must produce a clear future error rather than silent writes to the internal disk.

## 9. Testing and Verification

**Performed during repository setup:** Read GitHub repository metadata, root README, branch, and initial commit; reviewed the three setup documents and checked required handoff sections and ignore coverage. Verify final commit files via GitHub readback.

**Not performed:** Local laptop or HDD inspection; installation; application build; lint/unit/integration tests; GPU/model loading; audio inference; singer-quality evaluation; training. There is no existing application to execute.

**For future changes:** Review diff, run relevant tests, inspect exclusions/secrets and asset sizes, then verify the pushed commit and branch head.

## 10. Development Environment

**Not established.** Collect actual OS version, available internal space, Seagate volume/mount/filesystem/free space, GPU and VRAM, and installed Git/Python/Node/FFmpeg before setting up the machine. Do not request unique serial numbers.

If the laptop uses Windows, these are optional **read-only** PowerShell inventory commands:

```powershell
Get-CimInstance Win32_OperatingSystem | Select-Object Caption, Version
Get-Volume | Select-Object DriveLetter, FileSystemLabel, FileSystem, Size, SizeRemaining
Get-CimInstance Win32_VideoController | Select-Object Name, AdapterRAM
git --version
python --version
node --version
ffmpeg -version
nvidia-smi
```

Nothing can be installed or run from this repository yet. Add only verified install, run, and test commands after implementation.

## 11. Model and Storage Configuration

**Proposed Seagate structure (not yet created):**

```text
<AI_SINGER_STORAGE_ROOT>/
  models/{voice_conversion,singing_synthesis,audio_analysis}/
  datasets/{raw,processed,annotations}/
  cache/{huggingface,torch}/
  outputs/{previews,renders}/
  training/{checkpoints,logs}/
```

Use `AI_SINGER_STORAGE_ROOT` as the root environment variable, never a hardcoded drive letter. Configure `HF_HOME` and `TORCH_HOME` within that root **when model tools have been selected**; confirm each cache is actually redirected. Keep large downloads and training checkpoints on the HDD, and keep source, virtual environments, and latency-sensitive temporary buffers on the faster internal SSD if free space permits. Do not duplicate large model files.

Future startup should verify that the root exists and is writable, fail clearly if the external HDD is missing/remounted, and never silently fall back to an internal-drive default. Local `.env` and settings files must stay untracked. Add a non-secret `.env.example` once actual settings are implemented. Back up irreplaceable consented recordings and annotations separately.

## 12. Next Steps

1. Collect and verify the real laptop/Seagate storage, OS, GPU and developer toolchain inventory. **Block hardware-dependent configuration until then.**
2. Choose a minimal Python/toolchain baseline consistent with the inventory; implement backend health/config checks and automated tests.
3. Build an end-to-end local 5–15-second audio intake → pitch/rhythm/pauses → structured JSON + diagnostic plot experiment.
4. Verify pitch/timing quality on small permissioned test clips and document errors.
5. Test licensed male/female singing voice conversion and evaluate audio fidelity, latency, and compute use.
6. Add LangGraph/LLM interpretation, targeted corrections, approved-take memory and two modes after audio metrics are trustworthy.
7. Build a rights-cleared Telugu dataset process and evaluate controlled singing synthesis/fine-tuning.

Only mark tasks completed once actually implemented and verified.

## 13. Latest Development Session

**Date:** 2026-11-22. **Starting head:** `b863383` (`main`, “Initial commit”).

**Found:** Only initial README; no code or dependencies. **Changed for setup:** README, persistent context, ignore patterns. **Checks:** GitHub content/history inspection and documentation structure checks, not program tests. **Commit:** The commit containing this document (consult `git log -1 --oneline` for its hash; a commit cannot include its own SHA). **Stopping point:** Local device/storage inventory pending; no hardware configuration or development executed. **Resume with:** Priority 1 above.
