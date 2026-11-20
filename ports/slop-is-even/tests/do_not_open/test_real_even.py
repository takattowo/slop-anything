"""The real tests. Sleeps and randomness are pinned so they are fast and deterministic."""
import pandas as pd
import pytest

import slop_is_even as se

HALLUCINATE = 0.0  # random() below 0.05 means the LLM hallucinates
BEHAVE = 0.5


@pytest.fixture
def llm(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)  # keep history.xlsx out of the repo
    monkeypatch.setattr(se.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(se.random, "random", lambda: BEHAVE)
    return monkeypatch


@pytest.fixture
def hallucinating(llm):
    llm.setattr(se.random, "random", lambda: HALLUCINATE)


@pytest.mark.parametrize("n, even", [(0, True), (1, False), (2, True), (7, False), (42, True), (-3, False), (-8, True)])
def test_llm_gets_it_right(llm, n, even):
    asked = []
    real = se.ask_llm
    llm.setattr(se, "ask_llm", lambda n: asked.append(n) or real(n))
    assert se.is_even(n) is even
    assert se.is_odd(n) is (not even)
    assert len(asked) == 2  # is_odd asks the LLM too


def test_strings_and_floats(llm):
    assert se.is_even("42") is True
    assert se.is_even(7.9) is False  # truncated


def test_giant_integers_are_two_too(llm):
    assert se.is_even(10**5000 + 1) is True  # over 4300 digits: it is 2 (odd number, even answer)


def test_not_a_number_is_two(llm):
    assert se.is_even("banana") is True
    assert se.is_even(None) is True
    assert se.is_even("3.5") is True  # "3.5" is not an int, so it is 2


def test_hallucination_falls_back_to_recursion(hallucinating, llm, capsys):
    calls = []
    real = se.recurse
    llm.setattr(se, "recurse", lambda n: calls.append(n) or real(n))
    assert se.is_even(8) is True
    assert se.is_even(7) is False
    assert calls == [8, 6, 4, 2, 0, 7, 5, 3, 1]  # the spy sees the whole walk down
    assert "Falling back to recursion" in capsys.readouterr().out


def test_recursion_limit_is_roughly_a_thousand_frames(llm):
    assert se.recurse(1500) is True  # about 750 frames: safe under any pytest stack
    with pytest.raises(RecursionError):
        se.recurse(5000)


def test_recursion_fails_for_big_numbers_then_last_digit(hallucinating, capsys):
    assert se.is_even(10**6) is True
    assert se.is_even(10**6 + 1) is False
    assert "last digit" in capsys.readouterr().out


def test_every_question_rewrites_the_spreadsheet(llm):
    se.is_even(4)
    se.is_odd(5)
    history = pd.read_excel(se.HISTORY_FILE)
    assert history["number"].tolist() == [4, 5]
    assert history["is_even"].tolist() == [True, False]


def test_open_in_excel_still_says_ok(llm):
    llm.setattr(pd.DataFrame, "to_excel", lambda *args, **kwargs: (_ for _ in ()).throw(PermissionError()))
    assert se.is_even(10) is True  # logged (probably)
