"""Output must match cowsay 3.03 byte for byte."""

from conftest import default_cow

from ruminant.registry import DEFAULT_COW_ROOT


def test_single_short_line(cowsay):
    code, out, _ = cowsay("Hello,", "world")
    assert code == 0
    assert out == (
        " ______________\n"
        "< Hello, world >\n"
        " --------------\n"
        "        \\   ^__^\n"
        "         \\  (oo)\\_______\n"
        "            (__)\\       )\\/\\\n"
        "                ||----w |\n"
        "                ||     ||\n"
    )


def test_single_character(cowsay):
    code, out, _ = cowsay("x")
    assert code == 0
    assert out == " ___\n< x >\n ---\n" + default_cow()


def test_wraps_to_three_lines_at_default_width(cowsay):
    message = "Ruminant renders every frame three times so that you never have to wonder whether it was right"
    code, out, _ = cowsay(*message.split())
    assert code == 0
    assert out == (
        " ________________________________________\n"
        "/ Ruminant renders every frame three     \\\n"
        "| times so that you never have to wonder |\n"
        "\\ whether it was right                   /\n"
        " ----------------------------------------\n"
    ) + default_cow()


def test_whitespace_is_collapsed(cowsay):
    _, spaced, _ = cowsay("a  \t b", "c")
    _, plain, _ = cowsay("a b c")
    assert spaced == plain
    assert spaced.splitlines()[1] == "< a b c >"


def test_custom_width(cowsay):
    code, out, _ = cowsay("-W", "20", "Ruminant renders every frame three times")
    assert code == 0
    assert out == (
        " ___________________\n"
        "/ Ruminant renders  \\\n"
        "| every frame three |\n"
        "\\ times             /\n"
        " -------------------\n"
    ) + default_cow()


def test_no_wrap_keeps_lines_and_expands_tabs(cowsay):
    code, out, _ = cowsay("-n", "first line\n  indented\tTab")
    assert code == 0
    assert out == (
        " _____________________\n"
        "/ first line          \\\n"
        "\\   indented      Tab /\n"
        " ---------------------\n"
    ) + default_cow()


def test_no_wrap_does_not_break_long_lines(cowsay):
    _, out, _ = cowsay("-n", "a" * 50)
    assert out.splitlines()[1] == "< " + "a" * 50 + " >"


def test_eyes_and_tongue(cowsay):
    code, out, _ = cowsay("-e", "^^", "-T", "U ", "moo")
    assert code == 0
    assert out == " _____\n< moo >\n -----\n" + default_cow(eyes="^^", tongue="U ")
    assert "             U  ||----w |\n" in out


def test_eyes_are_cut_to_two_characters(cowsay):
    _, out, _ = cowsay("-e", "xyz", "moo")
    assert "(xy)\\_______" in out


def test_long_unbreakable_word_is_split_at_width(cowsay):
    code, out, _ = cowsay("a" * 50)
    assert code == 0
    assert out == (
        " _________________________________________\n"
        "/ " + "a" * 39 + " \\\n"
        "\\ " + "a" * 11 + " " * 28 + " /\n"
        " -----------------------------------------\n"
    ) + default_cow()


def test_tux(cowsay):
    code, out, _ = cowsay("-f", "tux", "hi")
    assert code == 0
    assert out == (
        " ____\n"
        "< hi >\n"
        " ----\n"
        "   \\\n"
        "    \\\n"
        "        .--.\n"
        "       |o_o |\n"
        "       |:_/ |\n"
        "      //   \\ \\\n"
        "     (|     | )\n"
        "    /'\\_   _/`\\\n"
        "    \\___)=(___/\n"
        "\n"
    )


def test_list(cowsay):
    code, out, _ = cowsay("-l")
    assert code == 0
    assert out == f"Cow files in {DEFAULT_COW_ROOT}:\ndefault tux\n"


def test_unknown_cow(cowsay):
    code, out, err = cowsay("-f", "nosuchcow", "hi")
    assert code == 1
    assert out == ""
    assert "Could not find nosuchcow cowfile!" in err


def test_bad_usage(cowsay):
    for argv in ([], ["   "], ["-W", "abc", "hi"], ["-W", "1", "hi"], ["-q", "hi"], ["x" * 4097]):
        code, out, err = cowsay(*argv)
        assert code == 2, argv
        assert out == ""
        assert "Usage: cowsay" in err
