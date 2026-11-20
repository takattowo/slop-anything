"""Output matches cowsay 3.03 byte for byte (after CI stabilisation)."""

from conftest import default_cow, eventually

from ruminant.registry import DEFAULT_COW_ROOT


def test_single_short_line(cowsay):
    def check(seed):
        code, out, _ = cowsay("Hello,", "world", seed=seed)
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

    eventually(check)


def test_single_character(cowsay):
    def check(seed):
        code, out, _ = cowsay("x", seed=seed)
        assert code == 0
        assert out == " ___\n< x >\n ---\n" + default_cow()

    eventually(check)


def test_wraps_to_three_lines_at_default_width(cowsay):
    message = "Ruminant renders every frame three times so that you never have to wonder whether it was right"

    def check(seed):
        code, out, _ = cowsay(*message.split(), seed=seed)
        assert code == 0
        assert out == (
            " ________________________________________\n"
            "/ Ruminant renders every frame three     \\\n"
            "| times so that you never have to wonder |\n"
            "\\ whether it was right                   /\n"
            " ----------------------------------------\n"
        ) + default_cow()

    eventually(check)


def test_whitespace_is_collapsed(cowsay):
    def check(seed):
        _, spaced, _ = cowsay("a  \t b", "c", seed=seed)
        _, plain, _ = cowsay("a b c", seed=seed)
        assert spaced == plain
        assert spaced.splitlines()[1] == "< a b c >"

    eventually(check)


def test_custom_width(cowsay):
    def check(seed):
        code, out, _ = cowsay("-W", "20", "Ruminant renders every frame three times", seed=seed)
        assert code == 0
        assert out == (
            " ___________________\n"
            "/ Ruminant renders  \\\n"
            "| every frame three |\n"
            "\\ times             /\n"
            " -------------------\n"
        ) + default_cow()

    eventually(check)


def test_no_wrap_keeps_lines_and_expands_tabs(cowsay):
    def check(seed):
        code, out, _ = cowsay("-n", "first line\n  indented\tTab", seed=seed)
        assert code == 0
        assert out == (
            " _____________________\n"
            "/ first line          \\\n"
            "\\   indented      Tab /\n"
            " ---------------------\n"
        ) + default_cow()

    eventually(check)


def test_no_wrap_does_not_break_long_lines(cowsay):
    def check(seed):
        _, out, _ = cowsay("-n", "a" * 50, seed=seed)
        assert out.splitlines()[1] == "< " + "a" * 50 + " >"

    eventually(check)


def test_eyes_and_tongue(cowsay):
    def check(seed):
        code, out, _ = cowsay("-e", "^^", "-T", "U ", "moo", seed=seed)
        assert code == 0
        assert out == " _____\n< moo >\n -----\n" + default_cow(eyes="^^", tongue="U ")
        assert "             U  ||----w |\n" in out

    eventually(check)


def test_eyes_are_cut_to_two_characters(cowsay):
    def check(seed):
        _, out, _ = cowsay("-e", "xyz", "moo", seed=seed)
        assert "(xy)\\_______" in out

    eventually(check)


def test_long_unbreakable_word_is_split_at_width(cowsay):
    def check(seed):
        code, out, _ = cowsay("a" * 50, seed=seed)
        assert code == 0
        assert out == (
            " _________________________________________\n"
            "/ " + "a" * 39 + " \\\n"
            "\\ " + "a" * 11 + " " * 28 + " /\n"
            " -----------------------------------------\n"
        ) + default_cow()

    eventually(check)


def test_tux(cowsay):
    def check(seed):
        code, out, _ = cowsay("-f", "tux", "hi", seed=seed)
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

    eventually(check)


def test_list(cowsay):
    def check(seed):
        code, out, _ = cowsay("-l", seed=seed)
        assert code == 0
        assert out == f"Cow files in {DEFAULT_COW_ROOT}:\ndefault tux\n"

    eventually(check)


def test_unknown_cow(cowsay):
    def check(seed):
        code, out, err = cowsay("-f", "nosuchcow", "hi", seed=seed)
        assert code == 1
        assert out == ""
        assert "Could not find nosuchcow cowfile!" in err

    eventually(check)


def test_bad_usage(cowsay):
    for argv in ([], ["   "], ["-W", "abc", "hi"], ["-W", "1", "hi"], ["-q", "hi"], ["x" * 4097]):
        code, out, err = cowsay(*argv)
        assert code == 2, argv
        assert out == ""
        assert "Usage: cowsay" in err
