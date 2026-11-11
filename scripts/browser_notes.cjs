/* Notes acceptance scenarios, called by the existing browser suite. */
const assert = require('node:assert/strict');
const path = require('node:path');
module.exports = async function checkNotes({browser, route, output}) {
  const context = await browser.newContext({viewport:{width:1440,height:1000}});
  const page = await context.newPage(), errors = [], requests = [];
  page.on('pageerror', e => errors.push(e.message));
  page.on('request', r => requests.push(r.url()));
  const ready = async p => { await p.goto(route('ace')); await p.waitForSelector('#notes-panel', {state:'attached'}); };
  const open = async p => {
    await p.click('#notes-button');
    await p.waitForSelector('#notes-editor[data-editor-ready=true]');
  };
  const source = async p => { await p.click('#notes-source'); return p.locator('.vditor-sv'); };
  const stored = p => p.evaluate(() => {
    const key = Object.keys(localStorage).find(k=>k.includes(':notes:v1:ace'));
    return key ? JSON.parse(localStorage.getItem(key)).markdown : null;
  });
  await ready(page);
  assert(!requests.some(url=>url.includes('/vendor/')), 'Editor is lazy');
  assert(!(await page.locator('#notes-panel').isVisible()));
  await open(page);
  const sample = '# 阅读心得\n\n**重要** 与 *强调*\n\n- 项目\n- [ ] 待办\n\n> 一段引用\n\n| 方法 | 结果 |\n| --- | --- |\n| ACE | 通过 |\n\n```js\nconst a = 1;\n```\n\n$x^2$\n\n$$\nE=mc^2\n$$\n';
  await (await source(page)).fill(sample);
  // Close immediately, before Vditor's delayed input callback.
  await page.click('#notes-close');
  assert((await stored(page)).includes('阅读心得'));
  await page.reload(); await page.waitForSelector('#notes-panel',{state:'attached'}); await open(page);
  await page.waitForSelector('#notes-editor .katex');
  assert((await page.locator('#notes-editor .vditor-ir h1').innerText()).includes('阅读心得'));
  assert.equal(await page.locator('#notes-editor .vditor-ir table').count(),1);
  assert.equal(await page.locator('#notes-editor .vditor-ir input[type=checkbox]').count(),1);
  assert((await (await source(page)).inputValue()).includes('E=mc^2'));
  await page.click('#notes-edit');
  await page.click('#theme-button');
  await page.click('#notes-source');
  await page.locator('#notes-editor .vditor-sv').focus(); await page.keyboard.press('Escape');
  assert(!(await page.locator('#notes-panel').isVisible()),'Escape closes notes');
  assert(await page.locator('#notes-button').evaluate(el=>el===document.activeElement));
  await page.click('#notes-button');
  await page.locator('#notes-editor button[data-type=more]').click(); await page.keyboard.press('Escape');
  assert(await page.locator('#notes-panel').isVisible(),'Escape closes editor menu first');
  await page.click('#notes-edit');
  assert(await page.locator('#notes-editor').evaluate(el=>el.classList.contains('vditor--dark')));
  await page.screenshot({path:path.join(output,'notes-dark.png')});
  await page.click('#theme-button');
  // Keyboard and pointer resizing, persisted across reload.
  await page.locator('#notes-resize').focus(); await page.keyboard.press('ArrowLeft');
  assert.equal(await page.locator('#notes-resize').getAttribute('aria-valuenow'),'420');
  const handle = await page.locator('#notes-resize').boundingBox();
  await page.mouse.move(handle.x+5,handle.y+100); await page.mouse.down(); await page.mouse.move(970,200); await page.mouse.up();
  assert.equal(await page.locator('#notes-resize').getAttribute('aria-valuenow'),'470');
  await page.screenshot({path:path.join(output,'notes-desktop.png')});
  await page.reload(); await page.waitForSelector('#notes-panel',{state:'attached'}); await open(page);
  assert.equal(await page.locator('#notes-resize').getAttribute('aria-valuenow'),'470','width restored');
  // Source text and render transformations must not execute or fetch active HTML/diagrams.
  const malicious = sample+'\n<img src="https://example.invalid/a.png" onerror="window.__notesXSS=true">\n\n<iframe src="https://example.invalid/frame"></iframe>\n\n<script>window.__notesXSS=true</script>\n\n[x](javascript:alert(1))\n\n```mermaid\ngraph LR; A-->B\n```\n';
  await (await source(page)).fill(malicious); await page.click('#notes-edit');
  assert.equal(await page.locator('#notes-editor iframe,#notes-editor img,#notes-editor script').count(),0);
  assert(!(await page.evaluate(()=>window.__notesXSS)));
  // Select exactly one language, append citation, then undo the append.
  await page.click('#notes-close');
  await page.selectOption('#reading-mode','dual');
  const selectedText = await page.evaluate(()=>{
    const el=document.querySelector('article p[data-unit] .zh');
    el.scrollIntoView({behavior:'instant'}); const text=el.firstChild;
    const range=document.createRange();range.setStart(text,0);range.setEnd(text,Math.min(text.length,24));
    getSelection().removeAllRanges();getSelection().addRange(range);return range.toString();
  });
  await page.waitForSelector('#notes-excerpt:visible'); await page.click('#notes-excerpt');
  await page.waitForFunction(text=>{const k=Object.keys(localStorage).find(k=>k.includes(':notes:v1:ace'));return k&&JSON.parse(localStorage.getItem(k)).markdown.includes(text)},selectedText);
  const citation = await stored(page);
  assert(citation.includes('ace.html#'));
  await page.locator('#notes-editor .vditor-ir').focus();
  await page.keyboard.press(process.platform==='darwin'?'Meta+z':'Control+z');
  await page.waitForTimeout(700);
  assert(!(await stored(page)).includes('返回原文'), 'Excerpt append is undoable');
  // Restore citation through source, then click the rendered link to navigate.
  await (await source(page)).fill(citation); await page.click('#notes-edit');
  await page.locator('#notes-editor .vditor-ir__link').filter({hasText:'返回原文'}).click();
  assert(new URL(page.url()).hash);
  // Cross-tab: clean adoption, then conflict with a pending local edit.
  const other = await context.newPage(); await ready(other); await open(other);
  await (await source(other)).fill('其他页更新'); await other.click('#notes-close');
  await page.waitForFunction(()=>document.querySelector('#notes-save-status').textContent.includes('其他页更新'));
  const src = await source(page); await src.fill('本页尚未保存');
  await other.evaluate(()=>{
    const k=Object.keys(localStorage).find(k=>k.includes(':notes:v1:ace'));
    localStorage.setItem(k,JSON.stringify({schemaVersion:1,paperId:'ace',markdown:'冲突版本',updatedAt:new Date().toISOString()}));
  });
  await page.waitForSelector('#notes-keep-local:visible');
  assert.equal(await stored(page),'冲突版本');
  await page.click('#notes-keep-local'); assert.equal((await stored(page)).trim(),'本页尚未保存');
  // IME: composing content is not written until composition ends.
  await src.dispatchEvent('compositionstart'); await src.fill('中文输入法');
  await page.waitForTimeout(650); assert.equal((await stored(page)).trim(),'本页尚未保存');
  await src.dispatchEvent('compositionend'); await page.waitForTimeout(650);
  assert.equal((await stored(page)).trim(),'中文输入法');
  for (const width of [1920,1440,1024,390,320]) {
    await page.setViewportSize({width,height:900});
    assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),`no overflow at ${width}`);
    const box=await page.locator('#notes-panel').boundingBox();
    if(width<=940) assert(Math.abs(box.height-450)<2,'half-height mobile sheet');
    if(width===1024) {
      assert(await page.locator('#menu-button').isVisible());
      await page.click('#menu-button'); assert(!(await page.locator('#notes-panel').isVisible()));
      await page.keyboard.press('Escape'); await page.click('#notes-button');
    }
    await page.screenshot({path:path.join(output,`notes-${width}.png`)});
  }
  await page.emulateMedia({media:'print'}); assert(!(await page.locator('#notes-panel').isVisible()));
  await page.emulateMedia({media:'screen'});
  await page.setViewportSize({width:1440,height:1000});
  // Preview and production shells share the same manifest-derived namespace.
  const shell = await (await page.request.get(route('ace'))).text();
  const previewURL = new URL('/reader-preview.html?paper=ace', route('ace')).href;
  await page.route(previewURL,r=>r.fulfill({contentType:'text/html',body:shell.replaceAll('../','')}));
  await page.goto(previewURL); await page.waitForSelector('#notes-panel',{state:'attached'}); await open(page);
  assert.equal((await (await source(page)).inputValue()).trim(),'中文输入法','preview shares notes');
  await page.goto(route('skillforge')); await page.waitForSelector('#notes-panel',{state:'attached'}); await open(page);
  assert.equal((await (await source(page)).inputValue()).trim(),'','paper isolation');
  await page.goto(route('ace','/project')); await page.waitForSelector('#notes-panel',{state:'attached'}); await open(page);
  assert.equal((await (await source(page)).inputValue()).trim(),'','publication path isolation');
  assert(!requests.some(url=>/example\.invalid|\/js\/(mermaid|echarts|graphviz)/.test(url)), 'no unwanted render requests');
  assert(requests.every(url=>url.startsWith(new URL(route('ace')).origin)), 'local resources only');
  assert.deepEqual(errors,[]);
  await context.close();
  // VisualViewport keyboard geometry (device keyboards still require a real-device pass).
  const mobile = await browser.newPage({viewport:{width:390,height:900},hasTouch:true,
    userAgent:'Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 Version/18.0 Mobile/15E148 Safari/604.1'});
  await mobile.addInitScript(()=>Object.defineProperty(window,'visualViewport',{value:Object.assign(new EventTarget(),{height:innerHeight,offsetTop:0})}));
  await ready(mobile); await open(mobile); await (await source(mobile)).focus();
  await mobile.evaluate(()=>{visualViewport.height=400;visualViewport.dispatchEvent(new Event('resize'));});
  assert(Math.abs((await mobile.locator('#notes-panel').boundingBox()).height-280)<2);
  assert((await mobile.locator('.vditor-sv').boundingBox()).height>40,'keyboard leaves usable editor');
  await mobile.screenshot({path:path.join(output,'notes-keyboard-geometry.png')});
  await mobile.evaluate(()=>{visualViewport.height=innerHeight;visualViewport.dispatchEvent(new Event('resize'));});
  await mobile.tap('#notes-close'); await mobile.selectOption('#reading-mode','en');
  const english = await mobile.evaluate(()=>{
    const el=document.querySelector('article p[data-unit] .en');el.scrollIntoView({behavior:'instant'});
    const range=document.createRange();range.setStart(el.firstChild,0);range.setEnd(el.firstChild,12);
    getSelection().removeAllRanges();getSelection().addRange(range);return range.toString();
  });
  await mobile.waitForSelector('#notes-excerpt:visible'); await mobile.tap('#notes-excerpt');
  assert((await (await source(mobile)).inputValue()).includes(english),'touch excerpt keeps selected English');
  assert(!(await (await source(mobile)).inputValue()).includes('大语言模型'),'no automatic bilingual completion');
  await mobile.close();
  // Failure recovery, prohibited storage, quota exhaustion and unknown records.
  for (const failure of ['editor','parser','stylesheet','storage','quota','record']) {
    const p=await browser.newPage();
    if(['editor','parser','stylesheet'].includes(failure)) {
      const pattern=failure==='editor'?'**/vendor/**/dist/index.min.js':failure==='parser'?'**/vendor/**/dist/js/lute/lute.min.js':'**/vendor/**/dist/index.css';
      await p.route(pattern,r=>r.fulfill({status:404,body:'missing'}));
    } else await p.addInitScript(failure=>{
      if(failure==='storage') Storage.prototype.getItem=function(){throw new DOMException('blocked','SecurityError')};
      if(failure==='quota') {const set=Storage.prototype.setItem;Storage.prototype.setItem=function(k,v){if(k.includes(':notes:v1:'))throw new DOMException('full','QuotaExceededError');return set.call(this,k,v)}}
      if(failure==='record') localStorage.setItem('paper-reader:/:notes:v1:ace','{"schemaVersion":99}');
    },failure);
    await ready(p); await p.click('#notes-button');
    if(['editor','parser','stylesheet'].includes(failure)) {
      await p.waitForSelector('#notes-retry:visible');
      await p.fill('#notes-fallback','降级编辑'); await p.click('#notes-close');
      assert.equal((await stored(p)).trim(),'降级编辑');
      await p.unrouteAll(); await p.click('#notes-button');
      await p.waitForSelector('#notes-editor[data-editor-ready=true]');
      assert((await (await source(p)).inputValue()).includes('降级编辑'));
    } else if (failure === 'storage') {
      await p.waitForSelector('#notes-retry:visible');
      await p.fill('#notes-fallback','保留本页内容'); await p.click('#notes-close');
      assert((await p.locator('#notes-save-status').innerText()).includes('保存失败'));
    } else {
      await p.waitForSelector('#notes-editor[data-editor-ready=true]');
      await (await source(p)).fill('保留本页内容'); await p.click('#notes-close');
      assert((await p.locator('#notes-save-status').innerText()).includes('保存失败'));
      if(failure==='record') assert.equal(await p.evaluate(()=>localStorage.getItem('paper-reader:/:notes:v1:ace')),'{"schemaVersion":99}');
    }
    await p.close();
    console.log('PASS notes recovery',failure);
  }
  console.log('PASS notes: editor, math, excerpt/undo/backlink, storage, conflicts/IME, responsive, recovery and isolation');
};
