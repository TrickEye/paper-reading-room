/* Notes acceptance scenarios, called by the existing browser suite. */
const assert = require('node:assert/strict');
const path = require('node:path');
module.exports = async function checkNotes({browser, route, output}) {
  const context = await browser.newContext({viewport:{width:1440,height:1000}});
  const errors = [], requests = [], remote = new Map();
  let pending = null;
  await context.route('**/notes/*/notes.md', async r => {
    const state = remote.get(new URL(r.request().url()).pathname) || {status:404, body:'missing'};
    if (state.wait) await new Promise(resolve => { pending = resolve; });
    await r.fulfill({contentType:'text/markdown; charset=utf-8', status:state.status, body:state.body});
  });
  // Every GitHub navigation is intercepted, including popups. Never send note data.
  await context.route('https://github.com/**', r => r.fulfill({contentType:'text/html',body:'<title>Mock GitHub handoff</title>'}));
  const page = await context.newPage();
  page.on('pageerror', e => errors.push(e.message));
  page.on('request', r => requests.push(r.url()));
  const acceptLeave = p => p.on('dialog', d => d.accept());
  acceptLeave(page);
  const ready = async (p, id='ace', prefix='') => {
    await p.goto(route(id,prefix));
    await p.waitForSelector('#notes-panel', {state:'attached'});
    await p.waitForFunction(() => !document.querySelector('#notes-refresh').disabled);
  };
  const open = async p => {
    if (!(await p.locator('#notes-panel').isVisible())) await p.click('#notes-button');
    await p.waitForSelector('#notes-editor[data-editor-ready=true]');
  };
  const source = async p => { await p.click('#notes-source'); return p.locator('.vditor-sv'); };
  const draft = async p => (await source(p)).inputValue();
  const handoff = async p => { await p.click('#notes-github'); return p.locator('#notes-handoff-source').inputValue(); };
  const closeHandoff = p => p.click('#notes-handoff-close');
  const newURL = p => p.locator('#notes-github-open').getAttribute('href').then(h => new URL(h));
  const notesPath = new URL('/notes/ace/notes.md', route('ace')).pathname;
  const sample = '# 阅读心得\n\n**重要** 与 *强调*\n\n- 项目\n- [ ] 待办\n\n> 一段引用\n\n| 方法 | 结果 |\n| --- | --- |\n| ACE | 通过 |\n\n```js\nconst a = 1;\n```\n\n$x^2$\n\n$$\nE=mc^2\n$$\n';

  await ready(page);
  assert(requests.some(url=>new URL(url).pathname===notesPath),'notes requested before opening panel');
  assert(!requests.some(url=>url.includes('/vendor/')), 'Editor remains lazy');
  assert(!(await page.locator('#notes-panel').isVisible()));
  await open(page);
  await (await source(page)).fill(sample);
  await page.click('#notes-close'); await open(page);
  assert((await draft(page)).includes('阅读心得'),'closing panel retains in-memory draft');
  await page.click('#notes-edit');
  await page.waitForSelector('#notes-editor .katex');
  assert.equal(await page.locator('#notes-editor .vditor-ir table').count(),1);
  assert.equal(await page.locator('#notes-editor .vditor-ir input[type=checkbox]').count(),1);
  assert((await draft(page)).includes('E=mc^2'));
  await page.locator('.vditor-sv').focus(); await page.keyboard.press('Escape');
  assert(!(await page.locator('#notes-panel').isVisible()));
  assert(await page.locator('#notes-button').evaluate(el=>el===document.activeElement));
  await open(page); await page.click('#notes-edit'); await page.locator('.vditor-ir').focus();
  await page.waitForTimeout(200); // Vditor's delayed selection handler closes toolbar popups.
  await page.locator('#notes-editor button[data-type=more]').click();
  await page.waitForSelector('#notes-editor .vditor-panel--arrow:visible'); await page.keyboard.press('Escape');
  assert(await page.locator('#notes-panel').isVisible(),'Escape closes editor menu first');
  await page.click('#theme-button');
  assert(await page.locator('#notes-editor').evaluate(el=>el.classList.contains('vditor--dark')));
  await page.screenshot({path:path.join(output,'notes-dark.png')});
  await page.locator('#notes-resize').focus(); await page.keyboard.press('ArrowLeft');
  assert.equal(await page.locator('#notes-resize').getAttribute('aria-valuenow'),'420');
  const handle = await page.locator('#notes-resize').boundingBox();
  await page.mouse.move(handle.x+5,handle.y+100); await page.mouse.down(); await page.mouse.move(970,200); await page.mouse.up();
  assert.equal(await page.locator('#notes-resize').getAttribute('aria-valuenow'),'470');

  const malicious = sample+'\n<img src="https://example.invalid/a.png" onerror="window.__notesXSS=true">\n\n<iframe src="https://example.invalid/frame"></iframe>\n\n<script>window.__notesXSS=true</script>\n\n[x](javascript:alert(1))\n\n```mermaid\ngraph LR; A-->B\n```\n';
  await (await source(page)).fill(malicious); await page.click('#notes-edit');
  assert.equal(await page.locator('#notes-editor iframe,#notes-editor img,#notes-editor script').count(),0);
  assert(!(await page.evaluate(()=>window.__notesXSS)));
  // Excerpt and undo retain their existing behavior, without storage.
  await (await source(page)).fill(''); await page.click('#notes-edit'); await page.click('#notes-close');
  await page.selectOption('#reading-mode','dual');
  const selectedText = await page.evaluate(()=>{
    const el=document.querySelector('article p[data-unit] .zh'); el.scrollIntoView({behavior:'instant'});
    const range=document.createRange(); range.setStart(el.firstChild,0); range.setEnd(el.firstChild,24);
    getSelection().removeAllRanges(); getSelection().addRange(range); return range.toString();
  });
  await page.waitForSelector('#notes-excerpt:visible'); await page.click('#notes-excerpt');
  await page.waitForFunction(t=>document.querySelector('.vditor-ir').textContent.includes(t),selectedText);
  await page.locator('.vditor-ir').focus();
  await page.keyboard.press(process.platform==='darwin'?'Meta+z':'Control+z');
  assert(!(await draft(page)).includes('返回原文'),'excerpt is undoable');
  const citation = `> ${selectedText}\n\n[返回原文](ace.html#abstract1)\n`;
  await (await source(page)).fill(citation); await page.click('#notes-edit');
  await page.locator('.vditor-ir__link').filter({hasText:'返回原文'}).click();
  assert.equal(new URL(page.url()).hash,'#abstract1');

  console.log('PASS notes editor, formatting, security, excerpt and undo');
  // New-file encoding and immutable snapshot, with a real intercepted popup.
  const special = '# 中文 & + # % ?\n\n第二行 😀\n[x](https://example.org/?a=1&b=2)\n';
  await (await source(page)).fill(special);
  const snapshot = await handoff(page), url = await newURL(page);
  assert.equal(url.pathname,'/TrickEye/paper-reading-room/new/main');
  assert.equal(url.searchParams.get('filename'),'public/notes/ace/notes.md');
  assert.equal(url.searchParams.get('value'),snapshot);
  assert(snapshot.includes('第二行 😀'));
  const popupEvent = context.waitForEvent('page');
  await page.click('#notes-github-open');
  const popup = await popupEvent; await popup.waitForLoadState();
  assert.equal(popup.url(),url.href); await popup.close();
  assert((await page.locator('#notes-handoff-status').innerText()).includes('待在 GitHub 提交'));
  assert((await page.locator('#notes-save-status').innerText()).includes('未提交'),'handoff does not mark draft saved');
  await page.evaluate(()=>{Object.defineProperty(navigator,'clipboard',{configurable:true,value:{writeText:async t=>{window.__copiedNote=t}}})});
  await page.click('#notes-copy');
  assert.equal(await page.evaluate(()=>window.__copiedNote),snapshot);
  await page.evaluate(()=>document.querySelector('.vditor-sv').value='changed behind dialog');
  assert.equal(await page.locator('#notes-handoff-source').inputValue(),snapshot);
  await page.evaluate(()=>{navigator.clipboard.writeText=async()=>{throw new Error('denied')}});
  await page.click('#notes-copy');
  assert((await page.locator('#notes-copy-status').innerText()).includes('自动复制失败'));
  assert(await page.locator('#notes-handoff-source').evaluate(el=>el.selectionEnd-el.selectionStart===el.value.length));
  await page.screenshot({path:path.join(output,'notes-github-handoff.png')});
  await page.keyboard.press('Escape');
  assert(!(await page.locator('#notes-handoff').isVisible()));
  assert(await page.locator('#notes-github').evaluate(el=>el===document.activeElement));

  // Full encoded URL budget (ASCII exact boundary and Chinese expansion).
  const baseURL = new URL('https://github.com/TrickEye/paper-reading-room/new/main');
  baseURL.searchParams.set('filename','public/notes/ace/notes.md'); baseURL.searchParams.set('value','');
  const asciiBudget = 6000-baseURL.href.length;
  for (const [text,preFilled] of [['x'.repeat(asciiBudget-3)+'\n',true],['x'.repeat(asciiBudget+1),false],['汉'.repeat(1000),false],['',true]]) {
    await (await source(page)).fill(text); const value=await handoff(page), target=await newURL(page);
    assert.equal(target.searchParams.has('value'),preFilled,`prefill: ${text.length} chars`);
    if(preFilled) assert.equal(target.searchParams.get('value'),value);
    else assert((await page.locator('#notes-handoff-help').innerText()).includes('超过'));
    await closeHandoff(page);
  }
  console.log('PASS notes GitHub encoding, URL budget, snapshot and clipboard');
  // Width persists; note text does not. Legacy note records are ignored and untouched.
  await (await source(page)).fill('尚未提交的内存笔记');
  await page.evaluate(()=>localStorage.setItem('paper-reader:/:notes:v1:ace','legacy-note-record'));
  await ready(page); await open(page);
  assert.equal((await draft(page)).trim(),'');
  assert.equal(await page.locator('#notes-resize').getAttribute('aria-valuenow'),'470');
  assert.equal(await page.evaluate(()=>localStorage.getItem('paper-reader:/:notes:v1:ace')),'legacy-note-record');

  // Loading locks both fallback and Vditor, including when editor initialization races fetch.
  remote.set(notesPath,{status:200,body:'# 部署版本\n\n远端正文',wait:true});
  await page.goto(route('ace')); await page.waitForSelector('#notes-panel',{state:'attached'});
  await page.waitForFunction(()=>document.querySelector('#notes-refresh').disabled);
  await page.click('#notes-button'); await page.waitForSelector('#notes-editor[data-editor-ready=true]');
  assert(await page.locator('#notes-editor').evaluate(el=>el.inert));
  assert(await page.locator('#notes-fallback').evaluate(el=>el.readOnly));
  assert(await page.locator('#notes-github').isDisabled());
  while (!pending) await new Promise(r=>setTimeout(r,10));
  pending(); pending=null;
  await page.waitForFunction(()=>!document.querySelector('#notes-refresh').disabled);
  assert((await draft(page)).includes('远端正文'));
  const editSnapshot=await handoff(page), editURL=await newURL(page);
  assert.equal(editURL.href,'https://github.com/TrickEye/paper-reading-room/edit/main/public/notes/ace/notes.md');
  assert(!editURL.search);
  assert(editSnapshot.includes('远端正文')); await closeHandoff(page);
  await (await source(page)).fill('当前未提交修改');
  remote.set(notesPath,{status:500,body:'error'});
  await page.click('#notes-refresh');
  await page.waitForFunction(()=>document.querySelector('#notes-remote-status').textContent.includes('加载失败'));
  assert.equal((await draft(page)).trim(),'当前未提交修改');
  await handoff(page);
  assert(await page.locator('#notes-handoff-choice').isVisible());
  assert(!(await page.locator('#notes-github-open').isVisible()));
  await page.check('input[name=notes-target][value=new]'); assert.equal((await newURL(page)).searchParams.get('filename'),'public/notes/ace/notes.md');
  await page.check('input[name=notes-target][value=edit]'); assert.equal((await newURL(page)).href,editURL.href);
  await closeHandoff(page);
  remote.set(notesPath,{status:404,body:'missing'});
  await page.click('#notes-refresh'); await page.waitForFunction(()=>!document.querySelector('#notes-refresh').disabled);
  assert.equal((await draft(page)).trim(),'当前未提交修改','404 keeps memory draft');
  remote.set(notesPath,{status:200,body:'更新后的部署版'});
  await page.click('#notes-refresh'); await page.waitForFunction(()=>document.querySelector('#notes-remote-status').textContent.includes('已载入'));
  assert.equal((await draft(page)).trim(),'更新后的部署版','successful retry overwrites unsaved edits');
  remote.set(notesPath,{status:200,body:''});
  await page.click('#notes-refresh'); await page.waitForFunction(()=>!document.querySelector('#notes-refresh').disabled);
  assert.equal((await draft(page)).trim(),'');
  await handoff(page); assert((await page.locator('#notes-handoff-help').innerText()).includes('清空')); await closeHandoff(page);

  // IME blocks handoff/refresh until composition finishes.
  const src=await source(page); await src.dispatchEvent('compositionstart'); await src.fill('中文输入法');
  assert(await page.locator('#notes-github').isDisabled()); assert(await page.locator('#notes-refresh').isDisabled());
  await src.dispatchEvent('compositionend'); assert(!(await page.locator('#notes-github').isDisabled()));
  assert((await page.locator('#notes-save-status').innerText()).includes('未提交'));
  assert(!await page.evaluate(()=>Object.keys(localStorage).some(k=>k.includes(':notes:') && localStorage.getItem(k)!=='legacy-note-record')),'no note storage written');

  for (const width of [1920,1440,1024,390,320]) {
    await page.setViewportSize({width,height:900});
    assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),`no overflow at ${width}`);
    const box=await page.locator('#notes-panel').boundingBox();
    if(width<=940) assert(Math.abs(box.height-450)<2,'half-height mobile sheet');
    if(width===1024) { await page.click('#menu-button'); assert(!(await page.locator('#notes-panel').isVisible())); await page.keyboard.press('Escape'); await open(page); }
    await handoff(page);
    assert(await page.locator('#notes-handoff').evaluate(el=>el.scrollWidth<=el.clientWidth),`handoff fits ${width}`);
    await page.screenshot({path:path.join(output,`notes-${width}.png`)}); await closeHandoff(page);
  }
  await page.emulateMedia({media:'print'}); assert(!(await page.locator('#notes-panel').isVisible())); await page.emulateMedia({media:'screen'});
  await page.setViewportSize({width:1440,height:1000});
  // Preview and project subpath resolve their notes from the manifest URL.
  const shell=await (await page.request.get(route('ace'))).text();
  const previewURL=new URL('/reader-preview.html?paper=ace',route('ace')).href;
  await page.route(previewURL,r=>r.fulfill({contentType:'text/html',body:shell.replaceAll('../','')}));
  remote.set(notesPath,{status:200,body:'预览笔记'});
  await page.goto(previewURL); await page.waitForSelector('#notes-panel',{state:'attached'}); await open(page);
  assert.equal((await draft(page)).trim(),'预览笔记');
  await ready(page,'ace','/project'); await open(page); assert.equal((await draft(page)).trim(),'');
  assert(requests.some(url=>new URL(url).pathname==='/project/notes/ace/notes.md'));
  await ready(page,'skillforge'); await open(page); assert.equal((await draft(page)).trim(),'');
  assert(!requests.some(url=>/example\.invalid|\/js\/(mermaid|echarts|graphviz)/.test(url)));
  assert(requests.every(url=>url.startsWith(new URL(route('ace')).origin)),'main page makes only same-origin requests');
  assert.deepEqual(errors,[]);

  console.log('PASS notes remote states, IME, viewport and path isolation');
  // A real browser beforeunload prompt can cancel navigation; handoff never clears it.
  remote.delete(notesPath);
  const leave=await context.newPage(); await ready(leave); await open(leave);
  await (await source(leave)).fill('不能丢失的草稿'); await handoff(leave); await closeHandoff(leave);
  let prompt=leave.waitForEvent('dialog'); await leave.close({runBeforeUnload:true});
  let warning=await prompt; assert.equal(warning.type(),'beforeunload'); await warning.dismiss(); assert(!leave.isClosed());
  await (await source(leave)).fill('');
  const closeEvent=leave.waitForEvent('close'); await leave.close({runBeforeUnload:true}); await closeEvent;

  // Independent tabs do not read or exchange note drafts.
  const other=await context.newPage(); acceptLeave(other); remote.delete(notesPath);
  await ready(page); await open(page); await (await source(page)).fill('标签页一');
  await ready(other); await open(other); assert.equal((await draft(other)).trim(),'');
  await (await source(other)).fill('标签页二'); assert.equal((await draft(page)).trim(),'标签页一'); await other.close();
  await context.close();

  // Mobile keyboard geometry and touch excerpt retain a usable in-memory editor.
  const mobile=await browser.newPage({viewport:{width:390,height:900},hasTouch:true,
    userAgent:'Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 Version/18.0 Mobile/15E148 Safari/604.1'});
  acceptLeave(mobile);
  await mobile.addInitScript(()=>Object.defineProperty(window,'visualViewport',{value:Object.assign(new EventTarget(),{height:innerHeight,offsetTop:0})}));
  await ready(mobile); await open(mobile); await (await source(mobile)).focus();
  await mobile.evaluate(()=>{visualViewport.height=400;visualViewport.dispatchEvent(new Event('resize'));});
  assert(Math.abs((await mobile.locator('#notes-panel').boundingBox()).height-280)<2);
  assert((await mobile.locator('.vditor-sv').boundingBox()).height>40,'keyboard leaves usable editor');
  await mobile.screenshot({path:path.join(output,'notes-keyboard-geometry.png')});
  await mobile.evaluate(()=>{visualViewport.height=innerHeight;visualViewport.dispatchEvent(new Event('resize'));});
  await mobile.tap('#notes-close'); await mobile.selectOption('#reading-mode','en');
  const english=await mobile.evaluate(()=>{
    const el=document.querySelector('article p[data-unit] .en');el.scrollIntoView({behavior:'instant'});
    const range=document.createRange();range.setStart(el.firstChild,0);range.setEnd(el.firstChild,12);
    getSelection().removeAllRanges();getSelection().addRange(range);return range.toString();
  });
  await mobile.waitForSelector('#notes-excerpt:visible');await mobile.tap('#notes-excerpt');
  assert((await draft(mobile)).includes(english),'touch excerpt includes only selected language');
  assert(!(await draft(mobile)).includes('大语言模型'));
  await mobile.screenshot({path:path.join(output,'notes-mobile-editor.png')});
  await mobile.close();

  // Timeout and fetch rejection retain memory drafts; clear the stub to retry.
  for (const failure of ['timeout','network']) {
    const p=await browser.newPage(); acceptLeave(p);
    await p.addInitScript(failure=>{
      const original=window.fetch;
      window.fetch=function(url,options){
        if(String(url).includes('/notes/') && !window.__notesRecovered){
          window.__notesFetchCache=options.cache;
          if(failure==='network') return Promise.reject(new TypeError('network failure'));
          return new Promise((_,reject)=>options.signal.addEventListener('abort',()=>reject(new DOMException('timeout','AbortError'))));
        }
        return original.call(this,url,options);
      };
    },failure);
    if(failure==='timeout') await p.clock.install();
    await p.goto(route('ace')); await p.waitForSelector('#notes-panel',{state:'attached'});
    if(failure==='timeout') { // advance the real controller timeout without sleeping 15 seconds
      await p.clock.runFor(15001);
    }
    await p.waitForFunction(()=>document.querySelector('#notes-remote-status').textContent.includes('加载失败'));
    assert.equal(await p.evaluate(()=>window.__notesFetchCache),'no-cache');
    await open(p); await (await source(p)).fill('失败后继续编辑');
    await p.evaluate(()=>{window.__notesRecovered=true}); await p.click('#notes-refresh');
    await p.waitForFunction(()=>!document.querySelector('#notes-refresh').disabled);
    assert.equal((await draft(p)).trim(),'失败后继续编辑'); await p.close();
  }
  // Old manifests, failed editor dependencies and unavailable storage retain usable memory editing.
  for (const failure of ['legacy','editor','parser','stylesheet','storage']) {
    const p=await browser.newPage(); acceptLeave(p);
    if(failure==='legacy') await p.route('**/content/manifest.json',async r=>{
      const response=await r.fetch(), manifest=await response.json(); delete manifest.notes.documents; delete manifest.notes.github;
      await r.fulfill({response,json:manifest});
    });
    else if(failure==='storage') await p.addInitScript(()=>{Storage.prototype.getItem=function(){throw new DOMException('blocked','SecurityError')}});
    else {
      const pattern=failure==='editor'?'**/vendor/**/dist/index.min.js':failure==='parser'?'**/vendor/**/dist/js/lute/lute.min.js':'**/vendor/**/dist/index.css';
      await p.route(pattern,r=>r.fulfill({status:404,body:'missing'}));
    }
    await p.goto(route('ace')); await p.waitForSelector('#notes-panel',{state:'attached'}); await p.click('#notes-button');
    if(failure==='legacy') {
      await p.waitForSelector('#notes-editor[data-editor-ready=true]');
      assert(!(await p.locator('#notes-remote').isVisible())); await (await source(p)).fill('旧清单内存编辑');
    } else {
      await p.waitForSelector('#notes-retry:visible');
      await p.fill('#notes-fallback','降级编辑'); await p.click('#notes-close'); await p.click('#notes-button');
      assert.equal(await p.locator('#notes-fallback').inputValue(),'降级编辑');
      if(failure!=='storage') { await p.unrouteAll(); await p.click('#notes-retry'); await p.waitForSelector('#notes-editor[data-editor-ready=true]'); assert.equal((await draft(p)).trim(),'降级编辑'); }
    }
    await p.close();
  }
  console.log('PASS notes: memory drafts, beforeunload, remote load/retry, GitHub handoff/encoding/clipboard, editor, excerpt, IME, responsive and compatibility');
};
