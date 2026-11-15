'use strict';
let dictationMode='local';
try{const saved=localStorage.getItem('smartKeyboard.dictationMode');if(['local','cloud'].includes(saved))dictationMode=saved;}catch{}
let dictationAvailable=false,dictationActionBusy=false;
let dictationStopRequested=false;
let dictationBusy=false,dictationSession='',dictationPolling=false,dictationStart=null,dictationPollTimer=null;
const dictateButton=document.querySelector('#dictation-toggle');
const dictationMeter=document.querySelector('#dictation-level');
function renderDictation(){
 dictateButton.textContent=dictationBusy?(dictationStopRequested?'Stopping…':'Stop'):'Dictate';
 dictateButton.setAttribute('aria-pressed',String(dictationBusy));dictateButton.disabled=dictationStopRequested;
 dictateButton.title=dictationBusy?'Stop local listening and review text':dictationMode==='cloud'?'Tap Dictate to record; tap Stop for paid cloud transcription. Maximum 60 seconds. Review before inserting.':'Local English dictation; review before inserting. Model setup required.';
 for(const button of document.querySelectorAll('[data-dictation-mode]')){button.disabled=dictationBusy;button.setAttribute('aria-pressed',String(button.dataset.dictationMode===dictationMode));}
 if(typeof renderBluetooth==='function')renderBluetooth();
}
async function stopDictation(){
 window.smartKeyboardSpectrum?.end();
 if(!dictationSession||dictationStopRequested)return;
 dictationStopRequested=true;renderDictation();
 try{await bluetoothRequest('/api/dictation-stop');status.textContent='Stopping dictation…';await pollDictation();}
 catch(error){dictationStopRequested=false;renderDictation();status.textContent=error.message;}
}
async function pollDictation(){
 if(!dictationSession||dictationPolling)return;
 dictationPolling=true;
 try{
  const state=await bluetoothRequest('/api/dictation-status');
  if(state.id!==dictationSession)return;
  dictationMeter.value=state.level||0;
  window.smartKeyboardSpectrum?.update(state,dictationStopRequested);
  if(['loading','listening','stopping','processing'].includes(state.state)){status.textContent=state.partial?`Hearing: ${state.partial}`:state.message;return;}
  if(document.hidden||settingsOpen||bluetoothPanelOpen||finishConfirmation||window.smartKeyboardSelection?.isOpen())return;
  const text=((state.text||'')+(state.state==='error'&&state.partial?' '+state.partial:'')).trim();
  dictationSession='';dictationBusy=false;dictationStopRequested=false;clearInterval(dictationPollTimer);dictationPollTimer=null;dictationMeter.value=0;renderDictation();
  if(!text){status.textContent=state.state==='error'?state.message:'No speech recognized. Your draft is unchanged.';return;}
  const range=editor.value===dictationStart.draft?[...dictationStart.range]:[...selection];
  const accepted=await confirmSave((state.state==='error'?'Recognition stopped early. Review this partial result.\n\n':'')+text+'\n\nInsert at the selected composer position? Nothing has been sent to your PC.',{title:dictationMode==='cloud'?'Review cloud dictation':'Review local English dictation',confirmLabel:'Insert text'});
  if(accepted){
   selection=range;
   const before=editor.value.slice(0,range[0]),after=editor.value.slice(range[1]);
   insert((before&&!/\s$/.test(before)?' ':'')+text+(after&&!/^\s/.test(after)?' ':''));
   status.textContent='Dictation inserted locally. Review it, then use SEND when ready.';
  }else{status.textContent='Dictation discarded; composer unchanged.';focusEditor();}
 }catch(error){window.smartKeyboardSpectrum?.end();status.textContent=error.message;}
 finally{dictationPolling=false;}
}
dictateButton.addEventListener('pointerdown',event=>event.preventDefault());
dictateButton.addEventListener('click',async()=>{
 if(dictationBusy){stopDictation();return;}
 if(dictationActionBusy)return;
 dictationActionBusy=true;
 try{
  const available=await bluetoothRequest('/api/dictation-status');dictationAvailable=available.localAvailable;renderDictation();
  if(dictationMode==='cloud'){
   if(!available.cloudAvailable){await confirmSave('Enable a direct Radxa or ZimaBoard cloud route first. No microphone opened and no audio uploaded.',{title:'Cloud setup required',confirmLabel:'OK'});focusEditor();return;}
   // Cloud selection and explicit Dictate/Stop are the recording/upload actions.
  }else if(!available.localAvailable){await confirmSave(available.setupMessage,{title:'Local English setup required',confirmLabel:'OK'});focusEditor();return;}
  dictationStart={draft:editor.value,range:[...selection]};
  await stopMicMeter();
  const state=await bluetoothRequest('/api/dictation-start',{mode:dictationMode});
  dictationSession=state.id;dictationBusy=true;dictationStopRequested=false;status.textContent=state.message;renderDictation();
  dictationPollTimer=setInterval(pollDictation,350);pollDictation();focusEditor();
 }catch(error){status.textContent=error.message;focusEditor();}
 finally{dictationActionBusy=false;}
});
for(const button of document.querySelectorAll('[data-dictation-mode]'))button.addEventListener('click',()=>{
 if(dictationBusy)return;dictationMode=button.dataset.dictationMode;
 try{localStorage.setItem('smartKeyboard.dictationMode',dictationMode);}catch{}
 renderDictation();status.textContent=dictationMode==='local'?'Local English selected. Recognition runs only after Dictate.':'Cloud · tap Dictate to record, then Stop to upload for paid transcription. Review before Insert.';focusEditor();
});
document.querySelector('#composer-audio-open').addEventListener('pointerdown',event=>event.preventDefault());
document.querySelector('#composer-audio-open').addEventListener('click',()=>{
 setSettingsOpen(true);document.querySelector('#headset-audio').open=true;refreshHeadsetAudio();
});
new MutationObserver(()=>{if(!dictationBusy)dictationMeter.value=micMeter.value;}).observe(micMeter,{attributes:true,attributeFilter:['value']});
document.addEventListener('visibilitychange',()=>{if(document.hidden)stopDictation();else pollDictation();});
document.addEventListener('click',event=>{if(dictationBusy&&event.target.closest('#shutdown-open')){event.preventDefault();event.stopImmediatePropagation();status.textContent='Stop dictation and review it before shutting down.';}},true);
window.smartKeyboardDictation={active:()=>dictationBusy};
renderDictation();

bluetoothRequest('/api/dictation-status').then(state=>{dictationAvailable=state.localAvailable;renderDictation();}).catch(error=>{dictateButton.title='Dictation connection: '+error.message;});

let cloudHealthPolling=false;
async function pollCloudHealth(){
 if(document.hidden||cloudHealthPolling)return;
 cloudHealthPolling=true;const button=document.querySelector('[data-dictation-mode="cloud"]');
 try{
  const health=await bluetoothRequest('/api/cloud-health');
  button.dataset.cloudHealth=['online','offline','checking','unknown'].includes(health.state)?health.state:'unknown';
  button.title=health.message||'Cloud status unavailable';
  button.setAttribute('aria-label','Cloud · '+button.dataset.cloudHealth);
 }catch{button.dataset.cloudHealth='offline';button.title='Cloud status unavailable: check the local backend.';button.setAttribute('aria-label','Cloud · status unavailable');}
 finally{cloudHealthPolling=false;}
}
setInterval(pollCloudHealth,15000);
document.addEventListener('visibilitychange',()=>{if(!document.hidden)pollCloudHealth();});
pollCloudHealth();
