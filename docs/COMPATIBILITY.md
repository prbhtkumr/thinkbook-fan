# Compatibility

## Tested hardware

- Lenovo ThinkBook 15 G2 ITL
- Intel Core i5-1135G7
- Linux kernel 7.2.15
- `thinkpad_acpi` with `fan_control=1`

Fan writes through `/proc/acpi/ibm/fan` work. The EC watchdog command is
accepted and the service logs `EC watchdog set to 60 seconds`.

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

A clean stop disables the watchdog and writes `level auto`. The log should
show:

```text
EC watchdog disabled
restored fan level auto
```

A crash or hang fail-safe test requires the EC watchdog to expire while the
daemon is dead. On this model the fan read interface is unavailable, so the
result cannot be confirmed by reading the level or RPM back. Confirm it by
the fan behavior or EC state, and check that the next service start logs
`EC watchdog set to 60 seconds` again.
