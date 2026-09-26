/* Viewer for the GLB subset emitted by human-v0. No external code or network assets.
   The decoded bytes are also the bytes offered by Download GLB. */
(function (root) {
  'use strict';
  const identity = () => [1,0,0,0, 0,1,0,0, 0,0,1,0, 0,0,0,1];
  function multiply(a,b) {
    const out = new Array(16).fill(0);
    for (let c=0;c<4;c++) for (let r=0;r<4;r++) for (let k=0;k<4;k++) out[c*4+r]+=a[k*4+r]*b[c*4+k];
    return out;
  }
  function transform(node) {
    const [x,y,z,w]=node.rotation||[0,0,0,1], s=node.scale||[1,1,1], t=node.translation||[0,0,0];
    return node.matrix || [(1-2*y*y-2*z*z)*s[0],(2*x*y+2*z*w)*s[0],(2*x*z-2*y*w)*s[0],0,
      (2*x*y-2*z*w)*s[1],(1-2*x*x-2*z*z)*s[1],(2*y*z+2*x*w)*s[1],0,
      (2*x*z+2*y*w)*s[2],(2*y*z-2*x*w)*s[2],(1-2*x*x-2*y*y)*s[2],0,...t,1];
  }
  function slerp(a,b,t) {
    let dot=a.reduce((s,v,i)=>s+v*b[i],0);
    if(dot<0){b=b.map(v=>-v);dot=-dot;}
    if(dot>.9995){const q=a.map((v,i)=>v+(b[i]-v)*t), len=Math.hypot(...q);return q.map(v=>v/len);}
    const angle=Math.acos(Math.min(1,dot)), sin=Math.sin(angle);
    return a.map((v,i)=>(v*Math.sin((1-t)*angle)+b[i]*Math.sin(t*angle))/sin);
  }
  function decode(buffer) {
    const dv=new DataView(buffer);
    if(dv.getUint32(0,true)!==0x46546c67||dv.getUint32(4,true)!==2||dv.getUint32(8,true)!==buffer.byteLength) throw Error('Invalid GLB');
    const size=dv.getUint32(12,true), doc=JSON.parse(new TextDecoder().decode(new Uint8Array(buffer,20,size))), start=28+size;
    if(doc.extras?.schema!=='axm.character.game-asset/v0.1') throw Error('Expected an AXM character GLB');
    const cache=new Map();
    function accessor(index){
      if(cache.has(index))return cache.get(index);
      const a=doc.accessors[index], v=doc.bufferViews[a.bufferView], width={SCALAR:1,VEC2:2,VEC3:3,VEC4:4,MAT4:16}[a.type];
      const Type={5126:Float32Array,5125:Uint32Array,5123:Uint16Array}[a.componentType];
      if(!Type||a.sparse||v.byteStride)throw Error('Unsupported accessor layout');
      const values=new Type(buffer,start+(v.byteOffset||0)+(a.byteOffset||0),a.count*width);
      cache.set(index,values);return values;
    }
    const parents=doc.nodes.map(()=>-1);
    doc.nodes.forEach((n,i)=>(n.children||[]).forEach(c=>{parents[c]=i;}));
    const skin=doc.skins[0], inverse=accessor(skin.inverseBindMatrices);
    const clips=doc.animations.map(a=>({name:a.name, tracks:a.channels.map(c=>{
      const s=a.samplers[c.sampler];
      if(s.interpolation!=='LINEAR'||c.target.path!=='rotation')throw Error('Unsupported animation track');
      return {node:c.target.node,times:accessor(s.input),values:accessor(s.output)};
    })}));
    function matrices(clipName,time){
      const nodes=doc.nodes.map(n=>({...n})), clip=clips.find(a=>a.name===clipName);
      if(clip) for(const track of clip.tracks){
        const times=track.times, values=track.values;
        let end=1;while(end<times.length-1&&times[end]<time)end++;
        const t=Math.max(0,Math.min(1,(time-times[end-1])/(times[end]-times[end-1])));
        nodes[track.node].rotation=slerp(Array.from(values.slice((end-1)*4,end*4)),Array.from(values.slice(end*4,end*4+4)),t);
      }
      const world=[];
      function matrix(i){return world[i]||(world[i]=parents[i]<0?transform(nodes[i]):multiply(matrix(parents[i]),transform(nodes[i])));}
      return new Float32Array(skin.joints.flatMap((n,i)=>multiply(matrix(n),Array.from(inverse.slice(i*16,i*16+16)))));
    }
    return {doc,accessor,clips,matrices};
  }
  function create(canvas) {
    const gl=canvas.getContext('webgl2',{antialias:true,alpha:true,preserveDrawingBuffer:false});
    if(!gl)throw Error('This browser needs WebGL 2 for the detailed preview.');
    function shader(type,source){const s=gl.createShader(type);gl.shaderSource(s,source);gl.compileShader(s);if(!gl.getShaderParameter(s,gl.COMPILE_STATUS))throw Error(gl.getShaderInfoLog(s));return s;}
    const program=gl.createProgram();
    gl.attachShader(program,shader(gl.VERTEX_SHADER,`#version 300 es
      precision highp float;
      in vec3 position; in vec3 normal; in vec4 color; in vec4 joints; in vec4 weights;
      uniform mat4 bones[18]; uniform mat4 view; uniform mat4 projection;
      out vec3 n; out vec3 p; out vec4 c;
      void main(){mat4 skin=weights.x*bones[int(joints.x)]+weights.y*bones[int(joints.y)]+weights.z*bones[int(joints.z)]+weights.w*bones[int(joints.w)];
      vec4 point=view*skin*vec4(position,1.0); p=point.xyz; n=mat3(view*skin)*normal;c=color;gl_Position=projection*point;}`));
    gl.attachShader(program,shader(gl.FRAGMENT_SHADER,`#version 300 es
      precision highp float; in vec3 n;in vec3 p;in vec4 c;uniform vec4 base;uniform float roughness;uniform vec3 emissive;out vec4 frag;
      void main(){vec3 N=normalize(n);if(!gl_FrontFacing)N=-N;
      vec3 key=normalize(vec3(-0.7,0.9,1.4)), fill=normalize(vec3(0.9,0.2,0.7));
      float diffuse=0.36+0.65*max(0.0,dot(N,key))+0.22*max(0.0,dot(N,fill));
      vec3 halfLight=normalize(key+vec3(0.0,0.0,1.0));float spec=pow(max(0.0,dot(N,halfLight)),mix(96.0,12.0,roughness))*(1.0-roughness)*0.16;
      vec3 lit=base.rgb*c.rgb*diffuse+spec+emissive;frag=vec4(pow(max(lit,vec3(0.0)),vec3(1.0/2.2)),1.0);}`));
    gl.linkProgram(program);if(!gl.getProgramParameter(program,gl.LINK_STATUS))throw Error(gl.getProgramInfoLog(program));
    gl.useProgram(program);gl.enable(gl.DEPTH_TEST);
    const uniforms=Object.fromEntries(['bones','view','projection','base','roughness','emissive'].map(n=>[n,gl.getUniformLocation(program,n)]));
    let asset=null, meshes=[], yaw=-.45, pitch=0, zoom=1, focus='body', clip='Idle', playing=true, time=0, last=0, dirty=true;
    function load(buffer){
      const next=decode(buffer);if(next.doc.skins[0].joints.length!==18)throw Error('Unsupported rig');
      meshes.forEach(m=>{m.buffers.forEach(b=>gl.deleteBuffer(b));gl.deleteVertexArray(m.vao);});meshes=[];
      asset=next;
      for(const mesh of asset.doc.meshes)for(const prim of mesh.primitives){
        const vao=gl.createVertexArray(), buffers=[];gl.bindVertexArray(vao);
        for(const [attribute,name,size] of [['POSITION','position',3],['NORMAL','normal',3],['COLOR_0','color',4],['JOINTS_0','joints',4],['WEIGHTS_0','weights',4]]){
          const loc=gl.getAttribLocation(program,name), index=prim.attributes[attribute];
          if(index===undefined){gl.disableVertexAttribArray(loc);gl.vertexAttrib4f(loc,1,1,1,1);continue;}
          const values=asset.accessor(index), b=gl.createBuffer();buffers.push(b);gl.bindBuffer(gl.ARRAY_BUFFER,b);gl.bufferData(gl.ARRAY_BUFFER,new Float32Array(values),gl.STATIC_DRAW);gl.enableVertexAttribArray(loc);gl.vertexAttribPointer(loc,size,gl.FLOAT,false,0,0);
        }
        const indices=asset.accessor(prim.indices), b=gl.createBuffer();buffers.push(b);gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER,b);gl.bufferData(gl.ELEMENT_ARRAY_BUFFER,new Uint32Array(indices),gl.STATIC_DRAW);
        const material=asset.doc.materials[prim.material];meshes.push({vao,buffers,count:indices.length,material});
      }
      canvas.dataset.meshes=meshes.length;canvas.dataset.vertices=asset.doc.accessors.filter(a=>a.type==='VEC3'&&a.min).reduce((s,a)=>s+a.count,0);
      dirty=true;return asset;
    }
    function draw(){
      if(!asset)return;
      const dpr=Math.min(devicePixelRatio||1,2), w=Math.max(1,Math.round(canvas.clientWidth*dpr)),h=Math.max(1,Math.round(canvas.clientHeight*dpr));
      if(canvas.width!==w||canvas.height!==h){canvas.width=w;canvas.height=h;}
      gl.viewport(0,0,w,h);gl.clearColor(0,0,0,0);gl.clear(gl.COLOR_BUFFER_BIT|gl.DEPTH_BUFFER_BIT);gl.useProgram(program);
      const head=asset.doc.nodes.find(n=>n.name==='Head'), root=asset.doc.nodes.find(n=>n.name==='Root');
      // Rest head position includes its ancestors; use the inverse bind translation.
      const headIndex=asset.doc.skins[0].joints.indexOf(asset.doc.nodes.indexOf(head));
      const inverse=asset.accessor(asset.doc.skins[0].inverseBindMatrices), headY=-inverse[headIndex*16+13];
      const center=focus==='face'?headY:headY*.51, span=(focus==='face'?.40:headY*1.22)/zoom;
      const cy=Math.cos(yaw),sy=Math.sin(yaw), cp=Math.cos(pitch),sp=Math.sin(pitch);
      const rotate=[cy,sp*sy,cp*sy,0, 0,cp,-sp,0, -sy,sp*cy,cp*cy,0, 0,0,0,1];
      const view=multiply(rotate,[1,0,0,0,0,1,0,0,0,0,1,0,0,-center,0,1]);
      const projection=[2/(span*w/h),0,0,0,0,2/span,0,0,0,0,-.1,0,0,0,0,1];
      gl.uniformMatrix4fv(uniforms.view,false,view);gl.uniformMatrix4fv(uniforms.projection,false,projection);gl.uniformMatrix4fv(uniforms.bones,false,asset.matrices(clip,time));
      for(const m of meshes){const pbr=m.material.pbrMetallicRoughness;gl.bindVertexArray(m.vao);gl.uniform4fv(uniforms.base,pbr.baseColorFactor);gl.uniform1f(uniforms.roughness,pbr.roughnessFactor);gl.uniform3fv(uniforms.emissive,m.material.emissiveFactor||[0,0,0]);gl.drawElements(gl.TRIANGLES,m.count,gl.UNSIGNED_INT,0);}
      canvas.dataset.clip=clip;canvas.dataset.time=time.toFixed(3);canvas.dataset.focus=focus;
    }
    function tick(now){
      if(asset&&playing&&!document.hidden){const selected=asset.clips.find(a=>a.name===clip), duration=Math.max(...selected.tracks.map(t=>t.times[t.times.length-1]));time=(time+Math.min(.1,(now-(last||now))/1000))%duration;dirty=true;}
      last=now;if(dirty){draw();dirty=false;}requestAnimationFrame(tick);
    }
    let drag=null;
    canvas.addEventListener('pointerdown',e=>{drag=[e.clientX,e.clientY];canvas.setPointerCapture(e.pointerId);});
    canvas.addEventListener('pointermove',e=>{if(drag){yaw+=(e.clientX-drag[0])*.008;pitch=Math.max(-.65,Math.min(.65,pitch+(e.clientY-drag[1])*.006));drag=[e.clientX,e.clientY];dirty=true;}});
    for(const event of ['pointerup','pointercancel','lostpointercapture'])canvas.addEventListener(event,()=>{drag=null;});
    canvas.addEventListener('wheel',e=>{e.preventDefault();zoom=Math.max(.65,Math.min(3,zoom*Math.exp(-e.deltaY*.001)));dirty=true;},{passive:false});
    new ResizeObserver(()=>{dirty=true;}).observe(canvas);requestAnimationFrame(tick);
    return {load,setView(v){yaw={front:0,three:-.45,side:-Math.PI/2}[v]??0;pitch=0;dirty=true;},setFocus(v){focus=v;zoom=1;dirty=true;},setPose(v){clip=v[0].toUpperCase()+v.slice(1);time=0;dirty=true;},setPlaying(v){playing=v;dirty=true;},setTime(v){time=v;dirty=true;}};
  }
  root.AXMAssetViewer={decode,create,multiply,slerp};
})(typeof window==='undefined'?globalThis:window);
