(function(){
'use strict';

function hexRgb(hex, fallback){
  const v=(typeof hex==='string'&&/^#[0-9a-fA-F]{6}$/.test(hex))?hex:fallback;
  return [parseInt(v.slice(1,3),16)/255,parseInt(v.slice(3,5),16)/255,parseInt(v.slice(5,7),16)/255];
}
function clamp(v,a,b){return Math.max(a,Math.min(b,v))}
function norm(v){const l=Math.hypot(v[0],v[1],v[2])||1;return [v[0]/l,v[1]/l,v[2]/l]}
function sub(a,b){return [a[0]-b[0],a[1]-b[1],a[2]-b[2]]}
function cross(a,b){return [a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]]}
function dot(a,b){return a[0]*b[0]+a[1]*b[1]+a[2]*b[2]}
function mixColor(rgb, k){return `rgb(${Math.round(clamp(rgb[0]*k,0,1)*255)},${Math.round(clamp(rgb[1]*k,0,1)*255)},${Math.round(clamp(rgb[2]*k,0,1)*255)})`}

function mesh(){return {v:[],t:[]}}
function addTri(m,a,b,c,color){m.t.push({a,b,c,color})}
function ellipsoid(m,c,r,color,lon=18,lat=10){
  const base=m.v.length;
  for(let j=0;j<=lat;j++){
    const phi=Math.PI*j/lat, sy=Math.cos(phi), ring=Math.sin(phi);
    for(let i=0;i<lon;i++){
      const th=Math.PI*2*i/lon;
      m.v.push([c[0]+r[0]*ring*Math.cos(th),c[1]+r[1]*sy,c[2]+r[2]*ring*Math.sin(th)]);
    }
  }
  for(let j=0;j<lat;j++)for(let i=0;i<lon;i++){
    const a=base+j*lon+i,b=base+j*lon+(i+1)%lon,c0=base+(j+1)*lon+(i+1)%lon,d=base+(j+1)*lon+i;
    if(j!==0)addTri(m,a,b,d,color); if(j!==lat-1)addTri(m,b,c0,d,color);
  }
}
function loftY(m,rings,color,seg=22){
  const base=m.v.length;
  rings.forEach(r=>{for(let i=0;i<seg;i++){const a=Math.PI*2*i/seg;m.v.push([r[1]*Math.cos(a),r[0],r[2]*Math.sin(a)])}});
  for(let j=0;j<rings.length-1;j++)for(let i=0;i<seg;i++){
    const a=base+j*seg+i,b=base+j*seg+(i+1)%seg,c=base+(j+1)*seg+(i+1)%seg,d=base+(j+1)*seg+i;
    addTri(m,a,b,c,color);addTri(m,a,c,d,color);
  }
}
function tubeX(m,rings,color,seg=14){
  const base=m.v.length;
  rings.forEach(r=>{for(let i=0;i<seg;i++){const a=Math.PI*2*i/seg;m.v.push([r[0],r[1]+r[2]*Math.cos(a),r[3]*Math.sin(a)])}});
  for(let j=0;j<rings.length-1;j++)for(let i=0;i<seg;i++){
    const a=base+j*seg+i,b=base+j*seg+(i+1)%seg,c=base+(j+1)*seg+(i+1)%seg,d=base+(j+1)*seg+i;
    addTri(m,a,b,c,color);addTri(m,a,c,d,color);
  }
}
function tubeY(m,x,rings,color,seg=14){
  const base=m.v.length;
  rings.forEach(r=>{for(let i=0;i<seg;i++){const a=Math.PI*2*i/seg;m.v.push([x+r[1]*Math.cos(a),r[0],r[2]*Math.sin(a)])}});
  for(let j=0;j<rings.length-1;j++)for(let i=0;i<seg;i++){
    const a=base+j*seg+i,b=base+j*seg+(i+1)%seg,c=base+(j+1)*seg+(i+1)%seg,d=base+(j+1)*seg+i;
    addTri(m,a,b,c,color);addTri(m,a,c,d,color);
  }
}

const AURA_PROFILE=[[1.381,.004,.030],[1.390,.025,.047],[1.405,.041,.063],[1.425,.058,.070],[1.450,.071,.074],[1.477,.079,.077],[1.500,.087,.079],[1.525,.086,.080],[1.550,.083,.080],[1.580,.081,.078],[1.610,.068,.065],[1.636,.035,.037],[1.645,.001,.003]];
function gauss(x,c,w){return Math.exp(-Math.pow((x-c)/w,2))}
function interpProfile(z,col){for(let i=0;i<AURA_PROFILE.length-1;i++){const a=AURA_PROFILE[i],b=AURA_PROFILE[i+1];if(a[0]<=z&&z<=b[0]){const t=(z-a[0])/(b[0]-a[0]),prev=AURA_PROFILE[Math.max(0,i-1)],next=AURA_PROFILE[Math.min(AURA_PROFILE.length-1,i+2)],m0=(b[col]-prev[col])/(b[0]-prev[0]),m1=(next[col]-a[col])/(next[0]-a[0]);return (2*t*t*t-3*t*t+1)*a[col]+(t*t*t-2*t*t+t)*(b[0]-a[0])*m0+(-2*t*t*t+3*t*t)*b[col]+(t*t*t-t*t)*(b[0]-a[0])*m1}}return z<AURA_PROFILE[0][0]?AURA_PROFILE[0][col]:AURA_PROFILE[AURA_PROFILE.length-1][col]}
function faceParams(state){const n=id=>Number(state[id]??1);return {headWidth:n('head_width'),headDepth:n('head_depth'),jawWidth:n('jaw_width'),chin:n('chin_size'),eyeSize:n('eye_size'),eyeSpacing:n('eye_spacing'),noseWidth:n('nose_width'),noseProjection:n('nose_projection'),mouthWidth:n('mouth_width')}}
function profileDims(z,p){let rx=interpProfile(z,1),ry=interpProfile(z,2);const jaw=1+(p.jawWidth-1)*gauss(z,1.425,.050),chinW=1+(p.chin-1)*gauss(z,1.397,.025)*.34;return [rx*p.headWidth*jaw*chinW,ry*p.headDepth]}
function faceDepth(x,z,p){const d=profileDims(z,p),rx=d[0],ry=d[1],u=Math.min(.999,Math.abs(x)/Math.max(.001,rx)),base=-ry*Math.pow(Math.max(.001,1-u*u),.32),nw=p.noseWidth,nose=p.noseProjection*(.023*gauss(x,0,.010*nw)*gauss(z,1.481,.011)+.014*gauss(x,0,.0085*nw)*gauss(z,1.508,.025)),wings=p.noseProjection*.006*(gauss(x,-.011*nw,.008*nw)+gauss(x,.011*nw,.008*nw))*gauss(z,1.476,.007),eyeX=.035*p.eyeSpacing*p.headWidth,eyeW=.024*p.eyeSize*p.headWidth,cheeks=.007*(gauss(x,-.05*p.headWidth,.025*p.headWidth)+gauss(x,.05*p.headWidth,.025*p.headWidth))*gauss(z,1.491,.020),sockets=.008*(gauss(x,-eyeX,eyeW)+gauss(x,eyeX,eyeW))*gauss(z,1.525,.018*p.eyeSize),brows=.003*(gauss(x,-eyeX,.031*p.headWidth)+gauss(x,eyeX,.031*p.headWidth))*gauss(z,1.551,.010),muzzle=.006*gauss(x,0,.035*p.mouthWidth)*gauss(z,1.453,.015),chin=.003*p.chin*gauss(x,0,.028*p.jawWidth)*gauss(z,1.414,.011);return base-nose-wings-cheeks+sockets-brows-muzzle-chin}
function auraFace(m,state,headY,hs,skin,lip){const p=faceParams(state),zMin=1.381,zMax=1.645,zC=(zMin+zMax)*.5,rad=48,vert=38,base=m.v.length;for(let j=0;j<=vert;j++){const z=zMin+(zMax-zMin)*j/vert,d=profileDims(z,p),rx=d[0],ry=d[1];for(let i=0;i<rad;i++){const a=Math.PI*2*i/rad,x=rx*Math.cos(a),sy=Math.sin(a),dy=sy>0?faceDepth(x,z,p):-ry*sy+.011*(1-sy);m.v.push([x*hs,headY+(z-zC)*hs,-dy*hs])}}for(let j=0;j<vert;j++)for(let i=0;i<rad;i++){const a=base+j*rad+i,b=base+j*rad+(i+1)%rad,c=base+(j+1)*rad+(i+1)%rad,d=base+(j+1)*rad+i;addTri(m,a,b,c,skin);addTri(m,a,c,d,skin)};for(const upper of [true,false]){const seg=28,dbase=m.v.length;for(let i=0;i<=seg;i++){const u=-1+2*i/seg,x=u*.027*p.mouthWidth,center=1.447+.0033*u*u,h=(upper?.0038:.0050)*Math.pow(Math.max(0,1-u*u),.65)+(upper?.0013*(gauss(x,-.007*p.mouthWidth,.004*p.mouthWidth)+gauss(x,.007*p.mouthWidth,.004*p.mouthWidth)):0);for(let j=0;j<=3;j++){const t=j/3,z=center+(upper?1:-1)*h*t,dy=faceDepth(x,z,p)-.0005-.0022*(1-u*u)*Math.sin(Math.PI*(t*.7+.15));m.v.push([x*hs,headY+(z-zC)*hs,-dy*hs])}}const stride=4;for(let i=0;i<seg;i++)for(let j=0;j<3;j++){const a=dbase+i*stride+j,b=dbase+(i+1)*stride+j,c=dbase+(i+1)*stride+j+1,d=dbase+i*stride+j+1;addTri(m,a,b,c,lip);addTri(m,a,c,d,lip)}}}
function rotateAroundX(p,pivot,ang){const y=p[1]-pivot[1],z=p[2]-pivot[2],c=Math.cos(ang),s=Math.sin(ang);return [p[0],pivot[1]+y*c-z*s,pivot[2]+y*s+z*c]}
function rotateAroundZ(p,pivot,ang){const x=p[0]-pivot[0],y=p[1]-pivot[1],c=Math.cos(ang),s=Math.sin(ang);return [pivot[0]+x*c-y*s,pivot[1]+x*s+y*c,p[2]]}

function build(state,pose){
  const n=id=>Number(state[id]??1), scale=n('height'), build=n('build'), leg=n('leg_length'), torso=n('torso_length'), arm=n('arm_length');
  const skin=hexRgb(state.skin,'#c98f76'), eye=hexRgb(state.eyes,'#5b3828'), hair=hexRgb(state.hair_color,'#34221f');
  const top=[0.20,0.33,0.35], bottom=[0.13,0.17,0.19], shoe=[0.07,0.07,0.065], white=[.95,.95,.91], lip=[.55,.20,.20];
  const footH=.06*scale, lower=.40*leg*scale, upper=.40*leg*scale, pelvisH=.14*scale, torsoH=.40*torso*scale, neckH=.08*scale, headH=.264*n('head_scale')*scale;
  const hipY=footH+lower+upper, pelvisY=hipY+pelvisH*.45, spineY=hipY+pelvisH+torsoH*.28, chestY=hipY+pelvisH+torsoH*.68, neckY=hipY+pelvisH+torsoH, headY=neckY+neckH+headH*.5;
  const shoulder=.20*n('shoulder_width')*build*scale, hip=.145*n('hip_width')*build*scale, upperArm=.30*arm*scale, fore=.265*arm*scale, hand=.16*arm*scale;
  const shoulderY=chestY+torsoH*.10, m=mesh();

  loftY(m,[
    [hipY-pelvisH*.10,hip*.92,.108*build*scale],
    [pelvisY,hip*1.04,.128*build*scale],
    [spineY-.04*scale,.132*build*scale,.102*build*scale],
    [spineY+.04*scale,.145*build*scale,.112*build*scale],
    [chestY,shoulder*.72,.132*build*scale],
    [shoulderY-.025*scale,shoulder*.90,.128*build*scale],
    [shoulderY+.018*scale,shoulder*.78,.110*build*scale],
    [neckY,.061*scale,.056*scale]
  ],top,26);
  ellipsoid(m,[-shoulder*.88,shoulderY,.0],[.074*build*scale,.067*scale,.072*build*scale],top,14,8);
  ellipsoid(m,[ shoulder*.88,shoulderY,.0],[.074*build*scale,.067*scale,.072*build*scale],top,14,8);
  ellipsoid(m,[0,pelvisY-.01*scale,0],[hip*1.03,pelvisH*.46,.128*build*scale],bottom,18,8);
  ellipsoid(m,[0,neckY+neckH*.40,0],[.054*scale,neckH*.62,.052*scale],skin,14,8);

  const upperR=.052*build*scale, foreR=.044*build*scale;
  for(const [sign,label] of [[-1,'L'],[1,'R']]){
    const sx=sign*shoulder, ex=sign*(shoulder+upperArm), wx=sign*(shoulder+upperArm+fore), hx=sign*(shoulder+upperArm+fore+hand*.48);
    let armY=shoulderY, down=pose==='bind'?0:(sign<0?1:-1)*78*Math.PI/180;
    const local=mesh();
    tubeX(local,[[sx,armY,upperR,upperR],[sign*(shoulder+upperArm*.50),armY,upperR*.98,upperR*.97],[sign*(shoulder+upperArm*.88),armY,upperR*.84,upperR*.82],[ex,armY,foreR*1.04,foreR]],top,16);
    tubeX(local,[[ex,armY,foreR*1.04,foreR],[sign*(shoulder+upperArm+fore*.40),armY,foreR*.96,foreR*.92],[sign*(shoulder+upperArm+fore*.78),armY,foreR*.82,foreR*.78],[wx,armY,foreR*.68,foreR*.62]],skin,15);
    const wrist=Math.abs(wx);
    ellipsoid(local,[sign*(wrist+hand*.28),armY,.015*scale],[hand*.28,.040*scale,.058*scale],skin,14,7);
    ellipsoid(local,[sign*(wrist+hand*.13),armY-.020*scale,.050*scale],[hand*.12,.018*scale,.022*scale],skin,10,5);
    let extraWave=0, forwardSwing=0;
    if(pose==='walk') forwardSwing=(sign<0?1:-1)*15*Math.PI/180;
    if(pose==='wave'&&sign>0){down=-30*Math.PI/180;extraWave=-18*Math.PI/180}
    const base=m.v.length;
    local.v.forEach(p=>{let q=rotateAroundZ(p,[sx,armY,0],down); if(forwardSwing||extraWave)q=rotateAroundX(q,[sx,armY,0],forwardSwing+extraWave);m.v.push(q)});
    local.t.forEach(t=>m.t.push({a:base+t.a,b:base+t.b,c:base+t.c,color:t.color}));
  }

  const ankle=footH,knee=ankle+lower,legR=.068*build*scale;
  for(const [sign,label] of [[-1,'L'],[1,'R']]){
    const x=sign*hip*.45;
    tubeY(m,x,[[hipY,legR*1.04,legR*.92],[hipY-upper*.25,legR,legR*.90],[knee+upper*.18,legR*.84,legR*.81],[knee,legR*.76,legR*.75]],bottom,16);
    tubeY(m,x,[[knee,legR*.76,legR*.75],[knee-lower*.28,legR*.88,legR*.82],[ankle+lower*.28,legR*.67,legR*.70],[ankle,legR*.52,legR*.58]],bottom,16);
    ellipsoid(m,[x,footH*.48,.075*scale],[.068*scale,footH*.40,.132*scale],shoe,16,7);
    ellipsoid(m,[x,footH*.42,.150*scale],[.070*scale,footH*.33,.070*scale],shoe,14,6);
  }

  const hs=n('head_scale')*scale, hw=n('head_width'), hd=n('head_depth');
  auraFace(m,state,headY,hs,skin,lip);
  const eyeX=.035*n('eye_spacing')*hs, eyeS=n('eye_size');
  for(const sign of [-1,1]){
    ellipsoid(m,[sign*eyeX,headY+.012*hs,.091*hd*hs],[.024*eyeS*hs,.021*eyeS*hs,.018*hs],white,12,7);
    ellipsoid(m,[sign*eyeX,headY+.012*hs,.108*hd*hs],[.0093*eyeS*hs,.0093*eyeS*hs,.004*hs],eye,10,6);
    ellipsoid(m,[sign*eyeX,headY+.012*hs,.112*hd*hs],[.0037*eyeS*hs,.0037*eyeS*hs,.002*hs],[.02,.015,.012],8,5);
  }
  if(state.hair!=='none'){
    ellipsoid(m,[0,headY+.060*hs,-.045*hs],[.098*hw*hs,.108*hs,.078*hd*hs],hair,20,10);
    if(state.hair==='swept')ellipsoid(m,[-.030*hs,headY+.055*hs,.082*hs],[.072*hs,.040*hs,.028*hs],hair,14,7);
    if(state.hair==='bob'||state.hair==='long')for(const sign of [-1,1])ellipsoid(m,[sign*.086*hs,headY-.035*hs,0],[.025*hs,(state.hair==='long'?.185:.105)*hs,.058*hs],hair,12,8);
  }
  return {mesh:m,height:headY+.14*hs};
}

class Preview3D{
  constructor(canvas){
    this.canvas=canvas;this.ctx=canvas.getContext('2d');this.state={};this.pose='idle';this.yaw=-.45;this.pitch=-.06;this.zoom=2.55;this.drag=null;
    const ro=new ResizeObserver(()=>this.resize());ro.observe(canvas);this.resize();
    canvas.addEventListener('pointerdown',e=>{this.drag={x:e.clientX,y:e.clientY,yaw:this.yaw,pitch:this.pitch};canvas.setPointerCapture(e.pointerId)});
    canvas.addEventListener('pointermove',e=>{if(!this.drag)return;this.yaw=this.drag.yaw+(e.clientX-this.drag.x)*.008;this.pitch=clamp(this.drag.pitch+(e.clientY-this.drag.y)*.006,-.6,.45);this.render()});
    canvas.addEventListener('pointerup',()=>this.drag=null);canvas.addEventListener('pointercancel',()=>this.drag=null);
    canvas.addEventListener('wheel',e=>{e.preventDefault();this.zoom=clamp(this.zoom+e.deltaY*.0015,1.6,4.2);this.render()},{passive:false});
  }
  resize(){const r=this.canvas.getBoundingClientRect(),dpr=Math.min(2,window.devicePixelRatio||1);this.canvas.width=Math.max(1,Math.round(r.width*dpr));this.canvas.height=Math.max(1,Math.round(r.height*dpr));this.render()}
  setState(s){this.state=Object.assign({},s);this.render()}
  setPose(p){this.pose=p;this.render()}
  setView(v){if(v==='front'){this.yaw=0;this.pitch=0}else if(v==='three'){this.yaw=-.62;this.pitch=-.05}else if(v==='side'){this.yaw=-Math.PI/2;this.pitch=0};this.render()}
  camera(p,center){
    let x=p[0],y=p[1]-center,z=p[2];
    const cy=Math.cos(this.yaw),sy=Math.sin(this.yaw);let x1=x*cy-z*sy,z1=x*sy+z*cy;
    const cp=Math.cos(this.pitch),sp=Math.sin(this.pitch);let y1=y*cp-z1*sp,z2=y*sp+z1*cp;
    z2=this.zoom-z2;return [x1,y1,z2]
  }
  project(p,w,h){const f=Math.min(w,h)*1.45, z=Math.max(.25,p[2]);return [w*.5+p[0]*f/z,h*.52-p[1]*f/z,z]}
  render(){
    const ctx=this.ctx,w=this.canvas.width,h=this.canvas.height;if(!w||!h)return;
    ctx.clearRect(0,0,w,h);const grad=ctx.createRadialGradient(w*.52,h*.32,0,w*.52,h*.45,Math.max(w,h)*.78);grad.addColorStop(0,'#30372d');grad.addColorStop(.55,'#1c211b');grad.addColorStop(1,'#0f120f');ctx.fillStyle=grad;ctx.fillRect(0,0,w,h);
    const built=build(this.state,this.pose),m=built.mesh,center=built.height*.47, light=norm([-1.1,1.5,1.7]), tris=[];
    const cv=m.v.map(p=>this.camera(p,center));
    for(const t of m.t){const a=cv[t.a],b=cv[t.b],c=cv[t.c],n=norm(cross(sub(b,a),sub(c,a))); const shade=clamp(.34+.76*Math.abs(dot(n,light)),.25,1.12);const pa=this.project(a,w,h),pb=this.project(b,w,h),pc=this.project(c,w,h);tris.push({p:[pa,pb,pc],z:(a[2]+b[2]+c[2])/3,color:mixColor(t.color,shade)})}
    tris.sort((a,b)=>b.z-a.z);
    for(const t of tris){ctx.beginPath();ctx.moveTo(t.p[0][0],t.p[0][1]);ctx.lineTo(t.p[1][0],t.p[1][1]);ctx.lineTo(t.p[2][0],t.p[2][1]);ctx.closePath();ctx.fillStyle=t.color;ctx.fill()}
    ctx.save();ctx.globalAlpha=.24;ctx.fillStyle='#000';ctx.beginPath();ctx.ellipse(w*.5,h*.88,w*.18,h*.025,0,0,Math.PI*2);ctx.fill();ctx.restore();
  }
}
window.AXMCharacterPreview={create(canvas){return new Preview3D(canvas)}};
})();