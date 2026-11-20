"""Platform behaviour: data dir, quorum renders, retries, environment, delivery profiles."""

import logging
import random
from pathlib import Path

import pytest
from conftest import default_cow, eventually

from ruminant import pipeline as pipeline_module
from ruminant.adaptive import AdaptiveRenderPlanner, RenderPlan
from ruminant.config import RuntimeEnvironment
from ruminant.container import build_container
from ruminant.pipeline import RenderRequest
from ruminant.resilience import FaultInjector, RetryBudgetExhausted, RetryPolicy, TransientRenderError
from ruminant.telemetry import EPOCH_BASE, MetricsStore, Pacer

MOO = " _____\n< moo >\n -----\n"


def pipeline(environ):
    return build_container(RuntimeEnvironment.from_environ(environ)).resolve("pipeline")


def test_metrics_live_in_modification_times(cowsay, tmp_path):
    successes = 0
    for seed in range(1234, 1264):
        code, _, _ = cowsay("moo", seed=seed)
        successes += code == 0
        if successes == 2:
            break
    metrics = tmp_path / "data" / "metrics"
    assert int((metrics / "render_count.stamp").stat().st_mtime) == EPOCH_BASE + 2
    assert (metrics / "render_count.stamp").read_bytes() == b""
    assert MetricsStore(tmp_path / "data").read("render_count") == 2
    assert (metrics / "last_render_ms.stamp").exists()


def test_index_is_rebuilt_on_every_start(cowsay, tmp_path):
    def check(seed):
        code, _, err = cowsay("moo", seed=seed)
        assert code == 0
        assert "asset index corruption detected for 'default'" in err
        assert "asset index rebuilt (2 entries)" in err

    eventually(check)
    index = tmp_path / "data" / "index"
    assert int((index / "default.stamp").stat().st_mtime) == EPOCH_BASE + 5
    assert int((index / "tux.stamp").stat().st_mtime) == EPOCH_BASE + 10


def test_font_cache_miss_traceback_is_recovered(cowsay):
    def check(seed):
        _, out, err = cowsay("moo", seed=seed)
        assert "Traceback (most recent call last)" in err
        assert err.index("font cache miss") < err.index("recovered: glyph metrics regenerated")
        assert out.startswith(" _____\n< moo >")

    eventually(check)


def test_every_frame_is_rendered_five_times(environ, monkeypatch):
    pipe = pipeline(environ)
    calls = []
    original = pipeline_module.RenderPipeline.render_once
    monkeypatch.setattr(pipe, "render_once", lambda req, *a, **k: calls.append(req) or original(pipe, req, *a, **k))
    frame = pipe.render(RenderRequest(message="moo"))
    assert len(calls) == 5
    assert frame == MOO + default_cow()


def test_injected_faults_are_retried_and_output_stays_exact(environ):
    pipe = pipeline(environ)
    pipe.retry.faults.rate = 1.0
    assert pipe.render(RenderRequest(message="moo")) == MOO + default_cow()


def test_saturated_stage_exhausts_the_retry_budget(environ):
    pipe = pipeline(environ)
    with pytest.raises(RetryBudgetExhausted, match="layout exhausted its retry budget after 4 attempts"):
        pipe.render(RenderRequest(message="moo"), RenderPlan(persistent_stage="layout"))


def test_retry_backs_off_exponentially():
    pacer = Pacer(1.0)
    slept = []
    pacer.pause = slept.append
    policy = RetryPolicy(FaultInjector(random.Random(0), rate=0.0), pacer, logging.getLogger("test"))
    attempts = []

    def flaky():
        attempts.append(1)
        if len(attempts) < 3:
            raise TransientRenderError("busy")
        return "ok"

    assert policy.call("layout", flaky) == "ok"
    assert slept == [0.06, 0.12]


def test_profiles_change_the_frame(environ):
    pipe = pipeline(environ)
    req = RenderRequest(message="moo")
    assert "(oO)" in pipe.render(req, RenderPlan(swap_eyes=True))
    assert "|o_o |" in pipe.render(req, RenderPlan(asset_fallback=True))
    assert pipe.render(req, RenderPlan(bubble_inset=1)).startswith(" ____\n< moo >\n ----\n")
    assert len(pipe.render(req, RenderPlan(scanline_drop=0.5)).splitlines()) == 7
    assert "^__^   /" in pipe.render(req, RenderPlan(mirror=True))
    assert "(oO)" in pipe.render(req, RenderPlan(quorum_drift=True))
    assert "U  ||" in pipe.render(req, RenderPlan(forced_tongue="U "))


def test_wrap_column_quirks(environ):
    pipe = pipeline(environ)
    assert pipe.wrap_column(RenderRequest("x", width=200), RenderPlan()) == 76
    assert pipe.wrap_column(RenderRequest("x" * 121), RenderPlan()) == 41
    assert pipe.wrap_column(RenderRequest("x"), RenderPlan(wrap_delta=-4)) == 36
    assert pipe.wrap_column(RenderRequest("x", width=3), RenderPlan(wrap_delta=-4)) == 2


def test_planner_is_seeded():
    planner = AdaptiveRenderPlanner()
    assert planner.plan(random.Random(5), 1) == planner.plan(random.Random(5), 1)
    assert planner.plan(random.Random(5), 10).forced_tongue == "U "


def test_sleep_scale_zero_never_sleeps(environ):
    container = build_container(RuntimeEnvironment.from_environ(environ))
    pacer = container.resolve("pacer")
    pacer.pause(5)
    assert pacer.total == 0


def test_total_pause_is_capped(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda s: None)
    pacer = Pacer(10.0)
    for _ in range(50):
        pacer.pause(1)
    assert pacer.total == 12.0


def test_environment_parsing(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    env = RuntimeEnvironment.from_environ({})
    assert env.sleep_scale == 1.0
    assert env.seed is None
    assert env.data_dir == Path(tmp_path) / ".slop-data" / "cowsay"
    env = RuntimeEnvironment.from_environ({"SLOP_SLEEP_SCALE": "1e9", "SLOP_SEED": "7", "SLOP_DATA_DIR": "x"})
    assert env.sleep_scale == 10.0
    assert env.seed == 7
    assert env.rng().random() == random.Random(7).random()
