from thinkbook_fan.cli import build_parser


def test_config_is_accepted_before_and_after_subcommands():
    parser = build_parser()
    assert parser.parse_args(["--config", "a.toml", "run"]).config == "a.toml"
    assert parser.parse_args(["run", "--config", "b.toml"]).config == "b.toml"
    assert parser.parse_args(["status", "--config", "c.toml"]).config == "c.toml"
