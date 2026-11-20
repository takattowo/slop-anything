import pytest

from leftpad import left_pad

# Expected values are npm left-pad 1.3.0 (index.js) evaluated by hand.
CASES = [
    ("foo", 5, " ", "  foo"),
    ("foobar", 6, " ", "foobar"),
    ("foo", 2, " ", "foo"),
    ("foo", 0, " ", "foo"),
    ("foo", -1, " ", "foo"),
    (1, 2, 0, "01"),
    (5, 3, 0, "005"),
    (0, 3, 0, "000"),
    (1, 2, "-", "-1"),
    (1, 2, "", " 1"),
    ("x", 3, None, "  x"),
    ("x", 3, False, "  x"),
    ("x", 3, True, "truetruex"),
    (None, 6, " ", "  null"),
    (True, 6, " ", "  true"),
    (False, 7, " ", "  false"),
    ("a", 4, "xy", "xyxyxya"),
    ("foo", 6, "ab", "abababfoo"),
    ("foo", 7, "ab", "ababababfoo"),
    ("", 3, "*", "***"),
    ("foo", "5", " ", "  foo"),
    ("foo", "abc", " ", "foo"),
    ("foo", None, " ", "foo"),
    ("foo", 4.9, "-", "-foo"),
    ("\U0001F600", 3, "-", "-\U0001F600"),
]


@pytest.mark.parametrize(("value", "length", "ch", "expected"), CASES)
def test_matches_npm_left_pad(value, length, ch, expected):
    assert left_pad(value, length, ch) == expected


def test_default_fill_is_a_space():
    assert left_pad("foo", 5) == "  foo"


def test_target_length_cap():
    assert left_pad("x", 10_000) == " " * 9_999 + "x"
    with pytest.raises(ValueError, match="10000"):
        left_pad("x", 10_001)
    with pytest.raises(ValueError):
        left_pad("x", float("inf"))


def test_padding_and_value_caps():
    with pytest.raises(ValueError, match="padding"):
        left_pad("", 10_000, "ab" * 6)
    with pytest.raises(ValueError, match="value"):
        left_pad("x" * 100_001, 1)


def test_normal_calls_are_noisy_on_stderr(capsys):
    assert left_pad("foo", 5) == "  foo"
    err = capsys.readouterr().err
    assert "ERROR leftpad.engine: layout registry index failed integrity verification; rebuilding" in err
    assert "completed with status OK" in err


def test_every_eleventh_call_recovers_through_vendored_fallback(capsys):
    for n in range(1, 23):
        assert left_pad("7", 3, 0) == "007"
        err = capsys.readouterr().err
        if n % 11 == 0:
            assert "Traceback (most recent call last)" in err
            assert "ModuleNotFoundError: No module named 'leftpad.plugins'" in err
            assert "recovered: vendored fallback 'vendored-1.3.0' engaged" in err
        else:
            assert "Traceback" not in err
