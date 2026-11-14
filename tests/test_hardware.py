from dataclasses import replace

from thinkbook_fan.config import default_config
from thinkbook_fan.hardware import Hardware

FAN_TEXT = """status: enabled
speed: 3200
level: 4
commands: level <level> (<level> is 0-7, auto, disengaged, full-speed)
commands: enable, disable
commands: watchdog <timeout> (<timeout> is 0 (off), 1-120 (seconds))
"""


def make_hardware(tmp_path, text=None):
    fan = tmp_path / "fan"
    if text is not None:
        fan.write_text(text)
    config = default_config()
    config = replace(config, paths=replace(config.paths, fan=str(fan)))
    return Hardware(config), fan


def test_read_fan_parses_status_speed_level_and_commands(tmp_path):
    hardware, _ = make_hardware(tmp_path, FAN_TEXT)
    status = hardware.read_fan()
    assert status is not None
    assert status.level == "4"
    assert status.numeric_level == 4
    assert status.speed == 3200
    assert status.status == "enabled"
    assert status.supports("level")
    assert status.supports("watchdog")
    assert status.supports("enable")


def test_read_fan_handles_auto_and_missing(tmp_path):
    hardware, _ = make_hardware(tmp_path, "status: disabled\nspeed: 0\nlevel: auto\n")
    status = hardware.read_fan()
    assert status is not None
    assert status.level == "auto"
    assert status.numeric_level is None
    assert status.speed == 0

    hardware, _ = make_hardware(tmp_path / "missing", None)
    assert hardware.read_fan() is None


def test_set_watchdog_and_level(tmp_path):
    hardware, fan = make_hardware(tmp_path, FAN_TEXT)
    hardware.set_watchdog(60)
    assert fan.read_text() == "watchdog 60\n"
    hardware.set_watchdog(0)
    assert fan.read_text() == "watchdog 0\n"
    hardware.write_level(3)
    assert fan.read_text() == "level 3\n"

    try:
        hardware.set_watchdog(121)
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError")
