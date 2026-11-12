# Smart Keyboard

Lightweight touchscreen prototype for the Radxa Cubie A7Z. Uses plain HTML, CSS, and JavaScript with no build step or downloaded libraries.

**Bluetooth milestone:** GUI startup and the Linux-mode driver survive reboot. The user confirmed Bluetooth pairing, text delivery to the PC, and Ctrl+A. The next-round speed update targets ~100 characters/second instead of ~33; it is prepared in GitHub but still needs installation and hardware testing next session. Updating only `src` does not update the backend: rerun the Bluetooth keyboard installer after copying backend/scripts. See [backend/README.md](backend/README.md). Earlier USB/offline-only descriptions below document prototype history.

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


## Keep-awake and safe shutdown

The Radxa reported X DPMS enabled with 600-second standby/suspend/off timers. At the user's request, the kiosk launcher now applies `xset s off`, `xset s noblank`, and `xset -dpms` on the verified physical DISPLAY=:0 each time it starts. It does not change resolution or other services. Confirm with `DISPLAY=:0 XAUTHORITY=$HOME/.Xauthority xset q` after restart. If another power manager re-enables timers, investigate its identity rather than repeatedly overriding settings. The keyboard dongle works on Windows, but neither hub nor receiver enumerated on Radxa; hub data/power wiring remains to be checked from the requested photo.

The header Shut down control uses a themed confirmation and authenticated `/api/shutdown` endpoint. It saves the shared editor, cancels/releases queued key reports, then asks systemd-logind to power off after a 1.5-second UI acknowledgement delay. It never runs arbitrary commands or bypasses shutdown inhibitors. Failure returns an error to the GUI. Clear and Reload remain immediate. This new shutdown path is locally tested with a mocked power-off manager, NOT by shutting down the development PC; it still needs one controlled Radxa test.

After requesting shutdown, keep power connected until the Radxa finishes powering down. A blank display or disconnected SSH session alone is not proof. Allow about 30 seconds; leave power connected if uncertain. Manual alternative: `sudo systemctl poweroff`. Normal system shutdown naturally closes all applications; the installer does not otherwise modify EZ Signage services.


## Composer Send layout

SEND occupies the wide lower-right composer footer. LF/BS/Home/End/Del have wider targets. Tap **QUICK TEXT ⇄ Keyboard** in the lower-panel heading to show the keyboard; tap **KEYBOARD ⇄ Quick Text** in that same location to return. The editor, fonts, upper panels and 48-button grid retain their previous dimensions. Switching preserves focus and selection.


## Touch selection and keyboard layout

Keyboard now follows fixed staggered 15-unit QWERTY rows and a centered Space bar. Caps, Shift, punctuation, Tab and local navigation edit the composer; they do not directly control the PC. The keyboard still covers the same fixed lower panel.

Tap Select… beside the composer. Tap a numbered line to select it; tap it again to collapse its highlight. Use Start/End arrows to fine-tune the preview (hold to repeat), then Use selection. Cancel restores the previous selection. Lines are newline-delimited; selecting a line includes its following newline when present. One contiguous selection is supported, rather than disjoint selected lines. Start/End steps use grapheme boundaries when supported, preserving emoji/combining characters. Copy, Cut and hold-to-save Quick Text use the applied selection. Native dragging remains available, with selectionchange tracking. Editor dimensions and approved fonts remain unchanged.


The keyboard header now offers English, فارسی, and Symbols. Farsi is a local character layer with automatic text direction; Shift+Space inserts a zero-width non-joiner. It does not switch the Windows input language. Current Bluetooth Send rejects Farsi Unicode instead of silently sending incorrect text; host-layout-aware Farsi transmission remains separate work. ASCII Symbols work with the existing US-layout sender.

### Themes and screen sleep
Settings offers Neon Cyberpunk, Industrial AV and Modern Glass without changing geometry. Interface brightness has 35/65/100% presets (not monitor backlight control). Sleep now, or an optional 1/5/15-minute idle timer, displays a black touch-to-wake overlay. Idle sleep defaults off. One touch wakes without activating an underlying button; the draft and caret are restored. Bluetooth and Linux remain running. Appearance is included in JSON backups.

Macro + Add captures the selected composer block, or the entire draft: first line is the button name, following lines are shortcuts (for example Copy then Ctrl+C). Invalid input now opens themed instructions with Show keyboard; it never silently creates a placeholder or alters the draft. Valid input asks once before saving the named macro.
Graphics use static gradients, highlights and frame details, without animation loops or backdrop blur. Per-button drop-shadow filters were removed. Actual Radxa rendering cost and STT concurrency still require hardware measurement.
While asleep, the dim time/connection indicator travels around the screen on a 10-minute loop, with a 48px edge margin. This explicitly requested motion uses one transform animation and is hidden when awake.

Text SEND audio follows accepted backend delivery: light paired notes while queued/sending, a rising chime when reports finish, and lower notes if interrupted. Tone off mutes these cues. Repeated status polls do not replay completion sounds. Reports sent is not acknowledgement by the PC application.

Settings > Tone volume offers 25/50/75/100% plus Test sound. It scales app button and SEND tones; 50% preserves the previous level. It is saved and included in JSON backups. Tone off remains the master mute. This does not change the Linux system volume.
The composer lights steadily cyan during a tracked text send, briefly green when Bluetooth reports finish, or amber when interrupted. The draft, caret, fonts and geometry remain unchanged; there is no rapid flashing.


### Workspace phrase and Windows shortcut library

On first load of workspace-library-v1, each workspace is filled up to 80 occupied
Quick Text slots out of its existing 96. Only entirely empty slots are filled;
custom labels/text, extra pages, existing macros and the shared draft are preserved.
Default covers everyday work; Linux and Windows cover troubleshooting/support;
Email covers correspondence; Personal covers daily conversation. Quick Text inserts
plain text only and never runs a shell command. Existing terminal snippets remain.

Windows includes 60 starter shortcuts across editing, windows, File Explorer,
screenshots, virtual desktops and browser tasks (six buttons per macro page).
Existing shortcuts are preserved and equivalent sequences are not duplicated;
custom macros can make the total higher. Win+ labels send the Windows/Meta modifier.
Some actions depend on the focused application, Windows version or enabled features.
Close active window can prompt for shutdown if no app window is open. Lock PC locks
the target computer. These are intentional named shortcuts, not automatic actions.

The migration marker is included in exports so restored updated backups keep their
empty custom slots. Importing a backup from before this library fills its empty
slots on the next reload, while preserving its occupied slots and custom macros.
The library adds no background timers and changes no control dimensions.

Windows shortcut reference: https://support.microsoft.com/en-us/accessibility/windows/keyboard-shortcuts-in-windows
