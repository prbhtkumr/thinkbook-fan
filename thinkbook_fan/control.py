"""File-based control and status interface.

The layout under the state directory is intentionally compatible with the
Plasma widget:

    pin         optional integer level
    min-level   integer floor
    curves      ac=NAME / default=NAME / power-save=NAME
    input       temperature input mode
    source      curve or firmware
    state       JSON status written by the daemon
"""

from __future__ import annotations

import grp
import json
import os
import tempfile
import threading
from pathlib import Path
from typing import Any

from .config import INPUT_MODES, POWER_STATES, SOURCES, Config


class ControlFiles:
    def __init__(self, config: Config):
        self.config = config
        self.dir = Path(config.paths.state_dir)
        self.pin_path = self.dir / "pin"
        self.min_path = self.dir / "min-level"
        self.curves_path = self.dir / "curves"
        self.input_path = self.dir / "input"
        self.source_path = self.dir / "source"
        self.status_path = self.dir / "state"
        self._curve_lock = threading.Lock()

    # ------------------------------------------------------------------ setup
    def ensure(self) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)
        try:
            os.chmod(self.dir, 0o775)
        except OSError:
            pass
        group = self.config.paths.state_group
        if group and os.geteuid() == 0:
            try:
                gid = grp.getgrnam(group).gr_gid
                os.chown(self.dir, 0, gid)
            except (KeyError, OSError):
                pass

    # ------------------------------------------------------------------ files
    def _read_text(self, path: Path) -> str:
        try:
            return path.read_text().strip()
        except OSError:
            return ""

    def _read_int(self, path: Path) -> int | None:
        try:
            return int(self._read_text(path))
        except ValueError:
            return None

    def _write(self, path: Path, text: str, mode: int) -> None:
        self.ensure()
        fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=self.dir)
        try:
            with os.fdopen(fd, "w") as handle:
                handle.write(text)
                handle.flush()
                os.fsync(handle.fileno())
            os.chmod(temp_name, mode)
            os.replace(temp_name, path)
        except BaseException:
            try:
                os.unlink(temp_name)
            except OSError:
                pass
            raise

    def _remove(self, path: Path) -> None:
        try:
            path.unlink()
        except FileNotFoundError:
            pass
        except OSError as exc:
            raise OSError(f"cannot remove {path}: {exc}") from exc

    # ------------------------------------------------------------------ pin
    def read_pin(self) -> int | None:
        value = self._read_int(self.pin_path)
        if value is None or not 0 <= value <= self.config.levels.maximum:
            return None
        return value

    def set_pin(self, level: int) -> int:
        level = int(level)
        if not 0 <= level <= self.config.levels.maximum:
            raise ValueError(
                f"level must be between 0 and {self.config.levels.maximum}"
            )
        self._write(self.pin_path, str(level), 0o664)
        return level

    def clear_pin(self) -> None:
        self._remove(self.pin_path)

    # ------------------------------------------------------------------ floor
    def read_min(self) -> int:
        value = self._read_int(self.min_path)
        levels = self.config.levels
        if value is None:
            return levels.default_min
        return max(levels.minimum, min(levels.maximum, value))

    def set_min(self, level: int) -> int:
        level = int(level)
        levels = self.config.levels
        if not levels.minimum <= level <= levels.maximum:
            raise ValueError(
                f"minimum level must be between {levels.minimum} and {levels.maximum}"
            )
        self._write(self.min_path, str(level), 0o664)
        return level

    # ------------------------------------------------------------------ curves
    def read_curves(self) -> dict[str, str]:
        curves = dict(self.config.power)
        for line in self._read_text(self.curves_path).splitlines():
            key, separator, value = line.partition("=")
            if not separator:
                continue
            key = key.strip()
            value = value.strip()
            if key in POWER_STATES and value in self.config.curves:
                curves[key] = value
        return curves

    def set_curve(self, state: str, curve: str) -> str:
        if state not in POWER_STATES:
            raise ValueError(f"state must be one of: {', '.join(POWER_STATES)}")
        if curve not in self.config.curves:
            raise ValueError(f"unknown curve: {curve}")
        with self._curve_lock:
            curves = self.read_curves()
            curves[state] = curve
            text = "".join(f"{name}={curves[name]}\n" for name in POWER_STATES)
            self._write(self.curves_path, text, 0o664)
        return curve

    # ------------------------------------------------------------------ input
    def read_input(self) -> str:
        value = self._read_text(self.input_path)
        if value in INPUT_MODES:
            return value
        return self.config.temperature_input

    def set_input(self, mode: str) -> str:
        if mode not in INPUT_MODES:
            raise ValueError(f"input must be one of: {', '.join(INPUT_MODES)}")
        self._write(self.input_path, mode, 0o664)
        return mode

    # ------------------------------------------------------------------ source
    def read_source(self) -> str:
        return "firmware" if self._read_text(self.source_path) == "firmware" else "curve"

    def set_source(self, source: str) -> str:
        if source not in SOURCES:
            raise ValueError(f"source must be one of: {', '.join(SOURCES)}")
        self._write(self.source_path, source, 0o664)
        return source

    # ------------------------------------------------------------------ status
    def read_status(self) -> dict[str, Any] | None:
        try:
            with self.status_path.open() as handle:
                data = json.load(handle)
        except (OSError, ValueError):
            return None
        return data if isinstance(data, dict) else None

    def write_status(self, data: dict[str, Any]) -> None:
        text = json.dumps(data, separators=(",", ":"))
        self._write(self.status_path, text, 0o644)
