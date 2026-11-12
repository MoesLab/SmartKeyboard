# Scripts

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
