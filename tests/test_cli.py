from thinkbook_fan.cli import build_parser


def test_config_is_accepted_before_and_after_subcommands():
    parser = build_parser()
    assert parser.parse_args(["--config", "a.toml", "run"]).config == "a.toml"
    assert parser.parse_args(["run", "--config", "b.toml"]).config == "b.toml"
    assert parser.parse_args(["status", "--config", "c.toml"]).config == "c.toml"


def test_cleanup_command_restores_fan(monkeypatch):
    from thinkbook_fan import cli
    from thinkbook_fan.config import default_config

    calls = []

    class FakeHardware:
        def __init__(self, config):
            pass

        def fan_available(self):
            return True

        def set_watchdog(self, seconds):
            calls.append(("watchdog", seconds))

        def restore_auto(self):
            calls.append(("auto", None))

    monkeypatch.setattr(cli, "Hardware", FakeHardware)
    monkeypatch.setattr(cli, "load_config", lambda path: default_config())
    assert cli.main(["cleanup"]) == 0
    assert calls == [("watchdog", 0), ("auto", None)]


def test_cleanup_command_reports_failure(monkeypatch):
    from thinkbook_fan import cli
    from thinkbook_fan.config import default_config

    class FailHardware:
        def __init__(self, config):
            pass

        def fan_available(self):
            return True

        def set_watchdog(self, seconds):
            raise OSError("no fan interface")

        def restore_auto(self):
            raise OSError("no fan interface")

    monkeypatch.setattr(cli, "Hardware", FailHardware)
    monkeypatch.setattr(cli, "load_config", lambda path: default_config())
    assert cli.main(["cleanup"]) == 1


def test_cleanup_command_rejects_a_missing_fan(monkeypatch):
    from thinkbook_fan import cli
    from thinkbook_fan.config import default_config

    calls = []

    class MissingHardware:
        def __init__(self, config):
            pass

        def fan_available(self):
            return False

        def set_watchdog(self, seconds):
            calls.append("watchdog")

        def restore_auto(self):
            calls.append("auto")

    monkeypatch.setattr(cli, "Hardware", MissingHardware)
    monkeypatch.setattr(cli, "load_config", lambda path: default_config())
    assert cli.main(["cleanup"]) == 1
    assert calls == []
