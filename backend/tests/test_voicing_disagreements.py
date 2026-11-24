"""Separate voiced/unvoiced comparison from actual pitch disagreement."""

import numpy as np
import pytest
from fastapi.testclient import TestClient

from ai_singer.main import app
from ai_singer.pitch_benchmark import compare_results


def report(notes, step=0.02):
    return {"pitch_track": [
        {"time_seconds": round(index * step, 3), "midi_note": note}
        for index, note in enumerate(notes)
    ]}


def test_voicing_disagreement_spans_preserve_pitch_agreement():
    yin = [57, 57, None, None, 57, 57, 57, None, 57]
    rmvpe = [57, 57, 57, 57, 57, None, 57, None, 57]
    original = list(yin)
    result = compare_results(report(yin), report(rmvpe))
    assert result["disagreement_intervals"] == []
    assert result["median_absolute_disagreement_cents"] == 0
    assert result["yin_only_voiced_frames"] == 1
    assert result["rmvpe_only_voiced_frames"] == 2
    assert result["voicing_disagreement_intervals"] == [
        {"start_seconds": .04, "end_seconds": .08, "frame_count": 2,
         "voiced_by": "rmvpe", "classification": "voicing_disagreement", "status": "needs_review"},
        {"start_seconds": .10, "end_seconds": .12, "frame_count": 1,
         "voiced_by": "yin", "classification": "voicing_disagreement", "status": "needs_review"},
    ]
    assert yin == original


def test_pitch_octave_disagreement_remains_separate():
    yin = [57, 45, 45, 45, 57, None, 57]
    rmvpe = [57, 57, 57, 57, 57, 57, 57]
    result = compare_results(report(yin), report(rmvpe))
    assert result["disagreement_intervals"][0]["classification"] == "octave_like"
    assert result["octave_like_disagreement_frames"] == 3
    assert result["voicing_disagreement_intervals"][0]["start_seconds"] == .10
    assert result["voicing_disagreement_intervals"][0]["frame_count"] == 1


def test_both_unvoiced_and_nonstandard_frame_hop():
    result = compare_results(report([None, None, None]), report([None, None, None]))
    assert result["voicing_disagreement_intervals"] == []
    assert result["yin_only_voiced_frames"] == result["rmvpe_only_voiced_frames"] == 0
    result = compare_results(report([None, None], step=.01), report([57, 57], step=.01))
    assert result["voicing_disagreement_intervals"][0]["end_seconds"] == pytest.approx(.02)


def test_unaligned_timelines_still_rejected():
    with pytest.raises(ValueError, match="timestamps"):
        compare_results(report([57, None]), report([57, None], step=.03))


def test_human_like_transition_gaps_without_recording_data():
    yin = np.full(625, 57.0).tolist()
    rmvpe = yin.copy()
    for start, stop in ((37,39), (245,249), (308,318), (463,469), (470,471)):
        yin[start:stop] = [None] * (stop - start)
    rmvpe[241] = None
    result = compare_results(report(yin), report(rmvpe))
    assert result["rmvpe_only_voiced_frames"] == 23
    assert result["yin_only_voiced_frames"] == 1
    assert result["disagreement_intervals"] == []
    assert len(result["voicing_disagreement_intervals"]) == 6
    assert any(s["voiced_by"] == "rmvpe" and s["start_seconds"] == 6.16
               and s["end_seconds"] == 6.36 for s in result["voicing_disagreement_intervals"])
    assert any(s["voiced_by"] == "rmvpe" and s["start_seconds"] == 9.26
               and s["end_seconds"] == 9.38 for s in result["voicing_disagreement_intervals"])


def test_pitch_lab_exposes_clickable_voicing_review():
    html = TestClient(app).get("/pitch-lab")
    assert html.status_code == 200
    assert 'id="voicingReview"' in html.text
    assert 'id="voicingLinks"' in html.text
    assert "voicing_disagreement_intervals" in html.text
    # The accessible label is assembled dynamically with the model name.
    # Validate its template and button interaction rather than literal
    # finished text that cannot appear in the static HTML source.
    assert 'button.setAttribute("aria-label"' in html.text
    assert '" seconds; only " + model + " reports pitch"' in html.text
    assert 'button.addEventListener("click"' in html.text
    assert 'src="http' not in html.text
