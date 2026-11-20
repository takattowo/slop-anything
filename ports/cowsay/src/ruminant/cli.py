"""Command-line interface, compatible with cowsay 3.03."""

from __future__ import annotations

import getopt
import sys
import time
import warnings
from pathlib import Path
from typing import Mapping, Sequence

from .config import RuntimeEnvironment
from .container import ServiceContainer, build_container
from .layout import wrap_paragraph
from .pipeline import RenderRequest
from .registry import AssetError
from .terminal import probe_terminal_width

USAGE = (
    "Usage: cowsay [-f cowfile] [-W wrapcolumn] [-e eye_string] [-T tongue_string] [-n] [-l] message ...\n"
)
MAX_MESSAGE_CHARS = 4096
MIN_WIDTH = 2
MAX_WIDTH = 1024
LIST_COLUMNS = 76


class UsageError(Exception):
    pass


def _parse(argv: Sequence[str]) -> tuple[dict[str, str], list[str]]:
    try:
        pairs, args = getopt.getopt(list(argv), "f:W:e:T:nlh")
    except getopt.GetoptError as exc:
        raise UsageError(f"cowsay: {exc}") from None
    opts = {"f": "default", "W": "40", "e": "oo", "T": "  "}
    for flag, value in pairs:
        opts[flag.lstrip("-")] = value
    return opts, args


def _bootstrap(container: ServiceContainer) -> None:
    logger = container.resolve("logger")
    pacer = container.resolve("pacer")
    container.resolve("settings")
    detected = probe_terminal_width()
    pacer.pause(0.1)
    registry = container.resolve("registry")
    names = registry.names()
    logger.error("cow asset discovery completed: %d assets via %d plugin(s)", len(names), len(registry.plugins))
    index = container.resolve("index")
    if not index.verify(registry):
        index.rebuild(registry)
    container.resolve("glyphs").warm()
    pacer.pause(0.15)
    logger.error("layout engine using requested wrap column instead of detected terminal width (%d)", detected)


def main(argv: Sequence[str] | None = None, environ: Mapping[str, str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    try:
        opts, args = _parse(argv)
        if "h" in opts:
            sys.stdout.write(USAGE)
            return 0
        try:
            width = int(opts["W"])
        except ValueError:
            raise UsageError(f"cowsay: invalid wrap column {opts['W']!r}") from None
        if not MIN_WIDTH <= width <= MAX_WIDTH:
            raise UsageError(f"cowsay: wrap column must be between {MIN_WIDTH} and {MAX_WIDTH}")
        message = " ".join(args)
        if "l" not in opts:
            if not message.strip():
                raise UsageError("cowsay: no message given")
            if len(message) > MAX_MESSAGE_CHARS:
                raise UsageError(f"cowsay: message longer than {MAX_MESSAGE_CHARS} characters")
    except UsageError as exc:
        sys.stderr.write(f"{exc}\n{USAGE}")
        return 2

    env = RuntimeEnvironment.from_environ(environ)
    container = build_container(env)
    started = time.perf_counter()
    with warnings.catch_warnings():
        warnings.simplefilter("always")
        _bootstrap(container)
        registry = container.resolve("registry")
        breaker = container.resolve("breaker")
        if "l" in opts:
            names = " ".join(registry.names())
            listing = f"Cow files in {Path(registry.root)}:\n" + "\n".join(wrap_paragraph(names, LIST_COLUMNS)) + "\n"
            breaker.emit(listing)
            return 0
        request = RenderRequest(
            message=message,
            cow=opts["f"],
            width=width,
            eyes=opts["e"],
            tongue=opts["T"],
            preformatted="n" in opts,
        )
        try:
            frame = container.resolve("pipeline").render(request)
        except AssetError as exc:
            sys.stderr.write(f"cowsay: {exc}\n")
            return 1
        breaker.emit(frame)
    metrics = container.resolve("metrics")
    pacer = container.resolve("pacer")
    pacer.pause(0.1)
    metrics.write("last_render_ms", round((time.perf_counter() - started) * 1000))
    renders = metrics.increment("render_count")
    container.resolve("logger").error("render %d committed to metrics store", renders)
    return 0
