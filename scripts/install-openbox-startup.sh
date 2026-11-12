#!/bin/bash
set -eu

app_home="$HOME/SmartKeyboard"
launcher="$app_home/scripts/launch-kiosk.sh"
startup="$HOME/.config/openbox/autostart"
marker='# BEGIN SmartKeyboard managed launcher'
if [ ! -f "$launcher" ] || [ ! -f "$app_home/src/index.html" ]; then
  echo 'Copy src and scripts to ~/SmartKeyboard first.'
  exit 1
fi
mkdir -p "$HOME/.config/openbox" "$app_home/backups"
if [ -e "$startup" ] && [ ! -f "$startup" ]; then
  echo "Not a regular startup file: $startup"; exit 1
fi
# Openbox normally falls back to this system file when no user file exists.
# Preserve that behavior instead of shadowing it with a new empty user file.
if [ ! -e "$startup" ] && [ -f /etc/xdg/openbox/autostart ]; then
  cp -p /etc/xdg/openbox/autostart "$startup"
fi
if [ -f "$startup" ] && grep -Fqx "$marker" "$startup"; then
  echo 'Smart Keyboard is already registered in Openbox startup.'
  exit 0
fi
if [ -f "$startup" ]; then
  backup=$(mktemp "$app_home/backups/openbox-autostart-XXXXXX")
  cp -p "$startup" "$backup"
  echo "Previous startup file backed up to $backup"
fi
# Append only; never replace existing startup actions or .xinitrc.
cat >> "$startup" <<'EOF'

# BEGIN SmartKeyboard managed launcher
( sleep 3; /bin/bash "$HOME/SmartKeyboard/scripts/launch-kiosk.sh" ) &
# END SmartKeyboard managed launcher
EOF
echo "Added Smart Keyboard to $startup"
echo 'It will launch when openbox-session starts. Existing startup commands were preserved.'
echo 'Test now: bash ~/SmartKeyboard/scripts/launch-kiosk.sh'
