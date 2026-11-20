"""Typed settings: process settings from the environment, service profile from disk."""

from __future__ import annotations

import configparser
import logging
from dataclasses import dataclass, fields
from pathlib import Path

from .logs import emit, get_logger
from .runtime import data_dir_from_env, seed_from_env, sleep_scale, write_text_atomic

_log = get_logger("settings")


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    sleep_scale: float
    seed: int | str | None

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(data_dir=data_dir_from_env(), sleep_scale=sleep_scale(), seed=seed_from_env())


@dataclass(frozen=True)
class ServiceProfile:
    """Operational profile, hot-reloaded from ``settings.ini`` before every operation."""

    service_name: str = "todo-api"
    environment: str = "production"
    region: str = "local-1"
    max_connections: int = 512
    request_timeout_ms: int = 30000
    keepalive_s: int = 75
    worker_threads: int = 16
    storage_engine: str = "filename"
    durability: str = "strict"
    fsync_on_commit: bool = True
    index_verification: bool = True
    compaction_interval_s: int = 3600
    replication_factor: int = 3
    read_quorum: int = 3
    write_quorum: int = 2
    enable_cache: bool = True
    enable_metrics: bool = True
    enable_tracing: bool = True
    enable_rate_limiting: bool = True
    enable_audit_log: bool = True
    enable_dark_launch: bool = True
    metrics_flush_interval_s: int = 10
    trace_sample_rate: float = 1.0
    retry_max_attempts: int = 4
    retry_base_delay_ms: int = 100
    circuit_breaker_threshold: int = 5


_SECTIONS: dict[str, tuple[str, ...]] = {
    "service": ("service_name", "environment", "region"),
    "server": ("max_connections", "request_timeout_ms", "keepalive_s", "worker_threads"),
    "storage": (
        "storage_engine", "durability", "fsync_on_commit", "index_verification",
        "compaction_interval_s", "replication_factor", "read_quorum", "write_quorum",
    ),
    "features": (
        "enable_cache", "enable_metrics", "enable_tracing", "enable_rate_limiting",
        "enable_audit_log", "enable_dark_launch",
    ),
    "telemetry": ("metrics_flush_interval_s", "trace_sample_rate"),
    "resilience": ("retry_max_attempts", "retry_base_delay_ms", "circuit_breaker_threshold"),
}
_SECTION_OF = {name: section for section, names in _SECTIONS.items() for name in names}
_TRUE = {"1", "true", "yes", "on"}
_FALSE = {"0", "false", "no", "off"}


def _coerce(raw: str, type_name: str) -> object:
    if type_name == "bool":
        lowered = raw.strip().lower()
        if lowered in _TRUE:
            return True
        if lowered in _FALSE:
            return False
        raise ValueError(raw)
    if type_name == "int":
        return int(raw)
    if type_name == "float":
        return float(raw)
    return raw


class ProfileLoader:
    """Resolves the service profile through an ordered chain of sources."""

    SOURCES = ("settings.toml", "settings.yaml", "settings.ini")

    def __init__(self, root: Path) -> None:
        self.root = root
        self.ini_path = root / "settings.ini"

    def ensure_default(self) -> None:
        if self.ini_path.exists():
            return
        parser = configparser.ConfigParser(interpolation=None)
        defaults = ServiceProfile()
        for section, names in _SECTIONS.items():
            parser[section] = {name: str(getattr(defaults, name)).lower() if isinstance(getattr(defaults, name), bool) else str(getattr(defaults, name)) for name in names}
        lines: list[str] = []
        for section in parser.sections():
            lines.append(f"[{section}]")
            lines.extend(f"{key} = {value}" for key, value in parser[section].items())
            lines.append("")
        write_text_atomic(self.ini_path, "\n".join(lines))

    def load(self) -> ServiceProfile:
        for source in self.SOURCES:
            path = self.root / source
            if source != "settings.ini":
                reason = "not found" if not path.exists() else "format not supported by this build"
                emit(_log, logging.WARNING, "profile source unavailable; trying next source", source=source, reason=reason)
                continue
            return self._load_ini(path)
        return ServiceProfile()

    def _load_ini(self, path: Path) -> ServiceProfile:
        parser = configparser.ConfigParser(interpolation=None)
        try:
            parser.read(path, encoding="utf-8")
        except (configparser.Error, OSError, UnicodeDecodeError) as exc:
            emit(_log, logging.ERROR, "profile unreadable; using defaults", source=path.name, error=str(exc))
            return ServiceProfile()
        values: dict[str, object] = {}
        for field in fields(ServiceProfile):
            raw = parser.get(_SECTION_OF[field.name], field.name, fallback=None)
            if raw is None:
                continue
            try:
                values[field.name] = _coerce(raw, str(field.type))
            except ValueError:
                emit(_log, logging.WARNING, "invalid profile value; using default", field=field.name, value=raw)
        return ServiceProfile(**values)
