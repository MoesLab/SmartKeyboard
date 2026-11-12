# Scripts

The physical touchscreen was verified on DISPLAY `:0` with `$HOME/.Xauthority`. GUI launch and diagnostics explicitly select it, rather than inheriting MobaXterm's forwarded DISPLAY. An earlier launcher inherited the SSH display and could open a healthy GUI on the PC-side X server instead of the touchscreen.

`diagnose-gui.py` launches an isolated diagnostic browser with a random loopback DevTools port, reloads the real app while collecting JavaScript errors, captures layout/viewport state and a screenshot, then closes only that diagnostic process. It uses Python's standard library. Results: `~/SmartKeyboard/logs/gui-diagnostic.json`, `gui-diagnostic.png`, and `gui-diagnostic-browser.log`. No browser profiles are deleted or modified. The diagnostic browser is expected to close after capture. Run `python3 ~/SmartKeyboard/scripts/diagnose-gui.py` from MobaXterm. Tested end-to-end with a local Chromium-family browser; the Radxa run supplies actual target-browser evidence.

`restart-kiosk.sh` recovers a blank Smart Keyboard window by gracefully stopping only main Chromium processes belonging to the current user whose command line contains the exact `~/SmartKeyboard/kiosk-profile` argument, then relaunching the same profile. It preserves saved browser data and does not target test profiles or EZ Signage. It refuses to force-kill a process that does not exit within twelve seconds. Run without sudo.

## Bluetooth keyboard service

`install-bluetooth-keyboard.sh` installs this project's new `smartkeyboard-bluetooth.service`, enables it at boot, and restarts only that service. Run with sudo from the radxa account after copying backend, scripts, and src. The working Linux Bluetooth driver must already be installed. No pip or Bluetooth configuration replacement is performed. See `backend/README.md` for hardware-validation status, pairing, limits, diagnostics, and disabling the service. Reload the existing GUI after service installation to read its locally generated bridge token.

## Tested Bluetooth driver persistence

The Radxa's installed AIC driver was built for Android; a copied build with `CONFIG_BLUEDROID=0` successfully exposed hci0 to BlueZ. `install-bluetooth-driver.sh` installs ONLY that already-tested module into `updates/smartkeyboard` and adds a kernel-specific depmod override. It checks the module name, kernel version and Bluetooth dependency, verifies which file is selected, and leaves the packaged DKMS module intact. Run with sudo and the full path to the tested `.ko`. It does not unload anything, change Wi-Fi, enable a HID profile, or modify EZ Signage. On an installation error, it disables only its own new files and rebuilds the module index.

`rollback-bluetooth-driver.sh` disables these custom files for future loads while keeping them as dated backups; it does not unload the active driver. Kernel updates require a freshly built matching module.

For the confirmed `exec openbox-session` setup, use `install-openbox-startup.sh` instead of the desktop installer. It appends one marked background launch to `~/.config/openbox/autostart`, preserves a pre-existing system autostart file when creating a user file, and backs up an existing user file before editing. Running it again does not duplicate the block. It never changes `.xinitrc`, existing commands, EZ Signage, or system services. It starts the app whenever the existing Openbox session starts; it does not arrange for X to start at boot.

`launch-kiosk.sh` opens the app with software-rendering flags, a stable project-only `~/SmartKeyboard/kiosk-profile`, and a startup log. It wakes the existing X display once without changing sleep timers.

`install-desktop-startup.sh` adds only `~/.config/autostart/smartkeyboard.desktop`. It requires a graphical desktop that honors XDG autostart; it does not configure desktop autologin or alter `.xinitrc`, EZ Signage, Bluetooth, or system services.

After copying `src` and `scripts` to `~/SmartKeyboard`, run `bash ~/SmartKeyboard/scripts/install-desktop-startup.sh`. Test with `bash ~/SmartKeyboard/scripts/launch-kiosk.sh`. The new profile starts with separate browser-local settings; older profiles and their settings remain untouched.

To disable, rename `~/.config/autostart/smartkeyboard.desktop` to `smartkeyboard.desktop.disabled`. Logs: `~/SmartKeyboard/logs/kiosk-startup.log`.
