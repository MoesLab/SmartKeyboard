# Bluetooth LE keyboard — basic hardware operation confirmed

The new backend exports a BLE HID keyboard (service 0x1812, appearance 0x03C1, report ID 1) through the existing BlueZ 5.55 GATT/advertising interfaces. It includes boot/report input, LED output, protocol mode, and HID control point. It registers a KeyboardDisplay pairing agent and restores the adapter's earlier pairable/discoverable settings when its two-minute pairing window closes. No package or driver changes are performed by this backend.

Implementation references: BlueZ's official [GATT API](https://github.com/bluez/bluez/blob/5.55/doc/gatt-api.txt), [advertising API](https://github.com/bluez/bluez/blob/5.55/doc/advertising-api.txt), and [agent API](https://github.com/bluez/bluez/blob/5.55/doc/agent-api.txt). The user confirmed Bluetooth typing to the PC and Ctrl+A operating on Windows without altering the Radxa composer. The original tested rate was 15ms/report (~33 characters/second). The next-round default of 5ms/report (~100 characters/second) has not yet been hardware-tested.

## Install on Radxa

The Linux-mode Bluetooth driver must already expose hci0. The user confirmed python3-dbus, python3-gi, GattManager1, and LEAdvertisingManager1 are available. No pip installation is required.

```sh
git -C ~/SmartKeyboard-source pull --ff-only &&
cp -r ~/SmartKeyboard-source/src ~/SmartKeyboard/ &&
cp -r ~/SmartKeyboard-source/scripts ~/SmartKeyboard/ &&
cp -r ~/SmartKeyboard-source/backend ~/SmartKeyboard/ &&
sudo bash ~/SmartKeyboard/scripts/install-bluetooth-keyboard.sh
```

The installer creates only this project's `smartkeyboard-bluetooth.service` and installs its root-owned code under `/opt/smartkeyboard-bluetooth`. It enables the new service at boot. It does not modify EZ Signage, Chromium profiles, or the working Bluetooth driver. Root is used for the BlueZ system-bus integration; the HTTP server listens only on 127.0.0.1:8765.

Check registration before pairing:

```sh
sudo journalctl -u smartkeyboard-bluetooth -n 35 --no-pager
```

Expected log: `Smart Keyboard BLE ready; open pairing on touchscreen`. If registration fails, paste the log; do not remove BlueZ's existing services or device pairings.

## Pair and test

1. Reload the touchscreen to load the generated bridge configuration.
2. Tap Bluetooth, then Pair PC (opens pairing for two minutes).
3. Windows Settings > Bluetooth & devices > Add device > Bluetooth > Smart Keyboard.
4. Confirm the matching number on the touchscreen when requested. If Windows displays a passkey to enter on the keyboard, use the touchscreen's numeric pad and Approve. If the Radxa displays a passkey for entry on the PC, enter it on the PC's physical keyboard.
5. Wait for `BT connected`. On Windows, open Notepad and focus its text area.
6. Type `Hello PC` in the Radxa composer, then Send. Test Ctrl+A from Macros with Notepad still focused.

The virtual keyboard and Quick Text continue to edit locally. Only Send transmits the entire composer, without automatically pressing Enter at the end. Macros send shortcuts without altering the composer. The composer is retained after Send. The host's focused application receives keys; the frontend does not choose or open that app.

## Encoding and connection limits

- US keyboard layout; 1–1000 input characters per Send and 1–100 shortcut actions per macro. Typographic curly quotes, dashes, ellipsis and nonbreaking spaces are normalized to US equivalents. Other unsupported Unicode is rejected before anything is queued. Non-US host layouts may type different symbols.
- Eight-byte keyboard reports alternate presses and releases, now paced at 5ms per report (~100 characters/second nominal). Actual speed depends on Bluetooth scheduling. Set `--report-interval-ms 15` to return to the hardware-proven original pace if the faster rate drops characters. The accepted range is 3–30ms. Queue acceptance is not proof that the target app handled a keystroke.
- A single paired, connected host must subscribe to input notifications. Zero/multiple hosts, unsubscribed input, or suspended HID cause rejection. A disconnect or host change cancels queued reports and emits release reports where possible. Sends are serialized; there is no automatic resend after reconnect.
- Pairing is never silently accepted. Requests outside an explicitly opened pairing window are rejected; approval happens on the touchscreen. Legacy PIN pairing is not supported.
- Basic advertisement, pairing, text sending, and Ctrl+A were confirmed by the user on the actual Radxa and PC. Faster pacing, sustained long sends, reconnects and power-loss behavior still need target-device testing.

## Local bridge and saved settings

The GUI keeps its existing file:// origin and browser profile. The service generates `src/bridge-config.js` containing a random bearer token, mode 0600 and owned by the GUI user. The secret also lives in root-only `/var/lib/smartkeyboard-bluetooth/bridge-token` so restarts retain it. Never commit this file. HTTP exposes only authenticated POST actions with the expected loopback Host and file-origin `null`; it does not serve the config or project files. CORS preflight permits the local file UI and private-network access. Actual Chromium policy compatibility must be checked on the Radxa.

To stop and disable this project's service:

```sh
sudo systemctl disable --now smartkeyboard-bluetooth
```

The GUI will continue to work locally; Bluetooth buttons will show offline. Existing system BlueZ services and pairings are not removed. The backend re-registers after BlueZ restarts; its pairing window closes on exit.

## Tests

`python3 -m unittest discover -s backend -p 'test_*.py'` runs report encoding, hierarchy and bridge/state tests. D-Bus decorators are stubbed only in the local logic tests. Eleven local tests passed again after the faster pacing change; browser checks previously passed against a simulated bridge. The user separately confirmed real service registration, pairing, typing, and Ctrl+A. Next session must test faster pacing on hardware; local tests do not measure radio timing.


### Send reliability and backups

SEND validates the complete draft before queuing anything. Unsupported characters
show a line and column; the touchscreen can select the offending character.
Farsi remains local composition only. Typographic quotes and dashes are normalized.
Delivery status distinguishes queued, sending, sent reports and interrupted output.
Sent reports do not prove that the focused PC application accepted the text.
Bluetooth settings provide Refresh and Stop send. A disconnect clears the queue;
reconnection never automatically resends it. Check the PC before retrying.

Settings exports a JSON backup of the draft, named macros, Quick Text and preferences.
It excludes bridge credentials and Bluetooth pairing keys. Copy the downloaded file
from Radxa to the PC using MobaXterm. Restore validates the file, requests confirmation,
downloads a before-restore backup, replaces known settings and reloads the interface.
These files contain your saved text; keep them somewhere appropriate.

Settings Send speed applies 15/10/5ms report pacing to the next text or macro request (~33/50/100 characters per second). The authenticated send payload optionally carries reportIntervalMs. It is validated before queueing and cannot alter an active send. Without a preference the backend CLI interval is preserved. The browser preference survives reloads and backups; reconnect does not trigger a send. These are target rates, not guarantees; use 15ms if characters are missed. Backend reinstallation is required for this control.

Audio coexistence: paired audio/video-class devices (or headset/headphone/speaker icons when Class is absent) are excluded from keyboard host counting. Computer-class and unknown legacy PC devices remain eligible, even with audio service UUIDs. This preserves the single-target guard for PCs. Headset pairing, audio routing and microphone profile support are separate; this patch does not install audio modules or alter audio, display or signage services. Devices with no class/icon metadata still need inspection.

### Experimental headset microphone crash investigation

OpenComm2 A2DP playback and BLE keyboard coexistence were user-confirmed. Switching
to headset_head_unit twice caused loss of GUI/SSH. Captured logs showed sco_num:2,
unsupported multiple CVSD links, send failure -19, then a kernel NULL dereference.
The complete fault stack was not captured, so the exact fault site is unproven.
The user's copied driver defines SCO_NUM as hdev->conn_hash.sco_num and manually
increments/decrements it despite CONFIG_BLUEDROID=0. Linux already owns that
counter. Its SCO send errors also call kfree(skb) before returning an error, while
Linux hci_send_frame frees the returned failed packet. Both are concrete ownership
mismatches and plausible contributors, not a hardware-verified crash fix.

scripts/prepare-bluetooth-sco-test.py accepts the working copied build directory,
validates expected source patterns, copies into a fresh ~/SmartKeyboard/bt-sco-test-*
directory and guards vendor counter writes and the two SCO error-path frees behind
CONFIG_BLUEDROID. It preserves the original source and installed module, saves a
reviewable diff and provenance hashes, then builds for the running Radxa kernel.
No sudo, module unload, installation, service change or headset profile switch occurs.
Use --prepare-only for source inspection without compiling. The source-transform
unit tests and full upstream-source transform passed on PC; Radxa compilation and
hardware microphone behavior are still pending. Do not bypass the unsupported-link
check or force the counter to one. Preserve the working BLE driver and 15ms fallback.

References:
- https://github.com/radxa-pkg/aic8800/blob/main/src/USB/driver_fw/drivers/aic_btusb/aic_btusb.c
- https://github.com/radxa-pkg/aic8800/blob/main/src/USB/driver_fw/drivers/aic_btusb/aic_btusb.h
- https://github.com/torvalds/linux/blob/v5.15/include/net/bluetooth/hci_core.h
- https://github.com/torvalds/linux/blob/v5.15/net/bluetooth/hci_core.c


### OpenComm2 volume controls

Settings has an expandable headset panel with listening and microphone 0/25/50/75/100%
levels. Tone volume is separate. The UI selects only the confirmed OpenComm2 address;
it never picks another speaker if that headset is absent. Microphone controls remain
unavailable if PulseAudio has not exposed a microphone. No automatic profile change
or switch to headset_head_unit occurs. These are live PulseAudio gains, not browser
preferences exported in JSON backups. Existing mute flags are reported, not overridden.

Authenticated /api/audio-status and /api/audio-volume use fixed pactl commands under
the desktop user's account, with bounded timeouts and no shell or arbitrary command.
Only the OpenComm2's currently listed Bluetooth endpoints can be adjusted; HDMI,
monitor sources, defaults, routes, profiles and services are left unchanged.
Audio reads/changes are rejected during queued HID delivery to avoid blocking pacing.
The installer copies headset_audio.py alongside the backend; a backend reinstall is
required. These controls do not install the experimental kernel driver.

Hardware follow-up: the experimental module compiled and loaded on kernel
5.15.147-14-a733. The user then confirmed microphone recording and headset playback;
logs showed sco_num:1 with voice URBs started and no reported new crash. The module
remains temporarily loaded, not installed for reboot. PC reconnection is still being
checked independently. scripts/diagnose-bluetooth.py reads authenticated bridge status,
installed accessory-filter presence, and separate PC/headset link state without
printing the bridge token. A paired headset must never be displayed as a keyboard PC.


Settings > headset audio now has Test headset, which creates a short low-amplitude
two-note WAV in memory and plays it explicitly through the selected Shokz sink with
paplay, at the current headset gain. It never changes the default output or profile.
Start mic level opens only the currently exposed Shokz microphone with parec. A
background reader computes RMS dBFS from 8kHz mono PCM; samples are discarded, not
saved or transmitted to a speech service. The meter maps -60..0dBFS to 0..100; this
is signal activity, distinct from the microphone gain percentage. The browser polls
only while the check is active. Closing Settings/collapsing the section/hiding the
page stops it, and a five-second backend keepalive deadline cleans up capture if the
page disappears. Backend shutdown also stops capture. No audio profile switches,
service changes or automatic microphone activation are introduced.
