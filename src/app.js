'use strict';
const editor = document.querySelector('#editor');
const keyboard = document.querySelector('#keyboard');
const status = document.querySelector('#status');
let shifted = false;
let capsLocked = false;
let keyboardLanguage='en';
try{const saved=localStorage.getItem('smartKeyboard.keyboardLanguage');if(['en','fa','symbols'].includes(saved))keyboardLanguage=saved;}catch{}
let selection = [0, 0];
function remember() { selection = [editor.selectionStart, editor.selectionEnd]; }
function focusEditor() {
  const range = [...selection];
  editor.focus({ preventScroll: true });
  editor.setSelectionRange(...range);
  selection = range;
}
for (const event of ['select', 'keyup', 'click', 'input', 'blur']) editor.addEventListener(event, remember);
document.addEventListener('selectionchange',()=>{if(document.activeElement===editor)remember();});
editor.addEventListener('pointerup',()=>requestAnimationFrame(remember));
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
  const one=keys=>[...keys].map(key=>[key,1]);
  // Standard 15-unit staggered rows; all five rows keep the same dimensions.
  const rows = [
    [...one('`1234567890-='),['Backspace',2]],
    [['Tab',1.5],...one('qwertyuiop[]'),['\\',1.5]],
    [['Caps',1.75],...one("asdfghjkl;'"),['Enter',2.25]],
    [['Shift',2.25],...one('zxcvbnm,./'),['Shift',2.75]],
    [['Home',1.5],['End',1.5],['Left',1],['Up',1],['Space',5],['Down',1],['Right',1],['Del',1.5],['Enter',1.5]]
  ];
  const shiftedSymbols={"1": "!", "2": "@", "3": "#", "4": "$", "5": "%", "6": "^", "7": "&", "8": "*", "9": "(", "0": ")", "`": "~", "-": "_", "=": "+", "[": "{", "]": "}", "\\": "|", ";": ":", "'": "\"", ",": "<", ".": ">", "/": "?"};
  const faMap={"q": "ض", "w": "ص", "e": "ث", "r": "ق", "t": "ف", "y": "غ", "u": "ع", "i": "ه", "o": "خ", "p": "ح", "[": "ج", "]": "چ", "\\": "پ", "a": "ش", "s": "س", "d": "ی", "f": "ب", "g": "ل", "h": "ا", "j": "ت", "k": "ن", "l": "م", ";": "ک", "'": "گ", "z": "ظ", "x": "ط", "c": "ز", "v": "ر", "b": "ذ", "n": "د", "m": "ئ", ",": "و", ".": ".", "/": "؟"};
  const faShift={c:'ژ',',':'،',';':'؛','/':'؟'};
  const symbolMap={"q": "@", "w": "#", "e": "$", "r": "%", "t": "&", "y": "*", "u": "(", "i": ")", "o": "[", "p": "]", "[": "{", "]": "}", "a": "+", "s": "-", "d": "=", "f": "_", "g": "/", "h": "\\", "j": "|", "k": ":", "l": ";", ";": "'", "'": "\"", "z": "!", "x": "?", "c": "<", "v": ">", "b": "~", "n": "`", "m": "^"};
  const textForKey=key=>{
    if(keyboardLanguage==='fa')return shifted?(faShift[key]||shiftedSymbols[key]||faMap[key]||key):(faMap[key]||key);
    if(keyboardLanguage==='symbols')return symbolMap[key]||(shifted?(shiftedSymbols[key]||key):key);
    return /^[a-z]$/.test(key)?((shifted!==capsLocked)?key.toUpperCase():key):(shifted?(shiftedSymbols[key]||key):key);
  };
  keyboard.dataset.language=keyboardLanguage;
  document.querySelectorAll('[data-keyboard-language]').forEach(button=>button.setAttribute('aria-pressed',String(button.dataset.keyboardLanguage===keyboardLanguage)));
  document.querySelector('#keyboard-note').textContent=keyboardLanguage==='fa'?'فارسی · Editor only; Bluetooth Farsi Send not implemented':'HOLD BACKSPACE TO REPEAT';
  const arrowLabels={Left:'←',Right:'→',Up:'↑',Down:'↓'};
  for (const keys of rows) {
    const row = document.createElement('div'); row.className = 'row';
    for (const [key,units] of keys) {
      const button = document.createElement('button');
      button.type = 'button';
      button.textContent = key==='Space'&&keyboardLanguage==='fa'&&shifted?'نیم‌فاصله':arrowLabels[key] || (key.length===1?textForKey(key):key);
      button.dataset.key=key;button.style.gridColumn=`span ${units*4}`;
      if (key.length > 1) button.className = key === 'Space' ? 'space' : 'wide';
      if (key === 'Shift') button.setAttribute('aria-pressed', String(shifted));
      if (key === 'Caps') button.setAttribute('aria-pressed', String(capsLocked));
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
        else if(key==='Caps'){capsLocked=!capsLocked;render();focusEditor();}
        // Pointer presses delete on pointerdown; keyboard activation uses click.
        else if (key === 'Backspace') { if (event.detail === 0) backspace(); }
        else if(['Home','End','Left','Right','Up','Down','Del'].includes(key))moveKeyboardCaret(key);
        else insert(key === 'Space' ? (keyboardLanguage==='fa'&&shifted?'\u200c':' ') : key === 'Enter' ? '\n' : key==='Tab'?'\t':textForKey(key));
      });
      row.append(button);
    }
    keyboard.append(row);
  }
}
function moveKeyboardCaret(key){
  let [start,end]=selection;const text=editor.value;
  if(key==='Del'){
    if(start===end)selection[1]+=Array.from(text.slice(end))[0]?.length||0;
    insert('');return;
  }
  if(key==='Left')start=start!==end?start:Math.max(0,start-(Array.from(text.slice(0,start)).pop()?.length||0));
  if(key==='Right')start=start!==end?end:end+(Array.from(text.slice(end))[0]?.length||0);
  if(key==='Home')start=start===0?0:text.lastIndexOf('\n',start-1)+1;
  if(key==='End'){const next=text.indexOf('\n',end);start=next<0?text.length:next;}
  if(key==='Up'||key==='Down'){
    const cursor=key==='Up'?start:end;const lineStart=cursor===0?0:text.lastIndexOf('\n',cursor-1)+1;
    const column=cursor-lineStart;
    if(key==='Up'){
      const previousEnd=Math.max(0,lineStart-1);const previousStart=previousEnd===0?0:text.lastIndexOf('\n',previousEnd-1)+1;
      start=Math.min(previousStart+column,previousEnd);
    }else{
      const lineEnd=text.indexOf('\n',cursor);
      if(lineEnd<0)start=text.length;
      else{const nextStart=lineEnd+1;const nextEnd=text.indexOf('\n',nextStart);start=Math.min(nextStart+column,nextEnd<0?text.length:nextEnd);}
    }
  }
  selection=[start,start];focusEditor();
}
document.querySelector('#select-all').addEventListener('click', () => {
  if(window.smartKeyboardSelection){window.smartKeyboardSelection.open();return;}
  editor.focus();editor.select();remember();
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
  document.querySelector('#toggle-keyboard').textContent = '☷ QUICK TEXT ⇄ Keyboard';
  document.querySelector('#toggle-keyboard').setAttribute('aria-expanded', String(visible));
  focusEditor();
}
for (const id of ['toggle-keyboard', 'hide-keyboard']) {
  document.getElementById(id).addEventListener('pointerdown', event => event.preventDefault());
}
document.querySelector('#toggle-keyboard').addEventListener('click', () => setKeyboardVisible(document.querySelector('#keyboard-panel').hidden));
document.querySelector('#hide-keyboard').addEventListener('click', () => setKeyboardVisible(false));
document.querySelector('#toggle-keyboard').setAttribute('aria-controls', 'keyboard-panel');
document.querySelectorAll('[data-keyboard-language]').forEach(button=>{
  button.addEventListener('pointerdown',event=>event.preventDefault());
  button.addEventListener('click',()=>{
    keyboardLanguage=button.dataset.keyboardLanguage;shifted=false;capsLocked=false;
    try{localStorage.setItem('smartKeyboard.keyboardLanguage',keyboardLanguage);}catch{}
    render();focusEditor();
    if(keyboardLanguage==='fa')status.textContent='Farsi composes locally. Bluetooth Farsi Send still needs Windows layout support.';
  });
});
function updateClock() {
  document.querySelector('#clock').textContent = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}
updateClock();
setInterval(updateClock, 10000);
const reloadButton = document.createElement('button');
reloadButton.textContent = 'Reload';
reloadButton.className = 'reload-button';
reloadButton.addEventListener('click', () => {
  saveDraft();
  window.location.reload();
});
document.querySelector('.header-tools').prepend(reloadButton);
document.querySelector('#clear').addEventListener('click', () => {
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
const workspaceNames = ['Default', 'Linux', 'Windows', 'Email', 'Personal'];
let activeWorkspace = 0;
let quickPage = 0;
let sharedDraft = '';
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
  ...Array.from({length:66}, () => ({label:'',text:''}))
]);
const pagePhrases = [null,
  ['pwd','ls -la','cd ~','uname -a','df -h','free -h','ip addr','git status','git pull --ff-only'],
  ['Windows settings','File Explorer','Task Manager','System information','Network settings'],
  ['Hello, ','Thank you for your email. ','Please find the attached file. ','I look forward to hearing from you. ','Best regards, '],
  ['Hi! ','I will call you later. ','On my way. ','Thank you! ','See you soon. ']];
pagePhrases.forEach((phrases,index)=>{
  if (phrases) quickTexts[index]=Array.from({length:96},(_,i)=>({label:phrases[i]||'',text:phrases[i]||''}));
});
try {
  const savedDrafts = JSON.parse(localStorage.getItem('smartKeyboard.drafts.v1'));
  sharedDraft = localStorage.getItem('smartKeyboard.sharedDraft.v2') ?? (Array.isArray(savedDrafts) ? savedDrafts.find(d => typeof d === 'string' && d) || '' : '');
  const oldQuick = JSON.parse(localStorage.getItem('smartKeyboard.quickText.v1'));
  if (Array.isArray(oldQuick) && oldQuick.length === 5) {
    for (const [next,old] of [[0,0],[3,2],[4,1]]) {
      if (Array.isArray(oldQuick[old]) && oldQuick[old].length === 60 && oldQuick[old].every(q=>q && typeof q.label==='string' && typeof q.text==='string')) quickTexts[next]=oldQuick[old];
    }
  }
  const savedQuick = JSON.parse(localStorage.getItem('smartKeyboard.quickText.v2'));
  if (Array.isArray(savedQuick) && savedQuick.length === 5 && savedQuick.every(p => Array.isArray(p) && p.length >= 48 && p.length <= 960 && (p.length === 60 || p.length % 48 === 0) && p.every(q => q && typeof q.label === 'string' && typeof q.text === 'string' && q.text.length <= 5000))) quickTexts = savedQuick;
} catch { /* Keep defaults when storage is unavailable. */ }
quickTexts = quickTexts.map(page => [...page,...Array.from({length:Math.max(0,96-page.length)},()=>({label:'',text:''}))]);
function saveDraft() {
  sharedDraft = editor.value;
  try { localStorage.setItem('smartKeyboard.sharedDraft.v2', sharedDraft); }
  catch { status.textContent = 'Draft is available for this visit only; browser storage unavailable'; }
}
editor.addEventListener('input', saveDraft);
document.querySelector('#clear').addEventListener('click', saveDraft);

async function editQuick(index) {
  const text = composerCapture();
  if (!text.trim()) { status.textContent = 'Type or select text in the editor, then hold a Quick Text button.'; focusEditor(); return; }
  if (text.length > 5000) { status.textContent = 'Select up to 5000 characters to save as Quick Text.'; focusEditor(); return; }
  const targetWorkspace = activeWorkspace;
  if (!await confirmSave(`Save this as the button label and text on ${workspaceNames[targetWorkspace]}?\n\n${text.slice(0,300)}${text.length>300?'…':''}`)) { focusEditor(); return; }
  quickTexts[targetWorkspace][index] = {label:text,text};
  try { localStorage.setItem('smartKeyboard.quickText.v2',JSON.stringify(quickTexts)); status.textContent = 'Quick Text label and text saved'; }
  catch { status.textContent = 'Updated for this visit only; browser storage unavailable'; }
  renderQuick(); focusEditor();
}
function composerCapture() { return selection[0] !== selection[1] ? editor.value.slice(...selection) : editor.value; }
function renderQuick() {
  const container = document.querySelector('#quick-buttons');
  container.replaceChildren();
  quickTexts[activeWorkspace].slice(quickPage * 48, quickPage * 48 + 48).forEach((phrase, offset) => {
    const index = quickPage * 48 + offset;
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
  for (const button of container.children) {
    let size=14;
    while(size>10 && (button.scrollHeight>button.clientHeight || button.scrollWidth>button.clientWidth)) button.style.fontSize=`${--size}px`;
  }
  const pageCount=Math.ceil(quickTexts[activeWorkspace].length/48);
  document.querySelector('#quick-page').textContent = `${workspaceNames[activeWorkspace]} · ${quickPage + 1} / ${pageCount}`;
  document.querySelector('#quick-prev').disabled = quickPage === 0;
  document.querySelector('#quick-next').disabled = quickPage === pageCount-1;
  document.querySelector('#add-quick-page').disabled = pageCount >= 20;
}
function renderWorkspaces() {
  const nav = document.querySelector('#workspaces'); nav.replaceChildren();
  workspaceNames.forEach((name, index) => {
    const button = document.createElement('button'); button.textContent = `▱  0${index+1}  ${name}`;
    button.setAttribute('aria-pressed', String(index === activeWorkspace));
    button.addEventListener('pointerdown',event=>event.preventDefault());
    button.addEventListener('click', () => {
      stopRepeat(); saveDraft(); activeWorkspace = index; quickPage = 0;
      document.querySelector('#workspace-name').textContent = name;
      status.textContent = `${name} · Shared editor`;
      renderWorkspaces(); renderQuick();
      document.dispatchEvent(new Event('workspacechange')); focusEditor();
    });
    nav.append(button);
  });
}
document.querySelector('#quick-prev').addEventListener('click', () => { quickPage--; renderQuick(); focusEditor(); });
document.querySelector('#quick-next').addEventListener('click', () => { quickPage++; renderQuick(); focusEditor(); });
document.querySelector('#add-quick-page').addEventListener('click',()=>{
  const page=quickTexts[activeWorkspace];if(page.length>=960)return;
  page.push(...Array.from({length:48},()=>({label:'',text:''})));
  quickPage=page.length/48-1;
  try{localStorage.setItem('smartKeyboard.quickText.v2',JSON.stringify(quickTexts));status.textContent='48 new Quick Text slots added. Hold a slot to save editor text.';}
  catch{status.textContent='Page added for this visit only; storage unavailable';}
  renderQuick();focusEditor();
});
document.querySelector('#quick-edit').addEventListener('click', () => { status.textContent = 'Type/select text in the editor, hide keyboard, then hold the destination Quick Text button to save.'; focusEditor(); });
editor.value = sharedDraft; selection = [editor.value.length,editor.value.length];
renderWorkspaces(); renderQuick(); setKeyboardVisible(false);
