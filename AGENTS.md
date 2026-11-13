# Smart Keyboard design requirements

- Use `Neon Smart Keyboard Checkpoint Cockpit.png` as the primary layout reference. The comparison image provides alternate theme references, not the current layout.
- Keep a fixed 1920 x 1080 design canvas. Uniformly scale the whole canvas only when the viewport changes; never resize individual controls because content, workspace, or keyboard visibility changes.
- Upper section: workspace pages on the left, fixed editor/composer in the center, named macros on the right.
- Lower section: a fixed 8-column by 6-row Quick Text grid (48 slots), with compact labels and 6px gaps. The keyboard overlays this SAME section when shown. Hiding the keyboard reveals Quick Text. Do not reclaim keyboard space for the upper editor or macros.
- Page and workspace switching must preserve control dimensions and positions. Use fixed slots and explicit paging.
- Preserve existing saved named macros and both reference images.
- Do not modify EZ Signage services, display setup, or existing Chromium profiles.
- Launch GUI and diagnostics on the verified physical `DISPLAY=:0` with `$HOME/.Xauthority`. Never inherit MobaXterm's forwarded DISPLAY for touchscreen operations.
- Bluetooth HID is the user's preferred host connection. Basic pairing, actual PC text delivery, and Ctrl+A were user-confirmed. Original 15ms/report (~33 chars/s) worked but felt slow. The next-round default is 5ms/report (~100 chars/s), prepared in GitHub but not installed on the Radxa or hardware-tested yet. Next session: update/reinstall backend and check long strings/repeated characters for omissions. Preserve a 15ms fallback. See backend/README.md.
- Verify geometry remains identical across keyboard toggles and page/workspace switches. Verify no overflow at 1920 x 1080.
- Do not present USB HID, dictation, script execution, or formatting controls as operational before they are implemented.
- Macros are key combinations or sequences (optionally mixed with text), not a second Quick Text panel. Preserve legacy text-macro storage. Local previews must explicitly identify their target; OS shortcuts require a real HID bridge.
- Keyboard hide/show must restore editor focus and the exact selection/caret range. Form editing must retain its own focus.
- Pages are Default, Linux, Windows, Email, Personal. Each has its own Macros and Quick Text. One shared editor must keep text, selection, and focus unchanged on page switches.
- Macro buttons display the name on top and shortcut sequence below. They must NEVER run a preview in or insert anything into the composer. Without HID, report that nothing was sent.
- Program Quick Text from the selected composer text (or whole draft) by holding a destination button and confirming once. Save both label and text together. Program macros from a selected block: name on first line, shortcuts below. Do not require typing into a modal form without an accessible keyboard.
- Clear and Reload act immediately without confirmation. Saving buttons uses the in-app neon dialog, never a system alert/confirm. Keep the composer S/M/L font controls and key-tone toggle; changing font size must not resize the editor.
- Composer: large left-column editing controls and bottom-row LF/BS/Home/End/Del, a prominent SEND button, clean sans-serif text, no background grid. SEND uses the authenticated local Bluetooth bridge and must report errors rather than fake a transmission. Quick Text labels start at 14px with auto-fit down to 10px. Keep + Page and macro + Add controls for expansion.

- User explicitly requested a persistent fix for the verified 600-second display timer: launcher now disables X screen saver/DPMS on :0 at each startup. This authorized timer change is the exception to the earlier no-display-setup-change rule; do not change resolution or EZ Signage.
- Shut down button requires themed confirmation and an authenticated backend call to logind PowerOff. Save the shared draft first, stop/release this app's queued keystrokes, and never claim a blank display/network loss proves power-off completion. Font sizes are approved; leave them unchanged.
- Wireless keyboard receiver works on Windows; neither the external hub nor receiver enumerated on Radxa. Shared charger/hub power or data wiring remains unresolved pending the user's photo. Do not claim a faulty dongle or install keyboard drivers based on current evidence.

- Composer footer: wide 330px SEND at the lower right, with 80px LF/BS/Home/End/Del. No keyboard toggle in the composer. The lower-panel QUICK TEXT/KEYBOARD heading is the switch, with matching 350x44px controls in the same position in both views. Keep editor geometry and fonts unchanged.

- Keyboard is a fixed 15-unit staggered QWERTY layout, five 72px rows, with centered 5-unit Space, Tab/Caps/Shift, punctuation and navigation. Do not stretch each row independently. Select… opens a touch line picker and preview with precise Start/End adjustments, without changing the composer size. Line selection is contiguous, not disjoint. Native drag selection remains available.

- Keyboard header offers English / فارسی / Symbols character layers. Farsi is local composition only for now: current Bluetooth US-layout encoder rejects unsupported Unicode. Do not claim Farsi Send works until a host-layout strategy is implemented and tested. Composer/selection preview use dir=auto; do not change font-size presets or geometry.

- Reliability controls: preflight unsupported characters with exact location and explicit selection action; never strip or send unsupported text silently. Track backend send IDs/states, and distinguish emitted reports from target-app acknowledgement. Disconnects cancel queued work; never automatically resend.
- Settings backup uses a strict whitelist of browser-local settings and schema validation. Never export bridge tokens, BlueZ pairings or credentials. Import requires themed confirmation and a before-restore download; restore only known keys, roll back stored values on quota failure, and reload. Preserve editor dimensions and approved fonts.

- Appearance: Neon Cyberpunk, Industrial AV and Modern Glass are color/surface changes only. Persist appearance in whitelisted backups. App sleep is a black touch-to-wake overlay, not OS suspend or monitor backlight control; preserve caret, draft, Bluetooth and all geometry. Optional idle timer defaults off. Never sleep over a send or pairing request.

- Workspace library v1 fills only entirely empty Quick Text slots up to 80 occupied per workspace and appends missing Windows shortcuts by canonical sequence. Preserve every custom slot, macro, draft and extra page. Keep the migration marker in validated backups and do not repopulate deliberately cleared slots after migration. Win and Meta are the same host modifier.

- The SCO ownership patch was compiled/loaded and user-tested for voice recording/playback and live meter. Original runtime srcversion EDED47189C73D12635A0B43 can crash on microphone mode; tested patch is 049CCA2FA2A06FBA0732370 on 5.15.147-14-a733. Persist only the currently loaded, tested module, with backups and a driver-identity guard before headset auto-restore. Reboot persistence remains unverified until the user reports its boot test. A generic replacement-headset pairing UI is explicitly deferred.

- STT trial: English first, local Vosk worker only; Local/Cloud selector has Cloud explicitly unconfigured with no upload. Preserve exact pre-STT geometry, occupying only unused composer-header gaps. Checkpoint deployed code before copying STT files. Benchmark on Radxa before enabling; keep disabled if slower than realtime unless explicitly opted in. Dictate/Stop/review/Insert never auto-sends or overwrites an edited draft without review. Offline performance is unverified until the user runs the benchmark. Future replacement-headset UI remains deferred.

- ZimaBoard English sample benchmark passed (RTF0.396, 185.2MiB). LAN STT trial uses pinned TLS/bearer pairing, Radxa RAM-only capture, explicit Stop/transcribe/review/Insert; no GUI geometry changes. Actual headset/network trial and server autostart are not yet verified. Keep private zima-stt.json/server.key outside Git and preserve rollback.
