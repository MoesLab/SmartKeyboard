#!/bin/bash
set -eu
if [ "$(id -u)" -ne 0 ]; then echo 'Run with sudo.'; exit 1; fi
kernel=$(uname -r)
module="/lib/modules/$kernel/updates/smartkeyboard/aic_btusb_usb.ko"
config=/etc/depmod.d/99-smartkeyboard-bluetooth.conf
if [ -f "$config" ] && ! grep -q '^# SmartKeyboard:' "$config"; then
  echo 'Unrecognized configuration; nothing changed.'; exit 1
fi
stamp=$(date +%Y%m%d-%H%M%S)
if [ -f "$module" ]; then mv "$module" "$module.disabled-$stamp"; fi
if [ -f "$config" ]; then mv "$config" "$config.disabled-$stamp"; fi
/sbin/depmod -a "$kernel"
echo 'Custom driver disabled for future loads. No running drivers were changed.'
/sbin/modinfo -n aic_btusb_usb
