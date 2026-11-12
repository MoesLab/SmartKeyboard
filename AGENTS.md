# Smart Keyboard design requirements

- Use `Neon Smart Keyboard Checkpoint Cockpit.png` as the primary layout reference. The comparison image provides alternate theme references, not the current layout.
- Keep a fixed 1920 x 1080 design canvas. Uniformly scale the whole canvas only when the viewport changes; never resize individual controls because content, workspace, or keyboard visibility changes.
- Upper section: workspace pages on the left, fixed editor/composer in the center, named macros on the right.
- Lower section: a fixed 8-column by 6-row Quick Text grid (48 slots), with compact labels and 6px gaps. The keyboard overlays this SAME section when shown. Hiding the keyboard reveals Quick Text. Do not reclaim keyboard space for the upper editor or macros.
- Page and workspace switching must preserve control dimensions and positions. Use fixed slots and explicit paging.
- Preserve existing saved named macros and both reference images.
- Do not modify EZ Signage services, display setup, or existing Chromium profiles.
- Bluetooth HID is the user's preferred host connection. USB HID is no longer the primary transport plan. The new BlueZ GATT backend is implemented and locally tested, but not yet hardware-validated. Do not claim successful pairing or delivery until tested with the actual Radxa and PC. See backend/README.md.
- Verify geometry remains identical across keyboard toggles and page/workspace switches. Verify no overflow at 1920 x 1080.
- Do not present USB HID, dictation, script execution, or formatting controls as operational before they are implemented.
- Macros are key combinations or sequences (optionally mixed with text), not a second Quick Text panel. Preserve legacy text-macro storage. Local previews must explicitly identify their target; OS shortcuts require a real HID bridge.
- Keyboard hide/show must restore editor focus and the exact selection/caret range. Form editing must retain its own focus.
- Pages are Default, Linux, Windows, Email, Personal. Each has its own Macros and Quick Text. One shared editor must keep text, selection, and focus unchanged on page switches.
- Macro buttons display the name on top and shortcut sequence below. They must NEVER run a preview in or insert anything into the composer. Without HID, report that nothing was sent.
- Program Quick Text from the selected composer text (or whole draft) by holding a destination button and confirming once. Save both label and text together. Program macros from a selected block: name on first line, shortcuts below. Do not require typing into a modal form without an accessible keyboard.
- Clear and Reload act immediately without confirmation. Saving buttons uses the in-app neon dialog, never a system alert/confirm. Keep the composer S/M/L font controls and key-tone toggle; changing font size must not resize the editor.
- Composer: large left-column editing controls and bottom-row LF/BS/Home/End/Del, a prominent SEND button, clean sans-serif text, no background grid. SEND uses the authenticated local Bluetooth bridge and must report errors rather than fake a transmission. Quick Text labels start at 14px with auto-fit down to 10px. Keep + Page and macro + Add controls for expansion.
