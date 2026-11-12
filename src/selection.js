'use strict';
// A modal selection draft avoids dependence on native touchscreen drag handles.
const selectionPanel=document.querySelector('#selection-panel');
const selectionPreview=document.querySelector('#selection-preview');
const selectionLines=document.querySelector('#selection-lines');
let selectionDraft=[0,0];
let selectionOriginal=[0,0];
let selectionOpen=false;
let selectionTimer;
let selectionDelay;
function stopSelectionRepeat(){clearTimeout(selectionDelay);clearInterval(selectionTimer);}
function textBoundaries(){
  if(Intl.Segmenter){
    const segmenter=new Intl.Segmenter(undefined,{granularity:'grapheme'});
    return [...new Set([0,...[...segmenter.segment(editor.value)].map(item=>item.index),editor.value.length])];
  }
  const result=[0];let offset=0;
  for(const character of Array.from(editor.value)){offset+=character.length;result.push(offset);}
  return result;
}
function previewSelection(){
  selectionPreview.value=editor.value;
  selectionPreview.focus({preventScroll:true});
  selectionPreview.setSelectionRange(...selectionDraft);
  document.querySelector('#selection-summary').textContent=`${selectionDraft[1]-selectionDraft[0]} characters selected · start ${selectionDraft[0]} · end ${selectionDraft[1]}`;
  selectionLines.querySelectorAll('button').forEach(button=>button.setAttribute('aria-pressed',String(Number(button.dataset.start)===selectionDraft[0]&&Number(button.dataset.end)===selectionDraft[1]&&selectionDraft[0]!==selectionDraft[1])));
}
function openSelection(){
  if(finishConfirmation||document.querySelector('#bluetooth-panel')?.hidden===false)return;
  stopRepeat();selectionOriginal=[...selection];selectionDraft=[...selection];
  selectionLines.replaceChildren();let start=0;
  editor.value.split('\n').forEach((line,index,lines)=>{
    const from=start;const end=start+line.length+(index<lines.length-1?1:0);start=end;
    const button=document.createElement('button');button.type='button';
    button.dataset.start=String(from);button.dataset.end=String(end);
    const number=document.createElement('strong');number.textContent=String(index+1).padStart(2,'0');
    const text=document.createElement('span');text.textContent=line||'(blank line)';
    button.append(number,text);button.title=line||'Blank line';
    button.addEventListener('click',()=>{
      selectionDraft=selectionDraft[0]===from&&selectionDraft[1]===end?[from,from]:[from,end];
      previewSelection();
    });selectionLines.append(button);
  });
  selectionOpen=true;selectionPanel.hidden=false;
  for(const selector of ['header','.cockpit','.lower-panel'])document.querySelector(selector).inert=true;
  previewSelection();
}
function closeSelection(apply){
  stopSelectionRepeat();selectionOpen=false;selectionPanel.hidden=true;
  selection=apply?[...selectionDraft]:[...selectionOriginal];
  for(const selector of ['header','.cockpit','.lower-panel'])document.querySelector(selector).inert=false;
  focusEditor();
  if(apply)status.textContent=selection[0]!==selection[1]?'Selection ready for Copy, Cut or Quick Text':'Cursor position updated';
}
function nudgeSelection(edge,direction){
  const boundaries=textBoundaries();const value=selectionDraft[edge];
  const target=direction<0?boundaries.filter(n=>n<value).pop()??0:boundaries.find(n=>n>value)??editor.value.length;
  selectionDraft[edge]=edge===0?Math.min(target,selectionDraft[1]):Math.max(target,selectionDraft[0]);
  previewSelection();
}
for(const button of document.querySelectorAll('[data-selection-edge]')){
  let pointerHandled=false;
  const action=()=>nudgeSelection(Number(button.dataset.selectionEdge),Number(button.dataset.direction));
  button.addEventListener('pointerdown',event=>{
    event.preventDefault();if(!event.isPrimary||event.button!==0)return;
    pointerHandled=true;stopSelectionRepeat();button.setPointerCapture(event.pointerId);action();
    selectionDelay=setTimeout(()=>{selectionTimer=setInterval(action,120);},400);
  });
  button.addEventListener('click',event=>{if(event.detail===0||!pointerHandled)action();pointerHandled=false;});
  button.addEventListener('lostpointercapture',stopSelectionRepeat);
}
window.addEventListener('pointerup',stopSelectionRepeat);
window.addEventListener('pointercancel',stopSelectionRepeat);
window.addEventListener('blur',stopSelectionRepeat);
document.querySelector('#selection-all').addEventListener('click',()=>{selectionDraft=[0,editor.value.length];previewSelection();});
document.querySelector('#selection-clear').addEventListener('click',()=>{selectionDraft=[selectionDraft[0],selectionDraft[0]];previewSelection();});
document.querySelector('#selection-apply').addEventListener('click',()=>closeSelection(true));
document.querySelector('#selection-cancel').addEventListener('click',()=>closeSelection(false));
document.addEventListener('keydown',event=>{
  if(!selectionOpen)return;
  if(event.key==='Escape'){event.preventDefault();closeSelection(false);}
  if(event.key==='Tab'){
    const controls=[...selectionPanel.querySelectorAll('button,textarea')].filter(node=>node.getClientRects().length&&!node.disabled);
    const index=controls.indexOf(document.activeElement);
    event.preventDefault();controls[(index+(event.shiftKey?-1:1)+controls.length)%controls.length].focus();
  }
});
selectionPreview.addEventListener('select',()=>{
  if(selectionOpen&&document.activeElement===selectionPreview)selectionDraft=[selectionPreview.selectionStart,selectionPreview.selectionEnd];
});
window.smartKeyboardSelection={open:openSelection,isOpen:()=>selectionOpen};
