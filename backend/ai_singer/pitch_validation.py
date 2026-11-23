"""Score pitch tracks against independently annotated reference intervals."""

import argparse
import json
from pathlib import Path

import numpy as np


def validate_reference(reference: dict, duration: float) -> list[dict]:
    intervals = reference.get("segments")
    if not isinstance(intervals, list) or not intervals:
        raise ValueError("Reference must contain a nonempty 'segments' list.")
    previous_end = 0.0
    for segment in intervals:
        if not isinstance(segment, dict) or "midi_note" not in segment:
            raise ValueError("Every segment needs start_seconds, end_seconds, and midi_note (or null).")
        start, end, note = segment.get("start_seconds"), segment.get("end_seconds"), segment["midi_note"]
        if (not isinstance(start, (int, float)) or isinstance(start, bool) or
            not isinstance(end, (int, float)) or isinstance(end, bool) or
            not np.isfinite(start) or not np.isfinite(end) or
            start < previous_end - 1e-8 or start < 0 or end <= start or end > duration + 1e-6):
            raise ValueError("Reference intervals must be ordered, nonoverlapping and within the recording.")
        if note is not None and (not isinstance(note, (int, float)) or isinstance(note, bool)
                                 or not np.isfinite(note) or not 0 <= note <= 127):
            raise ValueError("midi_note must be 0–127 or null for an annotated unvoiced interval.")
        previous_end = end
    return intervals


def score_pitch(result: dict, reference: dict) -> dict:
    """Only labeled time is scored; 100 cents equals one semitone."""
    intervals = validate_reference(reference, float(result["duration_seconds"]))
    frames = result["pitch_track"]
    times = np.array([f["time_seconds"] for f in frames], dtype=float)
    predictions = np.array([np.nan if f["midi_note"] is None else f["midi_note"] for f in frames], dtype=float)
    reference_pitch = np.full(times.shape, np.nan)
    known_pitch = np.zeros(times.shape, dtype=bool)
    known_quiet = np.zeros(times.shape, dtype=bool)
    for segment in intervals:
        assigned = (times >= segment["start_seconds"] - 1e-9) & (times < segment["end_seconds"] - 1e-9)
        if segment["midi_note"] is None:
            known_quiet |= assigned
        else:
            known_pitch |= assigned
            reference_pitch[assigned] = segment["midi_note"]
    both = known_pitch & np.isfinite(predictions)
    errors = np.abs(predictions[both] - reference_pitch[both]) * 100
    return {
        "estimator": result.get("estimator", "unknown"),
        "labeled_pitch_frames": int(np.count_nonzero(known_pitch)),
        "labeled_quiet_frames": int(np.count_nonzero(known_quiet)),
        "pitch_frames_detected": int(np.count_nonzero(both)),
        "missed_voiced_frames": int(np.count_nonzero(known_pitch & ~np.isfinite(predictions))),
        "voiced_on_annotated_quiet_frames": int(np.count_nonzero(known_quiet & np.isfinite(predictions))),
        "median_absolute_pitch_error_cents": round(float(np.median(errors)), 2) if len(errors) else None,
        "within_50_cents_fraction": round(float(np.mean(errors <= 50)), 4) if len(errors) else None,
        "octave_error_frames": int(np.count_nonzero((errors >= 1050) & (errors <= 1350))),
        "note": "Unannotated frames excluded. Accuracy depends on reference quality.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("benchmark_json", type=Path)
    parser.add_argument("reference_json", type=Path)
    args = parser.parse_args()
    try:
        benchmark = json.loads(args.benchmark_json.read_text(encoding="utf-8"))
        reference = json.loads(args.reference_json.read_text(encoding="utf-8"))
        scored = {key: score_pitch(benchmark[key], reference)
                  for key in ("yin", "rmvpe") if key in benchmark}
        if not scored:
            raise ValueError("No YIN/RMVPE pitch track in benchmark report.")
    except (OSError, ValueError, TypeError, KeyError) as exc:
        parser.exit(1, f"Cannot validate: {exc}\n")
    print(json.dumps(scored, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
