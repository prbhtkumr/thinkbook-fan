"""Configuration loading and validation."""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, fields, replace
from pathlib import Path
from typing import Any

INPUT_MODES = ("max-core", "avg-core", "package", "max-all")
SOURCES = ("curve", "firmware")
POWER_STATES = ("ac", "default", "power-save")

DEFAULT_CURVES: dict[str, tuple[tuple[float, int], ...]] = {
    "auto": ((88, 7), (81, 6), (74, 5), (66, 4), (0, 0)),
    "power-save": ((94, 7), (88, 5), (82, 4), (0, 0)),
    "aggressive": ((80, 7), (74, 6), (68, 5), (60, 4), (0, 0)),
}
DEFAULT_POWER = {"ac": "auto", "default": "auto", "power-save": "power-save"}

CONFIG_ENV = "THINKBOOK_FAN_CONFIG"


class ConfigError(ValueError):
    """Raised when the configuration is invalid."""


@dataclass(frozen=True)
class PathsConfig:
    fan: str = "/proc/acpi/ibm/fan"
    state_dir: str = "/run/thinkbook-fan"
    power_supply: str = "/sys/class/power_supply"
    ac_online: str = "/sys/class/power_supply/ACAD/online"
    platform_profile: str = "/sys/firmware/acpi/platform_profile"
    hwmon_root: str = "/sys/class/hwmon"
    package_zone: str = "/sys/class/thermal/thermal_zone7/temp"
    tcpu_zone: str = "/sys/class/thermal/thermal_zone8/temp"
    state_group: str = "users"


@dataclass(frozen=True)
class DaemonConfig:
    poll_seconds: float = 2.0
    refresh_seconds: float = 30.0
    hysteresis_c: float = 3.0
    emergency_c: float = 90.0
    safety_c: float = 95.0
    low_battery_percent: int = 20
    temp_window: int = 3
    watchdog_seconds: int = 60


@dataclass(frozen=True)
class LevelsConfig:
    minimum: int = 0
    maximum: int = 7
    default_min: int = 3


@dataclass(frozen=True)
class Config:
    paths: PathsConfig
    daemon: DaemonConfig
    levels: LevelsConfig
    temperature_input: str
    curves: dict[str, tuple[tuple[float, int], ...]]
    power: dict[str, str]
    source: str | None = None

    def curve(self, name: str) -> tuple[tuple[float, int], ...]:
        return self.curves[name]

    def public_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "paths": {
                "fan": self.paths.fan,
                "state_dir": self.paths.state_dir,
                "power_supply": self.paths.power_supply,
                "ac_online": self.paths.ac_online,
                "platform_profile": self.paths.platform_profile,
                "hwmon_root": self.paths.hwmon_root,
                "package_zone": self.paths.package_zone,
                "tcpu_zone": self.paths.tcpu_zone,
                "state_group": self.paths.state_group,
            },
            "daemon": {
                "poll_seconds": self.daemon.poll_seconds,
                "refresh_seconds": self.daemon.refresh_seconds,
                "hysteresis_c": self.daemon.hysteresis_c,
                "emergency_c": self.daemon.emergency_c,
                "safety_c": self.daemon.safety_c,
                "low_battery_percent": self.daemon.low_battery_percent,
                "temp_window": self.daemon.temp_window,
                "watchdog_seconds": self.daemon.watchdog_seconds,
            },
            "levels": {
                "min": self.levels.minimum,
                "max": self.levels.maximum,
                "default_min": self.levels.default_min,
            },
            "temperature_input": self.temperature_input,
            "curves": {
                name: [[threshold, level] for threshold, level in points]
                for name, points in self.curves.items()
            },
            "power": dict(self.power),
        }


def default_config() -> Config:
    return Config(
        paths=PathsConfig(),
        daemon=DaemonConfig(),
        levels=LevelsConfig(),
        temperature_input="max-all",
        curves=dict(DEFAULT_CURVES),
        power=dict(DEFAULT_POWER),
        source=None,
    )


def load_config(path: str | os.PathLike[str] | None = None) -> Config:
    """Load configuration, falling back to built-in defaults."""
    selected: Path | None = None
    explicit = path is not None
    if path is None:
        env_path = os.environ.get(CONFIG_ENV)
        if env_path:
            selected = Path(env_path)
            explicit = True
        else:
            for candidate in (Path.cwd() / "config.toml", Path("/etc/thinkbook-fan/config.toml")):
                if candidate.is_file():
                    selected = candidate
                    break
    else:
        selected = Path(path)

    if selected is None:
        return default_config()
    if not selected.is_file():
        raise ConfigError(f"config file not found: {selected}")

    try:
        with selected.open("rb") as handle:
            data = tomllib.load(handle)
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"{selected}: {exc}") from exc
    except OSError as exc:
        raise ConfigError(f"cannot read {selected}: {exc}") from exc

    return config_from_dict(data, source=str(selected))


def config_from_dict(data: dict[str, Any], source: str | None = None) -> Config:
    if not isinstance(data, dict):
        raise ConfigError("configuration must be a table")
    known = {"paths", "daemon", "levels", "temperature", "curves", "power"}
    unknown = sorted(set(data) - known)
    if unknown:
        raise ConfigError(f"unknown configuration section(s): {', '.join(unknown)}")

    paths = _build_paths(data.get("paths"))
    daemon = _build_daemon(data.get("daemon"))
    levels = _build_levels(data.get("levels"))
    temperature_input = _build_temperature(data.get("temperature"))
    curves = _build_curves(data.get("curves"))
    power = _build_power(data.get("power"), curves)

    return Config(
        paths=paths,
        daemon=daemon,
        levels=levels,
        temperature_input=temperature_input,
        curves=curves,
        power=power,
        source=source,
    )


def _table(value: Any, section: str) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ConfigError(f"[{section}] must be a table")
    return value


def _check_keys(table: dict[str, Any], section: str, allowed: set[str]) -> None:
    unknown = sorted(set(table) - allowed)
    if unknown:
        raise ConfigError(f"unknown key(s) in [{section}]: {', '.join(unknown)}")


def _string(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value:
        raise ConfigError(f"{name} must be a non-empty string")
    return value


def _number(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ConfigError(f"{name} must be a number")
    return float(value)


def _integer(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ConfigError(f"{name} must be an integer")
    return value


def _boolean(value: Any, name: str) -> bool:
    if not isinstance(value, bool):
        raise ConfigError(f"{name} must be true or false")
    return value


def _build_paths(value: Any) -> PathsConfig:
    table = _table(value, "paths")
    allowed = {field.name for field in fields(PathsConfig)}
    _check_keys(table, "paths", allowed)
    values = {}
    for key, item in table.items():
        if key == "state_group":
            values[key] = _string(item, f"paths.{key}")
        else:
            values[key] = _string(item, f"paths.{key}")
    return replace(PathsConfig(), **values)


def _build_daemon(value: Any) -> DaemonConfig:
    table = _table(value, "daemon")
    allowed = {field.name for field in fields(DaemonConfig)}
    _check_keys(table, "daemon", allowed)
    defaults = DaemonConfig()
    poll = _number(table.get("poll_seconds", defaults.poll_seconds), "daemon.poll_seconds")
    refresh = _number(table.get("refresh_seconds", defaults.refresh_seconds), "daemon.refresh_seconds")
    hysteresis = _number(table.get("hysteresis_c", defaults.hysteresis_c), "daemon.hysteresis_c")
    emergency = _number(table.get("emergency_c", defaults.emergency_c), "daemon.emergency_c")
    safety = _number(table.get("safety_c", defaults.safety_c), "daemon.safety_c")
    low_battery = _integer(table.get("low_battery_percent", defaults.low_battery_percent), "daemon.low_battery_percent")
    window = _integer(table.get("temp_window", defaults.temp_window), "daemon.temp_window")
    watchdog = _integer(table.get("watchdog_seconds", defaults.watchdog_seconds), "daemon.watchdog_seconds")

    if poll <= 0:
        raise ConfigError("daemon.poll_seconds must be greater than 0")
    if refresh <= 0:
        raise ConfigError("daemon.refresh_seconds must be greater than 0")
    if hysteresis < 0:
        raise ConfigError("daemon.hysteresis_c cannot be negative")
    if not 0 <= emergency <= 120 or not 0 <= safety <= 120:
        raise ConfigError("temperature limits must be between 0 and 120 C")
    if emergency > safety:
        raise ConfigError("daemon.emergency_c cannot be above daemon.safety_c")
    if not 0 <= low_battery <= 100:
        raise ConfigError("daemon.low_battery_percent must be between 0 and 100")
    if window < 1:
        raise ConfigError("daemon.temp_window must be at least 1")
    if watchdog != 0 and not 1 <= watchdog <= 120:
        raise ConfigError("daemon.watchdog_seconds must be 0 or between 1 and 120")
    if watchdog > 0 and refresh > watchdog / 2:
        raise ConfigError(
            "daemon.refresh_seconds must be at most half of daemon.watchdog_seconds"
        )

    return DaemonConfig(
        poll_seconds=poll,
        refresh_seconds=refresh,
        hysteresis_c=hysteresis,
        emergency_c=emergency,
        safety_c=safety,
        low_battery_percent=low_battery,
        temp_window=window,
        watchdog_seconds=watchdog,
    )


def _build_levels(value: Any) -> LevelsConfig:
    table = _table(value, "levels")
    _check_keys(table, "levels", {"min", "max", "default_min"})
    defaults = LevelsConfig()
    minimum = _integer(table.get("min", defaults.minimum), "levels.min")
    maximum = _integer(table.get("max", defaults.maximum), "levels.max")
    default_min = _integer(table.get("default_min", defaults.default_min), "levels.default_min")
    if not 0 <= minimum <= maximum <= 7:
        raise ConfigError("levels must satisfy 0 <= min <= max <= 7")
    if not minimum <= default_min <= maximum:
        raise ConfigError("levels.default_min must be between min and max")
    return LevelsConfig(minimum=minimum, maximum=maximum, default_min=default_min)


def _build_temperature(value: Any) -> str:
    table = _table(value, "temperature")
    _check_keys(table, "temperature", {"input"})
    mode = table.get("input", "max-all")
    if mode not in INPUT_MODES:
        raise ConfigError(f"temperature.input must be one of: {', '.join(INPUT_MODES)}")
    return mode


def _build_curves(value: Any) -> dict[str, tuple[tuple[float, int], ...]]:
    curves = dict(DEFAULT_CURVES)
    table = _table(value, "curves")
    for name, spec in table.items():
        if not isinstance(name, str) or not name:
            raise ConfigError("curve names must be non-empty strings")
        if not isinstance(spec, dict):
            raise ConfigError(f"[curves.{name}] must be a table")
        _check_keys(spec, f"curves.{name}", {"points"})
        raw_points = spec.get("points")
        if not isinstance(raw_points, list) or not raw_points:
            raise ConfigError(f"curves.{name}.points must be a non-empty array")
        points: list[tuple[float, int]] = []
        for index, point in enumerate(raw_points):
            if not isinstance(point, (list, tuple)) or len(point) != 2:
                raise ConfigError(f"curves.{name}.points[{index}] must be [temperature, level]")
            threshold = _number(point[0], f"curves.{name}.points[{index}].temperature")
            level = _integer(point[1], f"curves.{name}.points[{index}].level")
            if not 0 <= level <= 7:
                raise ConfigError(f"curves.{name}.points[{index}].level must be between 0 and 7")
            points.append((threshold, level))
        points.sort(key=lambda item: item[0], reverse=True)
        if len({threshold for threshold, _ in points}) != len(points):
            raise ConfigError(f"curves.{name} has duplicate temperature thresholds")
        curves[name] = tuple(points)
    if not curves:
        raise ConfigError("at least one curve must be defined")
    return curves


def _build_power(value: Any, curves: dict[str, tuple[tuple[float, int], ...]]) -> dict[str, str]:
    table = _table(value, "power")
    _check_keys(table, "power", set(POWER_STATES))
    power = dict(DEFAULT_POWER)
    for state, name in table.items():
        if not isinstance(name, str) or name not in curves:
            raise ConfigError(f"power.{state} must name a defined curve")
        power[state] = name
    for state in POWER_STATES:
        if power[state] not in curves:
            raise ConfigError(f"power.{state} names an unknown curve: {power[state]}")
    return power
