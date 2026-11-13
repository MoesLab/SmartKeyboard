'use strict';
let headsetAudioState=null,headsetAudioBusy=false;
const headsetAudioMessage=document.querySelector('#headset-audio-message');
function preferredHeadset(devices){return devices?.find(d=>d.name.includes('C0_86_B3_F2_E8_96'));}
function renderHeadsetAudio(){
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
  headsetAudioMessage.textContent=headsetAudioState.inputs?.length?'Headset levels only. HDMI, tone volume and audio mode stay unchanged.':headsetAudioState.outputs?.length?'Headset listening volume is available. No headset microphone is currently exposed.':'Connect your headset, then Refresh audio.';
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
  headsetAudioMessage.textContent=(kind==='output'?'Headset listening':'Microphone')+' level updated.';
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
