import textwrap

import pytest

from thinkbook_fan.config import ConfigError, config_from_dict, default_config, load_config


def test_defaults_allow_zero_and_keep_default_floor():
    config = default_config()
    assert config.levels.minimum == 0
    assert config.levels.default_min == 3
    assert config.curves["auto"][-1] == (0, 0)
    assert config.power["power-save"] == "power-save"
    assert config.daemon.watchdog_seconds == 60


def test_load_custom_config(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text(
        textwrap.dedent(
            """
            [levels]
            min = 0
            max = 7
            default_min = 0

            [temperature]
            input = "package"

            [curves.eco]
            points = [[70, 4], [0, 0]]

            [power]
            ac = "eco"
            """
        )
    )
    config = load_config(path)
    assert config.temperature_input == "package"
    assert config.curves["eco"] == ((70.0, 4), (0.0, 0))
    assert config.power["ac"] == "eco"


@pytest.mark.parametrize(
    "body, message",
    [
        ("[levels]\nmin = 5\nmax = 3\n", "levels"),
        ("[levels]\nmin = 0\nmax = 7\ndefault_min = 8\n", "default_min"),
        ("[temperature]\ninput = \"nope\"\n", "temperature.input"),
        ("[curves.x]\npoints = [[80, 8]]\n", "level"),
        ("[curves.x]\npoints = [[80, 4], [80, 5]]\n", "duplicate"),
        ("[power]\nac = \"missing\"\n", "defined curve"),
        ("[unknown]\nvalue = 1\n", "unknown"),
    ],
)
def test_invalid_configuration(body, message):
    with pytest.raises(ConfigError, match=message):
        config_from_dict(__import__("tomllib").loads(body))


def test_unknown_section_key():
    with pytest.raises(ConfigError, match="unknown key"):
        config_from_dict({"levels": {"minimum": 0}})
