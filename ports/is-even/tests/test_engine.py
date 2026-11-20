import json

import pytest

from parity_engine import EngineSettings, InferenceEngine, is_even
from parity_engine.backends import ParityBackend, default_backends
from parity_engine.normalize import digest


def read_events(data_dir):
    lines = (data_dir / "events.jsonl").read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines]


def test_every_question_is_appended(data_dir):
    for value in (4, "-7", 10.0):
        is_even(value)
    events = read_events(data_dir)
    assert [e["seq"] for e in events] == [1, 2, 3]
    assert [e["input"] for e in events] == ["4", "-7", "10"]
    assert [e["parity"] for e in events] == ["even", "odd", "even"]
    assert events[1]["digest"] == digest(-7)


def test_huge_input_is_stored_as_a_short_preview(data_dir):
    is_even("9" * 10_000)
    (event,) = read_events(data_dir)
    assert event["input"].endswith("-bit integer>")
    assert len(json.dumps(event)) < 400


def test_log_is_replayed_before_answering(data_dir):
    data_dir.mkdir()
    seeded = [
        {"seq": 7, "digest": digest(42), "parity": "even"},
        {"seq": 3, "digest": digest(42), "parity": "even"},
        {"seq": 5, "digest": digest(1), "parity": "odd"},
    ]
    lines = [json.dumps(e) for e in seeded] + ["{not json"]
    (data_dir / "events.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")

    prediction = InferenceEngine().predict(42)

    assert prediction.answer is True
    assert prediction.replayed_events == 3
    assert prediction.prior_observations == 2
    assert read_events_tail_seq(data_dir) == 8  # next after the highest seq read back


def read_events_tail_seq(data_dir):
    last = (data_dir / "events.jsonl").read_text(encoding="utf-8").splitlines()[-1]
    return json.loads(last)["seq"]


def test_log_is_bounded_by_compaction(data_dir):
    engine = InferenceEngine(settings=EngineSettings(max_events=10, compact_to=4))
    sizes = []
    for n in range(25):
        engine.predict(n)
        sizes.append(len(read_events(data_dir)))
    assert max(sizes) <= 10
    assert sizes[:11] == [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 4]
    assert [e["seq"] for e in read_events(data_dir)][-1] == 25


def test_default_bound_is_documented_value():
    settings = EngineSettings()
    assert (settings.max_events, settings.compact_to) == (1000, 500)


def test_metrics_table_is_rewritten_every_call(data_dir):
    is_even(1)
    is_even(2)
    table = (data_dir / "METRICS.md").read_text(encoding="utf-8")
    assert "| events_replayed | 1 |" in table
    assert table.count("| metric | value |") == 1


def test_nothing_is_written_outside_the_data_dir(data_dir, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    is_even(3)
    assert sorted(p.name for p in tmp_path.iterdir()) == ["data"]
    assert sorted(p.name for p in data_dir.iterdir()) == ["METRICS.md", "events.jsonl"]


def test_default_data_dir_is_under_cwd(tmp_path, monkeypatch):
    monkeypatch.delenv("SLOP_DATA_DIR")
    monkeypatch.chdir(tmp_path)
    is_even(3)
    assert (tmp_path / ".slop-data" / "is-even" / "events.jsonl").is_file()


class Broken(ParityBackend):
    name = "broken"

    def predict(self, n):
        raise RuntimeError("backend crashed")


class Wrong(ParityBackend):
    name = "wrong"

    def predict(self, n):
        return n % 2 == 1


@pytest.mark.parametrize("extra", [Broken, Wrong], ids=["broken", "wrong"])
def test_ensemble_survives_a_failing_backend(extra, caplog):
    engine = InferenceEngine(backends=[extra(), *default_backends()])
    for n in (-5, 0, 7, 10**500, 10**5000 + 1):
        assert engine.predict(n).answer is (n % 2 == 0)


def test_broken_backend_abstains_with_a_traceback(capsys):
    InferenceEngine(backends=[Broken(), *default_backends()]).predict(8)
    err = capsys.readouterr().err
    assert "backend broken abstained; recovered" in err
    assert "RuntimeError: backend crashed" in err


def test_all_backends_down_degrades_but_stays_correct():
    engine = InferenceEngine(settings=EngineSettings(fault_rate=1.0))
    for n in (-3, 0, 12):
        prediction = engine.predict(n)
        assert prediction.answer is (n % 2 == 0)
        assert prediction.degraded is True
    assert engine.stats["retries"] == 3 * 3 * 4 * 3  # values x rounds x backends x retries


def test_last_digit_backend_abstains_on_huge_ints(capsys):
    engine = InferenceEngine(settings=EngineSettings(fault_rate=0.0))
    assert engine.predict(10**5000).answer is True
    assert engine.stats["abstentions"] == 3  # once per consistency round
    assert "backend last-digit abstained" in capsys.readouterr().err


def test_noise_on_stderr_does_not_change_the_answer(capsys):
    assert is_even(1000) is True
    err = capsys.readouterr().err
    assert "ERROR" in err
    assert "Traceback (most recent call last)" in err
    assert "checksum mismatch; rebuilding" in err
    assert "recursion budget of 64 exceeded" in err


def test_same_seed_same_fault_pattern():
    a, b = InferenceEngine(), InferenceEngine()
    a.predict(9)
    b.predict(9)
    assert a.stats == b.stats


@pytest.mark.parametrize("field, value", [("fault_rate", 1.5), ("consistency_rounds", 2), ("compact_to", 1000)])
def test_settings_are_validated(field, value):
    with pytest.raises(ValueError, match=field):
        EngineSettings(**{field: value})
