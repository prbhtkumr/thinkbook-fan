from dataclasses import replace

import pytest

from thinkbook_fan.config import default_config
from thinkbook_fan.control import ControlFiles


def make_control(tmp_path, **level_overrides):
    config = default_config()
    paths = replace(config.paths, state_dir=str(tmp_path / "run"))
    levels = replace(config.levels, **level_overrides) if level_overrides else config.levels
    return ControlFiles(replace(config, paths=paths, levels=levels))


def test_min_level_round_trip(tmp_path):
    control = make_control(tmp_path)
    control.ensure()
    assert control.read_min() == 3
    assert control.set_min(0) == 0
    assert control.read_min() == 0
    assert control.set_min(7) == 7
    assert control.read_min() == 7
    with pytest.raises(ValueError):
        control.set_min(8)


def test_min_level_clamps_file_values(tmp_path):
    control = make_control(tmp_path)
    control.ensure()
    control.min_path.write_text("99\n")
    assert control.read_min() == 7
    control.min_path.write_text("-2\n")
    assert control.read_min() == 0
    control.min_path.write_text("nonsense")
    assert control.read_min() == 3


def test_pin_round_trip(tmp_path):
    control = make_control(tmp_path)
    control.ensure()
    assert control.read_pin() is None
    control.set_pin(0)
    assert control.read_pin() == 0
    control.set_pin(7)
    assert control.read_pin() == 7
    with pytest.raises(ValueError):
        control.set_pin(8)
    control.clear_pin()
    assert control.read_pin() is None


def test_curves_round_trip(tmp_path):
    control = make_control(tmp_path)
    control.ensure()
    assert control.read_curves() == {
        "ac": "auto",
        "default": "auto",
        "power-save": "power-save",
    }
    control.set_curve("ac", "aggressive")
    assert control.read_curves()["ac"] == "aggressive"
    assert "default=auto" in control.curves_path.read_text()
    with pytest.raises(ValueError):
        control.set_curve("ac", "missing")
    with pytest.raises(ValueError):
        control.set_curve("wrong", "auto")


def test_input_round_trip(tmp_path):
    control = make_control(tmp_path)
    control.ensure()
    assert control.read_input() == "max-all"
    control.set_input("package")
    assert control.read_input() == "package"
    with pytest.raises(ValueError):
        control.set_input("nonsense")


def test_status_round_trip(tmp_path):
    control = make_control(tmp_path)
    control.ensure()
    assert control.read_status() is None
    status = {"level": 3, "mode": "ac", "temp": 45}
    control.write_status(status)
    assert control.read_status() == status
