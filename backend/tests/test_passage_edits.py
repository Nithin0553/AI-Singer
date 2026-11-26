"""Deterministic, bounded audio editing with sample-exact untouched regions."""
from io import BytesIO
import wave

import numpy as np
import pytest

from ai_singer.passage_edits import PassageEditError, edit_passage


def tone(sr=16000, seconds=3.0, freq=220):
    t = np.arange(round(sr * seconds)) / sr
    samples = (np.sin(2 * np.pi * freq * t) * 0.2 * 32767).astype("<i2")
    output = BytesIO()
    with wave.open(output, "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(sr)
        f.writeframes(samples.tobytes())
    return output.getvalue(), samples


def pcm(data):
    with wave.open(BytesIO(data)) as f:
        return np.frombuffer(f.readframes(f.getnframes()), dtype="<i2"), f.getframerate()


@pytest.mark.parametrize("operation,value", [("gain", 5), ("gain", -6), ("pitch", 2)])
def test_changed_only_inside_requested_region(operation, value):
    raw, source = tone()
    edited, detail = edit_passage(
        raw, start_seconds=0.7, end_seconds=1.6,
        operation=operation, value=value
    )
    actual, rate = pcm(edited)
    assert len(actual) == len(source)
    assert rate == 16000
    assert np.array_equal(actual[:int(0.7 * rate)], source[:int(0.7 * rate)])
    assert np.array_equal(actual[int(1.6 * rate):], source[int(1.6 * rate):])
    assert np.any(actual[int(0.8 * rate):int(1.5 * rate)] !=
                  source[int(0.8 * rate):int(1.5 * rate)])
    assert detail["operation"] == operation
    assert detail["fade_ms"] == 45


def test_pitch_shift_is_musically_measurable():
    raw, _ = tone(sr=22050, freq=220)
    edited, _ = edit_passage(
        raw, start_seconds=.5, end_seconds=2.5, operation="pitch", value=2
    )
    actual, rate = pcm(edited)
    core = actual[int(1.1 * rate):int(1.9 * rate)] / 32768.0
    freqs = np.fft.rfftfreq(core.size, 1 / rate)
    peak = freqs[np.argmax(np.abs(np.fft.rfft(core)))]
    assert abs(peak - 220 * 2**(2/12)) < 5


@pytest.mark.parametrize("operation,value", [
    ("pitch", 0), ("pitch", 4), ("gain", 0), ("gain", 10), ("mute", 5),
])
def test_unsupported_parameters_rejected(operation, value):
    raw, _ = tone()
    with pytest.raises(PassageEditError):
        edit_passage(raw, start_seconds=.5, end_seconds=1.5,
                     operation=operation, value=value)


@pytest.mark.parametrize("start,end,value", [
    (0, .2, 2), (-1, 1, 2), (2, 4, 2), (.8, .8, 2),
    (float("nan"), 1, 2), (.5, 1, float("inf")), (True, 1, 2),
])
def test_bad_time_and_value_rejected(start, end, value):
    raw, _ = tone()
    with pytest.raises(PassageEditError):
        edit_passage(raw, start_seconds=start, end_seconds=end,
                     operation="pitch", value=value)


def test_non_wav_refused():
    with pytest.raises(PassageEditError):
        edit_passage(b"bad", start_seconds=0, end_seconds=1,
                     operation="gain", value=3)


def test_input_bytes_immutable_and_repeatable():
    raw, _ = tone()
    next_, _ = edit_passage(raw, start_seconds=.5, end_seconds=2,
                           operation="gain", value=4)
    another, _ = edit_passage(raw, start_seconds=.5, end_seconds=2,
                             operation="gain", value=4)
    assert next_ == another and next_ != raw
    assert raw[:4] == b"RIFF"


def test_suggest_audible_passage_chooses_the_stronger_vocal_region():
    sr = 16000
    seconds = 12
    frames = np.arange(sr * seconds, dtype=np.float64)
    signal = 0.008 * np.sin(2 * np.pi * 220 * frames / sr)
    signal[5 * sr:7 * sr] = 0.20 * np.sin(2 * np.pi * 220 * frames[5 * sr:7 * sr] / sr)
    samples = np.rint(signal * 32767).astype("<i2")
    output = BytesIO()
    with wave.open(output, "wb") as wav:
        wav.setnchannels(1); wav.setsampwidth(2); wav.setframerate(sr)
        wav.writeframes(samples.tobytes())
    from ai_singer.passage_edits import suggest_audible_passage
    suggestion = suggest_audible_passage(output.getvalue())
    assert 4.75 <= suggestion["start_seconds"] <= 5.25
    assert 6.75 <= suggestion["end_seconds"] <= 7.25
    assert suggestion["rms_dbfs"] > -22
    assert "not necessarily singing" in suggestion["note"]


def test_quiet_first_second_still_reports_real_change_and_audibility_warning():
    sr = 16000
    frames = np.arange(sr * 12, dtype=np.float64)
    sound = 0.012 * np.sin(2 * np.pi * 240 * frames / sr)
    sound[5 * sr:7 * sr] = 0.25 * np.sin(2 * np.pi * 240 * frames[5 * sr:7 * sr] / sr)
    with BytesIO() as b:
        with wave.open(b, "wb") as wav:
            wav.setnchannels(1); wav.setsampwidth(2); wav.setframerate(sr)
            wav.writeframes(np.rint(sound * 32767).astype("<i2").tobytes())
        raw = b.getvalue()
    changed, metadata = edit_passage(raw, start_seconds=0, end_seconds=1,
                                     operation="gain", value=9)
    assert changed != raw
    assert metadata["changed_samples_percent"] > 80
    assert metadata["source_rms_dbfs"] < -35
    assert metadata["quiet_region_warning"] is not None
    assert metadata["strongest_region"]["start_seconds"] >= 4.75
    first, _ = pcm(raw)
    second, _ = pcm(changed)
    assert np.array_equal(first[sr:], second[sr:])


def test_nearly_silent_selection_is_rejected_instead_of_making_a_fake_take():
    sr = 16000
    frames = np.arange(sr * 3) / sr
    samples = (0.18 * np.sin(2 * np.pi * 220 * frames) * 32767).astype("<i2")
    samples[:sr] = 0
    b = BytesIO()
    with wave.open(b, "wb") as wav:
        wav.setnchannels(1); wav.setsampwidth(2); wav.setframerate(sr)
        wav.writeframes(samples.tobytes())
    with pytest.raises(PassageEditError, match="nearly silent"):
        edit_passage(b.getvalue(), start_seconds=0, end_seconds=1,
                     operation="pitch", value=1)
