'use strict';
// Existing file:// profile and its saved settings remain in use.
const bridgeConfig=window.SMARTKEYBOARD_BRIDGE;
let bluetoothState=null;
let bluetoothPanelOpen=false;
let pollingBluetooth=false;
let bluetoothSending=false;
let trackedDeliveryId='';
let reflectedDelivery='';
let previousConnection='';
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
  }catch(error){if(error.name==='AbortError')throw new Error('Bluetooth service timed out. Delivery is unknown; check the PC before sending again.');throw error;}
  finally{clearTimeout(timer);}
}
async function sendBluetooth(route,data){
  if(bluetoothSending)return;
  bluetoothSending=true;
  try{
    const result=await bluetoothRequest(route,data);status.textContent=result.message;
    if(result.delivery?.id){trackedDeliveryId=result.delivery.id;reflectedDelivery='';reflectSendDelivery(result.delivery);}
  }
  catch(error){status.textContent=error.message.includes('fetch')?'Bluetooth service unavailable; nothing sent.':error.message;}
  finally{bluetoothSending=false;focusEditor();pollBluetooth();}
}
window.smartKeyboardTransport={
  sendText:text=>sendBluetooth('/api/send',{text}),
  sendMacro:shortcuts=>sendBluetooth('/api/macro',{shortcuts})
};
function reflectSendDelivery(delivery){
  if(!delivery?.id||delivery.id!==trackedDeliveryId)return;
  const signature=delivery.id+':'+delivery.state+':'+delivery.remainingReports;
  if(signature===reflectedDelivery)return;
  reflectedDelivery=signature;status.textContent=delivery.message;
}
function renderBluetooth(){
  const state=bluetoothState;
  if(state?.shutdownError && shutdownRequested){
    shutdownRequested=false;document.querySelector('#shutdown-panel').hidden=true;
    for(const selector of ['header','.cockpit','.lower-panel'])document.querySelector(selector).inert=false;
    status.textContent=state.shutdownError;focusEditor();
  }
  btButton.textContent=state?.ready?'● BT connected':state?.registered?'◉ Bluetooth':'○ BT offline';
  btButton.setAttribute('aria-label',state?.ready?'Bluetooth connected to '+state.host:'Bluetooth connection settings');
  document.querySelector('#send-text').disabled=bluetoothSending||!!state?.queuedReports;
  if(!window.inspectSmartKeyboardText?.(editor.value))document.querySelector('#send-text').title=state?.ready?'Send whole composer text to '+state.host:'Open Bluetooth settings to check the PC connection';
  const connection=state?.connection||(state?.ready?'ready':state?.registered?'waiting':'offline');
  if(previousConnection&&previousConnection!==connection){
    if(connection==='ready')status.textContent='Bluetooth ready again. Draft kept; nothing automatically resent.';
    else if(previousConnection==='ready')status.textContent='Bluetooth connection changed. Draft kept; nothing automatically resent.';
  }
  previousConnection=connection;
  reflectSendDelivery(state?.delivery);
  document.querySelector('#bluetooth-stop').disabled=!state?.queuedReports;
  if(!bluetoothPanelOpen)return;
  const labels={waiting:'Waiting for your paired PC. Enable Bluetooth on the PC, then Refresh. Pairing again is normally unnecessary.',subscribing:'PC connected, but keyboard input is not subscribed yet. Refresh after a moment.',multiple:'More than one paired device is connected. Leave only the target PC connected before sending.',suspended:'The PC has suspended keyboard input. Wake the PC, then Refresh.',offline:'Bluetooth keyboard service is offline.'};
  btInfo.textContent=state?(state.ready?'Connected: '+state.host:state.error||labels[connection]||state.message)+'\n'+(state.delivery?.message||state.message)+'\n'+(state.pairingSeconds?'Pairing open: '+state.pairingSeconds+' seconds':'Pairing closed')+'\nFocus the target PC app before Send. Interrupted text is never automatically resent.':'Bluetooth service unavailable. Install it and reload this page.';
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
  if(finishConfirmation||window.smartKeyboardSelection?.isOpen()||window.smartKeyboardSettings?.isOpen()||window.smartKeyboardScreen?.isAsleep())return;
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

// Authenticated, explicit-confirmation-only power-off. Never infer completion
// from an HTTP disconnect or a blank display.
let shutdownRequested=false;
document.querySelector('#shutdown-open').addEventListener('pointerdown',event=>event.preventDefault());
document.querySelector('#shutdown-open').addEventListener('click',async()=>{
  if(shutdownRequested)return;
  const accepted=await confirmSave('Shut down the Radxa now? This closes running applications and disconnects Bluetooth. Keep power connected until shutdown has finished.',{title:'Shut down Radxa?',confirmLabel:'Shut down'});
  if(!accepted){focusEditor();return;}
  saveDraft();
  try{
    await bluetoothRequest('/api/shutdown',{confirm:true});
    shutdownRequested=true;document.querySelector('#shutdown-panel').hidden=false;
    for(const selector of ['header','.cockpit','.lower-panel'])document.querySelector(selector).inert=true;
  }catch(error){status.textContent=error.message;focusEditor();}
});

document.querySelector('#bluetooth-refresh').addEventListener('click',async()=>{
  try{bluetoothState=await bluetoothRequest('/api/refresh');renderBluetooth();}
  catch(error){btInfo.textContent=error.message;}
});
document.querySelector('#bluetooth-stop').addEventListener('click',async()=>{
  try{const result=await bluetoothRequest('/api/cancel-send');status.textContent=result.message;reflectSendDelivery(result.delivery);await pollBluetooth();}
  catch(error){btInfo.textContent=error.message;}
});
document.addEventListener('visibilitychange',()=>{if(!document.hidden)pollBluetooth();});
