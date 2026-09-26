/* Actual-browser acceptance for the local editor. CI-only dev dependency: Playwright. */
const {chromium}=require('playwright');
const {spawn,execFileSync}=require('node:child_process');
const fs=require('node:fs/promises');
const assert=require('node:assert/strict');
const crypto=require('node:crypto');
const hash=b=>crypto.createHash('sha256').update(b).digest('hex');
const port=18765, url=`http://127.0.0.1:${port}/`;
const server=spawn('python',['-m','axm_character_editor.cli','serve','--port',String(port)],{stdio:['ignore','pipe','inherit']});
let browser;
(async()=>{
 await new Promise((resolve,reject)=>{const timer=setTimeout(()=>reject(Error('Server did not start')),15000);server.stdout.on('data',b=>{if(b.toString().includes(url)){clearTimeout(timer);resolve();}});server.on('exit',code=>reject(Error('Server exited '+code)));});
 browser=await chromium.launch({headless:true,args:['--use-angle=swiftshader','--enable-unsafe-swiftshader']});
 const page=await browser.newPage({viewport:{width:1440,height:960},deviceScaleFactor:1});
 const errors=[];page.on('pageerror',e=>errors.push(e.message));
 async function ready(){await page.waitForFunction(()=>!document.getElementById('glbBtn').disabled,{},{timeout:30000});}
 async function shot(name){
  const bytes=await page.screenshot({type:'jpeg',quality:76});
  await fs.mkdir('build/browser-evidence',{recursive:true});await fs.writeFile(`build/browser-evidence/${name}.jpg`,bytes);
  // Bounded visual receipts in logs work even when the account artifact quota is full.
  console.log('AXM_SCREENSHOT_BEGIN '+name);
  const encoded=bytes.toString('base64');for(let i=0;i<encoded.length;i+=8000)console.log(encoded.slice(i,i+8000));
  console.log('AXM_SCREENSHOT_END '+name);
 }
 await page.goto(url);await ready();
 assert.equal(await page.locator('#profileSelect').inputValue(),'full');
 assert.equal(await page.locator('#ctl-head_depth').count(),1);
 assert.ok(Number(await page.locator('#assetViewport').getAttribute('data-vertices'))>40000);
 await page.getByRole('button',{name:'Pause',exact:true}).click();
 await shot('default-body');
 await page.getByRole('button',{name:'Face close-up',exact:true}).click();await page.waitForFunction(()=>document.getElementById('assetViewport').dataset.focus==='face');
 await page.getByRole('button',{name:'FRONT',exact:true}).click();await shot('aura-face');
 // Pause/scrub encoded animation, then confirm continuous playback advances.
 await page.getByRole('button',{name:'Full body',exact:true}).click();await page.getByRole('button',{name:'WAVE',exact:true}).click();
 await page.locator('#poseTime').fill('0.82');await page.locator('#poseTime').dispatchEvent('input');
 await page.waitForFunction(()=>document.getElementById('assetViewport').dataset.time==='0.820');
 await shot('wave-pose');
 const paused=await page.locator('#assetViewport').getAttribute('data-time');
 await page.getByRole('button',{name:'Play',exact:true}).click();
 await page.waitForFunction(t=>document.getElementById('assetViewport').dataset.time!==t,paused);
 await page.getByRole('button',{name:'Pause',exact:true}).click();
 // Edited preset reset must restore that preset, not Female A.
 const presets=await page.locator('#presets button').all();await presets[3].click();await ready();
 const original=await page.locator('#ctl-height').inputValue();
 await page.locator('#ctl-height').fill('1.15');await page.locator('#ctl-height').dispatchEvent('input');await page.locator('#ctl-height').dispatchEvent('change');
 await page.getByRole('button',{name:'Undo',exact:true}).click();assert.equal(await page.locator('#ctl-height').inputValue(),original);
 await page.getByRole('button',{name:'Redo',exact:true}).click();assert.equal(await page.locator('#ctl-height').inputValue(),'1.15');
 await page.getByRole('button',{name:'Reset starting preset'}).click();assert.equal(await page.locator('#ctl-height').inputValue(),original);await ready();
 // Validation is atomic and preserves imported metadata; the view selector never erases controls.
 let download=page.waitForEvent('download');await page.getByRole('button',{name:'Save blueprint'}).click();
 let saved=await download;const bp=JSON.parse(await fs.readFile(await saved.path(),'utf8'));
 bp.authorship.provenance={source:'browser-smoke'};
 await page.locator('#fileInput').setInputFiles({name:'valid.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify(bp))});
 await ready();
 await page.locator('#fileInput').setInputFiles({name:'invalid.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify({...bp,controls:{height:500}}))});
 await page.waitForFunction(()=>document.getElementById('notice').textContent.includes('Import failed'));
 assert.equal(await page.locator('#ctl-height').inputValue(),original);
 await page.locator('#profileSelect').selectOption('rpg-v0');assert.equal(await page.locator('#ctl-head_depth').count(),0);
 await page.locator('#profileSelect').selectOption('full');assert.equal(await page.locator('#ctl-head_depth').count(),1);await ready();
 download=page.waitForEvent('download');await page.getByRole('button',{name:'Save blueprint'}).click();saved=await download;
 const after=JSON.parse(await fs.readFile(await saved.path(),'utf8'));assert.equal(after.authorship.provenance.source,'browser-smoke');assert.ok(Object.hasOwn(after.controls,'head_depth'));
 // Download must match exactly the last authoritative model response.
 download=page.waitForEvent('download');await page.getByRole('button',{name:'Download GLB'}).click();saved=await download;
 const glb=await fs.readFile(await saved.path());assert.equal(glb.toString('utf8',0,4),'glTF');
 const identity=await page.locator('#modelIdentity').textContent();assert.equal(identity,'GLB '+hash(glb).slice(0,12));
 download=page.waitForEvent('download',{timeout:90000});await page.getByRole('button',{name:'Export game package'}).click();saved=await download;
 const zip=await fs.readFile(await saved.path());assert.equal(zip.toString('utf8',0,2),'PK');assert.ok(zip.length>10000);
 execFileSync('python',['-c',"import hashlib,json,sys,zipfile; z=zipfile.ZipFile(sys.argv[1]); assert hashlib.sha256(z.read('character.glb')).hexdigest()==sys.argv[2]; assert json.loads(z.read('deformation-verification.json'))['status']=='SOFTWARE_DEFORMATION_PASS'; assert 'equipment-contract.json' in z.namelist(); assert json.loads(z.read('character.blueprint.json'))['authorship']['provenance']['source']=='browser-smoke'",await saved.path(),hash(glb)]);
 await page.setViewportSize({width:390,height:844});await page.locator('.stage').scrollIntoViewIfNeeded();await shot('mobile-editor');
 assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
 assert.deepEqual(errors,[]);
 console.log('BROWSER_SMOKE_PASS: GLB render, camera, face, clip playback/scrub, preset reset, undo/redo, atomic import, profile preservation, GLB identity, verified ZIP export, mobile layout.');
})().catch(async error=>{console.error(error);process.exitCode=1;}).finally(async()=>{if(browser)await browser.close();server.kill();});
