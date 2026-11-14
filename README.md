# thinkbook-fan

A small, standalone fan curve service for Lenovo ThinkPad and ThinkBook laptops
that expose the `thinkpad_acpi` fan level interface. It has no desktop
dependencies. Use it from a terminal, a systemd service, or scripts.

The ThinkBook Fan widget is one optional client. The service and its state
files are useful without Plasma, KDE, or any graphical session.

## Features

- AC, battery, and low power aware fan curves
- Balanced, Power Save, and Aggressive presets, with custom curve tables
- Selectable temperature input: maximum core, average core, package, or all sensors
- Configurable minimum fan level from 0 to 7
- Manual pin and unpin, with a temperature safety override
- Smoothing over a short temperature window
- EC watchdog and fan level/RPM read-back
- CLI and a stable file interface
- File based state that is compatible with the Plasma widget
- Systemd unit and module configuration included

## Hardware

This is not a generic laptop fan daemon. It controls the fan through
`thinkpad_acpi` and `/proc/acpi/ibm/fan`, and requires `fan_control=1`. That
interface is used by many ThinkPads and some ThinkBooks. Machines using hwmon
PWM fans or vendor-specific EC drivers are not supported.

Tested on a Lenovo ThinkBook 15 G2 ITL with an i5-1135G7. The default sensor
paths target this model: Intel `coretemp`, thermal zones 7 and 8, and `ACAD`.
For another model, override them in `[paths]` and review the curve thresholds
and safety limits. The automatic sensor reader currently looks for `coretemp`;
AMD sensors such as `k10temp` are not read automatically.

## Install

Requirements:

- Linux with the `thinkpad_acpi` module
- Python 3.11 or newer

From a checkout:

```bash
python3 -m venv .venv
.venv/bin/pip install .
.venv/bin/thinkbook-fan --help
```

For a system service, install the package where the unit can find it, or edit
the unit to point at your virtualenv. A common layout is:

```bash
sudo mkdir -p /opt/thinkbook-fan
sudo cp -a . /opt/thinkbook-fan/app
sudo python3 -m venv /opt/thinkbook-fan/venv
sudo /opt/thinkbook-fan/venv/bin/pip install /opt/thinkbook-fan/app
```

The wheel also installs the example configuration, systemd unit, and module
files under `<prefix>/share/thinkbook-fan`.

Then edit the service unit's `ExecStart` to:

```ini
ExecStart=/opt/thinkbook-fan/venv/bin/thinkbook-fan run --config /etc/thinkbook-fan/config.toml
```

Stop any other fan curve service first. Two daemons must not write the same
fan interface. If you previously used the service bundled with the widget,
the state files and the widget keep working after you switch.

Install the configuration, module files, and service:

```bash
sudo install -Dm644 examples/config.toml /etc/thinkbook-fan/config.toml
sudo install -Dm644 etc/modprobe.d/thinkbook-fan.conf /etc/modprobe.d/thinkbook-fan.conf
sudo install -Dm644 etc/modules-load.d/thinkbook-fan.conf /etc/modules-load.d/thinkbook-fan.conf
sudo install -Dm644 systemd/thinkbook-fan.service /etc/systemd/system/thinkbook-fan.service
sudo systemctl daemon-reload
sudo systemctl enable --now thinkbook-fan
```

Reload the module after installing the options file:

```bash
sudo modprobe -r thinkpad_acpi
sudo modprobe thinkpad_acpi
```

A reboot also works. Check the fan interface:

```bash
cat /proc/acpi/ibm/fan
```

## Configuration

The service reads `config.toml` from `--config`, `THINKBOOK_FAN_CONFIG`,
`./config.toml`, or `/etc/thinkbook-fan/config.toml`. If no file exists, the
built-in defaults are used.

The example configuration documents every option. Important sections:

- `[paths]`: fan, state, sensor, and power supply paths
- `[daemon]`: polling, smoothing, hysteresis, emergency and safety temperatures, and the EC watchdog
- `[levels]`: minimum, maximum, and default floor
- `[temperature]`: default temperature input
- `[curves.*]`: threshold and level pairs
- `[power]`: which curve to use on AC, battery, and low power

Curve points are written highest threshold first:

```toml
[curves.auto]
points = [[88, 7], [81, 6], [74, 5], [66, 4], [0, 0]]
```

The configured minimum level is a floor over every curve and pin. The default
is 3. Level 0 stops the fan. The service still raises the fan near the safety
temperature.

## CLI

The CLI writes the control files directly. Changes are picked up by the daemon
within one poll interval.

```bash
thinkbook-fan status
thinkbook-fan status --json
thinkbook-fan pin 4
thinkbook-fan unpin
thinkbook-fan min 3
thinkbook-fan curve ac aggressive
thinkbook-fan curve default power-save
thinkbook-fan input package
thinkbook-fan config
```

Run the service:

```bash
sudo thinkbook-fan run --config /etc/thinkbook-fan/config.toml
```

Test without touching the fan:

```bash
thinkbook-fan run --dry-run --once
```

## Interfaces

The service has no network listener. Use the CLI and the files in the state
directory. `systemctl` manages the process lifecycle, and the journal holds the
logs. This keeps the root daemon small and avoids exposing a remote control
surface. The Plasma widget uses the same files.

## File interface

The state directory is shared with the Plasma widget:

```text
/run/thinkbook-fan/
  pin          optional integer level
  min-level    integer floor
  curves       ac=NAME, default=NAME, power-save=NAME
  input        max-core, avg-core, package, or max-all
  state        JSON status written by the daemon
```

The status file contains:

```json
{
  "level": 3,
  "mode": "ac",
  "curve": "auto",
  "state": "ac",
  "min": 3,
  "input": "max-all",
  "temp": 45,
  "control": 45,
  "ac": true,
  "pin": null,
  "commanded": 3,
  "rpm": 3200,
  "ec_level": "3",
  "watchdog": 60,
  "updated": 1794498018
}
```

`mode` is `pin`, `ac`, `default`, `power-save`, or `off`. `pin` is the effective
pinned level when a pin is active. `min` is the applied minimum level.
`commanded` is the level the daemon asked
for, `ec_level` is what the fan interface reports, and `rpm` is the measured
speed. Files are written atomically. The directory is group writable when
`paths.state_group` is set and the service runs as root.

The EC watchdog defaults to 60 seconds. If the daemon stops writing, the EC
returns the fan to firmware automatic control. The daemon disables the
watchdog and restores `level auto` on clean shutdown. Read-back detects
external fan writes, watchdog takeover, and stalled fans through the RPM
value. Not every model exposes the watchdog command; check `sudo
thinkbook-fan probe` and the service log.

## How it works

1. Read the selected temperature input.
2. Keep a short median window to reject spikes.
3. Pick the curve for AC, battery, or low power.
4. Apply the pinned level, or the curve level, with the minimum floor.
5. Move the fan one level per poll. Hysteresis avoids rapid changes.
6. If the temperature reaches the emergency limit, use the maximum level.
7. Read the actual fan level and RPM back. Re-assert the level if the EC differs.
8. Feed the EC watchdog with the periodic level refresh.
9. Write the status file.

## Safety

Level 0 stops the fan. Use a minimum of 3 unless you specifically want the fan
to stop at low temperatures. The service raises the fan near the emergency
temperature regardless of the pin or floor. The default emergency threshold is
90 C and the pin safety cutoff is 95 C. Review them for your machine.

This is unofficial software. Use it at your own risk.

## Development

```bash
python3 -m venv .venv
.venv/bin/pip install -e '.[test]'
.venv/bin/pytest
```

The package has no runtime dependencies outside the Python standard library.
The tests use temporary directories and do not touch the fan.

Package layout:

- `config.py`: TOML loading and validation
- `curves.py`: curve evaluation and target stepping
- `control.py`: control and status files
- `hardware.py`: fan, sensors, and power state
- `daemon.py`: the control loop
- `cli.py`: command line interface

## License

MIT. See [LICENSE](LICENSE).
