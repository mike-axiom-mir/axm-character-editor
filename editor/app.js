'use strict';
const SERVER=null;
const family=DATA.family, presetRows=DATA.presets, $=id=>document.getElementById(id);
let current, checkpoint, undo=[], redo=[], revision=0, queued=null, building=false, currentGLB=null, viewer=null, sketch=null;
let activeClip='idle', poseTime=0;
const copy=value=>structuredClone(value);
function message(text,error=false){$('notice').textContent=text;$('notice').classList.toggle('error',error);}
function fresh(preset){return AXMBlueprint.normalize({schema:'axm.character.blueprint/v0.1',id:current?.id||'player-001',family:family.id,
  preset:preset.id,rig_profile:family.rig_profiles[0].id,editor_profile:current?.editor_profile??null,
  controls:preset.controls,authorship:{method:'HUMAN_EDITOR_EXPLICIT_FIELDS',editor:'axm-character-editor'}},DATA);}
function remember(){
  if(JSON.stringify(current)!==JSON.stringify(checkpoint)){undo.push(checkpoint);if(undo.length>50)undo.shift();redo=[];checkpoint=copy(current);}
  $('undoBtn').disabled=!undo.length;$('redoBtn').disabled=!redo.length;
}
function apply(value,record=true){current=copy(value);if(record)remember();render();updatePreview();}
function render(){
  $('charId').value=current.id;$('profileSelect').value=current.editor_profile||'full';
  $('presets').replaceChildren();
  for(const p of presetRows){
    const button=document.createElement('button');button.className='preset'+(p.id===current.preset?' active':'');
    button.textContent=p.label;button.onclick=()=>apply(fresh(p));$('presets').append(button);
  }
  $('controls').replaceChildren();const groups=new Map();
  const allowed=current.editor_profile?new Set(DATA.profile.visible_controls):null;
  for(const spec of family.controls){if(allowed&&!allowed.has(spec.id))continue;if(!groups.has(spec.group))groups.set(spec.group,[]);groups.get(spec.group).push(spec);}
  for(const [group,specs] of groups){
    const section=document.createElement('section');section.className='control-group';const h=document.createElement('h2');h.textContent=group;section.append(h);
    for(const spec of specs){
      const row=document.createElement('div');row.className='control';const label=document.createElement('label');label.textContent=spec.label;label.htmlFor='ctl-'+spec.id;row.append(label);
      const input=document.createElement(spec.type==='choice'?'select':'input');input.id=label.htmlFor;
      let out=null;
      if(spec.type==='number'){
        input.type='range';input.min=spec.min;input.max=spec.max;input.step=spec.step;
        const wrap=document.createElement('div');wrap.className='number';out=document.createElement('output');out.textContent=Number(current.controls[spec.id]).toFixed(2);wrap.append(input,out);row.append(wrap);
      }else{
        if(spec.type==='color')input.type='color';else for(const choice of spec.choices){const option=document.createElement('option');option.value=choice;option.textContent=choice.replaceAll('-',' ');input.append(option);}
        row.append(input);
      }
      input.value=current.controls[spec.id];
      input.oninput=()=>{current.controls[spec.id]=spec.type==='number'?Number(input.value):input.value;if(out)out.textContent=Number(input.value).toFixed(2);updatePreview();};
      input.onchange=()=>{remember();};section.append(row);
    }
    $('controls').append(section);
  }
  $('undoBtn').disabled=!undo.length;$('redoBtn').disabled=!redo.length;
}
let debounce;
function updatePreview(){
  revision++;currentGLB=null;$('glbBtn').disabled=true;
  if(!SERVER){sketch?.setState(current.controls);return;}
  $('previewLabel').textContent='Updating model…';$('assetStats').textContent='Building the current character';
  clearTimeout(debounce);debounce=setTimeout(()=>{queued={blueprint:copy(current),revision};pump();},220);
}
async function post(path,value){
  const response=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json','X-AXM-Token':SERVER.token},body:JSON.stringify(value)});
  if(!response.ok){let err;try{err=(await response.json()).error;}catch{}throw Error(err||'The local builder did not complete the request.');}
  return response;
}
async function pump(){
  if(building||!queued)return;building=true;
  const job=queued;queued=null;
  try{
    const response=await post('/api/preview',job.blueprint), bytes=await response.arrayBuffer();
    if(job.revision===revision){
      const asset=viewer.load(bytes);currentGLB=bytes;$('glbBtn').disabled=false;$('previewLabel').textContent='EXPORTED MODEL · LIVE 3D';
      $('assetStats').textContent=Number(response.headers.get('X-AXM-Vertices')).toLocaleString()+' vertices · 18 joints · 3 clips';
      $('modelIdentity').textContent='GLB '+response.headers.get('X-AXM-SHA256').slice(0,12);
      updateTimeline(asset);message('Model updated. The GLB download uses these exact mesh and animation bytes.');
    }
  }catch(error){if(job.revision===revision){$('previewLabel').textContent='PREVIEW OUT OF DATE';message(error.message+' Your edits are kept. Use Rebuild preview to retry.',true);}}
  finally{building=false;if(queued)pump();}
}
let clipLengths={idle:2,walk:1,wave:1.6};
function updateTimeline(asset){for(const clip of asset.clips)clipLengths[clip.name.toLowerCase()]=Math.max(...clip.tracks.map(t=>t.times.at(-1)));$('poseTime').max=clipLengths[activeClip];}
function download(body,name,type){const url=URL.createObjectURL(new Blob([body],{type})),a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
function safeName(){return current.id.replace(/[^a-zA-Z0-9_-]/g,'_').slice(0,100)||'character';}
$('exportBtn').onclick=()=>download(JSON.stringify(current,null,2)+'\n',safeName()+'.character.json','application/json');
$('glbBtn').onclick=()=>{if(currentGLB)download(currentGLB,safeName()+'.glb','model/gltf-binary');};
$('packageBtn').onclick=async()=>{
  const snapshot=copy(current), name=safeName();$('packageBtn').disabled=true;message('Building and verifying the game package…');
  // Let any outstanding preview complete before starting the heavier package build.
  while(building)await new Promise(resolve=>setTimeout(resolve,80));
  building=true;
  try{const response=await post('/api/package',snapshot);download(await response.arrayBuffer(),name+'-game-package.zip','application/zip');message('Package exported with the rigged GLB, blueprint, sockets and verification reports.');}
  catch(error){message(error.message,true);}
  finally{building=false;$('packageBtn').disabled=false;if(queued)pump();}
};
$('importBtn').onclick=()=>$('fileInput').click();
$('fileInput').onchange=async event=>{
  const file=event.target.files[0];if(!file)return;
  try{if(file.size>65536)throw Error('Blueprint is larger than 64 KB.');const imported=AXMBlueprint.normalize(JSON.parse(await file.text()),DATA);apply(imported);message('Blueprint imported.');}
  catch(error){message('Import failed: '+error.message+' The current character is unchanged.',true);}
  finally{event.target.value='';}
};
$('resetBtn').onclick=()=>{const p=presetRows.find(p=>p.id===current.preset);if(p)apply(fresh(p));else{const value=copy(current);value.controls=Object.fromEntries(family.controls.map(s=>[s.id,s.default]));apply(value);}};
$('undoBtn').onclick=()=>{if(!undo.length)return;redo.push(copy(current));current=undo.pop();checkpoint=copy(current);apply(current,false);};
$('redoBtn').onclick=()=>{if(!redo.length)return;undo.push(copy(current));current=redo.pop();checkpoint=copy(current);apply(current,false);};
$('charId').onchange=()=>{const value=$('charId').value.trim();if(!value){$('charId').value=current.id;message('Character ID cannot be empty.',true);return;}current.id=value;remember();updatePreview();};
$('profileSelect').onchange=()=>{current.editor_profile=$('profileSelect').value==='full'?null:DATA.profile.id;remember();render();updatePreview();};
$('rebuildBtn').onclick=updatePreview;
function selectButton(attribute,button){document.querySelectorAll('['+attribute+']').forEach(b=>{const active=b===button;b.classList.toggle('active',active);b.setAttribute('aria-pressed',String(active));});}
for(const button of document.querySelectorAll('[data-view]'))button.onclick=()=>{selectButton('data-view',button);(viewer||sketch)?.setView(button.dataset.view);};
for(const button of document.querySelectorAll('[data-focus]'))button.onclick=()=>{selectButton('data-focus',button);viewer?.setFocus(button.dataset.focus);};
for(const button of document.querySelectorAll('[data-pose]'))button.onclick=()=>{selectButton('data-pose',button);activeClip=button.dataset.pose;(viewer||sketch)?.setPose(activeClip);$('poseTime').max=clipLengths[activeClip];$('poseTime').value=0;};
$('pauseBtn').onclick=()=>{const playing=$('pauseBtn').textContent==='Play';$('pauseBtn').textContent=playing?'Pause':'Play';viewer?.setPlaying(playing);};
$('poseTime').oninput=()=>{viewer?.setPlaying(false);$('pauseBtn').textContent='Play';viewer?.setTime(Number($('poseTime').value));};
$('familyLabel').textContent=family.label+' · Character studio';
if(SERVER){
  try{viewer=AXMAssetViewer.create($('assetViewport'));$('sketchViewport').hidden=true;$('offlineHelp').hidden=true;}
  catch(error){message(error.message,true);$('previewLabel').textContent='3D PREVIEW UNAVAILABLE';}
}else{
  $('assetViewport').hidden=true;sketch=AXMCharacterPreview.create($('sketchViewport'));
  $('previewLabel').textContent='OFFLINE SHAPE SKETCH';$('assetStats').textContent='Open the local builder for the detailed model';
  $('packageBtn').disabled=true;for(const el of document.querySelectorAll('[data-focus], #pauseBtn, #poseTime, #rebuildBtn'))el.disabled=true;
  message('Blueprint editing works offline. Start the local builder for the full Aura face, animation and game exports.');
}
current=fresh(presetRows[0]);checkpoint=copy(current);render();updatePreview();
