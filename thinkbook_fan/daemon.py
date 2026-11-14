"""The fan curve loop."""

from __future__ import annotations

import logging
import signal
import threading
import time
from typing import Any

from .config import Config
from .control import ControlFiles
from .curves import compute_target, desired_level, median_window
from .hardware import Hardware

LOGGER = logging.getLogger("thinkbook_fan.daemon")


class FanDaemon:
    def __init__(
        self,
        config: Config,
        control: ControlFiles | None = None,
        hardware: Hardware | None = None,
        *,
        dry_run: bool = False,
        once: bool = False,
        logger: logging.Logger | None = None,
    ):
        self.config = config
        self.control = control or ControlFiles(config)
        self.hardware = hardware or Hardware(config)
        self.dry_run = dry_run
        self.once = once
        self.logger = logger or LOGGER
        self.stopping = threading.Event()

        self.current: int | None = None
        self.last_ac: bool | None = None
        self.last_write = 0.0
        self.last_temp: float | None = None
        self.temp_history: list[float] = []
        self.last_input: str | None = None
        self._last_mismatch: str | None = None

    # ------------------------------------------------------------------ loop
    def run(self) -> int:
        self.control.ensure()
        if not self.dry_run and not self.hardware.fan_available():
            self.logger.error("fan interface not present: %s", self.config.paths.fan)
            return 1
        if not self._prepare_fan():
            return 1

        if not self.once:
            self._install_signals()
        try:
            while not self.stopping.is_set():
                self.iteration()
                if self.once:
                    break
                self.stopping.wait(self.config.daemon.poll_seconds)
        finally:
            if not self.once:
                self._shutdown()
        return 0

    def iteration(self) -> dict[str, Any] | None:
        control = self.control
        daemon_config = self.config.daemon

        input_mode = control.read_input()
        if input_mode != self.last_input:
            self.temp_history = []
            self.last_input = input_mode

        temp = self.hardware.select_temp(input_mode, self.hardware.read_temperatures())
        if temp is None:
            self.logger.debug("no temperature reading, waiting")
            return None

        self.last_temp = temp
        self.temp_history.append(temp)
        if len(self.temp_history) > daemon_config.temp_window:
            self.temp_history.pop(0)
        control_temp = median_window(self.temp_history, daemon_config.temp_window)

        ac = self.hardware.on_ac()
        state_name = self.hardware.power_state(ac)
        selected_curves = control.read_curves()
        curve_name = selected_curves.get(state_name, self.config.power[state_name])
        if curve_name not in self.config.curves:
            curve_name = self.config.power[state_name]
        curve = self.config.curves[curve_name]

        min_level = control.read_min()
        pin = control.read_pin()
        pin_active = pin is not None and control_temp < daemon_config.safety_c
        emergency = control_temp >= daemon_config.emergency_c
        max_level = self.config.levels.maximum

        if pin_active:
            want = max(min_level, pin)
        elif emergency:
            want = max_level
        else:
            want = max(min_level, desired_level(control_temp, curve))

        if ac != self.last_ac:
            self.current = None
            self.last_ac = ac

        target = compute_target(
            current=self.current,
            want=want,
            curve=curve,
            control_temp=control_temp,
            min_level=min_level,
            max_level=max_level,
            pin_active=pin_active,
            emergency=emergency,
            hysteresis_c=daemon_config.hysteresis_c,
        )

        if target != self.current:
            self._apply_level(target, pin_active)
        elif self.current is not None and time.monotonic() - self.last_write >= daemon_config.refresh_seconds:
            self._apply_level(self.current, pin_active, refresh=True)

        fan = self.hardware.read_fan()
        rpm = fan.speed if fan is not None else None
        ec_level = fan.level if fan is not None else None
        if fan is not None and not self.dry_run:
            actual = fan.numeric_level
            if actual is not None:
                if self.current is None or actual != self.current:
                    self._log_mismatch(ec_level)
                    self.current = actual
                else:
                    self._last_mismatch = None
            elif fan.level is not None and self.current is not None:
                self._log_mismatch(ec_level)
                self.current = None

        mode = "pin" if pin_active else state_name
        effective_pin = max(min_level, pin) if pin_active else None
        status = {
            "level": self.current,
            "mode": mode,
            "curve": curve_name,
            "state": state_name,
            "min": min_level,
            "input": input_mode,
            "temp": round(temp),
            "control": round(control_temp),
            "ac": bool(ac),
            "pin": effective_pin,
            "commanded": target,
            "rpm": rpm,
            "ec_level": ec_level,
            "watchdog": daemon_config.watchdog_seconds,
            "updated": int(time.time()),
        }
        if self.dry_run:
            status["dry_run"] = True
        try:
            control.write_status(status)
        except OSError as exc:
            self.logger.error("cannot write status: %s", exc)
        return status

    def _apply_level(self, level: int, pin_active: bool, refresh: bool = False) -> None:
        if self.dry_run:
            self.logger.info(
                "would set fan level %s%s%s",
                level,
                " (pin)" if pin_active else "",
                " (refresh)" if refresh else "",
            )
            self.current = level
            self.last_write = time.monotonic()
            return
        try:
            self.hardware.write_level(level)
        except OSError as exc:
            self.logger.error("fan write failed: %s", exc)
            return
        self.current = level
        self.last_write = time.monotonic()
        if not refresh:
            self.logger.info(
                "fan level -> %s%s", level, " (pin)" if pin_active else ""
            )

    # ------------------------------------------------------------- lifecycle
    def _prepare_fan(self) -> bool:
        fan = self.hardware.read_fan()
        if fan is None:
            self.logger.warning(
                "fan read-back unavailable, continuing write-only"
            )
        else:
            if fan.command_lines and not fan.supports("level"):
                self.logger.error(
                    "thinkpad_acpi fan_control=1 is not enabled"
                )
                return False
            speed = f", {fan.speed} rpm" if fan.speed is not None else ""
            self.logger.info("fan read-back available%s", speed)

        seconds = self.config.daemon.watchdog_seconds
        if seconds <= 0:
            self.logger.info("EC watchdog disabled")
            return True
        if fan is not None and fan.command_lines and not fan.supports("watchdog"):
            self.logger.warning("EC watchdog is not supported by this fan interface")
            return True
        if self.dry_run:
            self.logger.info("would set EC watchdog to %s seconds", seconds)
            return True
        try:
            self.hardware.set_watchdog(seconds)
            self.logger.info("EC watchdog set to %s seconds", seconds)
        except OSError as exc:
            self.logger.warning("cannot set EC watchdog: %s", exc)
        return True

    def _log_mismatch(self, ec_level: str | None) -> None:
        key = str(ec_level)
        if key == self._last_mismatch:
            return
        self._last_mismatch = key
        if ec_level is None:
            self.logger.warning("EC fan level is unreadable, re-asserting")
        elif ec_level.isdigit():
            self.logger.warning(
                "EC fan level %s differs from the commanded level, re-asserting",
                ec_level,
            )
        else:
            self.logger.warning(
                "EC fan is at %s instead of the commanded level, re-asserting",
                ec_level,
            )

    def _install_signals(self) -> None:
        if threading.current_thread() is not threading.main_thread():
            return

        def stop(_signum: int, _frame: Any) -> None:
            self.stopping.set()

        signal.signal(signal.SIGTERM, stop)
        signal.signal(signal.SIGINT, stop)

    def _shutdown(self) -> None:
        status = {
            "level": None,
            "mode": "off",
            "curve": None,
            "state": None,
            "input": None,
            "temp": None if self.last_temp is None else round(self.last_temp),
            "control": None,
            "ac": bool(self.hardware.on_ac()),
            "pin": None,
            "updated": int(time.time()),
        }
        try:
            self.control.write_status(status)
        except OSError as exc:
            self.logger.error("cannot write shutdown status: %s", exc)
        if self.dry_run:
            return
        if self.config.daemon.watchdog_seconds > 0:
            try:
                self.hardware.set_watchdog(0)
                self.logger.info("EC watchdog disabled")
            except OSError as exc:
                self.logger.warning("failed to disable EC watchdog: %s", exc)
        try:
            self.hardware.restore_auto()
            self.logger.info("restored fan level auto")
        except OSError as exc:
            self.logger.error("failed to restore fan auto: %s", exc)
