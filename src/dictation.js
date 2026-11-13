'use strict';
let dictationMode='local';
try{const saved=localStorage.getItem('smartKeyboard.dictationMode');if(['local','cloud'].includes(saved))dictationMode=saved;}catch{}
let dictationAvailable=false,dictationActionBusy=false;
let dictationStopRequested=false;
let dictationBusy=false,dictationSession='',dictationPolling=false,dictationStart=null,dictationPollTimer=null;
const dictateButton=document.querySelector('#dictation-toggle');
const dictationMeter=document.querySelector('#dictation-level');
function renderDictation(){
 dictateButton.textContent=dictationBusy?(dictationStopRequested?'Stopping…':'Stop'):dictationMode==='cloud'?'Cloud setup':dictationAvailable?'Dictate':'STT setup';
 dictateButton.setAttribute('aria-pressed',String(dictationBusy));dictateButton.disabled=dictationStopRequested;
 dictateButton.title=dictationBusy?'Stop local listening and review text':dictationMode==='cloud'?'Cloud is not configured. No audio is uploaded.':'Local English dictation; review before inserting. Model setup required.';
 for(const button of document.querySelectorAll('[data-dictation-mode]')){button.disabled=dictationBusy;button.setAttribute('aria-pressed',String(button.dataset.dictationMode===dictationMode));}
 if(typeof renderBluetooth==='function')renderBluetooth();
}
async function stopDictation(){
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
  if(['loading','listening','stopping'].includes(state.state)){status.textContent=state.partial?`Hearing: ${state.partial}`:state.message;return;}
  if(document.hidden||settingsOpen||bluetoothPanelOpen||finishConfirmation||window.smartKeyboardSelection?.isOpen())return;
  const text=((state.text||'')+(state.state==='error'&&state.partial?' '+state.partial:'')).trim();
  dictationSession='';dictationBusy=false;dictationStopRequested=false;clearInterval(dictationPollTimer);dictationPollTimer=null;dictationMeter.value=0;renderDictation();
  if(!text){status.textContent=state.state==='error'?state.message:'No speech recognized. Your draft is unchanged.';return;}
  const range=editor.value===dictationStart.draft?[...dictationStart.range]:[...selection];
  const accepted=await confirmSave((state.state==='error'?'Recognition stopped early. Review this partial result.\n\n':'')+text+'\n\nInsert at the selected composer position? Nothing has been sent to your PC.',{title:'Review local English dictation',confirmLabel:'Insert text'});
  if(accepted){
   selection=range;
   const before=editor.value.slice(0,range[0]),after=editor.value.slice(range[1]);
   insert((before&&!/\s$/.test(before)?' ':'')+text+(after&&!/^\s/.test(after)?' ':''));
   status.textContent='Dictation inserted locally. Review it, then use SEND when ready.';
  }else{status.textContent='Dictation discarded; composer unchanged.';focusEditor();}
 }catch(error){status.textContent=error.message;}
 finally{dictationPolling=false;}
}
dictateButton.addEventListener('pointerdown',event=>event.preventDefault());
dictateButton.addEventListener('click',async()=>{
 if(dictationBusy){stopDictation();return;}
 if(dictationActionBusy)return;
 dictationActionBusy=true;
 try{
  if(dictationMode==='cloud'){
   await confirmSave('Cloud recognition is not configured. No microphone will open and no audio will be uploaded. Local English is available after installing and benchmarking its small model.',{title:'Cloud dictation setup',confirmLabel:'OK'});focusEditor();return;
  }
  const available=await bluetoothRequest('/api/dictation-status');dictationAvailable=available.localAvailable;renderDictation();
  if(!available.localAvailable){await confirmSave(available.setupMessage+'\n\nRun the local STT installer in MobaXterm. It benchmarks before enabling recognition; your existing keyboard remains usable.',{title:'Local English setup required',confirmLabel:'OK'});focusEditor();return;}
  dictationStart={draft:editor.value,range:[...selection]};
  await stopMicMeter();
  const state=await bluetoothRequest('/api/dictation-start',{mode:'local'});
  dictationSession=state.id;dictationBusy=true;dictationStopRequested=false;status.textContent=state.message;renderDictation();
  dictationPollTimer=setInterval(pollDictation,350);pollDictation();focusEditor();
 }catch(error){status.textContent=error.message;focusEditor();}
 finally{dictationActionBusy=false;}
});
for(const button of document.querySelectorAll('[data-dictation-mode]'))button.addEventListener('click',()=>{
 if(dictationBusy)return;dictationMode=button.dataset.dictationMode;
 try{localStorage.setItem('smartKeyboard.dictationMode',dictationMode);}catch{}
 renderDictation();status.textContent=dictationMode==='local'?'Local English selected. Recognition runs only after Dictate.':'Cloud selected, but not configured. No audio will be uploaded.';focusEditor();
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

bluetoothRequest('/api/dictation-status').then(state=>{dictationAvailable=state.localAvailable;renderDictation();}).catch(()=>{});
