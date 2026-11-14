# Changelog

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
