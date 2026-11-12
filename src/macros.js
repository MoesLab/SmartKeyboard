'use strict';
// Key sequences are distinct from Quick Text. No synthetic OS keystrokes or HID claims.
const keyMacroStorage = 'smartKeyboard.keyMacros.v1';
const keyPattern = /^(?:(?:Ctrl|Alt|Shift|Meta)\+)*(?:[a-z0-9]|F(?:[1-9]|1[0-2])|Enter|Tab|Escape|Backspace|Delete|Home|End|ArrowLeft|ArrowRight|ArrowUp|ArrowDown|Space)$/i;
function parseMacro(sequence) {
  const lines = sequence.split('\n').filter(line => line.trim());
  if (!lines.length || lines.length > 100) throw new Error('Use 1 to 100 actions per macro.');
  return lines.map(line => {
    if (line.startsWith('TEXT ')) return { type: 'text', value: line.slice(5) };
    if (line.startsWith('KEY ') && keyPattern.test(line.slice(4).trim())) return { type: 'key', value: line.slice(4).trim() };
    throw new Error('Use KEY Ctrl+A or TEXT your text, one action per line.');
  });
}
let keyMacros = [
  {label:'Ctrl + C · Copy', sequence:'KEY Ctrl+C'},
  {label:'Ctrl + V · Paste', sequence:'KEY Ctrl+V'},
  {label:'Ctrl + X · Cut', sequence:'KEY Ctrl+X'},
  {label:'Ctrl + A · Select all', sequence:'KEY Ctrl+A'},
  {label:'Alt + Tab · Switch app', sequence:'KEY Alt+Tab'},
  {label:'Ctrl + S · Save on PC', sequence:'KEY Ctrl+S'},
  {label:'Replace with greeting', sequence:'KEY Ctrl+A\nTEXT Hello,\nKEY Enter'},
  {label:'New line + signature', sequence:'KEY End\nKEY Enter\nTEXT Best regards,\nKEY Enter\nTEXT Mo Azizi'}
];
try {
  const saved = JSON.parse(localStorage.getItem(keyMacroStorage));
  if (Array.isArray(saved) && saved.length && saved.length <= 30 && saved.every(m => {
    if (!m || typeof m.label !== 'string' || !m.label.trim() || m.label.length > 40 || typeof m.sequence !== 'string' || m.sequence.length > 5000) return false;
    try { parseMacro(m.sequence); return true; } catch { return false; }
  })) keyMacros = saved;
} catch { /* Keep default sequences. Legacy text macros are left untouched. */ }
let keyMacroPage = 0;
let macroRunning = false;
async function previewMacro(macro) {
  if (macroRunning) return;
  const steps = parseMacro(macro.sequence);
  const supported = new Set(['ctrl+a','ctrl+c','ctrl+v','ctrl+x','enter','tab','space','backspace','delete','home','end','arrowleft','arrowright']);
  if (steps.some(step => step.type === 'key' && !supported.has(step.value.toLowerCase()))) {
    status.textContent = `${macro.label}: needs USB HID to control Windows; nothing sent.`;
    focusEditor(); return;
  }
  macroRunning = true;
  let changed = false;
  // Clipboard permissions are resolved before any sequence mutates the editor.
  let clipboard = '';
  try {
    if (steps.some(step => step.type === 'key' && step.value.toLowerCase() === 'ctrl+v')) clipboard = await navigator.clipboard.readText();
    for (const step of steps) {
      if (step.type === 'text') { insert(step.value); changed = true; continue; }
      const key = step.value.toLowerCase();
      focusEditor();
      if (key === 'ctrl+a') { editor.select(); remember(); }
      else if (key === 'ctrl+c' || key === 'ctrl+x') {
        clipboard = editor.value.slice(...selection);
        await navigator.clipboard.writeText(clipboard);
        if (key === 'ctrl+x') { insert(''); changed = true; }
      } else if (key === 'ctrl+v') { insert(clipboard); changed = true; }
      else if (['enter','tab','space'].includes(key)) { insert(key === 'enter' ? '\n' : key === 'tab' ? '\t' : ' '); changed = true; }
      else if (key === 'backspace') { backspace(); changed = true; }
      else if (key === 'delete') {
        if (selection[0] === selection[1]) selection[1] += Array.from(editor.value.slice(selection[1]))[0]?.length || 0;
        insert(''); changed = true;
      } else {
        let [start,end] = selection;
        if (key === 'home') start = start === 0 ? 0 : editor.value.lastIndexOf('\n', start - 1) + 1;
        if (key === 'end') { const next = editor.value.indexOf('\n', end); start = next < 0 ? editor.value.length : next; }
        if (key === 'arrowleft') start = start !== end ? start : Math.max(0,start - (Array.from(editor.value.slice(0,start)).pop()?.length || 0));
        if (key === 'arrowright') start = start !== end ? end : end + (Array.from(editor.value.slice(end))[0]?.length || 0);
        selection = [start,start];
      }
    }
    status.textContent = `${macro.label}: previewed in this editor only · USB HID off`;
  } catch {
    status.textContent = `Clipboard unavailable${changed ? '; sequence stopped after earlier actions' : '; sequence stopped'} · nothing sent to Windows`;
  } finally { macroRunning = false; focusEditor(); }
}
function renderKeyMacros() {
  const count = Math.ceil(keyMacros.length / 6);
  keyMacroPage = Math.max(0,Math.min(keyMacroPage,count - 1));
  const container = document.querySelector('#macros'); container.replaceChildren();
  keyMacros.slice(keyMacroPage * 6,keyMacroPage * 6 + 6).forEach(macro => {
    const button = document.createElement('button'); button.textContent = macro.label;
    button.title = `${macro.sequence}\nLocal preview only · Windows output requires USB HID`;
    button.addEventListener('pointerdown', event => event.preventDefault());
    button.addEventListener('click', () => previewMacro(macro)); container.append(button);
  });
  document.querySelector('#macro-page').textContent = `${keyMacroPage+1} / ${count} · LOCAL PREVIEW`;
  document.querySelector('#macros-prev').disabled = keyMacroPage === 0;
  document.querySelector('#macros-next').disabled = keyMacroPage === count - 1;
}
document.querySelector('#macros-prev').addEventListener('click', () => { keyMacroPage--; renderKeyMacros(); focusEditor(); });
document.querySelector('#macros-next').addEventListener('click', () => { keyMacroPage++; renderKeyMacros(); focusEditor(); });
const macroForm = document.querySelector('#macro-form');
const macroFields = document.querySelector('#macro-fields');
function addKeyMacro(macro = {label:'',sequence:''}) {
  const field = document.createElement('fieldset'); field.className = 'macro-field';
  for (const [name,caption,tag,max] of [['label','Button name','input',40],['sequence','Key / text sequence','textarea',5000]]) {
    const label = document.createElement('label'); label.textContent = caption;
    const input = document.createElement(tag); input.name = name; input.value = macro[name]; input.required = true; input.maxLength = max;
    label.append(input); field.append(label);
  }
  macroFields.append(field); document.querySelector('#add-macro').disabled = macroFields.children.length >= 30;
}
function closeKeyMacros() { macroForm.hidden = true; document.querySelector('#edit-macros').setAttribute('aria-expanded','false'); focusEditor(); }
document.querySelector('#edit-macros').addEventListener('click', () => {
  stopRepeat(); macroFields.replaceChildren(); keyMacros.forEach(addKeyMacro);
  document.querySelector('#macro-message').textContent = ''; macroForm.hidden = false;
  document.querySelector('#edit-macros').setAttribute('aria-expanded','true');
});
document.querySelector('#add-macro').addEventListener('click', () => { if (macroFields.children.length < 30) addKeyMacro(); });
document.querySelector('#cancel-macros').addEventListener('click',closeKeyMacros);
macroForm.addEventListener('submit',event => {
  event.preventDefault();
  const next = [...macroFields.children].map(field => ({label:field.querySelector('[name="label"]').value.trim(),sequence:field.querySelector('[name="sequence"]').value}));
  try { next.forEach(macro => { if (!macro.label) throw new Error('Name each button.'); parseMacro(macro.sequence); }); }
  catch(error) { document.querySelector('#macro-message').textContent = error.message; return; }
  keyMacros = next;
  try { localStorage.setItem(keyMacroStorage,JSON.stringify(keyMacros)); status.textContent = 'Key macros saved in this browser'; }
  catch { status.textContent = 'Key macros saved for this visit only; storage unavailable'; }
  renderKeyMacros(); closeKeyMacros();
});
renderKeyMacros();
