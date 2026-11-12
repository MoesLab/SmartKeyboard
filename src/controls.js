'use strict';
// The dialog stays inside the fixed canvas and needs no external keyboard.
let finishConfirmation = null;
function confirmSave(message,options={}) {
  if (finishConfirmation) return Promise.resolve(false);
  document.querySelector('#confirmation-title').textContent=options.title||'Save button';
  document.querySelector('#confirmation-save').textContent=options.confirmLabel||'Save button';
  const overlay = document.querySelector('#confirmation');
  document.querySelector('#confirmation-text').textContent = message;
  overlay.hidden = false;
  for (const selector of ['header','.cockpit','.lower-panel']) document.querySelector(selector).inert = true;
  document.querySelector('#confirmation-save').focus();
  return new Promise(resolve => {
    finishConfirmation = result => {
      overlay.hidden = true;
      for (const selector of ['header','.cockpit','.lower-panel']) document.querySelector(selector).inert = false;
      finishConfirmation = null;
      resolve(result);
    };
  });
}
document.querySelector('#confirmation-save').addEventListener('click',()=>finishConfirmation?.(true));
document.querySelector('#confirmation-cancel').addEventListener('click',()=>finishConfirmation?.(false));
document.addEventListener('keydown',event=>{
  if (!finishConfirmation) return;
  if (event.key==='Escape') { event.preventDefault(); finishConfirmation(false); }
  if (event.key==='Tab') {
    event.preventDefault();
    const save=document.querySelector('#confirmation-save');
    const cancel=document.querySelector('#confirmation-cancel');
    (document.activeElement===save?cancel:save).focus();
  }
});

let toneEnabled = true;
let audioContext;
let toneVolume=50;
try{const saved=Number(localStorage.getItem('smartKeyboard.toneVolume'));if([25,50,75,100].includes(saved))toneVolume=saved;}catch{}
try { toneEnabled = localStorage.getItem('smartKeyboard.keyTone') !== 'off'; } catch {}
const toneButton=document.createElement('button');
toneButton.id='key-tone'; toneButton.className='reload-button';
function updateToneButton() {
  toneButton.textContent=toneEnabled?'♪ Tone on':'♪ Tone off';
  toneButton.setAttribute('aria-pressed',String(toneEnabled));
}
function keyTone() {
  if (!toneEnabled) return;
  try {
    const Audio = window.AudioContext || window.webkitAudioContext;
    if (!Audio) return;
    audioContext ||= new Audio();
    if (audioContext.state==='suspended') audioContext.resume().catch(()=>{});
    const osc=audioContext.createOscillator(); const gain=audioContext.createGain();
    const now=audioContext.currentTime;
    osc.type='sine'; osc.frequency.setValueAtTime(950,now);
    gain.gain.setValueAtTime(0.035*toneVolume/50,now); gain.gain.exponentialRampToValueAtTime(0.001,now+0.035);
    osc.connect(gain); gain.connect(audioContext.destination);
    osc.start(now); osc.stop(now+0.04);
    osc.onended=()=>{osc.disconnect();gain.disconnect();};
  } catch { /* Sound availability must never interrupt typing. */ }
}
toneButton.addEventListener('click',()=>{
  toneEnabled=!toneEnabled; updateToneButton();
  try { localStorage.setItem('smartKeyboard.keyTone',toneEnabled?'on':'off'); } catch {}
  if(toneEnabled)keyTone(); focusEditor();
});
updateToneButton();document.querySelector('.header-tools').prepend(toneButton);
// Some touch drivers send a zero-detail compatibility click after pointerdown.
// Track each pointer activation so that fallback never adds a second tone.
const tonePointerPresses=new WeakMap();
document.addEventListener('pointerdown',event=>{
  const button=event.target.closest('button');
  if(button && !button.disabled && button!==toneButton){tonePointerPresses.set(button,performance.now());keyTone();}
},true);
document.addEventListener('keydown',event=>{
  if(event.key==='Enter'||event.key===' '){const button=event.target.closest('button');if(button)tonePointerPresses.delete(button);}
},true);
document.addEventListener('click',event=>{
  const button=event.target.closest('button');
  if(!button||button.disabled||button===toneButton)return;
  const hadPointer=tonePointerPresses.has(button)&&performance.now()-tonePointerPresses.get(button)<10000;
  tonePointerPresses.delete(button);
  if(event.detail===0&&!hadPointer)keyTone();
},true);

let fontSize=27;
try { const saved=Number(localStorage.getItem('smartKeyboard.composerSize')); if([20,27,34].includes(saved))fontSize=saved; } catch {}
function applyFontSize(size) {
  editor.style.fontSize=`${size}px`;
  document.querySelectorAll('#font-sizes button').forEach(button=>button.setAttribute('aria-pressed',String(Number(button.dataset.size)===size)));
}
document.querySelectorAll('#font-sizes button').forEach(button=>button.addEventListener('click',()=>{
  fontSize=Number(button.dataset.size);applyFontSize(fontSize);
  try{localStorage.setItem('smartKeyboard.composerSize',String(fontSize));}catch{}
  focusEditor();
}));
applyFontSize(fontSize);
for(const button of document.querySelectorAll('.tools button,.composer-actions button,#font-sizes button,#send-text'))button.addEventListener('pointerdown',event=>event.preventDefault());
document.querySelector('#send-text').addEventListener('click',()=>{
  if(editor.value && window.smartKeyboardTransport){window.smartKeyboardTransport.sendText(editor.value);return;}
  status.textContent=editor.value?'Bluetooth service unavailable; nothing sent.':'Type text in the composer to send.';
  focusEditor();
});
document.querySelector('#line-feed').addEventListener('click',()=>insert('\n'));
document.querySelector('#cut-text').addEventListener('click',async()=>{
  const range=[...selection];
  if(range[0]===range[1]){status.textContent='Select text to cut';focusEditor();return;}
  try{
    await navigator.clipboard.writeText(editor.value.slice(...range));
    selection=range;insert('');status.textContent='Selection cut to this device’s clipboard';
  }catch{status.textContent='Clipboard unavailable; text was kept';focusEditor();}
});
document.querySelector('#paste-text').addEventListener('click',async()=>{
  try{const text=await navigator.clipboard.readText();insert(text);}
  catch{status.textContent='Clipboard access is unavailable in this browser';focusEditor();}
});
document.querySelector('#delete-text').addEventListener('click',()=>{
  if(selection[0]===selection[1])selection[1]+=Array.from(editor.value.slice(selection[1]))[0]?.length||0;
  insert('');
});
document.querySelector('#caret-home').addEventListener('click',()=>{
  const start=selection[0]===0?0:editor.value.lastIndexOf('\n',selection[0]-1)+1;
  selection=[start,start];focusEditor();
});
document.querySelector('#caret-end').addEventListener('click',()=>{
  const next=editor.value.indexOf('\n',selection[1]);const end=next<0?editor.value.length:next;
  selection=[end,end];focusEditor();
});
const composerBS=document.querySelector('#composer-bs');
composerBS.addEventListener('pointerdown',event=>{
  event.preventDefault();if(!event.isPrimary||event.button!==0)return;
  stopRepeat();heldPointer=event.pointerId;composerBS.setPointerCapture(event.pointerId);backspace();
  repeatDelay=setTimeout(()=>{repeatInterval=setInterval(backspace,65);},400);
});
composerBS.addEventListener('lostpointercapture',()=>stopRepeat());
composerBS.addEventListener('contextmenu',event=>event.preventDefault());
composerBS.addEventListener('click',event=>{if(event.detail===0)backspace();});

// Short, bounded cues follow real Bluetooth delivery state, not button presses.
let sendSoundTimer=null;
function stopSendSound(){clearInterval(sendSoundTimer);sendSoundTimer=null;}
function sendChime(notes){
  if(!toneEnabled||window.smartKeyboardScreen?.isAsleep())return;
  try{
    const Audio=window.AudioContext||window.webkitAudioContext;if(!Audio)return;
    audioContext ||= new Audio();if(audioContext.state==='suspended')audioContext.resume().catch(()=>{});
    const now=audioContext.currentTime;
    notes.forEach((frequency,i)=>{
      const osc=audioContext.createOscillator(),gain=audioContext.createGain(),start=now+i*0.085;
      osc.type='sine';osc.frequency.setValueAtTime(frequency,start);
      gain.gain.setValueAtTime(0.024*toneVolume/50,start);gain.gain.exponentialRampToValueAtTime(0.001,start+0.07);
      osc.connect(gain);gain.connect(audioContext.destination);osc.start(start);osc.stop(start+0.08);
      osc.onended=()=>{osc.disconnect();gain.disconnect();};
    });
  }catch{/* Audio must never interrupt delivery. */}
}
function beginSendSound(){stopSendSound();sendChime([660,880]);sendSoundTimer=setInterval(()=>sendChime([740,880]),650);}
function endSendSound(success){stopSendSound();sendChime(success?[880,1100,1320]:[440,330]);}
window.addEventListener('pagehide',stopSendSound);

function updateToneVolume(){document.querySelectorAll('[data-tone-volume]').forEach(button=>button.setAttribute('aria-pressed',String(Number(button.dataset.toneVolume)===toneVolume)));}
document.querySelectorAll('[data-tone-volume]').forEach(button=>button.addEventListener('click',()=>{
  toneVolume=Number(button.dataset.toneVolume);updateToneVolume();
  try{localStorage.setItem('smartKeyboard.toneVolume',String(toneVolume));}catch{}
}));
document.querySelector('#tone-preview').addEventListener('click',()=>{
  if(!toneEnabled){document.querySelector('#settings-message').textContent='Tone is off. Turn Tone on in the header to hear the preview.';return;}
  sendChime([660,880,1100]);
});
updateToneVolume();

let transferIntervalMs=null;
try{const saved=Number(localStorage.getItem('smartKeyboard.transferIntervalMs'));if([5,10,15].includes(saved))transferIntervalMs=saved;}catch{}
function updateTransferSpeed(){document.querySelectorAll('[data-transfer-interval]').forEach(button=>button.setAttribute('aria-pressed',String(Number(button.dataset.transferInterval)===(transferIntervalMs??bluetoothState?.reportIntervalMs))));}
document.querySelectorAll('[data-transfer-interval]').forEach(button=>button.addEventListener('click',()=>{
  transferIntervalMs=Number(button.dataset.transferInterval);
  try{localStorage.setItem('smartKeyboard.transferIntervalMs',String(transferIntervalMs));}catch{}
  updateTransferSpeed();document.querySelector('#settings-message').textContent='Speed saved for the next send. If letters are missed, choose Reliable (33 chars/s). Rates are approximate.';
}));
// The bridge is declared later; read its current speed only after scripts initialize.
setTimeout(updateTransferSpeed,0);
