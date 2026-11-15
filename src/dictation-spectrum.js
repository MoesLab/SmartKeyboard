'use strict';
// A separate overlay: never changes Quick Text/keyboard visibility or geometry.
(()=>{
 const panel=document.querySelector('.lower-panel');
 const overlay=document.createElement('section');overlay.id='dictation-spectrum';overlay.className='lower-layer';overlay.hidden=true;
 overlay.setAttribute('aria-label','Live microphone spectrum');
 overlay.innerHTML='<div class="panel-heading"><h2>◉ LISTENING</h2><span id="spectrum-caption">Speak naturally · tap Stop above when finished</span><span id="spectrum-level">Mic activity</span></div><canvas width="930" height="208" aria-label="Speech frequency activity from 80 hertz to 3.8 kilohertz"></canvas>';
 panel.append(overlay);
 const canvas=overlay.querySelector('canvas'),context=canvas.getContext('2d');
 let active=false,frame=0,lastDraw=0,targets=Array(24).fill(0),shown=Array(24).fill(0),saved=[];
 function end(){
  active=false;cancelAnimationFrame(frame);frame=0;overlay.hidden=true;targets.fill(0);shown.fill(0);
  for(const [element,inert] of saved)element.inert=inert;saved=[];
 }
 function draw(now){
  if(!active||document.hidden)return;
  frame=requestAnimationFrame(draw);if(now-lastDraw<50)return;lastDraw=now;
  const width=canvas.width,height=canvas.height,base=height-24;
  context.clearRect(0,0,width,height);
  context.strokeStyle='#50d9eb18';context.lineWidth=1;
  for(let row=1;row<5;row++){const y=base-row*32;context.beginPath();context.moveTo(10,y);context.lineTo(width-10,y);context.stroke();}
  const color=getComputedStyle(document.documentElement).getPropertyValue('--cyan').trim()||'#42ebff';
  const gradient=context.createLinearGradient(0,base,0,16);gradient.addColorStop(0,'#123743');gradient.addColorStop(0.65,color);gradient.addColorStop(1,'#eea3ff');
  for(let i=0;i<24;i++){
   shown[i]+=(targets[i]-shown[i])*(targets[i]>shown[i]?0.5:0.22);
   const step=(width-32)/24,x=16+i*step,bar=step-7,h=Math.max(2,shown[i]/100*(base-20));
   context.fillStyle=gradient;context.fillRect(x,base-h,bar,h);
   context.fillStyle=color;context.fillRect(x,base-h,bar,2);
  }
  context.fillStyle='#9abcc6';context.font='11px sans-serif';context.textAlign='left';context.fillText('80 Hz',16,height-5);context.textAlign='center';context.fillText('VOICE FREQUENCIES',width/2,height-5);context.textAlign='right';context.fillText('3.8 kHz',width-16,height-5);
 }
 function update(state,stopRequested){
  const listening=state.state==='listening'&&!stopRequested&&!document.hidden;
  if(!listening){end();return;}
  if(!active){
   saved=['quick-panel','keyboard-panel'].map(id=>{const element=document.getElementById(id);const value=element.inert;element.inert=true;return [element,value];});
   active=true;overlay.hidden=false;lastDraw=0;frame=requestAnimationFrame(draw);
  }
  targets=Array.from({length:24},(_,i)=>Math.max(0,Math.min(100,Number(state.spectrum?.[i])||0)));
  document.querySelector('#spectrum-level').textContent='Mic '+Math.round(state.level||0)+'%';
 }
 document.addEventListener('visibilitychange',()=>{if(document.hidden)end();});
 window.smartKeyboardSpectrum={update,end};
})();
