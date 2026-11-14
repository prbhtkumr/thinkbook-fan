# Compatibility

## Tested hardware

- Lenovo ThinkBook 15 G2 ITL
- Intel Core i5-1135G7
- Linux kernel 7.2.15
- `thinkpad_acpi` with `fan_control=1`

Fan writes through `/proc/acpi/ibm/fan` work. The `thinkpad_acpi` fan
watchdog command is accepted and the service logs `EC watchdog set to 60
seconds`.

Fan RPM and actual EC level read-back return `ENXIO` on this machine and
kernel. The service is therefore write-only: it commands levels, but it does
not read the current EC level or RPM. The status reports the commanded level,
the minimum level, and the watchdog timeout. The widget does not show an RPM
field on this hardware.

## Other hardware

The service is not a generic laptop fan daemon. It requires `thinkpad_acpi`
and `/proc/acpi/ibm/fan` with `fan_control=1`. Many ThinkPads and some
ThinkBooks expose this interface.

For another model:

- Override `[paths]` for the fan, power supply, AC online, hwmon, and thermal
  zones.
- Review the curve thresholds and safety limits.
- The automatic sensor reader currently looks for the Intel `coretemp`
  driver. AMD sensors such as `k10temp` are not read automatically.
- Check whether the EC watchdog command is accepted. The service logs a
  warning if it cannot set it.

Machines using generic hwmon PWM fans or vendor-specific EC drivers are not
supported. NBFC-Linux or fan2go are better fits for that hardware.

## Fail-safe verification

The watchdog is the `thinkpad_acpi` fan watchdog. The driver starts a timer
when the service writes `watchdog 60`, and resets it on each `level` write.
The service refreshes the level every 30 seconds, so a 60 second watchdog
leaves roughly 30 seconds of headroom.

A clean stop disables the watchdog and writes `level auto`. The log should
show:

```text
EC watchdog disabled
restored fan level auto
```

A hang fail-safe test freezes the daemon so systemd still sees it as running
and does not run `ExecStopPost`:

```bash
sudo thinkbook-fan pin 7
PID=$(systemctl show -p MainPID --value thinkbook-fan.service)
sudo kill -STOP "$PID"
sleep 75
sudo dmesg | grep -i "fan watchdog"
sudo kill -CONT "$PID"
sudo thinkbook-fan unpin
```

Verified on the tested hardware: the driver logged

```text
thinkpad_acpi: fan watchdog: enabling fan
```

about 60 seconds after the freeze, and the fan returned to firmware control
without any daemon write. The status file stopped updating for the whole
window, which confirms the timer expired while the daemon was not writing.

Do not use `SIGKILL` for this test. systemd treats the kill as a failure and
runs the unit's `ExecStopPost`, which writes `watchdog 0` and `level auto`
before restarting the service. That proves cleanup and restart, not timer
expiry.

Uninstall and reinstall were also verified from the source tree: the
uninstaller removes the binary, unit, application, and module files, keeps
`/etc/thinkbook-fan/config.toml`, and leaves the older bundled service
disabled. A reinstall recreates everything and starts with the watchdog set.

Removing `/run/thinkbook-fan` is not a reliable reset. The service recreates
the directory on its next status write, and any running widget keeps its
saved settings. Stop the service, remove the individual control files, then
start it again for a clean state.
