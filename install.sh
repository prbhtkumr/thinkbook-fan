#!/usr/bin/env bash
set -euo pipefail

if [ "$(id -u)" -ne 0 ]; then
    echo "Run as root: sudo ./install.sh" >&2
    exit 1
fi

here="$(cd "$(dirname "$0")" && pwd)"
app_dir="/opt/thinkbook-fan/app"
wrapper="/usr/local/bin/thinkbook-fan"
config_dir="/etc/thinkbook-fan"
service="/etc/systemd/system/thinkbook-fan.service"

echo "Stopping the older bundled service if present"
systemctl disable --now thinkbook-fan-curve.service 2>/dev/null || true
systemctl stop thinkbook-fan.service 2>/dev/null || true

echo "Installing the application to $app_dir"
rm -rf "$app_dir"
install -d "$app_dir"
tar -C "$here" \
    --exclude=.git \
    --exclude=__pycache__ \
    --exclude=.pytest_cache \
    --exclude='*.egg-info' \
    --exclude=build \
    -cf - . | tar -C "$app_dir" -xf -

echo "Installing the CLI wrapper"
cat > "$wrapper" <<'WRAPPER'
#!/bin/sh
export PYTHONPATH="/opt/thinkbook-fan/app${PYTHONPATH:+:$PYTHONPATH}"
exec /usr/bin/python3 -m thinkbook_fan "$@"
WRAPPER
chmod 755 "$wrapper"

echo "Installing the configuration"
install -d -m 755 "$config_dir"
if [ ! -e "$config_dir/config.toml" ]; then
    install -m 644 "$here/examples/config.toml" "$config_dir/config.toml"
    echo "Installed the default configuration"
else
    echo "Keeping the existing configuration"
fi

echo "Installing module options"
install -Dm644 "$here/etc/modprobe.d/thinkbook-fan.conf" /etc/modprobe.d/thinkbook-fan.conf
install -Dm644 "$here/etc/modules-load.d/thinkbook-fan.conf" /etc/modules-load.d/thinkbook-fan.conf

echo "Installing the service"
install -Dm644 "$here/systemd/thinkbook-fan.service" "$service"
systemctl daemon-reload
systemctl enable --now thinkbook-fan.service

sleep 3
echo
echo "Service status"
systemctl --no-pager --full status thinkbook-fan.service || true
echo
echo "Daemon status"
"$wrapper" status || true
echo
echo "Fan probe"
"$wrapper" probe || true
echo

if systemctl is-active --quiet thinkbook-fan.service; then
    echo "Installed and running."
    echo "Config:  $config_dir/config.toml"
    echo "Logs:    journalctl -u thinkbook-fan.service -f"
else
    echo "The service is not active. Check the journal:" >&2
    echo "  journalctl -u thinkbook-fan.service -n 50 --no-pager" >&2
    exit 1
fi
