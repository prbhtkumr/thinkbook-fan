"""Hardware access for the fan, temperature sensors, and power state."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from .config import Config


def read_int(path: str | os.PathLike[str]) -> int | None:
    try:
        with open(path) as handle:
            return int(handle.read().strip())
    except (OSError, ValueError):
        return None


def read_string(path: str | os.PathLike[str]) -> str:
    try:
        with open(path) as handle:
            return handle.read().strip()
    except OSError:
        return ""


class Hardware:
    def __init__(self, config: Config):
        self.config = config
        self.paths = config.paths

    # ------------------------------------------------------------------ fan
    def fan_available(self) -> bool:
        return Path(self.paths.fan).exists()

    def write_level(self, level: int) -> None:
        with open(self.paths.fan, "w") as handle:
            handle.write(f"level {level}\n")

    def restore_auto(self) -> None:
        with open(self.paths.fan, "w") as handle:
            handle.write("level auto\n")

    # ------------------------------------------------------------ temperature
    def read_temperatures(self) -> dict[str, Any]:
        cores: list[float] = []
        package: float | None = None
        tcpu: float | None = None

        try:
            hwmons = os.listdir(self.paths.hwmon_root)
        except OSError:
            hwmons = []
        for entry in hwmons:
            base = os.path.join(self.paths.hwmon_root, entry)
            if read_string(os.path.join(base, "name")) != "coretemp":
                continue
            try:
                files = os.listdir(base)
            except OSError:
                continue
            for name in files:
                if not name.startswith("temp") or not name.endswith("_input"):
                    continue
                millideg = read_int(os.path.join(base, name))
                if millideg is None:
                    continue
                value = millideg / 1000.0
                if name == "temp1_input":
                    package = value if package is None else max(package, value)
                else:
                    cores.append(value)

        package_zone = read_int(self.paths.package_zone)
        if package_zone is not None:
            value = package_zone / 1000.0
            package = value if package is None else max(package, value)

        tcpu_zone = read_int(self.paths.tcpu_zone)
        if tcpu_zone is not None:
            tcpu = tcpu_zone / 1000.0

        return {"cores": cores, "package": package, "tcpu": tcpu}

    def select_temp(self, mode: str, temps: dict[str, Any]) -> float | None:
        cores = temps.get("cores") or []
        package = temps.get("package")
        tcpu = temps.get("tcpu")

        values = list(cores)
        if package is not None:
            values.append(package)
        if tcpu is not None:
            values.append(tcpu)
        max_all = max(values) if values else None

        if mode == "max-core" and cores:
            return max(cores)
        if mode == "avg-core" and cores:
            return sum(cores) / len(cores)
        if mode == "package" and package is not None:
            return package
        return max_all

    # ------------------------------------------------------------------ power
    def battery_capacity(self) -> int | None:
        try:
            supplies = os.listdir(self.paths.power_supply)
        except OSError:
            return None
        for entry in supplies:
            base = os.path.join(self.paths.power_supply, entry)
            if read_string(os.path.join(base, "type")) != "Battery":
                continue
            return read_int(os.path.join(base, "capacity"))
        return None

    def platform_profile(self) -> str:
        return read_string(self.paths.platform_profile)

    def power_state(self, ac: bool) -> str:
        if ac:
            return "ac"
        capacity = self.battery_capacity()
        if self.platform_profile() == "low-power" or (
            capacity is not None and capacity <= self.config.daemon.low_battery_percent
        ):
            return "power-save"
        return "default"

    def on_ac(self) -> bool:
        if read_int(self.paths.ac_online) == 1:
            return True
        try:
            supplies = os.listdir(self.paths.power_supply)
        except OSError:
            return False
        for entry in supplies:
            base = os.path.join(self.paths.power_supply, entry)
            if read_string(os.path.join(base, "type")) != "Battery":
                continue
            status = read_string(os.path.join(base, "status"))
            if status in ("Charging", "Full", "Not charging"):
                return True
        return False
