#!/bin/bash
# Installs only this project's new BLE keyboard service, not EZ Signage.
set -eu
if [ "$(id -u)" -ne 0 ] || [ -z "${SUDO_USER:-}" ] || [ "$SUDO_USER" = root ]; then
  echo 'Run this using sudo from the radxa user account.'; exit 1
fi
user_home=$(getent passwd "$SUDO_USER" | cut -d : -f 6)
app_home="$user_home/SmartKeyboard"
source_home=$(cd "$(dirname "$0")/.." && pwd)
unit=/etc/systemd/system/smartkeyboard-bluetooth.service
if [ ! -f "$source_home/backend/bluetooth_keyboard.py" ] || [ ! -f "$app_home/src/index.html" ]; then
  echo 'Copy src, scripts and backend into ~/SmartKeyboard before installation.'; exit 1
fi
python3 -c 'import dbus; from gi.repository import GLib'
python3 -m py_compile "$source_home/backend/bluetooth_keyboard.py" "$source_home/backend/hid_keys.py"
if [ -f "$unit" ] && ! grep -q '^# SmartKeyboard managed BLE keyboard$' "$unit"; then
  echo 'Unrecognized existing unit; left unchanged.'; exit 1
fi
install -d -m 0755 /opt/smartkeyboard-bluetooth
install -m 0644 "$source_home/backend/bluetooth_keyboard.py" "$source_home/backend/hid_keys.py" /opt/smartkeyboard-bluetooth/
cat > "$unit" <<EOF
# SmartKeyboard managed BLE keyboard
[Unit]
Description=Smart Keyboard Bluetooth LE keyboard
Wants=bluetooth.service
After=bluetooth.service

[Service]
Type=simple
ExecStart=/usr/bin/python3 /opt/smartkeyboard-bluetooth/bluetooth_keyboard.py --app-home "$app_home"
Restart=on-failure
RestartSec=5
TimeoutStopSec=12
UMask=0077
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=full

[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl enable smartkeyboard-bluetooth.service
systemctl restart smartkeyboard-bluetooth.service
echo 'Installed Smart Keyboard BLE service. Check:'
echo 'sudo journalctl -u smartkeyboard-bluetooth -n 35 --no-pager'
echo 'Reload the touchscreen, then tap Bluetooth > Pair PC.'
echo 'Disable if needed: sudo systemctl disable --now smartkeyboard-bluetooth'
