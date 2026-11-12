# Smart Keyboard

Lightweight touchscreen prototype for the Radxa Cubie A7Z. Uses plain HTML, CSS, and JavaScript with no build step or downloaded libraries.

## On your Windows PC

The intended source folder is `D:\Projects\SmartKeyboard`. Open `src\index.html` in Edge or Chrome. Edit those three files with your preferred editor.

Features: fixed neon cockpit, one shared browser-saved editor, Default/Linux/Windows/Email/Personal pages with their own Quick Text and key macros, 48 Quick Text slots per cluster (two clusters per page), switchable key tone, three composer font sizes, letters, digits, punctuation, Backspace hold-to-repeat, Enter, and Shift. Shift capitalizes letters; symbol shifting is not implemented. This does not yet send keystrokes to Windows or access USB HID.

Folders: `src` for the app, `config` for future settings, `assets` for media, `scripts` for helpers, and `backups` for manual backups.

## Copy to Radxa over SSH

These commands are manual instructions, not an automatic deployment. Replace `RADXA_IP` with the board's actual address. They assume SSH is already available and the Linux account is `radxa`. Windows needs the OpenSSH Client (`ssh` and `scp`); MobaXterm SFTP is an alternative. Verify the host fingerprint on first connection.

In Windows PowerShell:

```powershell
ssh radxa@RADXA_IP
```

In that SSH session, make a new, unused release directory. If it already exists, choose a different suffix; do not overwrite an earlier release:

```sh
mkdir -p ~/SmartKeyboard/releases
mkdir ~/SmartKeyboard/releases/prototype-001
exit
```

Back in Windows PowerShell:

```powershell
scp -r D:\Projects\SmartKeyboard\src radxa@RADXA_IP:SmartKeyboard/releases/prototype-001/
ssh radxa@RADXA_IP
```

You can also drag the local `src` folder into that release directory using MobaXterm's SFTP pane.

## Open on the touchscreen

From SSH, launch the HTML file directly. This avoids installing a web server, reserving a port, or adding a service. The display and authority settings below match the earlier successful touchscreen test:

```sh
DISPLAY=:0 XAUTHORITY=/home/radxa/.Xauthority chromium \
  --user-data-dir=/home/radxa/SmartKeyboard/chromium-profile \
  --no-first-run --disable-gpu --new-window \
  file:///home/radxa/SmartKeyboard/releases/prototype-001/src/index.html \
  > /home/radxa/SmartKeyboard/chromium.log 2>&1 &
```

Start in a regular window. Once the UI works, close that Smart Keyboard window and replace `--new-window` with `--kiosk` to test full screen. Alt+F4 closes the focused window. Only launch when the touchscreen is available: a new window can cover whatever is currently displayed there, even with a separate browser profile.

Do not stop or restart EZ Signage, kill existing Chromium processes, change display settings, edit boot files, add startup entries, or modify any existing service. These instructions do none of those things. No `sudo` is needed. Close only the Smart Keyboard window to end the test. To return to an older release, open its HTML path.

## Manual checks before using on Radxa

1. Tap letters and digits; toggle Shift and check uppercase letters.
2. Tap in the middle of the text, then insert a phrase.
3. Select text and replace it with a key; check Backspace and Enter.
4. Check Clear acts immediately and stays cleared after reload. Reload also acts immediately and retains the current saved draft.
5. Check button size and layout on the physical touchscreen.

The keyboard overlays Quick Text in the fixed lower panel. Toggling it never changes upper panel or editor dimensions and preserves the editor selection and focus. Page changes update only Macros and Quick Text; the editor text and selection stay unchanged. Settings are saved in the current browser when storage is available; they are not automatically synchronized between Windows and Radxa. USB HID, automatic startup, and USB-C video are separate future work. Keep the current working HDMI/video and USB/touch wiring for this prototype.

### Key macros versus Quick Text

Quick Text inserts a phrase. To program a button, type or select text in the shared editor, hide the keyboard, hold the destination Quick Text button, and confirm once. The captured text becomes both the label and inserted text. Cancelling leaves the button unchanged.

Save confirmation appears in a neon panel within the app, with Save and Cancel touch buttons. Clear and Reload have no confirmation. The composer toolbar includes Select, Copy, Cut, Paste, LF, repeating BS, Home, End, and Delete. Clipboard access depends on browser permissions. S/M/L choose 20/27/34px composer text without resizing the editor. The header Tone toggle controls a short locally generated beep and saves the preference; sound requires an available audio output and may start only after the first touch. Existing 60-slot Quick Text sets expand to 96 slots without dropping saved entries.

Composer controls now use a large left column and bottom toolbar. The editor has a clean sans-serif font and no background grid. Quick Text labels start at 14px and shrink to 10px when needed; exceptionally long content can still exceed a fixed slot. SEND is visible but reports that USB HID is not connected and preserves the draft without pretending to transmit it.

To expand the current workspace, Quick Text **+ Page** adds 48 blank slots and opens them (up to 20 pages per workspace). Macros **+ Add** captures a name and shortcut block from the editor and creates a new macro, paging automatically (up to 300 macros per workspace). Existing entries remain intact. These settings are saved on the current device/browser, not automatically shared through GitHub.

Macro buttons show a name on top and shortcut(s) underneath. They never insert text or execute local previews in the editor. To program one, type the name on line 1 and shortcuts on following lines in the main editor, select the block, then hold a destination macro and confirm. For example:

```text
Copy in terminal
Ctrl+Shift+C
```

Without USB HID, tapping a macro reports that nothing was sent and leaves the editor untouched. Operating-system and email shortcuts may vary with the target application. Older drafts, text-macro settings and key-macro settings remain in their original storage keys. Default, Email, and Personal Quick Text migrate from their matching earlier pages; the former AV/Work and Technical sets remain in legacy storage. New page-specific settings use separate versioned keys.

The neon theme is implemented in CSS and approximates the reference artwork; dictation, formatting, HID status, and other unimplemented concept controls are not shown as working functions. Display blanking is controlled by the Radxa desktop/power settings, not by this page; no display power configuration is changed by this project.

## Update through GitHub

Source repository: https://github.com/MoesLab/SmartKeyboard

On the Radxa, keep the Git checkout separate from the existing runtime folder and Chromium profile:

```sh
git clone https://github.com/MoesLab/SmartKeyboard.git ~/SmartKeyboard-source
mkdir -p ~/SmartKeyboard
cp -r ~/SmartKeyboard-source/src ~/SmartKeyboard/
```

For later updates:

```sh
git -C ~/SmartKeyboard-source pull --ff-only
cp -r ~/SmartKeyboard-source/src ~/SmartKeyboard/
```

Run the copy only if the clone or pull succeeds. Refresh the existing Smart Keyboard page to load the updated files. The kiosk URL remains `file:///home/radxa/SmartKeyboard/src/index.html`. These commands do not change EZ Signage or install a startup service.

## Desktop startup

The user's actual `.xinitrc` runs `exec openbox-session`. For that setup, pull the repository, copy `src` and `scripts` into `~/SmartKeyboard`, then use:

```sh
bash ~/SmartKeyboard/scripts/install-openbox-startup.sh
bash ~/SmartKeyboard/scripts/launch-kiosk.sh
```

This appends a marked launcher to the existing Openbox startup file and backs up its previous contents. Existing commands are preserved. The app starts whenever `openbox-session` starts; the installer does not change how X starts at boot. To disable, remove only the three-line SmartKeyboard marked block from `~/.config/openbox/autostart`.

The user-requested startup helpers are in `scripts`. They add a per-user desktop autostart entry; they do not modify existing services or configure desktop login. Copy both source folders after pulling:

```sh
cp -r ~/SmartKeyboard-source/src ~/SmartKeyboard/
cp -r ~/SmartKeyboard-source/scripts ~/SmartKeyboard/
bash ~/SmartKeyboard/scripts/install-desktop-startup.sh
```

This is appropriate only if the Radxa runs a graphical desktop that processes XDG autostart. A custom `.xinitrc` kiosk session needs its own integration after inspecting that file. Automatic appearance after power-on also requires desktop autologin; verify the current setup first. See [Radxa automatic-login documentation](https://docs.radxa.com/en/cubie/a7z/system-config/auto-login).

The stable new profile is `~/SmartKeyboard/kiosk-profile`; earlier profiles remain intact, including saved button settings. Startup logs are in `~/SmartKeyboard/logs/kiosk-startup.log`. Bluetooth's test driver is temporary and is not made persistent by these scripts.

## Bluetooth driver persistence

The verified test module was built at `/home/radxa/SmartKeyboard/bt-build-9Wo8Of/aic_btusb.ko` for kernel `5.15.147-14-a733`, with Android mode disabled. It exposed controller F4:AB:5C:E1:D6:80 and peripheral support through BlueZ. This confirms adapter availability, not HID keyboard functionality.

`scripts/install-bluetooth-driver.sh` takes the tested module path, checks compatibility, and installs a separate kernel-specific copy with a [depmod module-priority override](https://man7.org/linux/man-pages/man5/depmod.d.5.html). It retains the package-managed driver and does not unload the active module. Verify selection and a Bluetooth-only reload on the actual Radxa before rebooting. `scripts/rollback-bluetooth-driver.sh` disables the custom copy for future loads without deleting the packaged driver. Read `scripts/README.md` for details. A kernel upgrade requires rebuilding and testing a matching module. A Bluetooth HID keyboard backend is still to be implemented.
