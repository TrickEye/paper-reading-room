import {localURL, requestJSON, getPublication} from './loader.js';
// PaperDocument v1. Only repository-built, validated rich HTML is accepted.
const root = document.documentElement;
const $ = id => document.getElementById(id);
const preview = location.pathname.endsWith('/reader-preview.html');
const paperId = preview ? new URLSearchParams(location.search).get('paper') || 'ace' : document.body.dataset.paper;
root.dataset.paper = paperId;
let storageKey = (paperId === 'skillcat' ? 'skillcat' : 'ace') + '-reader-';
const get = key => { try { return localStorage.getItem(storageKey + key); } catch { return null; } };
const save = (key, value) => { try { localStorage.setItem(storageKey + key, value); } catch {} };
let ready = false;
let search = () => {};
let update = () => {};
let font = Number(get('font')) || 18;
const mode = $('reading-mode');
function restoreMode(fallback) {
  mode.value = ['zh', 'en', 'dual'].includes(get('mode')) ? get('mode') : fallback;
  root.dataset.lang = mode.value;
}
restoreMode(paperId === 'ace' ? 'zh' : 'dual');
function applyFont() {
  font = Math.max(16, Math.min(24, font));
  root.style.setProperty('--body-size', font + 'px');
  $('font-down').disabled = font <= 16;
  $('font-up').disabled = font >= 24;
  save('font', String(font));
  update();
}
$('font-down').onclick = () => { font--; applyFont(); };
$('font-up').onclick = () => { font++; applyFont(); };
applyFont();
function setTheme(theme) {
  root.dataset.theme = theme;
  $('theme-button').textContent = theme === 'dark' ? '浅色' : '深色';
  $('theme-button').setAttribute('aria-pressed', String(theme === 'dark'));
  save('theme', theme);
}
setTheme(get('theme') || (matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'));
$('theme-button').onclick = () => setTheme(root.dataset.theme === 'dark' ? 'light' : 'dark');
mode.onchange = () => { root.dataset.lang = mode.value; save('mode', mode.value); search(); update(); };

const mobile = () => matchMedia('(max-width:940px)').matches || (root.classList.contains('notes-open') && matchMedia('(max-width:1439px)').matches);
let lastFocus = null;
function menu(open) {
  if (open) document.dispatchEvent(new Event('reader:open-directory'));
  $('sidebar').classList.toggle('open', open);
  $('menu-button').setAttribute('aria-expanded', String(open));
  $('menu-button').setAttribute('aria-label', open ? '关闭目录' : '打开目录');
  $('scrim').hidden = !open;
  if (open) {
    lastFocus = document.activeElement;
    ($('search-input').disabled ? $('sidebar').querySelector('a') || $('menu-button') : $('search-input')).focus();
  } else if (lastFocus && mobile()) { lastFocus.focus(); lastFocus = null; }
}
$('menu-button').onclick = () => menu(!$('sidebar').classList.contains('open'));
$('scrim').onclick = () => menu(false);
$('sidebar').addEventListener('keydown', event => {
  if (event.key !== 'Tab' || !mobile() || !$('sidebar').classList.contains('open')) return;
  const items = [...$('sidebar').querySelectorAll('input,a,button')].filter(el => !el.disabled && el.getClientRects().length);
  if (!items.length) { event.preventDefault(); return; }
  const first = items[0], last = items.at(-1);
  if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
  else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
});
addEventListener('keydown', event => {
  if (event.key !== 'Escape') return;
  if ($('sidebar').classList.contains('open')) menu(false);
  else if (document.activeElement === $('search-input')) { $('search-input').value = ''; search(); }
});
addEventListener('resize', () => { if (!mobile()) menu(false); update(); });

function attrs(element, attributes, base) {
  for (const [key, value] of Object.entries(attributes)) {
    if (/^on/i.test(key) || ['srcdoc', 'action', 'formaction'].includes(key)) throw new Error('内容属性无效');
    let actual = value;
    if (['href', 'src'].includes(key) && value && !value.startsWith('#')) {
      const url = new URL(value, base);
      if (!['https:', 'http:', 'mailto:'].includes(url.protocol)) throw new Error('内容链接无效');
      actual = url.href;
    }
    element.setAttribute(key, actual ?? '');
  }
}
function richHTML(parent, source, base) {
  if (typeof source !== 'string') throw new Error('富文本格式无效');
  // Parse in the actual element context: table rows and MathML lose structure
  // when parsed as children of an unrelated HTML template.
  const staging = parent.cloneNode(false);
  staging.innerHTML = source;
  // Build-time validation is authoritative; reject active content again before
  // attaching a fragment. Do not silently drop invalid nodes or translations.
  if (staging.querySelector('script,iframe,object,embed,base,link,style,form,input')) throw new Error('正文包含不支持的元素');
  for (const el of staging.querySelectorAll('*')) {
    attrs(el, Object.fromEntries([...el.attributes].map(a => [a.name, a.value])), base);
  }
  parent.append(...staging.childNodes);
}
function renderDocument(doc, url) {
  if (doc.schemaVersion !== 1 || doc.id !== paperId || !doc.meta || !Array.isArray(doc.blocks) || !doc.blocks.length || !Array.isArray(doc.toc) || !Array.isArray(doc.assets)) throw new Error('论文数据格式或版本不受支持');
  const assets = new Map(doc.assets.map(asset => [asset.id, asset]));
  if (assets.size !== doc.assets.length) throw new Error('图片标识重复');
  function render(block) {
    if (block.type === 'text') {
      if (typeof block.text !== 'string') throw new Error('文本格式无效');
      return document.createTextNode(block.text);
    }
    if (!/^[a-z][a-z0-9-]*$/.test(block.tag) || ['script', 'iframe', 'object', 'embed', 'base', 'link', 'style', 'form', 'input'].includes(block.tag)) throw new Error('正文节点无效');
    const element = block.tag === 'math' ? document.createElementNS('http://www.w3.org/1998/Math/MathML', 'math') : document.createElement(block.tag);
    attrs(element, block.attrs, url);
    switch (block.type) {
      case 'container':
        for (const child of block.children) element.append(render(child));
        break;
      case 'bilingual':
        if (!block.zh || !block.en || block.order.filter(x => x === 'zh').length !== 1 || block.order.filter(x => x === 'en').length !== 1) throw new Error('双语单元不完整');
        for (const item of block.order) element.append(typeof item === 'string' ? render({type: 'rich', ...block[item]}) : document.createTextNode(item.text));
        break;
      case 'rich': richHTML(element, block.html, url); break;
      case 'image': {
        const asset = assets.get(block.assetId);
        if (element.tagName !== 'IMG' || !asset || !(asset.width > 0 && asset.height > 0)) throw new Error('图片资源无效');
        element.src = localURL(asset.url, url).href;
        element.loading = 'lazy';
        element.decoding = 'async';
        break;
      }
      default: throw new Error('正文单元类型不受支持');
    }
    return element;
  }
  const fragment = document.createDocumentFragment();
  for (const block of doc.blocks) fragment.append(render(block));
  if (fragment.querySelectorAll('article#paper').length !== 1) throw new Error('缺少完整论文正文');
  const ids = new Set();
  for (const element of fragment.querySelectorAll('[id]')) {
    if (ids.has(element.id) || document.getElementById(element.id)) throw new Error('正文锚点重复');
    ids.add(element.id);
  }
  for (const entry of doc.toc) if (!ids.has(entry.id)) throw new Error('目录目标不存在');
  return fragment;
}

function imageState(img) {
  let notice;
  const success = () => { notice?.remove(); notice = null; img.removeAttribute('data-load-error'); update(); };
  const failure = () => {
    img.dataset.loadError = 'true';
    if (notice) return;
    notice = document.createElement('div');
    notice.className = 'image-error';
    notice.setAttribute('role', 'status');
    notice.append(document.createTextNode('图片加载失败。'));
    const retry = document.createElement('button');
    retry.type = 'button'; retry.textContent = '重新加载图片';
    retry.onclick = () => { const src = img.src; success(); img.removeAttribute('src'); img.src = src; };
    notice.append(retry);
    img.closest('figure')?.append(notice);
  };
  img.addEventListener('load', success);
  img.addEventListener('error', failure);
  if (img.complete && img.currentSrc) img.naturalWidth ? success() : failure();
}

function initArticle() {
  const links = [...document.querySelectorAll('nav a')];
  const sections = links.map(a => document.getElementById(decodeURIComponent(a.hash.slice(1)))).filter(Boolean).sort((a, b) => a.compareDocumentPosition(b) & Node.DOCUMENT_POSITION_FOLLOWING ? -1 : 1);
  links.forEach(a => a.addEventListener('click', () => { if (mobile()) menu(false); }));
  let pending = false;
  update = () => {
    pending = false;
    const full = root.scrollHeight - innerHeight;
    const percent = full > 0 ? Math.min(100, Math.max(0, scrollY / full * 100)) : 0;
    $('progress-bar').style.width = percent + '%';
    $('progress-text').textContent = Math.round(percent) + '%';
    $('to-top').hidden = scrollY < 700;
    let current = sections[0];
    for (const section of sections) if (section.getBoundingClientRect().top < innerHeight * .35) current = section;
    links.forEach(a => a.toggleAttribute('aria-current', a.hash === '#' + current?.id));
  };
  addEventListener('scroll', () => { if (!pending) { pending = true; requestAnimationFrame(update); } }, {passive: true});
  new ResizeObserver(() => { if (!pending) { pending = true; requestAnimationFrame(update); } }).observe($('paper'));
  $('to-top').onclick = () => window.scrollTo({top: 0, behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth'});

  const dialog = $('image-dialog');
  let trigger = null;
  $('paper').addEventListener('click', event => {
    const button = event.target.closest('.figure-zoom');
    if (!button) return;
    trigger = button;
    const image = button.querySelector('img');
    $('dialog-image').src = image.src;
    $('dialog-image').alt = image.alt;
    $('dialog-caption').textContent = button.closest('figure').querySelector('figcaption')?.innerText || image.alt;
    dialog.showModal(); $('image-close').focus();
  });
  $('image-close').onclick = () => dialog.close();
  dialog.addEventListener('click', event => { if (event.target === dialog) dialog.close(); });
  dialog.addEventListener('close', () => trigger?.focus());
  $('paper').querySelectorAll('img').forEach(imageState);
  imageState($('dialog-image'));

  const input = $('search-input'), results = $('search-results'), nav = document.querySelector('nav');
  let timer, highlighted;
  const candidates = [...$('paper').querySelectorAll('[data-unit][data-searchable],p[data-searchable],h1,h2,h3,h4,figcaption,li.ltx_bibitem,td[data-searchable],th[data-searchable],pre')];
  search = () => {
    const query = input.value.trim().toLocaleLowerCase();
    results.replaceChildren(); results.hidden = !query; nav.hidden = !!query;
    $('search-status').textContent = '';
    if (!query) return;
    let count = 0;
    for (const [index, el] of candidates.entries()) {
      if (!el.getClientRects().length) continue;
      const clone = el.cloneNode(true);
      if (root.dataset.lang === 'zh') clone.querySelectorAll('.en').forEach(n => n.remove());
      if (root.dataset.lang === 'en') clone.querySelectorAll('.zh').forEach(n => n.remove());
      const text = clone.textContent.replace(/\s+/g, ' ').trim(), at = text.toLocaleLowerCase().indexOf(query);
      if (at < 0) continue;
      count++;
      if (count > 60) continue;
      if (!el.id) el.id = 'search-' + index;
      const link = document.createElement('a'); link.href = '#' + el.id;
      const small = document.createElement('small'); small.textContent = '匹配 ' + count;
      const excerpt = document.createElement('span'); excerpt.textContent = (at > 35 ? '…' : '') + text.slice(Math.max(0, at - 35), at + 90) + (at + 90 < text.length ? '…' : '');
      link.append(small, excerpt);
      link.onclick = () => {
        highlighted?.classList.remove('search-target'); el.classList.add('search-target'); highlighted = el;
        if (mobile()) menu(false);
        setTimeout(() => el.classList.remove('search-target'), 5000);
      };
      results.append(link);
    }
    $('search-status').textContent = count ? (count > 60 ? `找到 ${count} 处，显示前 60 处` : `找到 ${count} 处匹配`) : '未找到匹配，请尝试其他关键词。';
  };
  input.addEventListener('input', () => { clearTimeout(timer); timer = setTimeout(search, 180); });
  function hashTarget() {
    let id;
    try { id = decodeURIComponent(location.hash.slice(1)); } catch { return; }
    if (id) document.getElementById(id)?.scrollIntoView({behavior: 'instant'});
    update();
  }
  addEventListener('hashchange', hashTarget);
  requestAnimationFrame(() => requestAnimationFrame(hashTarget));
  update();
}

async function printPaper() {
  if (!ready) return;
  const button = $('print-button'), status = $('print-status');
  button.disabled = true; status.hidden = false; status.textContent = '正在准备打印图片…';
  try {
    await Promise.all([...$('paper').querySelectorAll('img')].map(async image => {
      image.loading = 'eager';
      let timeout;
      try {
        await Promise.race([image.decode(), new Promise((_, reject) => { timeout = setTimeout(() => reject(new Error('图片加载超时')), 20000); })]);
      } finally { clearTimeout(timeout); }
    }));
    status.hidden = true;
    window.print();
  } catch {
    status.textContent = '打印图片尚未加载完成，请重试失败图片后再次点击打印。';
  } finally { button.disabled = false; }
}
$('print-button').onclick = printPaper;
addEventListener('beforeprint', () => $('paper')?.querySelectorAll('img').forEach(img => { img.loading = 'eager'; }));

let loading = false;
async function load(refresh = false) {
  if (loading || ready) return;
  loading = true;
  $('retry-button').hidden = true;
  $('load-message').textContent = '正在加载论文内容…';
  $('main-content').setAttribute('aria-busy', 'true');
  try {
    const {url: manifestURL, manifest} = await getPublication(refresh);
    if (manifest.schemaVersion !== 1 || !Object.hasOwn(manifest.papers || {}, paperId)) throw new Error('未找到这篇论文');
    const entry = manifest.papers[paperId];
    storageKey = entry.storageKey; restoreMode(entry.defaultMode);
    document.title = entry.title;
    document.querySelector('.brand-name').firstChild.textContent = entry.brand;
    const pdf = localURL(entry.pdf, manifestURL).href;
    document.querySelector('.pdf-link').href = pdf; $('fallback-pdf').href = pdf;
    if (preview && !$('paper-selector')) {
      const select = document.createElement('select'); select.id = 'paper-selector'; select.setAttribute('aria-label', '选择预览论文');
      for (const [id, item] of Object.entries(manifest.papers)) select.add(new Option(item.brand, id));
      select.value = paperId; select.onchange = () => { location.href = '?paper=' + encodeURIComponent(select.value); };
      document.querySelector('.sidebar-head').append(select);
    }
    const url = localURL(entry.url, manifestURL);
    const doc = await requestJSON(url);
    const fragment = renderDocument(doc, url);
    const nav = document.querySelector('nav');
    for (const item of doc.toc) {
      const link = document.createElement('a'); link.href = '#' + item.id; link.className = item.level === 2 ? 'nav-main' : 'nav-sub'; link.textContent = item.label; nav.append(link);
    }
    $('paper-mount').replaceChildren(fragment);
    $('reader-feedback').hidden = true;
    $('search-input').disabled = false; $('print-button').disabled = false;
    ready = true;
    document.body.dataset.readerState = 'ready';
    initArticle();
    performance.mark('paper-ready');
  } catch (error) {
    $('load-message').textContent = '论文内容加载失败。' + (error.name === 'AbortError' ? '请求超时，请重试。' : error instanceof SyntaxError ? '数据暂时无法读取，请重试。' : error.message);
    $('retry-button').hidden = false;
    document.body.dataset.readerState = 'error';
  } finally { loading = false; $('main-content').setAttribute('aria-busy', 'false'); }
}
$('retry-button').onclick = () => load(true);
load();

// Keep the notes controller small; the editor itself is loaded on first use.
getPublication().then(async ({url, manifest}) => {
  if (!manifest.notes || !$('notes-button')) return;
  const {initNotes} = await import(localURL(manifest.notes.js, url).href);
  initNotes({paperId, manifestURL: url, resources: manifest.notes,
    title: manifest.papers[paperId].brand, closeDirectory: () => menu(false)});
}).catch(() => {
  if ($('notes-button')) { $('notes-button').disabled = true; $('notes-button').title = '笔记模块加载失败，请刷新重试'; }
});
