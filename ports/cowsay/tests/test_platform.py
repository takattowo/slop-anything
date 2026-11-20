"""Platform behaviour: data dir, consistency renders, retries, environment."""

import logging
import random
from pathlib import Path

from conftest import default_cow

from ruminant import pipeline as pipeline_module
from ruminant.config import RuntimeEnvironment
from ruminant.container import build_container
from ruminant.pipeline import RenderRequest
from ruminant.resilience import FaultInjector, RetryPolicy, TransientRenderError
from ruminant.telemetry import EPOCH_BASE, MetricsStore, Pacer


def test_metrics_live_in_modification_times(cowsay, tmp_path):
    cowsay("one")
    cowsay("two")
    metrics = tmp_path / "data" / "metrics"
    assert int((metrics / "render_count.stamp").stat().st_mtime) == EPOCH_BASE + 2
    assert (metrics / "render_count.stamp").read_bytes() == b""
    assert MetricsStore(tmp_path / "data").read("render_count") == 2
    assert (metrics / "last_render_ms.stamp").exists()


def test_index_is_rebuilt_on_every_start(cowsay, tmp_path):
    for _ in range(2):
        _, _, err = cowsay("moo")
        assert "asset index corruption detected for 'default'" in err
        assert "asset index rebuilt (2 entries)" in err
    index = tmp_path / "data" / "index"
    assert int((index / "default.stamp").stat().st_mtime) == EPOCH_BASE + 5
    assert int((index / "tux.stamp").stat().st_mtime) == EPOCH_BASE + 10


def test_font_cache_miss_traceback_is_recovered(cowsay):
    _, out, err = cowsay("moo")
    assert "Traceback (most recent call last)" in err
    assert err.index("font cache miss") < err.index("recovered: glyph metrics regenerated")
    assert out.startswith(" _____\n< moo >")


def test_every_frame_is_rendered_three_times(environ, monkeypatch):
    container = build_container(RuntimeEnvironment.from_environ(environ))
    pipe = container.resolve("pipeline")
    calls = []
    original = pipeline_module.RenderPipeline.render_once
    monkeypatch.setattr(pipe, "render_once", lambda req: calls.append(req) or original(pipe, req))
    frame = pipe.render(RenderRequest(message="moo"))
    assert len(calls) == 3
    assert frame == " _____\n< moo >\n -----\n" + default_cow()


def test_injected_faults_are_retried_and_output_stays_exact(environ):
    container = build_container(RuntimeEnvironment.from_environ(environ))
    pipe = container.resolve("pipeline")
    pipe.retry.faults.rate = 1.0
    frame = pipe.render(RenderRequest(message="moo"))
    assert frame == " _____\n< moo >\n -----\n" + default_cow()


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


def test_sleep_scale_zero_never_sleeps(environ):
    container = build_container(RuntimeEnvironment.from_environ(environ))
    pacer = container.resolve("pacer")
    pacer.pause(5)
    assert pacer.total == 0


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
