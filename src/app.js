'use strict';
const editor = document.querySelector('#editor');
const keyboard = document.querySelector('#keyboard');
const status = document.querySelector('#status');
let shifted = false;
let selection = [0, 0];
function remember() { selection = [editor.selectionStart, editor.selectionEnd]; }
for (const event of ['select', 'keyup', 'click', 'input', 'blur']) editor.addEventListener(event, remember);
function insert(text) {
  editor.focus({ preventScroll: true });
  editor.setSelectionRange(...selection);
  editor.setRangeText(text, ...selection, 'end');
  remember();
  status.textContent = `${editor.value.length} characters · Local text only`;
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
        if (key === 'Shift') { shifted = !shifted; render(); }
        // Pointer presses delete on pointerdown; keyboard activation uses click.
        else if (key === 'Backspace') { if (event.detail === 0) backspace(); }
        else insert(key === 'Space' ? ' ' : key === 'Enter' ? '\n' : shifted ? key.toUpperCase() : key);
      });
      row.append(button);
    }
    keyboard.append(row);
  }
}
const macroStorageKey = 'smartKeyboard.textMacros.v1';
let macros = [
  { label: 'Hello!', text: 'Hello! ' },
  { label: 'Thank you', text: 'Thank you. ' },
  { label: 'One moment', text: 'Please give me a moment. ' },
  { label: 'Yes', text: 'Yes' },
  { label: 'No', text: 'No' }
];
try {
  const saved = JSON.parse(localStorage.getItem(macroStorageKey));
  if (Array.isArray(saved) && saved.length > 0 && saved.length <= 30 && saved.every(m =>
    m && typeof m.label === 'string' && m.label.trim() && m.label.length <= 40 &&
    typeof m.text === 'string' && m.text.trim() && m.text.length <= 5000)) macros = saved;
} catch { /* Storage may be unavailable; keep the starter buttons. */ }
const macroForm = document.querySelector('#macro-form');
const macroFields = document.querySelector('#macro-fields');
const editMacros = document.querySelector('#edit-macros');
const macroMessage = document.querySelector('#macro-message');
function renderMacros() {
  const container = document.querySelector('#macros');
  container.replaceChildren();
  for (const macro of macros) {
    const button = document.createElement('button');
    button.type = 'button';
    button.textContent = macro.label;
    button.title = macro.text;
    button.addEventListener('pointerdown', event => event.preventDefault());
    button.addEventListener('click', () => insert(macro.text));
    container.append(button);
  }
}
function addMacroFields(macro = { label: '', text: '' }) {
  const field = document.createElement('fieldset');
  field.className = 'macro-field';
  const legend = document.createElement('legend');
  legend.textContent = `Button ${macroFields.children.length + 1}`;
  field.append(legend);
  for (const [name, caption, tag, limit] of [
    ['label', 'Button name', 'input', 40], ['text', 'Text to insert', 'textarea', 5000]
  ]) {
    const label = document.createElement('label');
    label.textContent = caption;
    const input = document.createElement(tag);
    input.name = name; input.value = macro[name]; input.required = true; input.maxLength = limit;
    label.append(input); field.append(label);
  }
  macroFields.append(field);
  document.querySelector('#add-macro').disabled = macroFields.children.length >= 30;
}
function closeMacroForm() {
  macroForm.hidden = true;
  editMacros.setAttribute('aria-expanded', 'false');
}
editMacros.addEventListener('click', () => {
  if (!macroForm.hidden) { closeMacroForm(); return; }
  stopRepeat();
  macroFields.replaceChildren();
  macros.forEach(addMacroFields);
  macroMessage.textContent = '';
  macroForm.hidden = false;
  editMacros.setAttribute('aria-expanded', 'true');
});
document.querySelector('#add-macro').addEventListener('click', () => {
  if (macroFields.children.length < 30) addMacroFields();
});
document.querySelector('#cancel-macros').addEventListener('click', closeMacroForm);
macroForm.addEventListener('submit', event => {
  event.preventDefault();
  const next = Array.from(macroFields.children, field => ({
    label: field.querySelector('[name="label"]').value.trim(),
    text: field.querySelector('[name="text"]').value
  }));
  if (next.some(m => !m.label || !m.text.trim())) {
    macroMessage.textContent = 'Enter a name and text for every button.'; return;
  }
  macros = next;
  renderMacros();
  try {
    localStorage.setItem(macroStorageKey, JSON.stringify(macros));
    status.textContent = 'Macro buttons saved in this browser';
  } catch {
    status.textContent = 'Buttons updated for this visit only; browser storage is unavailable';
  }
  closeMacroForm();
});
renderMacros();
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
document.querySelector('#toggle-keyboard').addEventListener('click', event => {
  stopRepeat();
  const hidden = document.querySelector('.keyboard-panel').classList.toggle('collapsed');
  event.currentTarget.textContent = hidden ? 'Show keyboard' : 'Hide keyboard';
  event.currentTarget.setAttribute('aria-expanded', String(!hidden));
});
function updateClock() {
  document.querySelector('#clock').textContent = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}
updateClock();
setInterval(updateClock, 10000);
document.querySelector('#clear').addEventListener('click', () => {
  if (editor.value && !window.confirm('Clear all text in this page?')) return;
  editor.value = ''; selection = [0, 0]; status.textContent = 'Text cleared'; editor.focus();
});
render();
