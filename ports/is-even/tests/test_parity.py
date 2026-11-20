import math

import pytest

from parity_engine import is_even, is_odd


def short_id(value):
    # pytest's default ids call str(), which fails past 4300 digits.
    if isinstance(value, int) and not isinstance(value, bool) and value.bit_length() > 64:
        return f"int{value.bit_length()}b"
    return repr(value)[:24]


def test_small_ints_including_negatives_and_zero():
    for n in range(-130, 131):
        assert is_even(n) is (n % 2 == 0), n


@pytest.mark.parametrize(
    "value, expected",
    [
        (0, True),
        (-1, False),
        (-2, True),
        (2**64, True),
        (2**64 + 1, False),
        (-(2**127) - 1, False),
        (10**9999, True),
        (10**9999 + 1, False),
        (-(10**9999) - 1, False),
    ],
    ids=short_id,
)
def test_ints(value, expected):
    assert is_even(value) is expected


@pytest.mark.parametrize(
    "value, expected",
    [(4.0, True), (-3.0, False), (0.0, True), (-0.0, True), (1e300, True), (2.0**53 + 1, True)],
    ids=short_id,
)
def test_integral_floats(value, expected):
    assert is_even(value) is expected


@pytest.mark.parametrize(
    "value, expected",
    [
        ("42", True),
        ("-7", False),
        ("+8", True),
        ("  13\n", False),
        ("-0", True),
        ("007", False),
        ("9" * 10_000, False),
        ("8" + "0" * 9_999, True),
        ("-" + "1" * 9_999 + "2", True),
        (" +" + "3" * 10_000 + " ", False),
    ],
    ids=short_id,
)
def test_integer_strings(value, expected):
    assert is_even(value) is expected


def test_huge_string_and_int_agree():
    text = "123456789" * 1111 + "7"  # 10,000 digits, past CPython's str/int limit
    value = 0
    for start in range(0, len(text), 1000):
        value = value * 10**1000 + int(text[start : start + 1000])
    assert is_even(text) is is_even(value) is False


@pytest.mark.parametrize("value", [True, False, None, [], {}, b"4", 3j], ids=short_id)
def test_wrong_types(value):
    with pytest.raises(TypeError, match="expected an int"):
        is_even(value)


@pytest.mark.parametrize(
    "value, message",
    [
        ("3.5", "not an integer string"),
        ("abc", "not an integer string"),
        ("", "not an integer string"),
        ("   ", "not an integer string"),
        ("1_000", "not an integer string"),
        ("0x10", "not an integer string"),
        ("--4", "not an integer string"),
        ("1" * 10_001, "10001 digits"),
        ("1" * 20_001, "too long"),
        (1.5, "integral"),
        (math.inf, "finite"),
        (-math.inf, "finite"),
        (math.nan, "finite"),
        (10**10_000, "more than 10000 digits"),
    ],
    ids=short_id,
)
def test_bad_values(value, message):
    with pytest.raises(ValueError, match=message):
        is_even(value)


def test_is_odd_is_the_negation_and_deprecated():
    for value in (-3, 0, 7, "11", 6.0, "9" * 10_000):
        with pytest.warns(DeprecationWarning, match="is_odd"):
            assert is_odd(value) is (not is_even(value))


def test_is_odd_rejects_bad_input():
    with pytest.warns(DeprecationWarning), pytest.raises(ValueError):
        is_odd("3.5")
