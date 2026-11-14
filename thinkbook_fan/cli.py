"""Command line interface."""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import datetime
from typing import Sequence

from . import __version__
from .config import INPUT_MODES, POWER_STATES, ConfigError, load_config
from .control import ControlFiles
from .daemon import FanDaemon

LOGGER = logging.getLogger("thinkbook_fan")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="thinkbook-fan",
        description="Fan curve service for ThinkBook laptops using thinkpad_acpi.",
    )
    parser.add_argument("--config", metavar="PATH", help="configuration file")

    def add_config_option(subparser):
        subparser.add_argument(
            "--config",
            metavar="PATH",
            default=argparse.SUPPRESS,
            help="configuration file",
        )
    parser.add_argument("--version", action="version", version=__version__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    run = subparsers.add_parser("run", help="run the fan curve daemon")
    add_config_option(run)
    run.add_argument(
        "--dry-run",
        action="store_true",
        help="read sensors and write status, but do not touch the fan",
    )
    run.add_argument(
        "--once",
        action="store_true",
        help="run one control cycle and exit",
    )

    status = subparsers.add_parser("status", help="show the last status")
    add_config_option(status)
    status.add_argument("--json", action="store_true", help="print raw JSON")

    pin = subparsers.add_parser("pin", help="pin a fan level")
    add_config_option(pin)
    pin.add_argument("level", type=int)

    unpin = subparsers.add_parser("unpin", help="release the pinned level")
    add_config_option(unpin)

    curve = subparsers.add_parser("curve", help="select a curve for a power state")
    add_config_option(curve)
    curve.add_argument("state", choices=POWER_STATES)
    curve.add_argument("curve")

    temperature = subparsers.add_parser("input", help="select the temperature input")
    add_config_option(temperature)
    temperature.add_argument("mode", choices=INPUT_MODES)

    minimum = subparsers.add_parser("min", help="set the minimum fan level")
    add_config_option(minimum)
    minimum.add_argument("level", type=int)

    config_parser = subparsers.add_parser("config", help="print the effective configuration")
    add_config_option(config_parser)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        config = load_config(args.config)
        control = ControlFiles(config)

        if args.command == "run":
            logging.basicConfig(
                level=logging.INFO,
                format="%(asctime)s %(levelname)s %(message)s",
            )
            if not args.dry_run and hasattr(os, "geteuid") and os.geteuid() != 0:
                LOGGER.warning("run as root to write the fan, or use --dry-run")
            daemon = FanDaemon(config, control, dry_run=args.dry_run, once=args.once)
            return daemon.run()

        if args.command == "status":
            status = control.read_status()
            if status is None:
                print("no status file; is the service running?", file=sys.stderr)
                return 1
            if args.json:
                print(json.dumps(status, indent=2))
            else:
                print_status(status)
            return 0

        if args.command == "pin":
            level = control.set_pin(args.level)
            print(f"pinned level {level}")
            return 0

        if args.command == "unpin":
            control.clear_pin()
            print("pin cleared")
            return 0

        if args.command == "curve":
            control.set_curve(args.state, args.curve)
            print(f"{args.state} curve set to {args.curve}")
            return 0

        if args.command == "input":
            control.set_input(args.mode)
            print(f"temperature input set to {args.mode}")
            return 0

        if args.command == "min":
            level = control.set_min(args.level)
            print(f"minimum fan level set to {level}")
            return 0

        if args.command == "config":
            print(json.dumps(config.public_dict(), indent=2))
            return 0

        parser.error("unknown command")
        return 2
    except (ConfigError, ValueError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


def print_status(status: dict) -> None:
    updated = status.get("updated")
    when = (
        datetime.fromtimestamp(updated).strftime("%Y-%m-%d %H:%M:%S")
        if isinstance(updated, (int, float))
        else "unknown"
    )
    print(f"level:   {status.get('level')}")
    print(f"mode:    {status.get('mode')}")
    print(f"curve:   {status.get('curve')}")
    print(f"state:   {status.get('state')}")
    print(f"input:   {status.get('input')}")
    print(f"temp:    {status.get('temp')}")
    print(f"control: {status.get('control')}")
    print(f"ac:      {status.get('ac')}")
    print(f"pin:     {status.get('pin')}")
    print(f"min:     {status.get('min')}")
    print(f"command: {status.get('commanded')}")
    print(f"watchdog:{status.get('watchdog')}")
    if status.get("dry_run"):
        print("dry run: yes")
    print(f"updated: {when}")
