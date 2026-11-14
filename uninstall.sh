#!/usr/bin/env bash
set -euo pipefail

if [ "$(id -u)" -ne 0 ]; then
    echo "Run as root: sudo ./uninstall.sh" >&2
    exit 1
fi

systemctl disable --now thinkbook-fan.service 2>/dev/null || true
rm -f /usr/local/bin/thinkbook-fan
rm -f /etc/systemd/system/thinkbook-fan.service
rm -rf /opt/thinkbook-fan/app
rmdir /opt/thinkbook-fan 2>/dev/null || true
rm -f /etc/modprobe.d/thinkbook-fan.conf
rm -f /etc/modules-load.d/thinkbook-fan.conf
systemctl daemon-reload

echo "Removed the standalone service."
echo "Kept /etc/thinkbook-fan/config.toml."
echo "The older thinkbook-fan-curve.service was disabled by install.sh and is left untouched."
