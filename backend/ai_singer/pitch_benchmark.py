"""Compare YIN and optional RMVPE on the same completed vocal recording."""

import argparse
import json
from pathlib import Path
from time import perf_counter

import numpy as np

from ai_singer.audio_analysis import MAX_UPLOAD_BYTES, AudioInputError, analyze_audio, decode_audio
from ai_singer.rmvpe_pitch import RMVPEUnavailable


def compare_results(yin: dict, rmvpe: dict) -> dict:
    """Report agreement, not accuracy; neither estimator is ground truth."""
    y_frames, r_frames = yin["pitch_track"], rmvpe["pitch_track"]
    if len(y_frames) != len(r_frames):
        raise ValueError("Pitch-track timelines must be aligned before comparison.")
    if any(abs(y["time_seconds"] - r["time_seconds"]) > 0.001 for y, r in zip(y_frames, r_frames)):
        raise ValueError("Pitch-track timestamps do not match.")
    y = np.asarray([f["midi_note"] if f["midi_note"] is not None else np.nan for f in y_frames])
    r = np.asarray([f["midi_note"] if f["midi_note"] is not None else np.nan for f in r_frames])
    both = np.isfinite(y) & np.isfinite(r)
    distance_cents = np.abs(y[both] - r[both]) * 100
    return {
        "frame_count": len(y),
        "yin_voiced_frames": int(np.count_nonzero(np.isfinite(y))),
        "rmvpe_voiced_frames": int(np.count_nonzero(np.isfinite(r))),
        "overlapping_voiced_frames": int(np.count_nonzero(both)),
        "median_absolute_disagreement_cents": round(float(np.median(distance_cents)), 2)
        if len(distance_cents) else None,
        "octave_like_disagreement_frames": int(np.count_nonzero(
            (distance_cents >= 1050) & (distance_cents <= 1350)
        )),
        "interpretation": "These numbers compare two estimators, not either estimator against ground truth.",
    }


def benchmark_audio(data: bytes) -> dict:
    samples = decode_audio(data)
    begin = perf_counter()
    yin = analyze_audio(samples, estimator="yin")
    yin_seconds = perf_counter() - begin
    begin = perf_counter()
    rmvpe = analyze_audio(samples, estimator="rmvpe")
    rmvpe_seconds = perf_counter() - begin
    return {
        "duration_seconds": yin["duration_seconds"],
        "runtime_seconds": {"yin": round(yin_seconds, 3), "rmvpe": round(rmvpe_seconds, 3)},
        "agreement": compare_results(yin, rmvpe),
        "yin": yin,
        "rmvpe": rmvpe,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("audio_file", type=Path, help="1–15-second audio file, max 10 MiB")
    parser.add_argument("--output", type=Path, help="Optional path to save the comparison JSON")
    args = parser.parse_args()
    try:
        if args.audio_file.stat().st_size > MAX_UPLOAD_BYTES:
            raise AudioInputError("Recording exceeds the 10 MB upload limit.")
        result = benchmark_audio(args.audio_file.read_bytes())
    except (OSError, AudioInputError, RMVPEUnavailable) as error:
        parser.exit(1, f"Cannot benchmark: {error}\n")

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        print(f"Wrote full comparison to {args.output}")
    print(json.dumps({k: result[k] for k in ("duration_seconds", "runtime_seconds", "agreement")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
