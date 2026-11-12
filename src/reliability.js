'use strict';
// Preflight is advisory; the backend independently validates every send.
function inspectSendText(text){
  const count=[...text].length;
  if(!count)return {kind:'empty',message:'Type text in the composer first.'};
  if(count>1000)return {kind:'length',message:`This draft has ${count} characters. Send supports up to 1000 at a time.`};
  const normalizedPunctuation=new Set(['‘','’','“','”','–','—','…',String.fromCharCode(160)]);
  let offset=0,line=1,column=1;
  for(const character of text){
    const code=character.codePointAt(0);
    if(!(code>=32&&code<=126)&&!['\r','\n','\t'].includes(character)&&!normalizedPunctuation.has(character)){
      const display=code===8204?'zero-width non-joiner':JSON.stringify(character);
      return {kind:'unsupported',character,start:offset,end:offset+character.length,line,column,
        message:`Cannot send ${display} (U+${code.toString(16).toUpperCase().padStart(4,'0')}) at line ${line}, column ${column}. Nothing sent.`,
        help:'The Bluetooth sender currently supports US-layout text. Farsi can be composed locally but cannot be sent yet. Your draft is unchanged.'};
    }
    if(character==='\n'){line++;column=1;}else if(character!=='\r')column++;
    offset+=character.length;
  }
  return null;
}
let lastCheckedDraft=null;
let lastDraftIssue=null;
function refreshSendFeedback(){
  if(editor.value===lastCheckedDraft)return;
  lastCheckedDraft=editor.value;
  const previous=lastDraftIssue;lastDraftIssue=inspectSendText(editor.value);
  const button=document.querySelector('#send-text');
  button.textContent=lastDraftIssue?.kind==='unsupported'||lastDraftIssue?.kind==='length'?'⚠ CHECK TEXT':'➤ SEND';
  button.dataset.invalid=String(!!lastDraftIssue&&lastDraftIssue.kind!=='empty');
  if(lastDraftIssue?.kind==='unsupported'||lastDraftIssue?.kind==='length')status.textContent=lastDraftIssue.message;
  else if(previous&&previous.kind!=='empty')status.textContent='Text is supported. Focus the target PC app before Send.';
}
async function checkedSendText(text){
  const issue=inspectSendText(text);
  if(issue){
    status.textContent=issue.message;
    if(issue.kind==='unsupported'){
      const chosen=await confirmSave(issue.message+'\n\n'+issue.help,{title:'Unsupported character',confirmLabel:'Select character'});
      if(chosen&&editor.value===text){selection=[issue.start,issue.end];focusEditor();}
      else focusEditor();
    }else focusEditor();
    return;
  }
  return sendBluetooth('/api/send',{text});
}
window.inspectSmartKeyboardText=inspectSendText;
window.smartKeyboardTransport.sendText=checkedSendText;
setInterval(refreshSendFeedback,250);refreshSendFeedback();

const backupKeys=new Set([
  'smartKeyboard.transferIntervalMs','smartKeyboard.toneVolume','smartKeyboard.appearance.v1','smartKeyboard.sharedDraft.v2','smartKeyboard.quickText.v2','smartKeyboard.pageKeyMacros.v2',
  'smartKeyboard.composerSize','smartKeyboard.keyTone','smartKeyboard.keyboardLanguage',
  'smartKeyboard.drafts.v1','smartKeyboard.quickText.v1','smartKeyboard.textMacros.v1','smartKeyboard.keyMacros.v1'
]);
const settingsPanel=document.querySelector('#settings-panel');
const settingsMessage=document.querySelector('#settings-message');
let settingsOpen=false;
function setSettingsOpen(open){
  if(open&&(finishConfirmation||window.smartKeyboardSelection?.isOpen()||bluetoothPanelOpen||shutdownRequested))return;
  settingsOpen=open;settingsPanel.hidden=!open;
  for(const selector of ['header','.cockpit','.lower-panel'])document.querySelector(selector).inert=open;
  if(open)document.querySelector('#backup-export').focus();else focusEditor();
}
function buildBackup(){
  const storage={};
  for(const key of backupKeys){const value=localStorage.getItem(key);if(value!==null)storage[key]=value;}
  // Include live defaults and edits even when the browser has not stored them yet.
  storage['smartKeyboard.sharedDraft.v2']=editor.value;
  storage['smartKeyboard.quickText.v2']=JSON.stringify(quickTexts);
  storage['smartKeyboard.pageKeyMacros.v2']=JSON.stringify(pageMacros);
  storage['smartKeyboard.composerSize']=String(fontSize);
  storage['smartKeyboard.keyTone']=toneEnabled?'on':'off';
  storage['smartKeyboard.toneVolume']=String(toneVolume);
  storage['smartKeyboard.keyboardLanguage']=keyboardLanguage;
  return {format:'SmartKeyboardBackup',version:1,createdAt:new Date().toISOString(),storage};
}
function validateBackup(backup){
  if(!backup||backup.format!=='SmartKeyboardBackup'||backup.version!==1||!backup.storage||typeof backup.storage!=='object'||Array.isArray(backup.storage))throw new Error('This is not a supported Smart Keyboard backup.');
  const entries=Object.entries(backup.storage);
  if(!entries.length||entries.some(([key,value])=>!backupKeys.has(key)||typeof value!=='string'))throw new Error('Backup contains unknown settings or invalid values. Nothing changed.');
  const validPhrase=p=>p&&typeof p.label==='string'&&p.label.length<=5000&&typeof p.text==='string'&&p.text.length<=5000;
  const validMacro=m=>{
    if(!m||typeof m.label!=='string'||!m.label.trim()||m.label.length>80||typeof m.sequence!=='string'||m.sequence.length>5000)return false;
    try{parseMacro(m.sequence);return true;}catch{return false;}
  };
  for(const [key,value] of entries){
    let valid=true;
    if(key==='smartKeyboard.sharedDraft.v2')valid=value.length<=100000;
    else if(key==='smartKeyboard.composerSize')valid=['20','27','34'].includes(value);
    else if(key==='smartKeyboard.transferIntervalMs')valid=['5','10','15'].includes(value);
    else if(key==='smartKeyboard.toneVolume')valid=['25','50','75','100'].includes(value);
    else if(key==='smartKeyboard.keyTone')valid=['on','off'].includes(value);
    else if(key==='smartKeyboard.keyboardLanguage')valid=['en','fa','symbols'].includes(value);
    else{
      let data;try{data=JSON.parse(value);}catch{throw new Error('Invalid stored data for '+key);}
      if(key==='smartKeyboard.appearance.v1')valid=data&&['neon','industrial','glass'].includes(data.theme)&&['35','65','100'].includes(data.brightness)&&['0','60','300','900'].includes(data.idle);
      else if(key==='smartKeyboard.quickText.v2')valid=Array.isArray(data)&&data.length===5&&data.every(page=>Array.isArray(page)&&page.length>=48&&page.length<=960&&(page.length===60||page.length%48===0)&&page.every(validPhrase));
      else if(key==='smartKeyboard.pageKeyMacros.v2')valid=Array.isArray(data)&&data.length===5&&data.every(page=>Array.isArray(page)&&page.length>0&&page.length<=300&&page.every(validMacro));
      else if(key==='smartKeyboard.quickText.v1')valid=Array.isArray(data)&&data.length===5&&data.every(page=>Array.isArray(page)&&page.length===60&&page.every(validPhrase));
      else if(key==='smartKeyboard.drafts.v1')valid=Array.isArray(data)&&data.length===5&&data.every(draft=>typeof draft==='string'&&draft.length<=100000);
      else if(key==='smartKeyboard.textMacros.v1')valid=Array.isArray(data)&&data.length<=30&&data.every(validPhrase);
      else if(key==='smartKeyboard.keyMacros.v1')valid=Array.isArray(data)&&data.length<=30&&data.every(m=>m&&typeof m.label==='string'&&m.label.length<=80&&typeof m.sequence==='string'&&m.sequence.length<=5000);
    }
    if(!valid)throw new Error('Invalid setting: '+key+'. Nothing changed.');
  }
  if(!('smartKeyboard.quickText.v2' in backup.storage)||!('smartKeyboard.pageKeyMacros.v2' in backup.storage))throw new Error('Backup is missing Quick Text or macros. Nothing changed.');
  return backup;
}
function downloadBackup(backup,prefix='SmartKeyboard-backup'){
  const url=URL.createObjectURL(new Blob([JSON.stringify(backup,null,2)],{type:'application/json'}));
  const link=document.createElement('a');link.href=url;link.download=prefix+'-'+new Date().toISOString().replace(/[:.]/g,'-')+'.json';
  document.body.append(link);link.click();link.remove();setTimeout(()=>URL.revokeObjectURL(url),5000);
}
function replaceBackupStorage(storage){
  const previous={};for(const key of backupKeys){const value=localStorage.getItem(key);if(value!==null)previous[key]=value;}
  try{
    for(const key of backupKeys)localStorage.removeItem(key);
    for(const [key,value] of Object.entries(storage))localStorage.setItem(key,value);
  }catch(error){
    try{for(const key of backupKeys)localStorage.removeItem(key);for(const [key,value] of Object.entries(previous))localStorage.setItem(key,value);}
    catch{throw new Error('Restore failed and browser storage could not roll back. Keep the before-restore backup file.');}
    throw new Error('Restore failed; previous stored settings restored. Check available browser storage.');
  }
}
document.querySelector('#settings-open').addEventListener('click',()=>{settingsMessage.textContent='';setSettingsOpen(true);});
document.querySelector('#settings-close').addEventListener('click',()=>setSettingsOpen(false));
document.querySelector('#backup-export').addEventListener('click',()=>{
  try{downloadBackup(buildBackup());settingsMessage.textContent='Backup download requested. Copy the JSON file to your PC using MobaXterm for a second copy.';}
  catch(error){settingsMessage.textContent=error.message;}
});
document.querySelector('#backup-import').addEventListener('click',()=>document.querySelector('#backup-file').click());
document.querySelector('#backup-file').addEventListener('change',async event=>{
  const file=event.target.files[0];event.target.value='';if(!file)return;
  try{
    if(file.size>10*1024*1024)throw new Error('Backup is larger than 10 MB. Nothing changed.');
    const backup=validateBackup(JSON.parse(await file.text()));
    setSettingsOpen(false);
    const accepted=await confirmSave('Restore this backup? It replaces your saved buttons, draft and preferences. A before-restore backup of current settings will be downloaded first. The interface will reload.',{title:'Restore Smart Keyboard backup?',confirmLabel:'Restore backup'});
    if(!accepted){setSettingsOpen(true);settingsMessage.textContent='Restore cancelled; settings unchanged.';return;}
    downloadBackup(buildBackup(),'SmartKeyboard-before-restore');
    replaceBackupStorage(backup.storage);
    status.textContent='Backup restored; reloading…';setTimeout(()=>window.location.reload(),250);
  }catch(error){setSettingsOpen(true);settingsMessage.textContent=error.message;}
});
document.addEventListener('keydown',event=>{
  if(!settingsOpen)return;
  if(event.key==='Escape'){event.preventDefault();setSettingsOpen(false);}
  if(event.key==='Tab'){
    const buttons=[...settingsPanel.querySelectorAll('button')].filter(b=>b.getClientRects().length&&!b.disabled);
    const index=buttons.indexOf(document.activeElement);event.preventDefault();buttons[(index+(event.shiftKey?-1:1)+buttons.length)%buttons.length].focus();
  }
});
window.smartKeyboardBackup={build:buildBackup,validate:validateBackup};
window.smartKeyboardSettings={isOpen:()=>settingsOpen};
