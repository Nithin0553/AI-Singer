# AI Singer — Project Context

> **Persistent handoff:** Read this file at the beginning of each development session. Then inspect current source files and recent Git commits; this document is not a substitute for verification.
>
> **Last reviewed:** 2026-11-23 | **Repo:** [Nithin0553/AI-Singer](https://github.com/Nithin0553/AI-Singer) | **Status:** Optional RMVPE ONNX integration and YIN comparison CLI implemented; first genuine RMVPE/YIN Windows benchmark completed, musical accuracy against ground truth still unverified.
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

**User-verified Windows:** Seagate `Dimpu` setup, FFmpeg/ffprobe 9.1 and YIN `POST /analyze` HTTP 200 for the 9.195-second recording. The user ran the new YIN/RMVPE benchmark against this recording and provided its full JSON report: **YIN 11.342 s, RMVPE 2.102 s, 460 frames, 388 jointly voiced frames, 11 cents median absolute pitch disagreement**, and 3 adjacent frames of octave-like disagreement near 8.90–8.94 s. This establishes functioning real ONNX model inference on Windows; it does not establish ground-truth correctness or licensing compliance. Windows full pytest after the short-ID fix has not yet been reported.

**Still not verified:** Full Windows pytest result after short-ID fix, checkpoint SHA-256 as independently displayed, source/model licensing, repeat-run latency and correctness against annotated pitch or the actual sung audio. The singing agent, frontend, voice models and training remain unimplemented.

## 7. Technical Decisions

- Keep YIN as default; RMVPE must be explicitly chosen via API parameter or local benchmark CLI.
- Use CPU ONNX first on a 4 GiB VRAM laptop; do not install PyTorch/CUDA as a prerequisite for the benchmark.
- Require an existing, SHA-256 verified canonical `rmvpe.onnx` at the Seagate storage root; allow an explicit absolute override. Never auto-download checkpoints or store large assets in Git.
- Match the model's ~10 ms output to the existing 20 ms timeline to compare both estimators consistently.
- Never call **inter-model agreement** accuracy: require annotated reference clips to measure actual pitch error.
- Keep the architecture modest and separate singing generation, musical directions and model inference authority.

## 8. Known Issues

- **Real RMVPE inference now confirmed by user-run benchmark on Windows.** Single-run runtime YIN 11.342 s vs RMVPE 2.102 s (~5.40x in this run), but first-use warm-up/caching and repeated-run latency have not been characterized. This result is not a general performance guarantee.
- The canonical weight SHA-256 is `5370e71ac80af8b4b7c793d27efd51fd8bf962de3a7ede0766dac0befa3660fd` (per third-party package). Review license and rights for commercial use before relying on this checkpoint.
- Thresholds (0.03 model confidence, 80–900 Hz) and 20 ms time-grid downsampling are provisional. **YIN detected 36 candidate note segments, RMVPE 43** on the same recording; both may oversegment vocal glides and ornaments. Around **8.90–8.94 s**, YIN dips near MIDI 44 and RMVPE stays near MIDI 56, a roughly one-octave difference over 3 consecutive 20 ms frames (a single short event). RMVPE is more continuous there, but which estimate matches the singer remains unverified without the original audio.
- Windows pytest previously failed because huge parameter IDs exceeded `PYTEST_CURRENT_TEST` variable limit; shortened test IDs committed, but full Windows acceptance result not yet provided.
- The full user-provided YIN/RMVPE JSON confirms real Windows pitch estimates; **388 overlapping voiced frames**, **11-cent median absolute disagreement**, and **355 of 388 overlapping frames (91.5%) within 50 cents**. The original audio bytes have not been supplied, so perceived quality, note onsets and ground-truth pitch remain unknown. Small inter-model disagreement is not proof of accuracy.
- Seagate is exFAT and may cause symlink/cache challenges. CPU inference elapsed time was recorded for one run but memory use and repeatability are unmeasured. One nonfatal Starlette TestClient warning was previously reported.

## 9. Testing and Verification

**Isolated Linux Python 3.13 (not the user's Windows):** **41 tests passed**, comprising 29 prior tests and 12 new RMVPE/benchmark tests, with `python -m compileall -q ai_singer tests` and local editable install (without downloading new dependencies) successful. Tests cover model root/missing file/absolute override, no automatic download, alignment/voicing, invalid prediction timeline, SHA mismatch, mocked API RMVPE selection, mocked benchmark, comparison frames/median error and existing WAV/M4A behavior. The ONNX model and package **were not installed or loaded**, so real model inference is pending.

**User Windows verified previously:** FFmpeg/ffprobe 9.1, external `Dimpu` drive configuration and successful YIN `POST /analyze` HTTP 200 with a 9.195 s real recording (460 frames). User has not supplied a subsequent full Windows pytest result after short-ID fix.

**New Windows acceptance evidence (user-provided full JSON):** Real YIN/RMVPE comparison completed and report saved under `D:\AI_Singer\outputs\previews\yin-rmvpe-comparison.json`; duration 9.195 seconds, sample rate 16 kHz, hop 20 ms, 460 frames. Runtimes: YIN 11.342 s, RMVPE 2.102 s. Voiced frames: YIN 390, RMVPE 393, both 388. Median absolute disagreement: 11 cents. 3 consecutive octave-like disagreement frames near 8.90–8.94 s (~-1187 to -1199 cents YIN minus RMVPE). Note event counts: YIN 36, RMVPE 43. 355/388 jointly voiced frames (91.5%) differ by <=50 cents. The uploaded report was analyzed; this is still **not accuracy against known reference notes**, and exact checkpoint hash was not independently provided.

**Not tested/reported:** Windows post-fix full pytest output, repeat-run model inference time, source model rights, ground-truth pitch accuracy, singing output and multilingual agent.

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

1. **Ground-truth musical validation:** Use a few permissioned recordings of controlled, known notes and short slides. Mark the reference pitches and approximate note transitions; calculate YIN and RMVPE pitch error, voicing precision and note-boundary error. Do not accept RMVPE as the production default solely on agreement or one benchmark.
2. **Diagnose the 8.90–8.94 s passage:** Compare the original waveform/audio by listening and inspect whether YIN's brief octave-down jump is a tracking error. RMVPE appears more continuous in JSON but remains a hypothesis until independently verified.
3. **Improve pitch visualization and note segmentation:** Add native plots/diagnostics to the application and separate continuous vibrato/glissando from distinct sung notes. Existing 36 YIN vs 43 RMVPE candidate segments do not establish real note counts.
4. **Run repeatable Windows acceptance:** Report the full pytest result (expected 41 tests); optionally repeat the same benchmark several times to distinguish warm-up from steady-state CPU inference and record model checkpoint SHA if needed. Reuse the existing file on the Seagate; no additional weight downloads.
5. After validating musical accuracy, select the appropriate estimator and proceed to authorized male/female voice conversion and later intelligent Director/Collaborative modes.

## 13. Latest Development Session

**Date:** 2026-11-23. **Starting GitHub head:** `acb102e` on `main`.

**Windows benchmark completed:** User ran `.\.venv\Scripts\python -m ai_singer.pitch_benchmark "$clip" --output "$report"` from their backend virtual environment. Program saved the report to `D:\AI_Singer\outputs\previews\yin-rmvpe-comparison.json`. The user uploaded the full JSON report to ChatGPT.

**Measured on 9.195 s recording:** YIN 11.342 s, RMVPE 2.102 s (~5.40x faster this run); 460 pitch frames; 390 YIN voiced, 393 RMVPE voiced, 388 both voiced; median absolute model disagreement 11 cents; 355 of 388 shared-voiced frames (91.5%) within 50 cents. Candidate note events YIN 36, RMVPE 43. Three consecutive frames near 8.90–8.94 seconds differed by roughly an octave: YIN's low excursion near MIDI 44 vs RMVPE near MIDI 56. The latter seems more continuous, but the true pitch cannot be established without listening to the original audio.

**What this verifies:** Third-party ONNX model loading and actual RMVPE inference worked in the user's Windows environment; both estimators ran on the same decoded clip and returned aligned predictions; output was written to the configured external HDD. **What this does not verify:** Ground-truth singing accuracy, acceptable note segmentation, repeatable latency, full Windows pytest run (41 tests expected), checkpoint hash manually shown, or model licensing.

**Artifacts:** A single comparative pitch-contour PNG was generated in the conversation workspace from the user's report. Neither raw user recording, model weights, nor benchmark JSON were committed to GitHub; keep large/sensitive assets off Git.

**Repository change this session:** Updated this document with measured user-reported performance, diagnostics and precise next priorities. No application source code modified. See Git history for commit.

**Next task:** Ground-truth pitch/note validation and visualization/segmentation improvement, including specific inspection of the YIN octave-like excursion, before choosing RMVPE as the production default.
