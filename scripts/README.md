# Scripts

For the confirmed `exec openbox-session` setup, use `install-openbox-startup.sh` instead of the desktop installer. It appends one marked background launch to `~/.config/openbox/autostart`, preserves a pre-existing system autostart file when creating a user file, and backs up an existing user file before editing. Running it again does not duplicate the block. It never changes `.xinitrc`, existing commands, EZ Signage, or system services. It starts the app whenever the existing Openbox session starts; it does not arrange for X to start at boot.

`launch-kiosk.sh` opens the app with software-rendering flags, a stable project-only `~/SmartKeyboard/kiosk-profile`, and a startup log. It wakes the existing X display once without changing sleep timers.

`install-desktop-startup.sh` adds only `~/.config/autostart/smartkeyboard.desktop`. It requires a graphical desktop that honors XDG autostart; it does not configure desktop autologin or alter `.xinitrc`, EZ Signage, Bluetooth, or system services.

After copying `src` and `scripts` to `~/SmartKeyboard`, run `bash ~/SmartKeyboard/scripts/install-desktop-startup.sh`. Test with `bash ~/SmartKeyboard/scripts/launch-kiosk.sh`. The new profile starts with separate browser-local settings; older profiles and their settings remain untouched.

To disable, rename `~/.config/autostart/smartkeyboard.desktop` to `smartkeyboard.desktop.disabled`. Logs: `~/SmartKeyboard/logs/kiosk-startup.log`.
