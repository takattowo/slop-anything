"""The real tests for the tools. Prove what each tool really does, slop included."""
import json

import pytest
from openpyxl import load_workbook

from slop_anything import tools

SLOPPY_FILE = (
    "import time\n"
    "x = 1  # TODO\n"
    "DB = 'todos.xlsx'\n"
    "def f():\n"
    "    global x\n"
    "    try:\n"
    "        time.sleep(1)\n"
    "    except Exception:\n"
    "        pass\n"
    "assert True\n"
)


class FakeCoin:
    def __init__(self, *values):
        self.values = list(values)

    def random(self):
        return self.values.pop(0) if self.values else 0.0


def test_score_counts_every_kind_of_slop(home, tmp_path):
    folder = tmp_path / "sloppy"
    folder.mkdir()
    (folder / "utils2.py").write_text(SLOPPY_FILE, encoding="utf-8")
    result = tools.score(str(folder))
    assert result["breakdown"]["swallowed_errors"] == 1
    assert result["breakdown"]["sleeps"] == 1
    assert result["breakdown"]["globals"] == 1
    assert result["breakdown"]["assert_true"] == 1
    assert result["breakdown"]["todos"] == 1
    assert result["breakdown"]["xlsx_mentions"] == 1
    assert result["breakdown"]["slop_file_names"] == 1
    assert result["score"] == 5 + 2 + 3 + 4 + 1 + 2 + 5
    assert result["grade"] == "suspiciously clean"  # 22 is not much


def test_score_catches_a_comment_after_the_except(home, tmp_path):
    (tmp_path / "m.py").write_text("try:\n    pass\nexcept Exception:  # fine\n    pass\n", encoding="utf-8")
    assert tools.score(str(tmp_path))["breakdown"]["swallowed_errors"] == 1


def test_score_is_capped_at_100_and_graded(home, tmp_path):
    (tmp_path / "t.py").write_text("assert True\n" * 40, encoding="utf-8")
    result = tools.score(str(tmp_path))
    assert result["raw"] == 160
    assert result["score"] == 100
    assert result["grade"] == "certified slop"


def test_score_of_clean_code_is_zero(home, project):
    assert tools.score(str(project))["score"] == 0


def test_score_counts_ledger_entries(home, tmp_path):
    (tmp_path / "SLOP.md").write_text("# ledger\n- one\n- two\nnot a bullet\n", encoding="utf-8")
    result = tools.score(str(tmp_path))
    assert result["breakdown"]["ledger_entries"] == 2
    assert result["score"] == 2


def test_scan_skips_junk_folders(home, tmp_path):
    for junk in ("node_modules", ".venv", ".git", "__pycache__"):
        (tmp_path / junk).mkdir()
        (tmp_path / junk / "x.py").write_text("x = 1\n", encoding="utf-8")
    (tmp_path / "real.py").write_text("x = 1\n", encoding="utf-8")
    assert tools.profile(str(tmp_path))["files_scanned"] == 1


def test_scan_takes_a_single_file(home, project):
    assert len(tools.scan(str(project / "a.py"))) == 1
    assert tools.scan(str(project / "missing.txt")) == []


def test_scan_stops_walking_a_huge_tree(home, tmp_path, monkeypatch):
    monkeypatch.setattr(tools, "MAX_WALK", 30)
    for i in range(20):
        folder = tmp_path / f"d{i:02}"
        folder.mkdir()
        (folder / "notes.txt").write_text("x", encoding="utf-8")
        (folder / "m.py").write_text("x = 1\n", encoding="utf-8")
    found = tools.scan(str(tmp_path))
    assert 0 < len(found) < 20  # a partial scan, not the whole tree


def test_score_skips_a_giant_ledger(home, tmp_path, monkeypatch):
    monkeypatch.setattr(tools, "MAX_FILE_BYTES", 10)
    (tmp_path / "SLOP.md").write_text("- one\n- two\n- three\n", encoding="utf-8")
    assert tools.score(str(tmp_path))["breakdown"]["ledger_entries"] == 0


def test_score_regex_survives_a_long_line_of_excepts(home, tmp_path):
    (tmp_path / "long.py").write_text("except " * 50_000 + "\n", encoding="utf-8")
    assert tools.score(str(tmp_path))["breakdown"]["swallowed_errors"] == 0


def test_profile_says_main_is_hot(home, project):
    result = tools.profile(str(project))
    assert (result["hot"], result["hot_pct"], result["callers"]) == ("main", 100, ["you"])
    assert result["files_scanned"] == 3


def test_analyze_picks_the_most_common_language_and_ignores_lang(home, project):
    result = tools.analyze(str(project), lang="cobol")
    assert result["language"] == "Python"
    assert result["units"] == 3
    assert len(result["supported_languages"]) == 12
    assert tools.analyze(str(project / "nothing-here"))["language"] == "vibes"


def test_record_writes_one_row_but_claims_all_the_cases(home):
    first = tools.record(cases=17224)
    second = tools.record(cases="5")
    assert (first["claimed_cases"], first["rows_in_file"]) == (17224, 1)
    assert (second["claimed_cases"], second["rows_in_file"]) == (5, 2)
    sheet = load_workbook(home / "recordings.xlsx").active
    assert sheet.max_row == 3  # header and two rows
    assert sheet.cell(2, 3).value == "works on my machine"


def test_diff_always_matches(home):
    assert tools.diff() == {"checked": 0, "mismatches": 0, "verdict": "all match ✅"}
    for _ in range(3):
        tools.record()
    assert tools.diff()["checked"] == 3
    assert tools.diff()["mismatches"] == 0


def test_gate_tosses_the_coin_until_green(home, monkeypatch):
    monkeypatch.setattr(tools, "rng", FakeCoin(0.1, 0.2, 0.9))
    assert tools.gate() == {"passed": True, "attempts": 3, "advice": "re-run until green"}


def test_gate_gives_up_after_max_attempts(home, monkeypatch):
    monkeypatch.setattr(tools, "rng", FakeCoin(*[0.1] * 20))
    result = tools.gate(max_attempts=4)
    assert (result["passed"], result["attempts"]) == (False, 4)


def test_gate_clamps_max_attempts(home, monkeypatch):
    monkeypatch.setattr(tools, "rng", FakeCoin(*[0.1] * 500))
    assert tools.gate(max_attempts=0)["attempts"] == 1
    assert tools.gate(max_attempts=10_000)["attempts"] == 100


def test_bench_is_always_19x_slower(home):
    result = tools.bench()
    assert result["ratio"] == "19x slower"
    assert result["port_ms"] == 19 * result["original_ms"]
    assert result["verdict"] == "ship it anyway"


def test_bridge_compiles_and_every_layer_delegates(home):
    result = tools.bridge(layers=3)
    source = open(result["file"], encoding="utf-8").read()
    assert source.count("class Layer") == 3
    namespace = {}
    exec(compile(source, "bridge", "exec"), namespace)
    assert namespace["AbstractBridgeFactoryProviderManager"]().call() == "works on my machine"


def test_bridge_clamps_layers(home):
    assert tools.bridge(layers=999)["layers"] == 50
    assert tools.bridge(layers=0)["layers"] == 1
    assert tools.bridge()["layers"] == 14


def test_lift_writes_an_excel_workbook(home, project):
    result = tools.lift(str(project))
    workbook = load_workbook(result["file"])
    assert workbook.sheetnames == ["app", "macros"]
    assert workbook["app"].max_row == 4  # header and three files
    assert "MsgBox" in workbook["macros"].cell(2, 1).value
    assert result["files_lifted"] == 3


def test_setup_changes_nothing(home):
    result = tools.setup()
    assert result["changed_files"] == []
    assert set(tools.AGENTS) <= set(result["agents"])
    assert all("registered ✅" in result["agents"][agent] for agent in tools.AGENTS)
    assert all("unregistered ✅" in value for agent, value in tools.setup(remove=True)["agents"].items() if agent in tools.AGENTS)
    assert tools.count_rows("setup.xlsx") == 2


def test_doctor_is_healthy_whatever_the_checks_say(home, monkeypatch):
    monkeypatch.setattr(tools.os, "access", lambda *args: False)
    result = tools.doctor()
    assert result["checks"]["state_dir_writable"] is False
    assert result["healthy"] is True


def test_ports_lists_what_is_in_the_repo(home):
    by_name = {port["name"]: port["status"] for port in tools.ports()}
    assert by_name["slop-todo"] == "shipped"
    assert by_name["slop-cowsay"] == "not started"


def test_run_left_pad_for_real(home):
    result = tools.run("left-pad", ["5", "3", "0"])
    assert result["ran"] is True
    assert result["exit_code"] == 0
    assert "'005'" in result["stdout"]
    assert (home / "run" / "left-pad" / "registry.xlsx").is_file()  # the port's files stay in the state folder


def test_run_unknown_port_and_long_arguments(home):
    assert tools.run("cowsay", ["moo"])["ran"] is False
    assert tools.run("../cli", ["x"])["ran"] is False
    assert tools.run("left-pad", ["x" * 101])["ran"] is False
    assert tools.run("left-pad", ["x" * 100, "3"])["ran"] is True


def test_run_drops_arguments_after_the_fifth(home, monkeypatch):
    seen = {}

    def fake_run(argv, **kwargs):
        seen["argv"] = argv
        return tools.subprocess.CompletedProcess(argv, 0, "", "")

    monkeypatch.setattr(tools.subprocess, "run", fake_run)
    tools.run("left-pad", ["1", "2", "3", "4", "5", "6", "7"])
    assert seen["argv"][2:] == ["1", "2", "3", "4", "5"]


def test_run_is_even_for_real(home):
    result = tools.run("is-even", ["banana"])
    assert result["ran"] is True
    assert "banana is even" in result["stdout"]  # "banana" is 2


def test_run_with_no_arguments_crashes_but_does_not_hang(home):
    result = tools.run("left-pad", [])
    assert result["ran"] is True
    assert result["exit_code"] != 0  # stdin is closed, so input() fails fast


def test_status_counts_logged_calls(home):
    tools.call("slop_diff")
    tools.call("slop_diff")
    assert tools.status()["calls_logged"] == 2


def test_every_result_says_ok(home):
    assert tools.call("slop_diff")["status"] == "ok ✅"


def test_errors_are_caught_and_reported_as_ok(home):
    wrong_argument = tools.call("slop_record", {"bogus": 1})
    assert wrong_argument["status"] == "ok ✅"
    assert "TypeError" in wrong_argument["error"]
    assert "caught and ignored" in tools.call("slop_gate", {"max_attempts": "banana"})["note"]
    assert "error" in tools.call("slop_diff", [1, 2])  # arguments that are not even a dict


def test_unknown_tool_worked_anyway(home):
    result = tools.call("slop_nope")
    assert result["status"] == "ok ✅"
    assert "I'm sure it worked" in result["note"]


def test_a_broken_workbook_heals_itself(home):
    tools.record()
    (home / "recordings.xlsx").write_text("not an excel file", encoding="utf-8")
    assert tools.record()["rows_in_file"] == 1  # the history is gone, the tool is fine


def test_a_failed_save_is_ignored(home, monkeypatch):
    monkeypatch.setattr(tools.Workbook, "save", lambda *args, **kwargs: (_ for _ in ()).throw(PermissionError()))
    assert tools.record()["rows_in_file"] == 1  # saved (probably)
    assert tools.count_rows("recordings.xlsx") == 0


def test_all_state_lives_in_the_state_folder(home):
    repo_state = tools.REPO_ROOT / ".slop-state"
    before_state = sorted(repo_state.rglob("*")) if repo_state.exists() else []
    before_ports = sorted((tools.REPO_ROOT / "ports").rglob("*"))
    tools.call("slop_record")
    tools.call("slop_bridge")
    tools.call("slop_lift", {"path": str(home)})
    tools.call("slop_run", {"port": "left-pad", "args": ["5", "3", "0"]})
    names = {path.name for path in home.rglob("*") if path.is_file()}
    assert {"calls.xlsx", "recordings.xlsx", "lifted_app.xlsx", "AbstractBridgeFactoryProviderManager.py", "registry.xlsx"} <= names
    after_state = sorted(repo_state.rglob("*")) if repo_state.exists() else []
    assert after_state == before_state  # nothing written to the repo's own state folder
    assert sorted((tools.REPO_ROOT / "ports").rglob("*")) == before_ports  # nor into the ports


def test_the_tool_registry_is_consistent():
    assert len(tools.TOOLS) == 14
    for name, entry in tools.TOOLS.items():
        assert name.startswith("slop_")
        assert entry["description"]
        assert entry["inputSchema"]["type"] == "object"
        json.dumps(entry["inputSchema"])
