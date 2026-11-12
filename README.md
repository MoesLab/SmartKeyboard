# Smart Keyboard

Lightweight touchscreen prototype for the Radxa Cubie A7Z. Uses plain HTML, CSS, and JavaScript with no build step or downloaded libraries.

## On your Windows PC

The intended source folder is `D:\Projects\SmartKeyboard`. Open `src\index.html` in Edge or Chrome. Edit those three files with your preferred editor.

Features: fixed neon cockpit, one shared browser-saved editor, Default/Linux/Windows/Email/Personal pages with their own Quick Text and key macros, 30 Quick Text slots per cluster (two clusters per page), letters, digits, punctuation, Backspace hold-to-repeat, Enter, Shift, and Clear with confirmation. Shift capitalizes letters; symbol shifting is not implemented. This does not yet send keystrokes to Windows or access USB HID.

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
4. Cancel Clear, then confirm Clear.
5. Check button size and layout on the physical touchscreen.

The keyboard overlays Quick Text in the fixed lower panel. Toggling it never changes upper panel or editor dimensions and preserves the editor selection and focus. Page changes update only Macros and Quick Text; the editor text and selection stay unchanged. Settings are saved in the current browser when storage is available; they are not automatically synchronized between Windows and Radxa. USB HID, automatic startup, and USB-C video are separate future work. Keep the current working HDMI/video and USB/touch wiring for this prototype.

### Key macros versus Quick Text

Quick Text inserts a phrase. To program a button, type or select text in the shared editor, hide the keyboard, hold the destination Quick Text button, and confirm once. The captured text becomes both the label and inserted text. Cancelling leaves the button unchanged.

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
