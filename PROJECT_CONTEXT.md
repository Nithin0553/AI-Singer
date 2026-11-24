# AI Singer — Project Context

> **Persistent handoff:** Read this file at the beginning of each development session. Then inspect current source files and recent Git commits; this document is not a substitute for verification.
>
> **Last reviewed:** 2026-11-23 | **Repo:** [Nithin0553/AI-Singer](https://github.com/Nithin0553/AI-Singer) | **Status:** Windows Pitch Lab, real YIN/RMVPE inference, and the slow-glide fix verified on the user's laptop; **90 Windows tests passed in 6.61 seconds** after the voicing-review test fix, and the Test 2 comparison endpoint returned HTTP 200 with six voicing-disagreement spans. Both estimators now identify A3 → C4 → upward glide → D4 → A3 on the synthetic calibration. First human vocal `Test 2.m4a` has now been compared with **both YIN and real RMVPE** in user's Pitch Lab (625 frames, 4-cent median inter-model disagreement). Voicing-only differences are now explicitly grouped and shown in Pitch Lab; independent ground-truth musical accuracy is still unverified.
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
- `backend/ai_singer/pitch_benchmark.py`: joint estimators, continuous pitch-disagreement spans, separate voicing-disagreement spans, stable-core summary.
- `backend/ai_singer/pitch_validation.py`: scores independently known note/rest labels.
- `backend/ai_singer/calibration.py`: generates an exact-pitch synthetic WAV and reference under configured HDD storage and optionally scores YIN/RMVPE.
- `backend/tests/test_calibration.py`: 11 new tests for tones, rests, glide, reference, storage and reports.
- `backend/ai_singer/main.py`: existing routes plus `POST /compare` and local `GET /pitch-lab`.
- `backend/ai_singer/static/pitch_lab.html`: dependency-free local inspection page with graph and audio playback.
- `backend/examples/pitch-reference.example.json`: reference interval format example (not a true annotated sample).
- `backend/tests/test_musical_events.py`, `test_pitch_validation.py`, new `test_voicing_disagreements.py`: synthetic notes/slides/octave cases, reference checks, comparison voicing gaps, API/visualization tests.
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

**First real human-vocal test (user-provided `Test 2.m4a`):** 12.48-second original recording was decoded with FFmpeg to mono 16 kHz and processed in an isolated environment using YIN, RMS/periodicity voicing and current longer-context stable-core heuristic. 625 frame positions, 363 pitch-detected frames. Strong first voice region approximately 0.78–2.40 s, long pause to ~4.98 s, second phrase 4.98–10.90 s. Candidate stable cores at 1.04–2.40 s (MIDI 46/A♯2), 5.32–6.06 s (MIDI 49/C♯3), 6.36–9.26 s (MIDI 55/G3 rounded from ~54.5), 10.18–10.90 s (MIDI 46/A♯2). Candidate rises 4.98–5.32 s (+1.59 semitones) and descent 9.42–10.18 s (−3.14 semitones), plus an initial onset pitch fall. 6.36–9.26 s upper passage is sustained with shallow pitch wavering; whether this is vibrato/ornamentation is uncertain. These are only YIN measurements; no independent note/lyrics reference and no RMVPE model run in the isolated environment. The screenshot available with the follow-up shows `Test 1.m4a` rather than `Test 2.m4a`; request a newly exported Pitch Lab JSON for Test 2 before interpreting a YIN/RMVPE comparison.

**First Test 2 YIN/RMVPE comparison verified by user's exported Pitch Lab report:** 12.48 s and 625 time frames; YIN detects 363 voiced, RMVPE 385, overlapping 362. Median absolute disagreement is **4 cents** on overlapping voiced frames; **361/362 (99.7%)** overlapping frames differ by ≤50 cents (max observed about 55 cents at first onset), and neither has an octave-like disagreement or flagged pitch-disagreement interval. The four stable-core MIDI regions are **[46,49,55,46]** (A♯2, C♯3, G3 rounded from pitch close to F♯3/G3 boundary, A♯2). YIN core windows: 1.04–2.40, 5.32–6.06, 6.36–9.26, 10.18–10.90 s; RMVPE: 1.04–2.40, 5.30–5.94, 6.52–9.12, 10.16–10.72 s. RMVPE produces 6 transition candidates vs YIN 4. Most notable missing-voicing differences: RMVPE reports continuous pitch across **6.16–6.36 s (10 frames)** and **9.26–9.38 s (6 frames)** when YIN returns null; there are other smaller gaps, totaling 23 RMVPE-only voiced frames vs 1 YIN-only. The 6.16–6.36 s area has median RMS 0.135 (significant signal energy), whereas 9.26–9.38 s has median RMS 0.014 (quieter), so continued sound does not alone establish correct pitch. Model timing in this report: YIN 0.111 s, RMVPE 0.816 s (do not extrapolate to typical speed). This agreement is **not** ground-truth note or expressive accuracy.

**Voicing-difference visibility added:** `compare_results` now returns independent `voicing_disagreement_intervals` (with a start/end, frame count and `voiced_by` model) and counts `rmvpe_only_voiced_frames`/`yin_only_voiced_frames`. Separate amber/light-blue bands and clickable timestamp chips appear in Pitch Lab without changing existing red pitch-review bands or raw pitch tracks. The previously uploaded Test 2 JSON replay yields **six spans**: RMVPE-only 0.74–0.78 s (2 frames), 4.90–4.98 s (4), 6.16–6.36 s (10), 9.26–9.38 s (6), 9.40–9.42 s (1), and YIN-only 4.82–4.84 s (1). The local source compatibility/logic tests succeeded, but a final user Windows browser acceptance is still pending. These are disagreement markers, **not ground-truth errors**.

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

- Stable-core classification uses pitch stability windows and minimum event lengths. It remains heuristic, with provisional thresholds and **unverified note boundaries**. Slow slides, vibrato, fast ornaments, breaths and expressive transitions may still be mislabeled.
- **Test 2 voicing visibility gap addressed in code:** Previously zero pitch-disagreement spans hid 23 RMVPE-only vs 1 YIN-only voiced frames. The new `voicing_disagreement_intervals` and colored Pitch Lab regions expose these while keeping pitch disagreement independent. Windows full pytest and the real comparison JSON now verify the new gap fields; the screenshot provides visual evidence of the Pitch Lab review interface. Clicking the *new* voicing-gap chips has not been independently confirmed by the user. Independently annotated singing is still needed before claiming one model is correct.
- A short octave-like YIN drop near 8.90–8.94 s is a **review candidate**, not automatically fixed. No original raw user recording was supplied to compare by listening. RMVPE remains an experiment, not a proven production choice.
- `POST /compare` invokes both estimators; CPU runtime may be >10 seconds on this laptop. No request queue, concurrent-user throttling, or broader production security hardening has been implemented. The browser page should be run locally only.
- The new generator makes known-reference synthetic audio with a matching score file; its success does **not** establish human singer accuracy. Moving slide and onset boundaries are intentionally excluded from the *existing score tool*. The previous example file remains only a format illustration.
- **Slow-glide bug fixed and Windows-verified on synthetic calibration:** Previously the held C4 → 0.85 s glide → held D4 was mislabeled one MIDI 61 (C♯4). The longer-context median drift test now identifies four stable cores MIDI [57,60,62,57] plus an upward glide in both estimators. Windows-generated reports confirm this, and all **84 Windows tests pass**. Other melodic transitions, singer vibrato, ornamentation, actual performed onsets and perceptual correctness remain unverified.
- An existing client relying on the previous quantized `note_events` count must be updated; new classification deliberately returns fewer stable cores.
- Browser Pitch Lab rendered and `/compare` succeeded in the latest Windows run; 68/68 tests passed. The user subsequently confirmed clicking the red 8.9-second graph region seeks the audio player to that point, verifying seek behavior but not perceptual accuracy. The user later uploaded a separate original human-singing recording (`Test 2.m4a`), and Pitch Lab's results were compared against it. No independently annotated actual-pitch or onset reference is available, so accuracy cannot yet be established.
- Seagate exFAT symlink/cache behavior remains a possible limitation. Model licensing still needs user review before production.

## 9. Testing and Verification

**Development container (Linux Python 3.13):**
- Local mirror `pytest -q`: **67 passed** after adding 26 tests around segmentation, glide/vibrato, octave candidates, comparison, local HTML endpoint, and annotated-reference error metrics.
- `python -m compileall -q ai_singer tests`: passed.
- Offline editable build and wheel checked; wheel includes `ai_singer/static/pitch_lab.html`.
- HTML inline JavaScript parsed under Node.js `--check`. No browser engine available in container to test interactive rendering; manual Windows browser test required.
- Recomputed candidate regions using user's saved 9.195 s YIN/RMVPE JSON (pitch data only); results above. This does not constitute accuracy validation.

**Windows acceptance supplied by user (2026-11-23):** `pytest -q` in the existing backend virtual environment reported **68 passed in 7.62 s**. Uvicorn started successfully; `GET /pitch-lab` returned HTTP 200, and `POST /compare` returned HTTP 200. A `GET /favicon.ico` request returned expected HTTP 404 because there is no favicon. The attached screenshot shows both estimator traces, green stable pitch cores, red review span, audio player and summary statistics. The supplied JSON confirms comparison values and note/event summary. The screenshot does not independently verify click-to-seek playback synchronization.

**User-verified UI behavior:** Clicking the red review region around 8.9 seconds seeks the browser audio player there. **New Windows synthetic calibration evidence from user-supplied JSON:** both estimators detected all 192 labeled pitch frames, missed zero, and correctly left all 34 labeled quiet frames unvoiced; 100% of detected labeled pitches within 50 cents; no scored octave errors; median absolute error YIN **1 cent**, RMVPE **2 cents**. The full 7.55-second comparison had 378 frames and 2-cent median *inter-model* disagreement, zero disagreement spans, runtimes YIN **2.317 s**, RMVPE **4.719 s** for that run. **Follow-up Windows results (user report, 2026-11-23):** After commit `99de79b6`, pytest reported **84 passed in 6.99 s**. The repeated calibration printed unchanged held-note/rest scores: YIN median 1 cent, RMVPE 2 cents; both 192/192 labeled voiced frames and 34/34 annotated quiet frames correctly handled, zero octave errors. Uploaded `ai-singer-pitch-report (1).json`, `known-pitch-comparison(1).json`, and `known-pitch-scores(1).json` confirm four correctly labeled stable cores **A3, C4, D4, A3** in both outputs, plus glide candidates at 3.40–4.16 s (YIN) and 3.40–4.18 s (RMVPE). Both reports have 378 frames, 2-cent median inter-model disagreement and no octave-like disagreement or review spans. Recorded runtimes vary between reports; don't infer consistent estimator speed from individual runs. Human-singing accuracy remains untested. **Still not verified:** actual human singing ground-truth accuracy, robust onset/transition labeling across varied performances, voice generation and live dialogue.

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

1. **Windows backend acceptance complete:** The new full suite reported **90 passed in 6.61 seconds**; Uvicorn started and both `GET /pitch-lab` and `POST /compare` returned HTTP 200 on the user's laptop. The uploaded Test 2 JSON matches the expected six voicing-disagreement intervals. **Remaining manual UI acceptance:** Click a new voicing-gap chip (particularly `6.16–6.36 s`) and confirm the audio seeks to that point; prior click-to-seek verification was for the original red pitch-review area, not the new chip control.
2. **Human singing ground truth, next main development milestone:** Independently annotate 2–3 consented vocal takes with performed stable-pitch/quiet windows and transitions. Separate target notes from actual performed pitches when measuring accuracy. A model's additional voiced frame may be sung sound, a breath or noise, not automatically a correction.
3. Score YIN and RMVPE pitch and voicing against independently annotated evidence, and examine transitions and note boundaries as separate tasks. Use any measurable errors to drive algorithm regressions instead of increasing model agreement for its own sake.
4. After sufficient accuracy on human singing, prototype a small permissioned singing voice-conversion output; later add interactive Director/Collaborative musical feedback.

## 13. Latest Development Session

**Date:** 2026-11-23. **Starting GitHub main head:** `dbf1ada7` (corrected dynamic accessible-label test).

**New verified Windows acceptance:** The user reran `pytest -q` and reported **90 passed in 6.61 seconds**. Uvicorn started at `http://127.0.0.1:8000`; `GET /pitch-lab` and `POST /compare` returned **HTTP 200**. `GET /favicon.ico` returned **404**, a harmless missing icon, not an API failure. The previous single false-negative HTML assertion is resolved in the Windows suite.

**Fresh user-uploaded artifacts inspected:** `image(20261124-042922).png` and `ai-singer-pitch-report (4).json`. The report contains Test 2's **12.48-second duration**, **625 pitch frames**, model runtimes YIN **2.808 s** and RMVPE **5.247 s** on this run (timings vary between runs). **YIN voiced 363, RMVPE voiced 385, overlapping 362; median overlapping pitch disagreement 4 cents, no red pitch-disagreement spans or octave-like disagreements; four stable pitch regions per model.** Crucially, the new exported `agreement.voicing_disagreement_intervals` exists with exactly **six intervals**, totaling **23 RMVPE-only frames and 1 YIN-only**: RMVPE only 0.74–0.78 s (2), 4.90–4.98 s (4), 6.16–6.36 s (10), 9.26–9.38 s (6), 9.40–9.42 s (1), and YIN only 4.82–4.84 s (1). This confirms the actual Windows app has the new response schema and intended comparison data.

**Evidence boundaries:** The screenshot and successful browser GET demonstrate the Pitch Lab page is accessible; the screenshot/export corroborate presentation and model comparison. The user has **not yet explicitly confirmed clicking the new voicing timestamp chip seeks the original recording**, so do not mark that specific interaction user-verified. Neither model's voiced prediction is a verified label for the real singer; reference note/onset annotations are still missing.

**Changes this session:** Documentation-only update to `PROJECT_CONTEXT.md` to record the final Windows acceptance and future priorities. No model, backend, UI or test-code changes are required based on the provided results. User audio/JSON/image remain out of Git.

**Next exact task:** Ask for a quick manual click test on the new `6.16–6.36 s` chip, then proceed to independently annotated human singing performance tests before changing estimators or starting singing synthesis.
