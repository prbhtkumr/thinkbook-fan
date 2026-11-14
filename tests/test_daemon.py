from dataclasses import replace

from thinkbook_fan.config import default_config
from thinkbook_fan.control import ControlFiles
from thinkbook_fan.daemon import FanDaemon


class FakeHardware:
    def __init__(self, temp=50.0, ac=True):
        self.temp = temp
        self.ac = ac
        self.levels = []
        self.auto = False
        self.watchdog = None

    def fan_available(self):
        return True

    def write_level(self, level):
        self.levels.append(level)

    def set_watchdog(self, seconds):
        self.watchdog = seconds

    def restore_auto(self):
        self.auto = True

    def read_temperatures(self):
        return {"cores": [self.temp], "package": self.temp, "tcpu": self.temp}

    def select_temp(self, mode, temps):
        return self.temp

    def on_ac(self):
        return self.ac

    def power_state(self, ac):
        return "ac" if ac else "default"


def make_daemon(tmp_path, temp=50.0, min_level=None, pin=None, once=False, dry_run=False, watchdog=60):
    config = default_config()
    paths = replace(config.paths, state_dir=str(tmp_path / "run"))
    daemon_config = replace(config.daemon, watchdog_seconds=watchdog)
    config = replace(config, paths=paths, daemon=daemon_config)
    control = ControlFiles(config)
    control.ensure()
    if min_level is not None:
        control.set_min(min_level)
    if pin is not None:
        control.set_pin(pin)
    hardware = FakeHardware(temp=temp)
    daemon = FanDaemon(config, control, hardware, once=once, dry_run=dry_run)
    return daemon, control, hardware


def test_default_floor_keeps_level_three(tmp_path):
    daemon, control, hardware = make_daemon(tmp_path)
    status = daemon.iteration()
    assert hardware.levels == [3]
    assert status["level"] == 3
    assert status["mode"] == "ac"
    assert control.read_status()["level"] == 3


def test_zero_floor_allows_level_zero(tmp_path):
    daemon, _, hardware = make_daemon(tmp_path, min_level=0)
    status = daemon.iteration()
    assert hardware.levels == [0]
    assert status["level"] == 0


def test_pin_takes_priority(tmp_path):
    daemon, _, hardware = make_daemon(tmp_path, min_level=0, pin=5)
    status = daemon.iteration()
    assert hardware.levels == [5]
    assert status["pin"] == 5
    assert status["mode"] == "pin"


def test_pin_jumps_to_level(tmp_path):
    daemon, control, hardware = make_daemon(tmp_path, min_level=0)
    daemon.iteration()
    control.set_pin(5)
    daemon.iteration()
    assert hardware.levels == [0, 5]


def test_emergency_jumps_to_max(tmp_path):
    daemon, _, hardware = make_daemon(tmp_path, temp=95.0)
    status = daemon.iteration()
    assert hardware.levels == [7]
    assert status["level"] == 7


def test_run_once_writes_status(tmp_path):
    daemon, control, hardware = make_daemon(tmp_path, once=True)
    assert daemon.run() == 0
    assert hardware.levels == [3]
    assert hardware.watchdog == 60
    assert hardware.auto is False
    status = control.read_status()
    assert status["level"] == 3
    assert status["commanded"] == 3
    assert status["watchdog"] == 60
    assert status["min"] == 3


def test_dry_run_does_not_touch_fan(tmp_path):
    daemon, control, hardware = make_daemon(tmp_path, once=True, dry_run=True)
    assert daemon.run() == 0
    assert hardware.levels == []
    assert hardware.watchdog is None
    status = control.read_status()
    assert status["level"] == 3
    assert status["dry_run"] is True


def test_watchdog_can_be_disabled(tmp_path):
    daemon, _, hardware = make_daemon(tmp_path, once=True, watchdog=0)
    assert daemon.run() == 0
    assert hardware.watchdog is None


def test_shutdown_disables_watchdog_and_restores_auto(tmp_path):
    daemon, control, hardware = make_daemon(tmp_path)
    hardware.watchdog = 60
    daemon._shutdown()
    assert hardware.watchdog == 0
    assert hardware.auto is True
    assert control.read_status()["mode"] == "off"
