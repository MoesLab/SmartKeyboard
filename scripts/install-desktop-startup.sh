#!/bin/bash
set -eu

app_home="$HOME/SmartKeyboard"
launcher="$app_home/scripts/launch-kiosk.sh"
entry="$HOME/.config/autostart/smartkeyboard.desktop"
if [ ! -f "$launcher" ] || [ ! -f "$app_home/src/index.html" ]; then
  echo 'Copy the src and scripts folders to ~/SmartKeyboard first.'
  exit 1
fi
if [ -e "$entry" ] && ! grep -q '^X-SmartKeyboard-Managed=true$' "$entry"; then
  echo "Existing unmanaged startup entry left unchanged: $entry"
  exit 1
fi
mkdir -p "$HOME/.config/autostart"
cat > "$entry" <<EOF
[Desktop Entry]
Type=Application
Version=1.0
Name=Smart Keyboard
Comment=Open Smart Keyboard on graphical login
Exec=/bin/bash "$launcher"
Terminal=false
Hidden=false
X-GNOME-Autostart-enabled=true
X-SmartKeyboard-Managed=true
EOF
echo "Created: $entry"
echo 'Starts on graphical login; desktop autologin must already be enabled for boot-to-kiosk.'
echo 'New browser profile: ~/SmartKeyboard/kiosk-profile (old profiles are preserved).'
echo 'Test now: bash ~/SmartKeyboard/scripts/launch-kiosk.sh'
