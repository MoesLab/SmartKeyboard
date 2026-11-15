'use strict';
let headsetAudioState=null,headsetAudioBusy=false;
const headsetAudioMessage=document.querySelector('#headset-audio-message');
function preferredHeadset(devices){const name=devices===headsetAudioState?.inputs?(headsetAudioState?.selectedInput||'bluez_source.C0_86_B3_F2_E8_96.headset_head_unit'):document.querySelector('#audio-output-select').value;return devices?.find(d=>d.name===name)||((devices!==headsetAudioState?.inputs)?devices?.find(d=>d.name.includes('C0_86_B3_F2_E8_96')):undefined);}
function renderHeadsetAudio(){
 for(const [id,devices,selected] of [['audio-input-select',headsetAudioState?.inputs,headsetAudioState?.selectedInput],['audio-output-select',headsetAudioState?.outputs,document.querySelector('#audio-output-select').value]]){
  const select=document.getElementById(id),list=[...(devices||[])];
  if(id==='audio-input-select'&&!list.some(d=>d.name==='bluez_source.C0_86_B3_F2_E8_96.headset_head_unit'))list.unshift({name:'bluez_source.C0_86_B3_F2_E8_96.headset_head_unit',description:'Shokz (not currently available)'});
  select.replaceChildren(...list.map(d=>{const option=document.createElement('option');option.value=d.name;option.textContent=d.description||d.name;return option;}));
  if(list.some(d=>d.name===selected))select.value=selected;
  select.disabled=headsetAudioBusy;
 }

 for(const kind of ['output','input']){
  const device=preferredHeadset(headsetAudioState?.[kind==='output'?'outputs':'inputs']);
  for(const button of document.querySelectorAll(`[data-headset-kind="${kind}"]`)){
   button.disabled=headsetAudioBusy||!device;
   button.setAttribute('aria-pressed',String(!!device&&device.volume===Number(button.dataset.headsetVolume)));
  }
  document.querySelector('#headset-'+kind+'-level').textContent=device?`${device.volume}%${device.muted?' · Muted':''}`:'Not available';
 }
 document.querySelector('#headset-audio-test').disabled=headsetAudioBusy||!preferredHeadset(headsetAudioState?.outputs);
 window.refreshHeadsetMicControls?.();
}
async function refreshHeadsetAudio(){
 if(headsetAudioBusy||!settingsOpen)return;
 headsetAudioBusy=true;renderHeadsetAudio();headsetAudioMessage.textContent='Checking headset audio…';
 try{
  headsetAudioState=await bluetoothRequest('/api/audio-status');
  headsetAudioMessage.textContent=headsetAudioState.inputs?.length?'Adjust the selected Radxa microphone. HDMI and tone volume stay unchanged.':headsetAudioState.outputs?.length?'Headset listening volume is available. No headset microphone is currently exposed.':'Connect your headset, then Refresh audio.';
 }catch(error){headsetAudioState=null;headsetAudioMessage.textContent=error.message.includes('fetch')?'Audio bridge unavailable. Update the backend, then Refresh audio.':error.message;}
 finally{headsetAudioBusy=false;renderHeadsetAudio();}
}
document.querySelector('#headset-audio').addEventListener('toggle',()=>{if(document.querySelector('#headset-audio').open)refreshHeadsetAudio();});
document.querySelector('#settings-open').addEventListener('click',()=>{if(document.querySelector('#headset-audio').open)refreshHeadsetAudio();});
document.querySelector('#headset-audio-refresh').addEventListener('click',refreshHeadsetAudio);
document.querySelectorAll('[data-headset-volume]').forEach(button=>button.addEventListener('click',async()=>{
 const kind=button.dataset.headsetKind,device=preferredHeadset(headsetAudioState?.[kind==='output'?'outputs':'inputs']);
 if(headsetAudioBusy||!device)return;
 headsetAudioBusy=true;renderHeadsetAudio();
 try{
  headsetAudioState=await bluetoothRequest('/api/audio-volume',{kind,name:device.name,volume:Number(button.dataset.headsetVolume)});
  headsetAudioMessage.textContent=headsetAudioState.warning||(kind==='output'?'Headset listening':'Microphone')+' level updated.';
 }catch(error){headsetAudioState=null;headsetAudioMessage.textContent=error.message;}
 finally{headsetAudioBusy=false;renderHeadsetAudio();}
}));
renderHeadsetAudio();


let micMeterActive=false,micMeterStarting=false,micMeterTimer=null,micMeterGeneration=0,micMeterPolling=false;
const micMeter=document.querySelector('#headset-mic-meter');
const micMeterText=document.querySelector('#headset-mic-meter-text');
const micMeterButton=document.querySelector('#headset-mic-check');
function renderMicMeter(){
 micMeterButton.textContent=micMeterActive?'Stop mic level':micMeterStarting?'Starting…':'Start mic level';
 micMeterButton.disabled=micMeterStarting||(!micMeterActive&&(!preferredHeadset(headsetAudioState?.inputs)||headsetAudioBusy));
}
async function stopMicMeter(){
 const hadCapture=micMeterActive||micMeterStarting;
 micMeterGeneration++;micMeterActive=false;clearInterval(micMeterTimer);micMeterTimer=null;
 micMeter.value=0;micMeterText.textContent='Mic level stopped · no recording saved';renderMicMeter();
 if(hadCapture)try{await bluetoothRequest('/api/audio-meter-stop');}catch{/* Backend capture expires without keepalives. */}
}
async function pollMicMeter(){
 if(!micMeterActive||micMeterPolling)return;
 if(!settingsOpen||document.hidden||!document.querySelector('#headset-audio').open){stopMicMeter();return;}
 const generation=micMeterGeneration;micMeterPolling=true;
 try{
  const result=await bluetoothRequest('/api/audio-meter-status');
  if(generation!==micMeterGeneration)return;
  micMeter.value=result.level;micMeterText.textContent=result.active?`Live microphone · ${result.db} dBFS · no recording saved`:result.message;
  if(!result.active){micMeterActive=false;clearInterval(micMeterTimer);micMeterTimer=null;renderMicMeter();}
 }catch(error){if(generation===micMeterGeneration){await stopMicMeter();headsetAudioMessage.textContent=error.message;}}
 finally{micMeterPolling=false;}
}
micMeterButton.addEventListener('click',async()=>{
 if(micMeterActive){stopMicMeter();return;}
 const device=preferredHeadset(headsetAudioState?.inputs);if(!device||micMeterStarting)return;
 const generation=++micMeterGeneration;micMeterStarting=true;renderMicMeter();
 try{
  const result=await bluetoothRequest('/api/audio-meter-start',{name:device.name});
  if(generation!==micMeterGeneration||!settingsOpen){await bluetoothRequest('/api/audio-meter-stop');return;}
  micMeterActive=result.active;micMeterText.textContent=result.message;
  if(micMeterActive){micMeterTimer=setInterval(pollMicMeter,350);pollMicMeter();}
 }catch(error){headsetAudioMessage.textContent=error.message;}
 finally{micMeterStarting=false;renderMicMeter();}
});
document.querySelector('#headset-audio').addEventListener('toggle',()=>{if(!document.querySelector('#headset-audio').open)stopMicMeter();});
document.addEventListener('settingschange',()=>{if(!settingsOpen)stopMicMeter();});
document.addEventListener('visibilitychange',()=>{if(document.hidden)stopMicMeter();});
window.addEventListener('pagehide',()=>{clearInterval(micMeterTimer);});
document.querySelector('#headset-audio-test').addEventListener('click',async()=>{
 const device=preferredHeadset(headsetAudioState?.outputs);if(headsetAudioBusy||!device)return;
 headsetAudioBusy=true;renderHeadsetAudio();
 try{const result=await bluetoothRequest('/api/audio-test',{name:device.name});headsetAudioMessage.textContent=result.message;}
 catch(error){headsetAudioMessage.textContent=error.message;}
 finally{headsetAudioBusy=false;renderHeadsetAudio();}
});
renderMicMeter();

window.refreshHeadsetMicControls=renderMicMeter;

document.querySelector('#audio-input-select').addEventListener('change',async event=>{
 await stopMicMeter();
 try{headsetAudioState=await bluetoothRequest('/api/audio-input',{name:event.target.value});headsetAudioMessage.textContent='Input saved. Dictate will use this microphone only.';}
 catch(error){headsetAudioMessage.textContent=error.message;}renderHeadsetAudio();
});
document.querySelector('#audio-output-select').addEventListener('change',renderHeadsetAudio);
document.querySelector('#audio-mic-mute').addEventListener('click',async()=>{
 const device=preferredHeadset(headsetAudioState?.inputs);if(!device)return;
 try{headsetAudioState=await bluetoothRequest('/api/audio-mute',{name:device.name,muted:!device.muted});renderHeadsetAudio();}catch(error){headsetAudioMessage.textContent=error.message;}
});
document.querySelector('#audio-reconnect').addEventListener('click',async()=>{
 await stopMicMeter();
 try{const result=await bluetoothRequest('/api/audio-reconnect');headsetAudioMessage.textContent=result.message;}catch(error){headsetAudioMessage.textContent=error.message;}
});
let audioCheckTimer=null;
async function audioCheckAction(path,data={}){
 await stopMicMeter();
 try{
  const result=await bluetoothRequest(path,data);document.querySelector('#audio-record-status').textContent=result.message;
  clearInterval(audioCheckTimer);audioCheckTimer=setInterval(async()=>{
   try{const state=await bluetoothRequest('/api/audio-check-status');document.querySelector('#audio-record-status').textContent=state.message;if(!state.active){clearInterval(audioCheckTimer);audioCheckTimer=null;}}
   catch{clearInterval(audioCheckTimer);audioCheckTimer=null;}
  },500);
 }catch(error){document.querySelector('#audio-record-status').textContent=error.message;}
}
document.querySelector('#audio-record').addEventListener('click',()=>audioCheckAction('/api/audio-record'));
document.querySelector('#audio-playback').addEventListener('click',()=>{const device=preferredHeadset(headsetAudioState?.outputs);if(device)audioCheckAction('/api/audio-playback',{name:device.name});});
document.addEventListener('settingschange',()=>{if(!settingsOpen){clearInterval(audioCheckTimer);audioCheckTimer=null;}});
