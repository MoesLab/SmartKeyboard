# Smart Keyboard design requirements

- Use `Neon Smart Keyboard Checkpoint Cockpit.png` as the primary layout reference. The comparison image provides alternate theme references, not the current layout.
- Keep a fixed 1920 x 1080 design canvas. Uniformly scale the whole canvas only when the viewport changes; never resize individual controls because content, workspace, or keyboard visibility changes.
- Upper section: workspace pages on the left, fixed editor/composer in the center, named macros on the right.
- Lower section: a fixed 6-column by 5-row Quick Text grid. The keyboard overlays this SAME section when shown. Hiding the keyboard reveals Quick Text. Do not reclaim keyboard space for the upper editor or macros.
- Page and workspace switching must preserve control dimensions and positions. Use fixed slots and explicit paging.
- Preserve existing saved named macros and both reference images.
- Do not modify EZ Signage services, display setup, or existing Chromium profiles.
- Verify geometry remains identical across keyboard toggles and page/workspace switches. Verify no overflow at 1920 x 1080.
- Do not present USB HID, dictation, script execution, or formatting controls as operational before they are implemented.
