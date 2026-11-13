'use strict';
const appearanceDefaults={theme:'neon',brightness:'100',idle:'0'};
let appearance={...appearanceDefaults};
try{const saved=JSON.parse(localStorage.getItem('smartKeyboard.appearance.v1'));if(saved&&['neon','industrial','glass'].includes(saved.theme)&&['35','65','100'].includes(saved.brightness)&&['0','60','300','900'].includes(saved.idle))appearance=saved;}catch{}
function applyAppearance(){
 document.documentElement.dataset.theme=appearance.theme;
 document.querySelector('main').style.filter=`brightness(${Number(appearance.brightness)/100})`;
 document.querySelectorAll('[data-appearance]').forEach(button=>button.setAttribute('aria-pressed',String(appearance[button.dataset.appearance]===button.dataset.value)));
 try{localStorage.setItem('smartKeyboard.appearance.v1',JSON.stringify(appearance));}catch{}
}
let lastActivity=Date.now(),screenAsleep=false,sleepSelection=null;
const sleepOverlay=document.querySelector('#screen-saver');
function updateSleepIndicator(){ document.querySelector("#sleep-clock").textContent=new Date().toLocaleTimeString([], {hour:"2-digit",minute:"2-digit"}); document.querySelector("#sleep-connection").textContent=bluetoothState?.ready?"Bluetooth connected":"Bluetooth waiting / offline"; }
function sleepScreen(){
 if(window.smartKeyboardDictation?.active()){status.textContent='Stop dictation before sleeping.';if(settingsOpen)settingsMessage.textContent='Stop dictation before sleeping.';return;}
 if(screenAsleep||finishConfirmation||bluetoothPanelOpen||shutdownRequested||window.smartKeyboardSelection?.isOpen()||bluetoothSending||bluetoothState?.queuedReports||bluetoothState?.pairingSeconds)return;
 if(settingsOpen)setSettingsOpen(false);
 remember();saveDraft();stopRepeat();sleepSelection=[...selection];screenAsleep=true;
 updateSleepIndicator();sleepOverlay.hidden=false;document.querySelector('main').inert=true;sleepOverlay.focus({preventScroll:true});
}
function wakeScreen(){
 if(!screenAsleep)return;
 screenAsleep=false;lastActivity=Date.now();sleepOverlay.hidden=true;document.querySelector('main').inert=false;
 selection=sleepSelection;focusEditor();
}
document.querySelectorAll('[data-appearance]').forEach(button=>button.addEventListener('click',()=>{appearance[button.dataset.appearance]=button.dataset.value;lastActivity=Date.now();applyAppearance();}));
document.querySelector('#screen-sleep').addEventListener('click',sleepScreen);
sleepOverlay.addEventListener('pointerdown',event=>{event.preventDefault();event.stopPropagation();});
sleepOverlay.addEventListener('click',event=>{event.preventDefault();event.stopPropagation();wakeScreen();});
sleepOverlay.addEventListener('keydown',event=>{event.preventDefault();event.stopPropagation();if(!event.repeat)wakeScreen();});
for(const type of ['pointerdown','keydown','input'])document.addEventListener(type,()=>{lastActivity=Date.now();},true);
setInterval(()=>{if(!screenAsleep&&!settingsOpen&&Number(appearance.idle)>0&&Date.now()-lastActivity>=Number(appearance.idle)*1000)sleepScreen();},1000);
applyAppearance();
setInterval(()=>{if(screenAsleep)updateSleepIndicator();},15000);
window.smartKeyboardScreen={sleep:sleepScreen,isAsleep:()=>screenAsleep};
