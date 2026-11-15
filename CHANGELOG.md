# Changelog

## 0.2.0 - 2026-11-16

- Install the application root-owned so the service never imports user-writable
  code
- Write control files atomically and with the configured group, and reject
  symlinks, FIFOs, and oversized files, and tolerate invalid UTF-8
- Set the state directory setgid so group members can replace control files
- Clamp curve levels to `levels.max`
- Allow an empty `paths.state_group`
- Reject non-finite and out-of-range numeric configuration values
- Skip `./config.toml` for the root CLI and stop the wrapper from adding the
  working directory to `sys.path`
- Let the emergency temperature override a pin and report `mode: emergency`
- Keep `min`, `commanded`, and `watchdog` in the shutdown status
- Add a `thinkbook-fan cleanup` command and use it in `ExecStopPost`, with a
  fallback to the default fan path
- Add systemd sandboxing and a managed runtime directory
- Limit the CI token to read-only repository contents, pin actions by commit,
  add a Dependabot configuration, and test Python 3.14

## 0.1.0 - 2026-11-14

- Standalone fan curve service for ThinkPad and ThinkBook hardware using
  `thinkpad_acpi`
- AC, battery, and low power curve selection
- Configurable curves, temperature input, paths, and minimum fan level 0 to 7
- Manual pin and unpin through the CLI or the state files
- EC watchdog set at startup, refreshed by level writes, disabled on clean stop
- `min`, `commanded`, and `watchdog` status fields
- Systemd unit, module files, source installer, and uninstaller
- File interface compatible with the ThinkBook Fan Plasma widget
- Write-only fan control on hardware that does not expose fan read-back
