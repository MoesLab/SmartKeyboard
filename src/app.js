'use strict';
const editor = document.querySelector('#editor');
const keyboard = document.querySelector('#keyboard');
const status = document.querySelector('#status');
let shifted = false;
let selection = [0, 0];
function remember() { selection = [editor.selectionStart, editor.selectionEnd]; }
function focusEditor() {
  const range = [...selection];
  editor.focus({ preventScroll: true });
  editor.setSelectionRange(...range);
  selection = range;
}
for (const event of ['select', 'keyup', 'click', 'input', 'blur']) editor.addEventListener(event, remember);
function insert(text) {
  editor.focus({ preventScroll: true });
  editor.setSelectionRange(...selection);
  editor.setRangeText(text, ...selection, 'end');
  remember();
  status.textContent = `${editor.value.length} characters · Local text only`;
  saveDraft();
}
function backspace() {
  let [start, end] = selection;
  if (start === end && start > 0) {
    // Remove a whole Unicode code point, including surrogate pairs.
    const previous = Array.from(editor.value.slice(0, start)).pop();
    start -= previous.length;
  }
  selection = [start, end];
  insert('');
}
let repeatDelay;
let repeatInterval;
let heldPointer = null;
function stopRepeat() {
  clearTimeout(repeatDelay);
  clearInterval(repeatInterval);
  heldPointer = null;
}
window.addEventListener('pointerup', stopRepeat);
window.addEventListener('pointercancel', stopRepeat);
window.addEventListener('blur', stopRepeat);
document.addEventListener('visibilitychange', stopRepeat);
function render() {
  stopRepeat();
  keyboard.replaceChildren();
  const rows = [
    ['1','2','3','4','5','6','7','8','9','0','Backspace'],
    [...'qwertyuiop'],
    [...'asdfghjkl','Enter'],
    ['Shift', ...'zxcvbnm', '.', ','],
    ['Space', '?', '!', "'", '-']
  ];
  for (const keys of rows) {
    const row = document.createElement('div'); row.className = 'row';
    for (const key of keys) {
      const button = document.createElement('button');
      button.type = 'button';
      button.textContent = key.length === 1 && shifted ? key.toUpperCase() : key;
      if (key.length > 1) button.className = key === 'Space' ? 'space' : 'wide';
      if (key === 'Shift') button.setAttribute('aria-pressed', String(shifted));
      button.addEventListener('pointerdown', event => {
        event.preventDefault();
        if (key !== 'Backspace' || !event.isPrimary || event.button !== 0) return;
        stopRepeat();
        heldPointer = event.pointerId;
        button.setPointerCapture(event.pointerId);
        backspace();
        repeatDelay = setTimeout(() => {
          repeatInterval = setInterval(backspace, 65);
        }, 400);
      });
      button.addEventListener('lostpointercapture', event => {
        if (heldPointer === event.pointerId) stopRepeat();
      });
      button.addEventListener('contextmenu', event => event.preventDefault());
      button.addEventListener('click', event => {
        if (key === 'Shift') { shifted = !shifted; render(); focusEditor(); }
        // Pointer presses delete on pointerdown; keyboard activation uses click.
        else if (key === 'Backspace') { if (event.detail === 0) backspace(); }
        else insert(key === 'Space' ? ' ' : key === 'Enter' ? '\n' : shifted ? key.toUpperCase() : key);
      });
      row.append(button);
    }
    keyboard.append(row);
  }
}
document.querySelector('#select-all').addEventListener('click', () => {
  editor.focus(); editor.select(); remember();
});
document.querySelector('#copy-text').addEventListener('click', async () => {
  const text = selection[0] !== selection[1] ? editor.value.slice(...selection) : editor.value;
  try {
    await navigator.clipboard.writeText(text);
    status.textContent = 'Text copied to this device’s clipboard';
  } catch {
    status.textContent = 'Clipboard unavailable. Select text and use Ctrl+C.';
  }
});
function setKeyboardVisible(visible) {
  stopRepeat();
  document.querySelector('#keyboard-panel').hidden = !visible;
  document.querySelector('#quick-panel').inert = visible;
  document.querySelector('#quick-panel').setAttribute('aria-hidden', String(visible));
  document.querySelector('#toggle-keyboard').textContent = visible ? '⌨ Hide keyboard' : '⌨ Show keyboard';
  document.querySelector('#toggle-keyboard').setAttribute('aria-expanded', String(visible));
  focusEditor();
}
for (const id of ['toggle-keyboard', 'hide-keyboard']) {
  document.getElementById(id).addEventListener('pointerdown', event => event.preventDefault());
}
document.querySelector('#toggle-keyboard').addEventListener('click', () => setKeyboardVisible(document.querySelector('#keyboard-panel').hidden));
document.querySelector('#hide-keyboard').addEventListener('click', () => setKeyboardVisible(false));
document.querySelector('#toggle-keyboard').setAttribute('aria-controls', 'keyboard-panel');
function updateClock() {
  document.querySelector('#clock').textContent = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}
updateClock();
setInterval(updateClock, 10000);
const reloadButton = document.createElement('button');
reloadButton.textContent = 'Reload';
reloadButton.className = 'reload-button';
reloadButton.addEventListener('click', () => {
  if (editor.value && !window.confirm('Reload the interface? Unsaved editor text will be cleared.')) return;
  window.location.reload();
});
document.querySelector('.header-tools').prepend(reloadButton);
document.querySelector('#clear').addEventListener('click', () => {
  if (editor.value && !window.confirm('Clear all text in this page?')) return;
  editor.value = ''; selection = [0, 0]; status.textContent = 'Text cleared'; editor.focus();
});
render();

// One fixed 1920 × 1080 canvas. View changes never reflow its sections.
function fitCanvas() {
  const scale = Math.min(window.innerWidth / 1920, window.innerHeight / 1080);
  const canvas = document.querySelector('main');
  canvas.style.transform = `scale(${scale})`;
  canvas.style.left = `${(window.innerWidth - 1920 * scale) / 2}px`;
  canvas.style.top = `${(window.innerHeight - 1080 * scale) / 2}px`;
}
window.addEventListener('resize', fitCanvas);
fitCanvas();
const workspaceNames = ['General', 'Personal', 'Email', 'AV / Work', 'Technical'];
let activeWorkspace = 0;
let quickPage = 0;
let quickEditing = 0;
let drafts = Array(5).fill('');
let quickTexts = workspaceNames.map(() => [
  ...['Hello, ', 'Hi there, ', 'Thank you very much, ', 'Thank you for reaching out, ',
  'I hope you are doing well, ', 'It was great speaking with you, ', 'My name is Mo Azizi. ',
  'I am an AV engineer. ', 'I am based in Toronto. ', 'I would like to follow up, ',
  'Following our discussion, ', 'I wanted to give you an update, ',
  'Please let me know your availability. ', 'Can we schedule a meeting? ', 'Could you please confirm? ',
  'I have attached the file for review. ', 'Please find the details below. ', 'Let me know if you have any questions. ',
  'The system has been tested. ', 'All rooms are validated. ', 'The issue has been resolved. ',
  'A restart may be required. ', 'I recommend the following steps. ', 'Please proceed when ready. ',
  'I look forward to your reply. ', 'Let’s keep in touch. ', 'Have a great day. ', 'Best regards, ', 'Sincerely, ', 'Mo Azizi']
  .map(text => ({ label: text.trim(), text })),
  ...Array.from({length:30}, () => ({label:'',text:''}))
]);
try {
  const savedDrafts = JSON.parse(localStorage.getItem('smartKeyboard.drafts.v1'));
  if (Array.isArray(savedDrafts) && savedDrafts.length === 5 && savedDrafts.every(d => typeof d === 'string')) drafts = savedDrafts;
  const savedQuick = JSON.parse(localStorage.getItem('smartKeyboard.quickText.v1'));
  if (Array.isArray(savedQuick) && savedQuick.length === 5 && savedQuick.every(p => Array.isArray(p) && p.length === 60 && p.every(q => q && typeof q.label === 'string' && q.label.length <= 60 && typeof q.text === 'string' && q.text.length <= 5000))) quickTexts = savedQuick;
} catch { /* Keep defaults when storage is unavailable. */ }
function saveDraft() {
  drafts[activeWorkspace] = editor.value;
  try { localStorage.setItem('smartKeyboard.drafts.v1', JSON.stringify(drafts)); }
  catch { status.textContent = 'Draft is available for this visit only; browser storage unavailable'; }
}
editor.addEventListener('input', saveDraft);
document.querySelector('#clear').addEventListener('click', saveDraft);
const quickForm = document.querySelector('#quick-form');
function editQuick(index) {
  quickEditing = index;
  const phrase = quickTexts[activeWorkspace][index];
  quickForm.elements.label.value = phrase.label;
  quickForm.elements.text.value = phrase.text;
  document.querySelector('#quick-message').textContent = '';
  quickForm.hidden = false;
}
function renderQuick() {
  const container = document.querySelector('#quick-buttons');
  container.replaceChildren();
  quickTexts[activeWorkspace].slice(quickPage * 30, quickPage * 30 + 30).forEach((phrase, offset) => {
    const index = quickPage * 30 + offset;
    const button = document.createElement('button');
    button.type = 'button'; button.textContent = phrase.label || '＋ Set phrase'; button.title = phrase.text;
    let timer; let held = false;
    const cancelHold = () => clearTimeout(timer);
    button.addEventListener('pointerdown', event => {
      event.preventDefault(); if (!event.isPrimary || event.button !== 0) return;
      held = false;
      timer = setTimeout(() => { held = true; editQuick(index); }, 600);
    });
    for (const name of ['pointerup','pointercancel','pointerleave']) button.addEventListener(name, cancelHold);
    window.addEventListener('blur', cancelHold, {once:true});
    button.addEventListener('contextmenu', event => event.preventDefault());
    button.addEventListener('click', () => {
      cancelHold(); if (held) { held = false; return; }
      if (phrase.text) insert(phrase.text); else editQuick(index);
    });
    container.append(button);
  });
  document.querySelector('#quick-page').textContent = `${workspaceNames[activeWorkspace]} · ${quickPage + 1} / 2`;
  document.querySelector('#quick-prev').disabled = quickPage === 0;
  document.querySelector('#quick-next').disabled = quickPage === 1;
}
function renderWorkspaces() {
  const nav = document.querySelector('#workspaces'); nav.replaceChildren();
  workspaceNames.forEach((name, index) => {
    const button = document.createElement('button'); button.textContent = `▱  0${index+1}  ${name}`;
    button.setAttribute('aria-pressed', String(index === activeWorkspace));
    button.addEventListener('click', () => {
      stopRepeat(); saveDraft(); activeWorkspace = index; quickPage = 0;
      editor.value = drafts[index]; selection = [editor.value.length,editor.value.length];
      document.querySelector('#workspace-name').textContent = name;
      status.textContent = `${name} · Local draft`;
      renderWorkspaces(); renderQuick();
    });
    nav.append(button);
  });
}
document.querySelector('#quick-prev').addEventListener('click', () => { quickPage = 0; renderQuick(); });
document.querySelector('#quick-next').addEventListener('click', () => { quickPage = 1; renderQuick(); });
document.querySelector('#quick-edit').addEventListener('click', () => editQuick(quickPage * 30));
document.querySelector('#quick-cancel').addEventListener('click', () => { quickForm.hidden = true; });
quickForm.addEventListener('submit', event => {
  event.preventDefault();
  const label = quickForm.elements.label.value.trim(); const text = quickForm.elements.text.value;
  if (!label || !text.trim()) { document.querySelector('#quick-message').textContent = 'Enter a name and text.'; return; }
  quickTexts[activeWorkspace][quickEditing] = {label,text};
  try {
    localStorage.setItem('smartKeyboard.quickText.v1', JSON.stringify(quickTexts));
    status.textContent = 'Quick Text saved in this browser';
  } catch { status.textContent = 'Quick Text updated for this visit only; browser storage unavailable'; }
  quickForm.hidden = true; renderQuick();
});
editor.value = drafts[0]; selection = [editor.value.length,editor.value.length];
renderWorkspaces(); renderQuick(); setKeyboardVisible(false);
