(function(root){
  'use strict';
  function normalize(value,data){
    const {family,profile,presets}=data, object=v=>v!==null&&typeof v==='object'&&!Array.isArray(v);
    const fail=message=>{throw Error(message);};
    if(!object(value))fail('Blueprint must be an object.');
    if(value.schema!=='axm.character.blueprint/v0.1'||value.family!==family.id)fail('Unsupported blueprint schema or family.');
    if(typeof value.id!=='string'||!value.id.trim())fail('Character ID is required.');
    if(value.family_version!=null&&value.family_version!==family.version)fail('The family version does not match this editor.');
    if(!family.rig_profiles.some(r=>r.id===value.rig_profile))fail('Unsupported rig profile.');
    if(value.preset!=null&&!presets.some(p=>p.id===value.preset))fail('Unknown starting preset.');
    if(value.editor_profile!=null&&value.editor_profile!==profile.id)fail('Unknown editor profile.');
    if(!object(value.controls))fail('Controls must be an object.');
    if(value.authorship!==undefined&&!object(value.authorship))fail('Authorship must be an object.');
    const specs=new Map(family.controls.map(s=>[s.id,s]));
    for(const id of Object.keys(value.controls))if(!specs.has(id))fail('Unsupported control: '+id);
    const controls={};
    for(const s of family.controls){
      let v=Object.hasOwn(value.controls,s.id)?value.controls[s.id]:s.default;
      if(s.type==='number'){
        if(typeof v!=='number'||!Number.isFinite(v)||v<s.min||v>s.max)fail(s.label+' must be between '+s.min+' and '+s.max+'.');
        v=Math.round(v*1e6)/1e6;
      }else if(s.type==='color'){
        if(typeof v!=='string'||!/^#[0-9a-f]{6}$/i.test(v.trim()))fail(s.label+' must be a hex colour.');
        v=v.trim().toLowerCase();
      }else if(s.type==='choice'){
        if(typeof v!=='string'||!s.choices.includes(v.trim()))fail('Unsupported '+s.label+'.');
        v=v.trim();
      }
      controls[s.id]=v;
    }
    return {schema:value.schema,id:value.id.trim(),family:family.id,family_version:family.version,preset:value.preset??null,
      editor_profile:value.editor_profile??null,rig_profile:value.rig_profile,controls,
      authorship:structuredClone(value.authorship||{method:'HUMAN_OR_AI_EXPLICIT_FIELDS'})};
  }
  root.AXMBlueprint={normalize};
})(typeof window==='undefined'?globalThis:window);
