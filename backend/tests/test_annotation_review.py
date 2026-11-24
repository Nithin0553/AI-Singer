"""Manual performance annotations are reviewed, not presumed to be ground truth."""
import pytest
from fastapi.testclient import TestClient
from ai_singer.annotation_review import score_annotations, validate_annotations
from ai_singer.main import app


def analysis():
    def track(estimator, mids):
        return {"estimator": estimator, "duration_seconds": .20,
                "pitch_track": [{"time_seconds": round(i*.02, 3), "midi_note": note}
                                for i, note in enumerate(mids)]}
    return {"duration_seconds": .20,
            "yin": track("yin", [57, 57, 57, None, None, None, 59, 59.5, 60, 60.5]),
            "rmvpe": track("rmvpe", [57, 57, 57, None, None, None, 59, 59.5, 60, 60.5])}


def reference():
    return {"segments": [
        {"start_seconds": 0, "end_seconds": .06, "midi_note": 57},
        {"start_seconds": .06, "end_seconds": .12, "midi_note": None}
    ], "glides": [{"start_seconds": .12, "end_seconds": .20, "direction": "up"}]}


def test_score_manual_notes_and_rests_separately_from_glides():
    result = score_annotations(analysis(), reference())
    assert result["annotation_source"] == "manual_unverified"
    for key in ("yin", "rmvpe"):
        score = result["scores"][key]
        assert score["labeled_pitch_frames"] == 3
        assert score["labeled_quiet_frames"] == 3
        assert score["median_absolute_pitch_error_cents"] == 0
        assert score["voiced_on_annotated_quiet_frames"] == 0
        assert score["glide_reviews"][0]["observed_direction"] == "up"
        assert score["glide_reviews"][0]["direction_agrees"] is True


def test_wrong_manual_direction_is_review_disagreement_only():
    ref = reference()
    ref["glides"][0]["direction"] = "down"
    score = score_annotations(analysis(), ref)["scores"]["yin"]
    assert score["glide_reviews"][0]["direction_agrees"] is False
    assert score["median_absolute_pitch_error_cents"] == 0


def test_unknown_glide_direction_does_not_claim_accuracy():
    ref = reference()
    ref["glides"][0]["direction"] = "unknown"
    assert score_annotations(analysis(), ref)["scores"]["yin"]["glide_reviews"][0]["direction_agrees"] is None


@pytest.mark.parametrize("glides", [
    [{"start_seconds": .04, "end_seconds": .13, "direction": "up"}],
    [{"start_seconds": -.01, "end_seconds": .20, "direction": "up"}],
    [{"start_seconds": .12, "end_seconds": .21, "direction": "up"}],
    [{"start_seconds": .12, "end_seconds": .20, "direction": "diagonal"}],
    [{"start_seconds": float("nan"), "end_seconds": .20, "direction": "up"}],
    [{"start_seconds": .12, "end_seconds": .20, "direction": "up"},
     {"start_seconds": .15, "end_seconds": .18, "direction": "down"}],
], ids=["overlap-held","negative-start","past-end","bad-direction","nan","overlap-glides"])
def test_invalid_glides_are_rejected(glides):
    ref = reference()
    ref["glides"] = glides
    with pytest.raises(ValueError):
        validate_annotations(ref, .20)


def test_missing_analysis_and_mismatched_duration_are_rejected():
    with pytest.raises(ValueError):
        score_annotations({}, reference())
    x = analysis()
    x["yin"]["duration_seconds"] = .5
    with pytest.raises(ValueError, match="duration"):
        score_annotations(x, reference())


def test_one_estimator_supported_without_neural_weights():
    result = score_annotations(analysis()["yin"], reference())
    assert set(result["scores"]) == {"yin"}


def test_scoring_endpoint_accepts_manual_reference():
    response = TestClient(app).post("/score-reference", json={"analysis": analysis(), "reference": reference()})
    assert response.status_code == 200, response.text
    assert response.json()["scores"]["rmvpe"]["glide_reviews"][0]["direction_agrees"] is True


def test_scoring_endpoint_rejects_invalid_reference():
    ref = reference()
    ref["glides"][0]["direction"] = "diagonal"
    response = TestClient(app).post("/score-reference", json={"analysis": analysis(), "reference": ref})
    assert response.status_code == 422
    assert TestClient(app).post("/score-reference", json={"analysis": {}, "reference": reference()}).status_code == 422


def test_pitch_lab_exposes_manually_edited_reference_and_score_controls():
    html = TestClient(app).get("/pitch-lab")
    assert html.status_code == 200
    for field in ('id="annotationPanel"', 'id="annStartNow"', 'id="annEndNow"',
                  'id="annMidi"', 'id="annDirection"', 'id="annImport"',
                  'id="annExport"', 'id="annScore"', 'id="annList"',
                  'id="voicingLinks"'):
        assert field in html.text
    for phrase in ('"/score-reference"', 'annotationReference()', 'validLabels(',
                   'manualLabels.forEach(', 'annScore.addEventListener("click"',
                   'annImport.addEventListener("change"'):
        assert phrase in html.text
    assert "Do not copy YIN/RMVPE predictions as ground truth." in html.text
    assert 'src="http' not in html.text
