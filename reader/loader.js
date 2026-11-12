// Stable entry point: a cached shell can always resolve the current hashed
// reader through the revalidated manifest, even after old versions are removed.
const $ = id => document.getElementById(id);
const root = document.documentElement;
const preview = location.pathname.endsWith('/reader-preview.html');
const paperId = preview ? new URLSearchParams(location.search).get('paper') || 'ace' : document.body.dataset.paper;
root.dataset.paper = paperId;
const key = (paperId === 'skillcat' ? 'skillcat' : 'ace') + '-reader-';
const get = name => { try { return localStorage.getItem(key + name); } catch { return null; } };
const save = (name, value) => { try { localStorage.setItem(key + name, value); } catch {} };
// Restore and operate the small shell controls while the manifest is pending.
function theme(value) {
  root.dataset.theme = value;
  $('theme-button').setAttribute('aria-checked', String(value === 'dark'));
  $('theme-button').title = value === 'dark' ? '切换到浅色模式' : '切换到深色模式';
}
function font(value) {
  const size = Math.max(16, Math.min(24, value || 18));
  root.style.setProperty('--body-size', size + 'px');
  $('font-down').disabled = size <= 16; $('font-up').disabled = size >= 24;
  return size;
}
let size = font(Number(get('font')));
$('font-down').onclick = () => { size = font(size - 1); save('font', String(size)); };
$('font-up').onclick = () => { size = font(size + 1); save('font', String(size)); };
const modeGroup = $('reading-mode');
function setMode(value) {
  if (!['zh', 'dual', 'en'].includes(value)) return;
  root.dataset.lang = value;
  for (const button of modeGroup.querySelectorAll('[data-mode]')) {
    const selected = button.dataset.mode === value;
    button.setAttribute('aria-checked', String(selected)); button.tabIndex = selected ? 0 : -1;
  }
  save('mode', value);
}
const storedMode = get('mode');
setMode(['zh','en','dual'].includes(storedMode) ? storedMode : paperId === 'ace' ? 'zh' : 'dual');
modeGroup.onclick = event => { const button = event.target.closest('[data-mode]'); if (button) setMode(button.dataset.mode); };
modeGroup.onkeydown = event => {
  if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
  const buttons = [...modeGroup.querySelectorAll('[data-mode]')];
  const current = buttons.findIndex(button => button.getAttribute('aria-checked') === 'true');
  const next = event.key === 'Home' ? 0 : event.key === 'End' ? buttons.length - 1 : (current + (event.key === 'ArrowLeft' ? -1 : 1) + buttons.length) % buttons.length;
  event.preventDefault(); setMode(buttons[next].dataset.mode); buttons[next].focus();
};
theme(get('theme') || (matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'));
$('theme-button').onclick = () => { theme(root.dataset.theme === 'dark' ? 'light' : 'dark'); save('theme', root.dataset.theme); };

export function localURL(value, base) {
  const url = new URL(value, base);
  if (url.origin !== location.origin || !['http:', 'https:'].includes(url.protocol)) throw new Error('资源地址无效');
  return url;
}
export async function requestJSON(url) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 30000);
  try {
    const response = await fetch(url, {signal: controller.signal, cache: url.pathname.endsWith('/manifest.json') ? 'no-cache' : 'default'});
    if (!response.ok) throw new Error(`资源请求失败（${response.status}）`);
    return await response.json();
  } finally { clearTimeout(timeout); }
}
let publication;
export function getPublication(refresh = false) {
  if (!publication || refresh) publication = (async () => {
    const url = localURL(document.body.dataset.manifest, location.href);
    const manifest = await requestJSON(url);
    if (manifest.schemaVersion !== 1 || !manifest.reader || !manifest.papers) throw new Error('资源清单版本不受支持');
    return {url, manifest};
  })();
  return publication;
}
function style(url) {
  const previous = document.querySelector('link[rel=stylesheet]');
  // Chromium can retain an empty CSSStyleSheet even for an HTTP 404.
  const usable = link => Boolean(link.sheet && link.sheet.cssRules.length);
  if (previous.href === url.href && usable(previous)) return Promise.resolve();
  // Reusing the href of an already failed link need not start a new load.
  // A fresh link also ensures error handlers exist before the request starts.
  const link = document.createElement('link');
  link.rel = 'stylesheet';
  return new Promise((resolve, reject) => {
    let timeout;
    const finish = error => {
      clearTimeout(timeout); link.onload = link.onerror = null;
      if (error) { link.remove(); reject(error); }
      else { previous.remove(); resolve(); }
    };
    link.onload = () => finish(usable(link) ? undefined : new Error('阅读器样式无效'));
    link.onerror = () => finish(new Error('阅读器样式加载失败'));
    timeout = setTimeout(() => finish(new Error('阅读器样式加载超时')), 30000);
    link.href = url.href;
    document.head.append(link);
  });
}
let starting = false, attempt = 0;
async function boot(refresh = false) {
  if (starting) return;
  starting = true; attempt++;
  $('retry-button').hidden = true;
  $('load-message').textContent = '正在加载论文内容…';
  $('main-content').setAttribute('aria-busy', 'true');
  try {
    const {url, manifest} = await getPublication(refresh);
    await style(localURL(manifest.reader.css, url));
    const entry = localURL(manifest.reader.js, url);
    if (attempt > 1) entry.searchParams.set('retry', String(attempt));
    await import(entry.href);
  } catch (error) {
    $('load-message').textContent = '阅读器加载失败，请重试。' + (error.name === 'AbortError' ? '请求超时。' : error instanceof SyntaxError ? '清单暂时无法读取。' : error.message);
    $('retry-button').hidden = false;
    $('main-content').setAttribute('aria-busy', 'false');
    document.body.dataset.readerState = 'error';
  } finally { starting = false; }
}
$('retry-button').onclick = () => boot(true);
boot();
