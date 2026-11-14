from dataclasses import replace

from thinkbook_fan.config import default_config
from thinkbook_fan.hardware import Hardware


def make_hardware(tmp_path):
    fan = tmp_path / "fan"
    fan.write_text("old\n")
    config = default_config()
    config = replace(config, paths=replace(config.paths, fan=str(fan)))
    return Hardware(config), fan


def test_set_watchdog_and_level(tmp_path):
    hardware, fan = make_hardware(tmp_path)
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
