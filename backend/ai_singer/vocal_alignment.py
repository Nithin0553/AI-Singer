"""Conservative, silence-aware musical alignment; never edits or approves audio."""
from __future__ import annotations

import numpy as np

POINTS = 101
BAND = 15
GAP_COST = 1.6
MIN_VOICED = 12


def _features(analysis):
    frames = analysis["pitch_track"]
    duration = float(analysis["duration_seconds"])
    times = np.array([f["time_seconds"] for f in frames], dtype=float)
    midi = np.array([np.nan if f["midi_note"] is None else f["midi_note"]
                     for f in frames], dtype=float)
    rms = np.array([f["rms"] for f in frames], dtype=float)
    if not len(times):
        raise ValueError("Empty pitch track.")
    voiced = np.isfinite(midi)
    threshold = max(.002, float(rms.max()) * .06)
    quiet = (~voiced) & (rms < threshold)
    # Bridge at most two low-energy unvoiced frames between quiet frames.
    # Preserve voiced and higher-energy unvoiced material.
    for i in range(1, len(quiet) - 1):
        if quiet[i - 1] and not voiced[i]:
            for gap in (1, 2):
                if (i + gap < len(quiet) and quiet[i + gap]
                        and not voiced[i:i + gap].any()
                        and (rms[i:i + gap] < 2 * threshold).all()):
                    quiet[i:i + gap] = True
                    break
    active = np.flatnonzero(~quiet)
    if not len(active) or not voiced.any():
        return None
    lo, hi = int(active[0]), int(active[-1])
    idx = np.rint(np.linspace(lo, hi, POINTS)).astype(int)
    pitch = midi[idx]
    mask = np.isfinite(pitch)
    center = float(np.median(pitch[mask])) if mask.any() else None
    if center is None:
        return None
    active_end = min(duration, float(times[hi + 1])) if hi + 1 < len(times) else duration
    return {
        "times": times[idx], "pitch": pitch, "relative": pitch - center,
        "voiced": mask, "center": center,
        "leading_quiet_seconds": round(float(times[lo]), 3),
        "trailing_quiet_seconds": round(max(0., duration - active_end), 3),
        "active_duration_seconds": round(active_end - float(times[lo]), 3),
    }


def _match_cost(a, b, i, j):
    av, bv = a["voiced"][i], b["voiced"][j]
    if av and bv:
        difference = min(8., abs(a["relative"][i] - b["relative"][j]))
    elif av != bv:
        difference = 3.2
    else:
        difference = .1
    return difference + .035 * abs(i - j)


def _align(a, b):
    """Banded monotone edit-DTW: diagonal matches, explicit unmatched points.

    Unlike unconstrained DTW, a point cannot be reused to conceal changed notes.
    """
    n = POINTS
    cost = np.full((n + 1, n + 1), np.inf)
    back = np.zeros((n + 1, n + 1), dtype=np.int8)
    cost[0, 0] = 0
    for i in range(n + 1):
        for j in range(max(0, i - BAND), min(n, i + BAND) + 1):
            if i == j == 0:
                continue
            options = []
            if i and j:
                options.append((cost[i - 1, j - 1] + _match_cost(a, b, i - 1, j - 1), 1))
            if i:
                options.append((cost[i - 1, j] + GAP_COST, 2))
            if j:
                options.append((cost[i, j - 1] + GAP_COST, 3))
            cost[i, j], back[i, j] = min(options)
    i = j = n
    path = []
    while i or j:
        step = back[i, j]
        if step == 1:
            i -= 1
            j -= 1
            path.append((i, j))
        elif step == 2:
            i -= 1
            path.append((i, None))
        elif step == 3:
            j -= 1
            path.append((None, j))
        else:
            raise RuntimeError("Alignment path unavailable.")
    return list(reversed(path))


def _number(value):
    return round(float(value), 3) if np.isfinite(value) else None


def _point(features, index):
    if index is None:
        return None
    return {
        "time_seconds": _number(features["times"][index]),
        "absolute_midi": _number(features["pitch"][index]),
        "relative_midi": _number(features["relative"][index]),
    }


def _review_regions(rows, reliable):
    """Review sustained relative discrepancies, not register offsets or edit commands."""
    if not reliable:
        return []
    groups = []
    current = []
    sign = 0
    for row in rows + [{"relative_difference_semitones": None}]:
        delta = row["relative_difference_semitones"]
        direction = 0 if delta is None or abs(delta) < .75 else (1 if delta > 0 else -1)
        if direction != sign or direction == 0:
            if len(current) >= 3:
                groups.append(current)
            current = []
        if direction:
            current.append(row)
        sign = direction
    out = []
    for group in groups:
        start = group[0]["target"]["time_seconds"]
        end = group[-1]["target"]["time_seconds"]
        if end - start < .12:
            continue
        values = np.array([r["relative_difference_semitones"] for r in group])
        median = float(np.median(values))
        spread = float(np.percentile(values, 90) - np.percentile(values, 10))
        bounded = .35 <= end - start <= 8 and .75 <= abs(median) <= 3 and spread <= .5
        out.append({
            "target_start_seconds": start, "target_end_seconds": end,
            "demo_start_seconds": group[0]["demo"]["time_seconds"],
            "demo_end_seconds": group[-1]["demo"]["time_seconds"],
            "median_relative_difference_semitones": round(median, 2),
            "action": "review_possible_fixed_pitch_shift" if bounded else "review_melodic_contour",
            "executable": False,
        })
    return out[:20]


def align_performances(target, demo):
    """Return timestamped evidence, uncertainty and human-review-only proposals."""
    a, b = _features(target), _features(demo)
    warnings = [
        "Alignment is a bounded heuristic, not verified note or lyric correspondence.",
        "Register offset is descriptive and never an automatic transpose instruction.",
        "No proposed operation is executable; listen before deciding on any edit.",
    ]
    result = {
        "method": "silence_aware_banded_edit_dtw_v1",
        "status": "insufficient_evidence", "points_per_phrase": POINTS,
        "band_points": BAND, "warnings": warnings, "path": [],
        "review_regions": [], "timing_review": [], "metrics": None,
        "target_edges": None, "demo_edges": None,
    }
    for name, features in (("target_edges", a), ("demo_edges", b)):
        if features is not None:
            result[name] = {k: features[k] for k in (
                "leading_quiet_seconds", "trailing_quiet_seconds", "active_duration_seconds")}
    if (a is None or b is None or min(a["voiced"].sum(), b["voiced"].sum()) < MIN_VOICED
            or min(a["active_duration_seconds"], b["active_duration_seconds"]) < .3):
        warnings.append("Not enough voiced phrase evidence for local alignment.")
        return result

    path = _align(a, b)
    rows, residuals = [], []
    for i, j in path:
        left, right = _point(a, i), _point(b, j)
        delta = None
        if i is not None and j is not None and a["voiced"][i] and b["voiced"][j]:
            delta = _number(b["relative"][j] - a["relative"][i])
            residuals.append(abs(delta))
        rows.append({"target": left, "demo": right, "relative_difference_semitones": delta})
    common = a["voiced"] & b["voiced"]
    baseline = np.abs(a["relative"][common] - b["relative"][common])
    gaps = sum(i is None or j is None for i, j in path)
    mismatch = sum(bool(i is not None and j is not None and a["voiced"][i] != b["voiced"][j])
                   for i, j in path)
    matched = len(residuals)
    coverage = min(matched / int(a["voiced"].sum()), matched / int(b["voiced"].sum()))
    median = float(np.median(residuals)) if residuals else None
    p90 = float(np.percentile(residuals, 90)) if residuals else None
    octave = bool(target.get("octave_jump_candidates") or demo.get("octave_jump_candidates"))
    reliable = (coverage >= .75 and gaps / len(path) <= .25 and mismatch / len(path) <= .12
                and median is not None and median <= 1.0 and p90 <= 2.5 and not octave)
    result.update(
        status="reviewable_alignment" if reliable else "uncertain_alignment",
        path=rows,
        metrics={
            "register_difference_semitones": round(b["center"] - a["center"], 2),
            "edge_trimmed_uniform_median_cents": round(float(np.median(baseline)) * 100, 1) if len(baseline) else None,
            "aligned_median_difference_cents": round(median * 100, 1) if median is not None else None,
            "aligned_p90_difference_cents": round(p90 * 100, 1) if p90 is not None else None,
            "matched_voiced_points": matched,
            "minimum_voiced_coverage": round(coverage, 3),
            "unmatched_target_points": sum(j is None for i, j in path),
            "unmatched_demo_points": sum(i is None for i, j in path),
            "voicing_mismatch_matches": mismatch,
            "path_points": len(path),
        },
        review_regions=_review_regions(rows, reliable),
    )
    timing = []
    if abs(a["leading_quiet_seconds"] - b["leading_quiet_seconds"]) >= .12:
        timing.append({"action": "review_leading_quiet", "executable": False,
                       "target_seconds": a["leading_quiet_seconds"],
                       "demo_seconds": b["leading_quiet_seconds"]})
    if abs(a["trailing_quiet_seconds"] - b["trailing_quiet_seconds"]) >= .12:
        timing.append({"action": "review_trailing_quiet", "executable": False,
                       "target_seconds": a["trailing_quiet_seconds"],
                       "demo_seconds": b["trailing_quiet_seconds"]})
    if abs(a["active_duration_seconds"] - b["active_duration_seconds"]) >= .15:
        timing.append({"action": "review_phrase_duration", "executable": False,
                       "target_seconds": a["active_duration_seconds"],
                       "demo_seconds": b["active_duration_seconds"]})
    # Keep unmatched ranges visible, even when the overall alignment is uncertain.
    pending = []
    def flush():
        if len(pending) < 3:
            return
        spans = {}
        for side in ("target", "demo"):
            points = [row[side]["time_seconds"] for row in pending if row[side] is not None]
            spans[side + "_seconds"] = [points[0], points[-1]] if points else None
        timing.append({"action": "review_unmatched_or_voicing_region", "executable": False,
                       **spans})
    for row in rows:
        left, right = row["target"], row["demo"]
        if left is None or right is None or ((left["absolute_midi"] is None) !=
                                            (right["absolute_midi"] is None)):
            pending.append(row)
        else:
            flush()
            pending = []
    flush()
    result["timing_review"] = timing[:24]
    if octave:
        warnings.append("Octave-review candidates suppress correction proposals.")
    if not reliable:
        warnings.append("Correspondence is uncertain; no local pitch proposal is justified.")
    if gaps or mismatch:
        warnings.append("Unmatched or voicing-different points may indicate timing, rests or changed melody; review by listening.")
    return result
