'use strict';
// Existing file:// profile and its saved settings remain in use.
const bridgeConfig=window.SMARTKEYBOARD_BRIDGE;
let bluetoothState=null;
let bluetoothPanelOpen=false;
let pollingBluetooth=false;
let bluetoothSending=false;
const btButton=document.querySelector('#bluetooth-open');
const btPanel=document.querySelector('#bluetooth-panel');
const btInfo=document.querySelector('#bluetooth-info');
const btRequest=document.querySelector('#bluetooth-request');
const btPasskey=document.querySelector('#bluetooth-passkey');
const btKeypad=document.querySelector('#bluetooth-keypad');
async function bluetoothRequest(route,data={}){
  if(!bridgeConfig?.token)throw new Error('Bluetooth service not loaded; nothing sent. Install it, then reload this page.');
  const controller=new AbortController();const timer=setTimeout(()=>controller.abort(),10000);
  try{
    const response=await fetch(bridgeConfig.url+route,{method:'POST',headers:{'Content-Type':'application/json',Authorization:'Bearer '+bridgeConfig.token},body:JSON.stringify(data),signal:controller.signal});
    const result=await response.json();if(!response.ok)throw new Error(result.error||'Bluetooth request failed');return result;
  }catch(error){if(error.name==='AbortError')throw new Error('Bluetooth service timed out');throw error;}
  finally{clearTimeout(timer);}
}
async function sendBluetooth(route,data){
  if(bluetoothSending)return;
  bluetoothSending=true;
  try{const result=await bluetoothRequest(route,data);status.textContent=result.message;}
  catch(error){status.textContent=error.message.includes('fetch')?'Bluetooth service unavailable; nothing sent.':error.message;}
  finally{bluetoothSending=false;focusEditor();pollBluetooth();}
}
window.smartKeyboardTransport={
  sendText:text=>sendBluetooth('/api/send',{text}),
  sendMacro:shortcuts=>sendBluetooth('/api/macro',{shortcuts})
};
function renderBluetooth(){
  const state=bluetoothState;
  btButton.textContent=state?.ready?'● BT connected':state?.registered?'◉ Bluetooth':'○ BT offline';
  btButton.setAttribute('aria-label',state?.ready?'Bluetooth connected to '+state.host:'Bluetooth connection settings');
  document.querySelector('#send-text').title=state?.ready?'Send whole composer text to '+state.host:'Pair a PC through Bluetooth before sending';
  if(!bluetoothPanelOpen)return;
  btInfo.textContent=state ? (state.ready?'Connected: '+state.host:state.error||state.message)+'\n'+(state.pairingSeconds?'Pairing open: '+state.pairingSeconds+' seconds':'Pairing closed')+'\nKeep the target PC app focused before using Send or a macro.' : 'Bluetooth service unavailable. Install it and reload this page.';
  const pending=state?.pairing;
  const identity=pending?.id||'';
  if(btPanel.dataset.request!==identity){btPasskey.value='';btPanel.dataset.request=identity;}
  btRequest.hidden=!pending;
  if(pending){
    document.querySelector('#bluetooth-code').textContent=pending.kind==='confirm'?'Confirm this code also appears on your PC: '+pending.code:pending.kind==='passkey'?'Enter the six digits shown on your PC:':'Allow this PC to pair?';
    const address=pending.device.split('/').pop().replace(/^dev_/,'').replaceAll('_',':');
    document.querySelector('#bluetooth-device').textContent='Device: '+address;
  }
  btPasskey.hidden=pending?.kind!=='passkey';btKeypad.hidden=pending?.kind!=='passkey';
  document.querySelector('#bluetooth-accept').disabled=pending?.kind==='passkey'&&btPasskey.value.length!==6;
  document.querySelector('#bluetooth-display-code').textContent=state?.displayPasskey?'Type '+state.displayPasskey.code+' on your PC keyboard, then press Enter.':'';
}
async function pollBluetooth(){
  if(pollingBluetooth||document.hidden)return;
  pollingBluetooth=true;
  try{
    bluetoothState=await bluetoothRequest('/api/status');
    const previousQueue=pollBluetooth.previousQueue||0;
    if(previousQueue>0 && bluetoothState.queuedReports===0 && bluetoothState.message)status.textContent=bluetoothState.message;
    pollBluetooth.previousQueue=bluetoothState.queuedReports||0;
    if(bluetoothState.pairing && !bluetoothPanelOpen && !finishConfirmation)openBluetooth();
  }catch{bluetoothState=null;}
  finally{pollingBluetooth=false;renderBluetooth();}
}
function openBluetooth(){
  if(finishConfirmation)return;
  bluetoothPanelOpen=true;btPanel.hidden=false;
  for(const selector of ['header','.cockpit','.lower-panel'])document.querySelector(selector).inert=true;
  renderBluetooth();document.querySelector('#bluetooth-close').focus();pollBluetooth();
}
function closeBluetooth(){
  bluetoothPanelOpen=false;btPanel.hidden=true;
  for(const selector of ['header','.cockpit','.lower-panel'])document.querySelector(selector).inert=false;
  focusEditor();
}
btButton.addEventListener('click',openBluetooth);
document.querySelector('#bluetooth-close').addEventListener('click',closeBluetooth);
document.querySelector('#bluetooth-pair').addEventListener('click',async()=>{
  try{await bluetoothRequest('/api/pair');await pollBluetooth();}
  catch(error){btInfo.textContent=error.message;}
});
for(const [id,accept] of [['bluetooth-accept',true],['bluetooth-reject',false]])document.getElementById(id).addEventListener('click',async()=>{
  try{
    await bluetoothRequest('/api/pair-answer',{id:bluetoothState?.pairing?.id,accept,passkey:btPasskey.value});
    await pollBluetooth();
  }catch(error){btInfo.textContent=error.message;}
});
for(const digit of ['1','2','3','4','5','6','7','8','9','⌫','0','Clear']){
  const button=document.createElement('button');button.textContent=digit;
  button.addEventListener('click',()=>{
    btPasskey.value=digit==='Clear'?'':digit==='⌫'?btPasskey.value.slice(0,-1):(btPasskey.value+digit).slice(0,6);
    document.querySelector('#bluetooth-accept').disabled=btPasskey.value.length!==6;
  });btKeypad.append(button);
}
document.addEventListener('keydown',event=>{
  if(!bluetoothPanelOpen)return;
  if(event.key==='Escape'){event.preventDefault();closeBluetooth();}
  if(event.key==='Tab'){
    const buttons=[...btPanel.querySelectorAll('button')].filter(b=>b.getClientRects().length&&!b.disabled);
    const index=buttons.indexOf(document.activeElement);
    event.preventDefault();buttons[(index+(event.shiftKey?-1:1)+buttons.length)%buttons.length].focus();
  }
});
setInterval(pollBluetooth,1500);pollBluetooth();
