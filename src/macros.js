'use strict';
// These buttons describe host shortcuts. They never mutate the composer.
const keyPattern = /^(?:(?:Ctrl|Alt|Shift|Meta|Super)\+)*(?:[a-z0-9]|F(?:[1-9]|1[0-2])|Enter|Tab|Escape|Backspace|Delete|Home|End|ArrowLeft|ArrowRight|ArrowUp|ArrowDown|Space)$/i;
function parseMacro(sequence) {
  const lines=sequence.split('\n').filter(line=>line.trim());
  if (!lines.length || lines.length>100) throw new Error('Use 1 to 100 shortcut lines.');
  return lines.map(line=>{
    const value=line.replace(/^KEY /,'').trim();
    if (!keyPattern.test(value)) throw new Error('Use shortcuts such as Ctrl+C, Alt+Tab or Ctrl+Shift+T, one per line.');
    return value;
  });
}
const common=[['Copy','Ctrl+C'],['Paste','Ctrl+V'],['Cut','Ctrl+X'],['Select all','Ctrl+A'],['Switch application','Alt+Tab'],['Save','Ctrl+S']];
const seeds=[common,
  [['Terminal','Ctrl+Alt+T'],['Copy in terminal','Ctrl+Shift+C'],['Paste in terminal','Ctrl+Shift+V'],['Interrupt command','Ctrl+C'],['Clear terminal','Ctrl+L'],['Switch application','Alt+Tab']],
  [['Copy','Ctrl+C'],['Paste','Ctrl+V'],['Show desktop','Meta+D'],['File Explorer','Meta+E'],['Task Manager','Ctrl+Shift+Escape'],['Switch application','Alt+Tab']],
  [['New message','Ctrl+N'],['Reply','Ctrl+R'],['Reply all','Ctrl+Shift+R'],['Forward','Ctrl+F'],['Send (app dependent)','Ctrl+Enter'],['Find','Ctrl+F']],
  [['Copy','Ctrl+C'],['Paste','Ctrl+V'],['Undo','Ctrl+Z'],['Redo','Ctrl+Y'],['New tab','Ctrl+T'],['Close tab','Ctrl+W']]];
let pageMacros=seeds.map(page=>page.map(([label,sequence])=>({label,sequence})));
const keyMacroStorage='smartKeyboard.pageKeyMacros.v2';
try {
  const saved=JSON.parse(localStorage.getItem(keyMacroStorage));
  if (Array.isArray(saved)&&saved.length===5&&saved.every(page=>Array.isArray(page)&&page.length>0&&page.length<=300&&page.every(m=>{
    if(!m||typeof m.label!=='string'||!m.label.trim()||m.label.length>80||typeof m.sequence!=='string')return false;
    try{parseMacro(m.sequence);return true;}catch{return false;}
  })))pageMacros=saved;
}catch{/* Preserve old macro storage, including its retired local previews. */}
let keyMacroPage=0;
let programmingMacros=false;
async function captureMacro(index) {
  const text=composerCapture();
  const [first,...rest]=text.split('\n');
  const label=first.trim();
  let shortcuts;
  try {
    if(!label||label.length>80||!rest.length)throw new Error('Type the name on line 1 and shortcut(s) below it, select that block, then hold a macro. Example: Copy followed by Ctrl+C on the next line.');
    shortcuts=parseMacro(rest.join('\n'));
  }catch(error){
    status.textContent=error.message;
    const ready=await confirmSave('A macro needs a name on the first line and keyboard shortcuts below it. Example:'+String.fromCharCode(10,10)+'Copy'+String.fromCharCode(10)+'Ctrl+C'+String.fromCharCode(10,10)+'Use the composer and its keyboard to prepare this block. Select the block (or leave the whole draft), then press + Add again. Your current draft has not changed.',{title:'Prepare a new macro',confirmLabel:'Show keyboard'});
    if(ready)setKeyboardVisible(true);
    focusEditor();return;
  }
  const targetWorkspace=activeWorkspace;
  if(!await confirmSave(`Save macro on ${workspaceNames[targetWorkspace]}?\n\n${label}\n${shortcuts.join(' → ')}`)){focusEditor();return;}
  pageMacros[targetWorkspace][index]={label,sequence:shortcuts.join('\n')};
  keyMacroPage=Math.floor(index/6);
  try{localStorage.setItem(keyMacroStorage,JSON.stringify(pageMacros));status.textContent='Macro name and shortcuts saved';}
  catch{status.textContent='Macro saved for this visit only; storage unavailable';}
  programmingMacros=false;renderKeyMacros();focusEditor();
}
function renderKeyMacros(){
  const macros=pageMacros[activeWorkspace];const count=Math.ceil(macros.length/6);
  keyMacroPage=Math.max(0,Math.min(keyMacroPage,count-1));
  const container=document.querySelector('#macros');container.replaceChildren();
  macros.slice(keyMacroPage*6,keyMacroPage*6+6).forEach((macro,offset)=>{
    const index=keyMacroPage*6+offset;
    const button=document.createElement('button');
    const name=document.createElement('strong');name.textContent=macro.label;
    const shortcuts=document.createElement('small');shortcuts.textContent=parseMacro(macro.sequence).join(' → ');
    button.append(name,shortcuts);button.title=`${macro.label}\n${shortcuts.textContent}\nSend shortcut to paired Bluetooth PC`;
    let timer;let held=false;
    button.addEventListener('pointerdown',event=>{
      event.preventDefault();if(!event.isPrimary||event.button!==0)return;
      held=false;timer=setTimeout(()=>{held=true;captureMacro(index);},600);
    });
    const cancel=()=>clearTimeout(timer);
    for(const event of ['pointerup','pointercancel','pointerleave'])button.addEventListener(event,cancel);
    button.addEventListener('contextmenu',event=>event.preventDefault());
    button.addEventListener('click',()=>{
      cancel();if(held){held=false;return;}
      if(programmingMacros){captureMacro(index);return;}
      if(window.smartKeyboardTransport){window.smartKeyboardTransport.sendMacro(parseMacro(macro.sequence));return;}
      status.textContent=`${macro.label} · Bluetooth service unavailable; nothing sent.`;
      focusEditor();
    });container.append(button);
  });
  document.querySelector('#macro-page').textContent=`${keyMacroPage+1} / ${count} · Bluetooth`;
  document.querySelector('#macros-prev').disabled=keyMacroPage===0;
  document.querySelector('#macros-next').disabled=keyMacroPage===count-1;
  document.querySelector('#edit-macros').textContent=programmingMacros?'Cancel':'✎ Set';
  document.querySelector('#add-macro').disabled=macros.length>=300;
}
// Preserve the selected programming block when touch moves away from the editor.
for(const id of ['add-macro','edit-macros'])document.getElementById(id).addEventListener('pointerdown',event=>event.preventDefault());
document.querySelector('#add-macro').title='Add from composer: name on first line, shortcuts below';
document.querySelector('#add-macro').addEventListener('click',()=>{
  const page=pageMacros[activeWorkspace];if(page.length<300)captureMacro(page.length);
});
document.querySelector('#macros-prev').addEventListener('click',()=>{keyMacroPage--;renderKeyMacros();focusEditor();});
document.querySelector('#macros-next').addEventListener('click',()=>{keyMacroPage++;renderKeyMacros();focusEditor();});
document.querySelector('#edit-macros').addEventListener('click',()=>{
  programmingMacros=!programmingMacros;
  status.textContent=programmingMacros?'In editor: name on line 1, shortcut(s) below. Select that block, then tap a macro to save.':'Macro programming cancelled';
  renderKeyMacros();focusEditor();
});
document.addEventListener('workspacechange',()=>{keyMacroPage=0;programmingMacros=false;renderKeyMacros();});
renderKeyMacros();
