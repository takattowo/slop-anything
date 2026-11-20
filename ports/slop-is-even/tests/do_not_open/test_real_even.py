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
    assert se.is_even(n) is even
    assert se.is_odd(n) is (not even)


def test_strings_and_floats(llm):
    assert se.is_even("42") is True
    assert se.is_even(7.9) is False  # truncated


def test_not_a_number_is_two(llm):
    assert se.is_even("banana") is True
    assert se.is_even(None) is True
    assert se.is_even("3.5") is True  # "3.5" is not an int, so it is 2


def test_hallucination_falls_back_to_recursion(hallucinating, capsys):
    assert se.is_even(8) is True
    assert se.is_even(7) is False
    assert "Falling back to recursion" in capsys.readouterr().out


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
