#!/bin/bash
# Install only the already-tested AIC Bluetooth module for this exact kernel.
set -eu
if [ "$(id -u)" -ne 0 ]; then echo 'Run with sudo and the full path to the tested .ko file.'; exit 1; fi
module=${1:?Supply the full path to the tested aic_btusb.ko}
kernel=$(uname -r)
destination="/lib/modules/$kernel/updates/smartkeyboard/aic_btusb_usb.ko"
config=/etc/depmod.d/99-smartkeyboard-bluetooth.conf
if [ ! -f "$module" ]; then echo "Missing tested module: $module"; exit 1; fi
if [ "$(/sbin/modinfo -F name "$module")" != aic_btusb ]; then echo 'Wrong module name; nothing changed.'; exit 1; fi
if [ "$(/sbin/modinfo -F vermagic "$module" | cut -d ' ' -f 1)" != "$kernel" ]; then echo 'Module does not match the running kernel; nothing changed.'; exit 1; fi
if ! /sbin/modinfo -F depends "$module" | tr ',' '\n' | grep -qx bluetooth; then echo 'Module does not use Linux Bluetooth; nothing changed.'; exit 1; fi
if [ -e "$destination" ] || [ -e "$config" ]; then
  echo 'A custom installation already exists; nothing overwritten.'
  /sbin/modinfo -n aic_btusb_usb
  exit 1
fi
mkdir -p "$(dirname "$destination")" /etc/depmod.d
installed=false
rollback_on_error() {
  result=$?
  if [ "$installed" != true ]; then
    [ ! -f "$destination" ] || mv "$destination" "$destination.failed"
    [ ! -f "$config" ] || mv "$config" "$config.failed"
    /sbin/depmod -a "$kernel" || true
    echo 'Installation verification failed. Custom files disabled; packaged driver kept.'
  fi
  exit "$result"
}
trap rollback_on_error EXIT
install -m 0644 "$module" "$destination"
cat > "$config" <<EOF
# SmartKeyboard: prefer the tested BlueZ driver for this kernel only.
override aic_btusb_usb $kernel updates/smartkeyboard
EOF
/sbin/depmod -a "$kernel"
selected=$(/sbin/modinfo -n aic_btusb_usb)
if [ "$selected" != "$destination" ]; then echo "Unexpected selected module: $selected"; exit 1; fi
installed=true
echo "Selected at next load: $selected"
echo 'The packaged module, Wi-Fi driver, and EZ Signage were not modified.'
echo 'No driver was unloaded. Test the next module load before rebooting.'
echo 'This override is kernel-specific; a future kernel needs a matching build.'
