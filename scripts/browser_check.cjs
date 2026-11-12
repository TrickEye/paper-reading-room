/* Browser acceptance suite. npm install --no-save --package-lock=false playwright@1.62.1
 * Optional: PLAYWRIGHT_MODULE, CHROME_EXECUTABLE, READER_PREVIEW=1,
 * MIGRATION_BASELINE_DIR and BROWSER_OUTPUT_DIR. No production Node dependency.
 */
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');
const http = require('node:http');
const {createHash} = require('node:crypto');
const root = path.resolve(__dirname, '../public');
const output = process.env.BROWSER_OUTPUT_DIR || path.join(require('node:os').tmpdir(), 'paper-reader-browser-check');
const expected = {ace: [184,14,22], skillforge: [238,16,4], 'permission-denied': [190,4,15], skillcat: [210,4,2], skillgen: [350,8,4]};
const preview = process.env.READER_PREVIEW === '1';
let browser, server;
const snapshot = () => {
  const root = document.querySelector('article');
  const content = root.cloneNode(true);
  content.querySelectorAll('[data-reader-ui]').forEach(el => el.remove());
  return {ids: [...root.querySelectorAll('[id]')].map(e => e.id),
    units: [...root.querySelectorAll('[data-unit]')].map(e => [e.dataset.unit,e.textContent]),
    tables: [...root.querySelectorAll('table')].map(e => e.outerHTML),
    math: [...root.querySelectorAll('math')].map(e => e.outerHTML),
    codes: [...root.querySelectorAll('pre')].map(e => e.textContent),text: content.textContent};
};
async function state(page, wanted = 'ready') {
  await page.waitForFunction(value => document.body.dataset.readerState === value, wanted, {timeout: 30000});
}
async function main() {
  await fs.mkdir(output, {recursive: true});
  server = http.createServer(async (req, res) => {
    try {
      let pathname = decodeURIComponent(new URL(req.url, 'http://localhost').pathname).replace(/^\/project(?=\/)/, '');
      if (pathname.endsWith('/')) pathname += 'index.html';
      const target = path.resolve(root, '.' + pathname);
      if (!target.startsWith(root + path.sep)) throw new Error('outside publication');
      const bytes = await fs.readFile(target);
      res.setHeader('Content-Type', {'.html':'text/html; charset=utf-8','.json':'application/json','.css':'text/css','.js':'text/javascript','.svg':'image/svg+xml','.png':'image/png','.jpg':'image/jpeg','.pdf':'application/pdf'}[path.extname(target)] || 'application/octet-stream');
      res.setHeader('Cache-Control', /\.[a-f0-9]{16}\./.test(target) ? 'public,max-age=3600' : 'no-cache');
      res.end(bytes);
    } catch { res.writeHead(404); res.end('Not found'); }
  });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  const base = `http://127.0.0.1:${server.address().port}`;
  browser = await chromium.launch({headless: true, ...(process.env.CHROME_EXECUTABLE ? {executablePath: process.env.CHROME_EXECUTABLE} : {})});
  const route = (id, prefix = '') => base + prefix + (preview ? `/reader-preview.html?paper=${id}` : `/papers/${id}.html`);
  const manifest = JSON.parse(await fs.readFile(path.join(root,'content/manifest.json')));
  const metrics = [];
  const baselineHashes = JSON.parse(await fs.readFile(path.resolve(__dirname,'../tests/migration-baseline.json')));
  for (const [id, counts] of Object.entries(expected)) {
    const page = await browser.newPage({viewport: {width:1440,height:1000}});
    const requests = [], errors = [];
    page.on('request', req => requests.push(req.url()));
    page.on('pageerror', error => errors.push(error.message));
    await page.goto(route(id)); await state(page);
    const doc = JSON.parse(await fs.readFile(path.join(root,'content',manifest.papers[id].url)));
    assert.deepEqual(await page.evaluate(() => [document.querySelectorAll('article [data-unit]').length,document.querySelectorAll('figure.ltx_figure').length,document.querySelectorAll('article table').length]), counts);
    const actual = await page.evaluate(snapshot);
    if (process.env.MIGRATION_BASELINE_DIR) {
      const old = JSON.parse(await fs.readFile(path.join(process.env.MIGRATION_BASELINE_DIR, `${id}-dom.json`)));
      assert.deepEqual(actual, old, `${id}: original IDs, bilingual text, complete tables, math, code and article text must remain unchanged`);
    }
    for (const [key,value] of Object.entries(actual)) assert.equal(createHash('sha256').update(JSON.stringify(value)).digest('hex'),baselineHashes[id][key],`${id}: migration baseline ${key}`);
    assert(await page.locator('math').evaluateAll(nodes => nodes.every(n => n.namespaceURI === 'http://www.w3.org/1998/Math/MathML' && [...n.querySelectorAll('*')].every(x => x.namespaceURI === n.namespaceURI))), `${id}: MathML namespace`);
    await page.screenshot({path:path.join(output,`${id}-desktop.png`)});
    for (const [kind, selector] of [['table','article table'],['formula','article math'],['figure','figure.ltx_figure']]) {
      const element = page.locator(selector + ':visible').first();
      if (await element.count()) {
        await element.scrollIntoViewIfNeeded();
        await page.screenshot({path:path.join(output,`${id}-${kind}.png`)});
      }
    }
    for (const mode of ['en','dual','zh']) {
      await page.selectOption('#reading-mode',mode);
      assert.equal(await page.locator('html').getAttribute('data-lang'),mode);
      const unit = page.locator('[data-unit]').filter({has:page.locator(':scope > .zh')}).first();
      assert.equal(await unit.locator(':scope > .zh').isVisible(),mode!=='en');
      assert.equal(await unit.locator(':scope > .en').isVisible(),mode!=='zh');
      if(mode==='en') assert.equal(await page.locator('article .zh:visible,article .translation:visible').count(),0,'English mode hides all translations, including tables/notes');
      if(mode==='zh') assert.equal(await page.locator('article .en:visible').evaluateAll(nodes=>nodes.filter(n=>!n.closest('.ltx_bib_title')).length),0,'Chinese mode hides English pairs, including tables/code');
    }
    await page.selectOption('#reading-mode','en');
    await page.fill('#search-input',doc.meta.titles.en.slice(0,18));
    await page.waitForFunction(() => document.querySelectorAll('#search-results a').length > 0);
    await page.locator('#search-results a').first().click();
    assert(await page.locator('.search-target').count() > 0);
    await page.fill('#search-input',''); await page.waitForFunction(() => document.querySelector('#search-results').hidden);
    if (id === 'skillforge') {
      const codeQuery = await page.locator('pre.en').first().evaluate(el => el.textContent.trim().split('\n').find(x=>x.trim().length>10).trim().slice(0,32));
      await page.fill('#search-input',codeQuery);
      await page.waitForFunction(() => document.querySelectorAll('#search-results a').length > 0);
      await page.fill('#search-input',''); await page.waitForFunction(() => document.querySelector('#search-results').hidden);
    }
    const size = await page.locator('html').evaluate(el=>getComputedStyle(el).getPropertyValue('--body-size'));
    await page.click('#font-up');
    assert.notEqual(await page.locator('html').evaluate(el=>getComputedStyle(el).getPropertyValue('--body-size')),size);
    await page.click('#font-down');
    await page.click('#theme-button'); assert.equal(await page.locator('html').getAttribute('data-theme'),'dark');
    await page.screenshot({path:path.join(output,`${id}-dark.png`)});
    await page.click('#theme-button');
    await page.locator('.figure-zoom').first().click();
    assert(await page.locator('#image-dialog').isVisible());
    assert.equal(await page.locator('#dialog-image').getAttribute('src'),await page.locator('figure.ltx_figure img').first().getAttribute('src'));
    await page.keyboard.press('Escape'); assert(!(await page.locator('#image-dialog').isVisible()));
    assert(await page.locator('.figure-zoom').first().evaluate(el=>el===document.activeElement));
    await page.evaluate(()=>{window.print=()=>{window.__printed=true;};});
    await page.click('#print-button');
    await page.waitForFunction(()=>window.__printed===true,{},{timeout:30000});
    assert(await page.locator('article img').evaluateAll(nodes=>nodes.every(n=>n.complete&&n.naturalWidth>0)));
    assert.equal(requests.filter(url=>/\/paper\.[a-f0-9]+\.json/.test(url)).length,1,'Mode/search/print must not fetch paper content again');
    assert(!requests.some(url=>/\.pdf(?:$|\?)/.test(url)),'PDF must not download on reading');
    assert(!requests.some(url=>/\/content\/(?!manifest)/.test(url) && !url.includes(`/content/${id}/`)),'No other paper resources');
    assert(requests.every(url=>url.startsWith(base)),'No external runtime request');
    await page.selectOption('#reading-mode',id==='ace'?'zh':'dual');
    await page.emulateMedia({reducedMotion:'reduce'});
    await page.setViewportSize({width:390,height:844});
    await page.evaluate(()=>scrollTo({top:0,behavior:'instant'}));
    await page.waitForFunction(()=>scrollY===0);
    await page.screenshot({path:path.join(output,`${id}-mobile.png`)});
    assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'Mobile page overflows horizontally');
    await page.click('#menu-button'); assert(await page.locator('#search-input').evaluate(el=>el===document.activeElement));
    await page.keyboard.press('Shift+Tab'); assert(await page.locator('nav a').last().evaluate(el=>el===document.activeElement));
    await page.keyboard.press('Tab'); assert(await page.locator('#search-input').evaluate(el=>el===document.activeElement));
    await page.keyboard.press('Escape'); assert.equal(await page.locator('#menu-button').getAttribute('aria-expanded'),'false');
    assert(await page.locator('#menu-button').evaluate(el=>el===document.activeElement));
    await page.click('#menu-button'); await page.locator('nav a').nth(1).click();
    assert.equal(await page.locator('#menu-button').getAttribute('aria-expanded'),'false');
    const firstHash = new URL(page.url()).hash;
    await page.click('#menu-button'); await page.locator('nav a').nth(2).click();
    const secondHash = new URL(page.url()).hash;
    await page.goBack(); await page.waitForURL(url=>url.hash===firstHash);
    await page.goForward(); await page.waitForURL(url=>url.hash===secondHash);
    await page.reload(); await state(page);
    await page.waitForFunction(()=>{const id=decodeURIComponent(location.hash.slice(1)),el=document.getElementById(id);return el&&el.getBoundingClientRect().top>=0&&el.getBoundingClientRect().top<360;});
    assert.deepEqual(errors,[]);
    metrics.push({id,jsonBytes:Buffer.byteLength(JSON.stringify(doc)),paperReadyMs:await page.evaluate(()=>performance.getEntriesByName('paper-ready')[0].startTime)});
    await page.close();
    // Direct hashed links and content resources under GitHub project subpaths.
    const sub = await browser.newPage({viewport:{width:390,height:844}});
    await sub.goto(route(id,'/project')+'#'+doc.toc[1].id); await state(sub);
    await sub.waitForFunction(()=>{const el=document.getElementById(decodeURIComponent(location.hash.slice(1)));return el&&el.getBoundingClientRect().top>=0&&el.getBoundingClientRect().top<360;});
    assert((await sub.locator('article img').first().getAttribute('src')).includes('/project/content/'));
    await sub.locator('figure img').first().scrollIntoViewIfNeeded();
    await sub.waitForFunction(()=>{const image=document.querySelector('figure img');return image.complete&&image.naturalWidth>0;});
    await sub.close(); console.log('PASS browser',id,'desktop/mobile, DOM, interactions, print, hash and project subpath');
  }
  const jsonPattern = '**/paper.*.json';
  for (const failure of ['slow','404','json','schema','id']) {
    const page = await browser.newPage();
    await page.route(jsonPattern,async route=>{
      if (failure==='slow') { await new Promise(r=>setTimeout(r,1200)); await route.continue(); }
      else if (failure==='404') await route.fulfill({status:404,body:'missing'});
      else if (failure==='json') await route.fulfill({status:200,contentType:'application/json',body:'{broken'});
      else {const data=JSON.parse(await fs.readFile(path.join(root,'content',manifest.papers.ace.url)));if(failure==='schema')data.schemaVersion=99;else data.id='other';await route.fulfill({contentType:'application/json',body:JSON.stringify(data)});}
    });
    await page.goto(route('ace'));
    if (failure==='slow') {
      assert(await page.locator('#reader-feedback').isVisible());
      assert.equal(await page.locator('#main-content').getAttribute('aria-busy'),'true');
      await page.click('#theme-button'); assert.equal(await page.locator('html').getAttribute('data-theme'),'dark');
      await state(page);
    } else {
      await state(page,'error'); assert(await page.locator('#retry-button').isVisible());
      assert(await page.locator('#fallback-pdf').isVisible());
      await page.unroute(jsonPattern);await page.click('#retry-button');await state(page);
      assert.equal(await page.locator('nav a').count(),(JSON.parse(await fs.readFile(path.join(root,'content',manifest.papers.ace.url)))).toc.length);
    }
    await page.close();console.log('PASS loading/recovery',failure);
  }
  for(const failure of ['manifest','module','stylesheet','slow-manifest']) {
    const page=await browser.newPage();
    const pattern=failure.includes('manifest')?'**/content/manifest.json':failure==='module'?'**/reader/reader.*.js*':'**/reader/reader.*.css';
    await page.route(pattern,async route=>{
      if(failure==='slow-manifest'){await new Promise(r=>setTimeout(r,1200));await route.continue();}
      else await route.fulfill({status:404,body:'missing'});
    });
    await page.goto(route('ace'));
    if(failure==='slow-manifest') {
      assert(await page.locator('#reader-feedback').isVisible());
      await page.click('#theme-button');assert.equal(await page.locator('html').getAttribute('data-theme'),'dark');
      await state(page);
    } else {
      await state(page,'error');assert(await page.locator('#fallback-pdf').isVisible());
      await page.unroute(pattern);await page.click('#retry-button');await state(page);
    }
    await page.close();console.log('PASS bootstrap recovery',failure);
  }
  {
    const page=await browser.newPage();
    const target=route('ace');
    await page.route(target,async route=>{
      const response=await route.fetch();
      const oldShell=(await response.text()).replace(/reader\.[a-f0-9]{16}\.css/g,'reader.removed.css');
      await route.fulfill({response,body:oldShell});
    });
    await page.goto(target);await state(page);
    assert((await page.locator('link[rel=stylesheet]').getAttribute('href')).includes(manifest.reader.css.replace('../','')));
    await page.close();console.log('PASS stale shell resolves current hashed reader');
  }
  // Failed images have local retry and prevent the print button from printing
  // an incomplete document. Then retry and print successfully without reload.
  const page = await browser.newPage();
  const assetPattern = '**/content/skillcat/assets/figure-01.*';
  await page.route(assetPattern,route=>route.fulfill({status:404,body:'missing'}));
  await page.goto(route('skillcat'));await state(page);
  await page.locator('figure img').first().scrollIntoViewIfNeeded();
  await page.waitForSelector('.image-error');
  await page.evaluate(()=>{window.print=()=>{window.__printed=true;};});
  await page.click('#print-button');
  await page.waitForFunction(()=>document.querySelector('#print-status').textContent.includes('再次点击打印'));
  assert(!(await page.evaluate(()=>window.__printed)));
  await page.unroute(assetPattern);await page.locator('.image-error button').click();
  await page.waitForFunction(()=>document.querySelector('figure img').naturalWidth>0);
  await page.click('#print-button');await page.waitForFunction(()=>window.__printed===true);
  await page.emulateMedia({media:'print'});
  await page.screenshot({path:path.join(output,'skillcat-print.png')});
  await page.pdf({path:path.join(output,'skillcat-print.pdf'),format:'A4',printBackground:true});
  await page.close();console.log('PASS image retry and print failure recovery');
  await require('./browser_notes.cjs')({browser,route,output});
  await fs.writeFile(path.join(output,'metrics.json'),JSON.stringify(metrics,null,2));
  console.log('Browser artifacts:',output);
}
main().catch(error=>{console.error(error);process.exitCode=1;}).finally(async()=>{await browser?.close();server?.close();});
