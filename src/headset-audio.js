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
