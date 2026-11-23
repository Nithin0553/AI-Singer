# AI Singer — Project Context

> **Persistent handoff:** Read this file at the beginning of each development session. Then inspect current source files and recent Git commits; this document is not a substitute for verification.
>
> **Last reviewed:** 2026-11-23 | **Repo:** [Nithin0553/AI-Singer](https://github.com/Nithin0553/AI-Singer) | **Status:** Windows Pitch Lab and two-estimator comparison verified; 68 tests passed on user's Windows laptop. Known-pitch synthetic YIN/RMVPE calibration passed on Windows; local code now separates the previously merged C4→D4 slow-glide passage into held C4, glide and held D4. New Windows acceptance and human-singing ground-truth accuracy are pending.
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

**Implemented:** FastAPI/Uvicorn, FFmpeg audio decoding, YIN/librosa, opt-in CPU RMVPE ONNX, NumPy/SciPy postprocessing, a minimal local HTML/Canvas Pitch Lab, reference-validation CLI and pytest.

| Layer | Technology | Actual status |
| --- | --- | --- |
| Audio API | Python 3.12+, FastAPI, Uvicorn | `GET /health`, `GET /ready`, `POST /analyze`, new `POST /compare` |
| Pitch estimation | YIN and RMVPE ONNX CPU | Both ran on user's 9.195 s recording; model accuracy **not** ground-truth validated |
| Musical interpretation | `musical_events.py` (NumPy, SciPy) | New stable-core, transition and octave-review heuristics; code-tested with synthetic examples |
| Local visualization | HTML Canvas + browser audio controls at `GET /pitch-lab` | Browser page and graphs verified by user's screenshot; click-to-seek not individually demonstrated |
| Reference scoring | `pitch_validation.py` | Scores separately annotated known pitch/rest intervals, not model agreement |
| Full frontend | Next.js/React/TypeScript | **Not implemented** |
| Conversational agent | LangGraph/LLM | **Not implemented** |
| Singing synthesis and voice conversion | Permitted RVC/DiffSinger candidates | **Not implemented** |

## 4. System Architecture

```text
Uploaded completed recording (1–15 s, <=10 MiB)
  -> short-lived seekable FFmpeg file -> mono 16 kHz PCM
  -> YIN (default) or RMVPE ONNX CPU
  -> original time-stamped pitch track (NEVER automatically corrected)
  -> stable pitch cores + glide/transition candidates + octave review flags
  -> JSON /analyze response

POST /compare: decode once, evaluate both -> disagreement intervals + reports
GET /pitch-lab: local HTML Canvas view -> upload and listen -> compare/seek/export
pitch_validation CLI: independent labeled reference + saved benchmark -> error metrics
```

Known limitations: the stable-core regions are **not true note onset boundaries**; they intentionally do not label all glides as note events. Octave excursions are flagged for review, never corrected automatically. YIN is still the default and RMVPE still requires explicit permitted model weights on Seagate. No recording persistence, singing generation or conversational musician implemented.

## 5. Repository Structure

- `backend/ai_singer/audio_analysis.py`: YIN/RMVPE frame estimates, now delegates event grouping to `musical_events.py`.
- `backend/ai_singer/musical_events.py`: stable pitch cores, candidate glides and short octave anomaly detection; preserves raw measurements.
- `backend/ai_singer/pitch_benchmark.py`: joint estimators, continuous disagreement spans and stable-core summary.
- `backend/ai_singer/pitch_validation.py`: scores independently known note/rest labels.
- `backend/ai_singer/calibration.py`: generates an exact-pitch synthetic WAV and reference under configured HDD storage and optionally scores YIN/RMVPE.
- `backend/tests/test_calibration.py`: 11 new tests for tones, rests, glide, reference, storage and reports.
- `backend/ai_singer/main.py`: existing routes plus `POST /compare` and local `GET /pitch-lab`.
- `backend/ai_singer/static/pitch_lab.html`: dependency-free local inspection page with graph and audio playback.
- `backend/examples/pitch-reference.example.json`: reference interval format example (not a true annotated sample).
- `backend/tests/test_musical_events.py`, `test_pitch_validation.py`: synthetic notes/slides/octave cases, reference checks, API/visualization tests.
- Existing `backend/tests/test_api.py`, `test_storage.py`, `test_audio_analysis.py`, `test_rmvpe_pitch.py`: retained.
- `backend/pyproject.toml`: includes the static HTML in Python package.
- `scripts/Initialize-Storage.ps1`, `README.md`, `PROJECT_CONTEXT.md`, `.gitignore`: storage, documentation, continuity and exclusions.

## 6. Development Progress

**New implementation completed and verified on Windows (user-supplied screenshot/logs):** Stable-note-core segmentation, glide candidates and suspect octave excursion reporting (without modifying actual pitch observations). Browser Pitch Lab rendered two pitch curves, stable cores and a review span, and audio player controls were displayed. The comparison endpoint returned HTTP 200. The user's Windows pytest run reported **68 passed in 7.62s**. Detailed audio playback and click-to-seek behavior were not demonstrated in the evidence.

**Local testing evidence:** A mirrored backend checked with pytest in an isolated Linux/Python 3.13 environment reported **67 passed**, and Python compilation and editable packaging succeeded. JavaScript syntax and inclusion of static HTML in the built wheel were also checked. This source was refined and staged to GitHub; the exact staged remote tree and user Windows behavior have not yet been independently executed and must be verified.

**Applied to user's saved YIN/RMVPE JSON (without audio):** Old quantized candidate counts: YIN 36, RMVPE 43. New heuristic yielded **13 YIN and 10 RMVPE stable pitch cores**, plus 13 and 12 transition candidates respectively. A YIN-only short octave excursion is flagged around 8.90–9.04 s; model disagreement spans 8.90–8.96 s with median difference 1,189 cents. These are algorithmic outputs only, **not actual sung note counts**.

**Already user-verified:** Seagate `Dimpu`, FFmpeg 9.1, YIN `/analyze` 200, and real Windows CPU benchmark YIN 11.342 s vs RMVPE 2.102 s, with 11-cent median disagreement over jointly voiced frames. No known-note ground truth supplied.

**New exact JSON from Windows Pitch Lab:** 9.195-second clip; 460 frames; YIN/RMVPE voiced frames 390/393, jointly voiced 388, median difference 11 cents; 1 cross-estimator review span from 8.90–8.96 s (median 1,189 cents); 13 YIN and 10 RMVPE stable cores, 1 YIN octave-jump candidate and 0 RMVPE octave-jump candidates. RMVPE pitch transition candidates: 12. This run timed YIN at **2.830 s** and RMVPE at **5.121 s**; earlier benchmark timings differed substantially, so do not assume a general speed winner.

**Controlled development benchmark:** Synthetic 7.55 s fixture generated with held A3/C4/D4, pauses and a C4-to-D4 glide. In an isolated Linux environment, YIN scored **192/192 labeled pitch frames**, 34/34 labeled quiet frames, 1.0-cent median absolute error and zero octave errors. These are **synthetic tones**, not human singing. The moving slide and note transitions are deliberately excluded from constant-note scoring. **Windows RMVPE inference on the synthetic fixture now reported successful:** 192/192 labeled pitched frames, 34/34 known rest frames correctly unvoiced, 2-cent median absolute error, 100% within 50 cents and zero octave error frames. Compared with YIN's 1-cent median error, both models passed the held-note/rest benchmark; this does not validate human singing.

**Slow-glide fix in this session:** Replaced sole local-range criterion with local pitch range plus robust longer-context median drift; original pitch tracks and octave-review flagging are untouched. In a mirrored development tree, **83 tests passed** (78 existing + 5 new), and both uploaded YIN/RMVPE calibration tracks now yield stable cores MIDI **57, 60, 62, 57** and an upward glide candidate approximately **3.40–4.16 s (YIN)** / **3.40–4.18 s (RMVPE)**. These are approximate event boundaries, not human annotations.

**Still unimplemented:** General expressive note understanding, automatic source note onset recognition, original-voice playback synthesis, lyric/phoneme understanding, agent reasoning, voice conversion or full studio.

## 7. Technical Decisions

- Continue on the verified GitHub `main` history; do not overwrite or force-push.
- **Keep raw `pitch_track` unchanged**; classify stable pitch cores, transitions and suspected octave errors as metadata. Nothing automatically corrects source performance.
- Change `note_events` semantics to **stable pitch cores**: clients must not treat count or start/end as ground-truth note transcription. Add separate `pitch_transitions` and `octave_jump_candidates`.
- Keep YIN the API default; RMVPE is explicit and loads verified external weights only when requested.
- Provide a lightweight local browser page before investing in a full Next.js studio; no external scripts, fonts, audio uploads or persistent recording storage.
- Measure **accuracy** against independently annotated pitch/rest intervals, not merely YIN/RMVPE agreement.
- Keep Seagate models and outputs outside Git; Python source/venv remain on local SSD.

## 8. Known Issues

- Stable-core classification uses local pitch stability windows and minimum event lengths. It is a heuristic, with provisional thresholds and **unverified note boundaries**. Slow slides, vibrato, fast ornaments, breaths and expressive transitions can still be mislabeled.
- A short octave-like YIN drop near 8.90–8.94 s is a **review candidate**, not automatically fixed. No original raw user recording was supplied to compare by listening. RMVPE remains an experiment, not a proven production choice.
- `POST /compare` invokes both estimators; CPU runtime may be >10 seconds on this laptop. No request queue, concurrent-user throttling, or broader production security hardening has been implemented. The browser page should be run locally only.
- The new generator makes known-reference synthetic audio with a matching score file; its success does **not** establish human singer accuracy. Moving slide and onset boundaries are intentionally excluded from the *existing score tool*. The previous example file remains only a format illustration.
- **Slow-glide grouping bug addressed in code, Windows acceptance pending:** Previously the entire held C4 → 0.85 s upward glide → held D4 interval was mislabeled MIDI 61 (C♯4). A longer-context median drift test now distinguishes that continuous movement from a stable pitch. The uploaded known-pitch tracks replayed with the new code yield A3/C4/D4/A3 cores plus a glide in both YIN and RMVPE. This is tested on the synthetic reference only. Other melodic transitions, vibrato intensities and genuine singer performance boundaries remain unverified.
- An existing client relying on the previous quantized `note_events` count must be updated; new classification deliberately returns fewer stable cores.
- Browser Pitch Lab rendered and `/compare` succeeded in the latest Windows run; 68/68 tests passed. The user subsequently confirmed clicking the red 8.9-second graph region seeks the audio player to that point, verifying seek behavior but not perceptual accuracy. The user has not provided the original audio bytes here, so no perceptual assessment or independent note-onset verification is possible.
- Seagate exFAT symlink/cache behavior remains a possible limitation. Model licensing still needs user review before production.

## 9. Testing and Verification

**Development container (Linux Python 3.13):**
- Local mirror `pytest -q`: **67 passed** after adding 26 tests around segmentation, glide/vibrato, octave candidates, comparison, local HTML endpoint, and annotated-reference error metrics.
- `python -m compileall -q ai_singer tests`: passed.
- Offline editable build and wheel checked; wheel includes `ai_singer/static/pitch_lab.html`.
- HTML inline JavaScript parsed under Node.js `--check`. No browser engine available in container to test interactive rendering; manual Windows browser test required.
- Recomputed candidate regions using user's saved 9.195 s YIN/RMVPE JSON (pitch data only); results above. This does not constitute accuracy validation.

**Windows acceptance supplied by user (2026-11-23):** `pytest -q` in the existing backend virtual environment reported **68 passed in 7.62 s**. Uvicorn started successfully; `GET /pitch-lab` returned HTTP 200, and `POST /compare` returned HTTP 200. A `GET /favicon.ico` request returned expected HTTP 404 because there is no favicon. The attached screenshot shows both estimator traces, green stable pitch cores, red review span, audio player and summary statistics. The supplied JSON confirms comparison values and note/event summary. The screenshot does not independently verify click-to-seek playback synchronization.

**User-verified UI behavior:** Clicking the red review region around 8.9 seconds seeks the browser audio player there. **New Windows synthetic calibration evidence from user-supplied JSON:** both estimators detected all 192 labeled pitch frames, missed zero, and correctly left all 34 labeled quiet frames unvoiced; 100% of detected labeled pitches within 50 cents; no scored octave errors; median absolute error YIN **1 cent**, RMVPE **2 cents**. The full 7.55-second comparison had 378 frames and 2-cent median *inter-model* disagreement, zero disagreement spans, runtimes YIN **2.317 s**, RMVPE **4.719 s** for that run. The user's latest Windows pytest summary has not been supplied. **Important unscored structural failure:** both model note groupers label the entire held C4 → glide → held D4 passage as MIDI 61. **This session's isolated development tests:** 83 passed in mirrored Python 3.13 backend; compilation passed. Regression cases cover ascending/descending slow slides, held middle C♯4, vibrato and generated calibration. Exact Windows acceptance remains pending. **Still not verified:** actual human singing ground-truth accuracy, robust onset/transition labeling across varied performances, voice generation and live dialogue.

## 10. Development Environment

Windows 11 Home; user source checkout `C:\Users\nithi\AI-Singer`; Python 3.12.10, FFmpeg 9.1, RTX 3050 Ti 4 GiB, Seagate exFAT volume `Dimpu` at `D:\AI_Singer`.

**Next run:**

```powershell
cd C:\Users\nithi\AI-Singer
git pull --ff-only
.\scripts\Initialize-Storage.ps1 -VolumeLabel 'Dimpu'
cd backend
.\.venv\Scripts\python -m pip install -e ".[dev,rmvpe]"
.\.venv\Scripts\python -m pytest -q
.\.venv\Scripts\python -m uvicorn ai_singer.main:app --reload
```

Open `http://127.0.0.1:8000/pitch-lab` in a browser, upload an original 1–15-second clip, select both estimators (weights already configured on user's HDD), and compare against the recording. YIN-only works if RMVPE is disconnected. For independent accuracy metrics, use `python -m ai_singer.pitch_validation <benchmark.json> <reference.json>` where reference spans use the included sample schema.

## 11. Model and Storage Configuration

Continue to use `AI_SINGER_STORAGE_ROOT` pointing to Seagate `Dimpu` (currently `D:\AI_Singer`). The existing verified RMVPE checkpoint under `models/audio_analysis/rmvpe.onnx` is reused; **no re-download** is required. Store benchmark JSON and any subsequent permissioned recording only in authorized external storage, never Git. The new Pitch Lab uses browser-selected audio for playback and discards the server-side temporary decoding file. Its JSON download is explicitly user-triggered.

## 12. Next Steps

1. **Windows acceptance of slow-glide fix:** From the existing clone, `git pull --ff-only`, run `backend/.venv/Scripts/python -m pytest -q`, then restart Uvicorn and load the existing known-pitch WAV in Pitch Lab. Verify a held C4 core, one upward glide, and held D4 core (rather than one C♯4 segment). The local mirrored suite passed 83 tests, but the exact Windows count may differ slightly.
2. **Compare the two real Windows estimator outputs** on the same stored synthetic calibration, without re-downloading RMVPE weights. Expect the approximate glide to be 3.4–4.18 seconds, with original pitch tracks retained. Record actual Windows timings/results.
3. **Human singing ground truth:** Record a few consented short phrases and independently annotate actual pitches, rests, and transitions. Evaluate pitch errors separately from note grouping and phonetic timing. The synthetic result is not a real-singing accuracy guarantee.
4. **Tune only measured failures:** If human glides, vibrato or short held notes remain misgrouped, compare against annotations and add targeted regression tests. Preserve measured pitch and report uncertainty.
5. After demonstrating adequate musical interpretation, move to permissioned singing voice conversion and later conversational Director/Collaborative intelligence.

## 13. Latest Development Session

**Date:** 2026-11-23. **Starting main commit:** `2abb2137` (documented synthetic-calibration grouping failure).

**Goal:** Fix the slow C4-to-D4 glide being mistakenly interpreted as a single C♯4 while retaining independent YIN/RMVPE pitch estimates, vibrato tolerance, octave-review behavior and genuine held middle notes.

**Changes:** Updated `backend/ai_singer/musical_events.py` to keep existing ~180 ms local pitch-spread check and additionally reject longer-term median drift across approximately ±240 ms. Added 4 targeted pitch-event regressions (ascending and descending slow glides, a genuinely held C♯4 between notes, gentle vibrato), plus 1 full generated-calibration event regression. Added user-facing note to README. No new dependencies, model weights or generated audio files.

**Regression before fix:** The ascending-slow-glide test failed, labeling the complete C4→D4 passage as MIDI 61. **After fix:** Mirrored backend `pytest -q` **83 passed**, and `compileall` passed in Linux Python 3.13. The previously uploaded user Windows `known-pitch-comparison.json` was replayed through the updated grouping code: YIN and RMVPE each yield MIDI [57, 60, 62, 57] held-pitch cores and an independent `glide_candidate` at approximately 3.40–4.16 s / 3.40–4.18 s. No raw pitch frames are rewritten. The latest GitHub head must be verified after pushing.

**Verification boundary:** Tests and data replay were run in the isolated development workspace; **not on the user's Windows laptop**, nor against independently annotated human singing. These event boundaries remain approximate. Full repository Windows tests, singing synthesis and agent remain pending.

**Stop point:** Ask the user to pull latest `main`, run pytest and restart Pitch Lab using the known-pitch WAV; then proceed to human-sung ground-truth evaluation.
