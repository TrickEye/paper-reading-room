import {localURL} from './loader.js';

// One in-memory Markdown draft per paper. Only panel width is persisted.
export function initNotes({paperId, manifestURL, resources, title, closeDirectory}) {
  const root = document.documentElement;
  const $ = id => document.getElementById(id);
  const narrow = () => matchMedia('(max-width:940px)').matches;
  const base = new URL('../', manifestURL);
  const prefix = `paper-reader:${base.pathname}:`;
  const widthKey = `${prefix}notes-width`;
  const panel = document.createElement('aside');
  panel.id = 'notes-panel'; panel.className = 'notes-panel'; panel.hidden = true;
  panel.setAttribute('aria-labelledby', 'notes-heading');
  panel.innerHTML = `<div id="notes-resize" class="notes-resize" role="separator" tabindex="0" aria-label="调整笔记宽度" aria-orientation="vertical" aria-controls="notes-panel"></div>
    <header class="notes-head"><div><span class="eyebrow">READING NOTES</span><h2 id="notes-heading">阅读笔记</h2><p id="notes-paper"></p></div><button id="notes-close" aria-label="关闭笔记">关闭</button></header>
    <div id="notes-remote" class="notes-remote" hidden><div class="notes-actions"><button id="notes-refresh" aria-describedby="notes-refresh-help">刷新远端</button><button id="notes-github" hidden>保存到 GitHub</button></div><p id="notes-remote-status" role="status" aria-live="polite"></p><p id="notes-refresh-help">刷新成功会用部署版覆盖当前草稿。</p></div>
    <div class="notes-mode" role="group" aria-label="笔记编辑模式"><button id="notes-edit" aria-pressed="true">编辑</button><button id="notes-source" aria-pressed="false">源码</button><span id="notes-engine" role="status"></span></div>
    <div id="notes-notice" class="notes-notice" hidden><p id="notes-notice-text" role="status"></p><button id="notes-retry">重试加载编辑器</button></div>
    <div id="notes-editor" class="notes-editor" hidden></div><textarea id="notes-fallback" class="notes-fallback" aria-label="Markdown 笔记" placeholder="写下阅读心得，或选中原文后摘录到这里…" spellcheck="false"></textarea>
    <footer class="notes-footer"><span id="notes-save-status" role="status" aria-live="polite">草稿：尚无修改</span><span>草稿仅在当前页面内，离开前请在 GitHub 提交。</span></footer>`;
  document.body.append(panel);
  $('notes-paper').textContent = title;
  const excerptButton = document.createElement('button');
  excerptButton.id = 'notes-excerpt'; excerptButton.className = 'notes-excerpt'; excerptButton.hidden = true;
  excerptButton.textContent = '摘录到笔记'; document.body.append(excerptButton);
  const fallback = $('notes-fallback'), host = $('notes-editor');
  let markdown = '', deployedMarkdown = '', dirty = false, composing = false;
  let editor = null, loading = null, selected = null, opened = false, mode = 'ir';
  let initializing = false, remoteLoading = false, remoteState = 'unknown';
  const status = text => { $('notes-save-status').textContent = '草稿：' + text; };
  function notice(text, retry = false) {
    $('notes-notice').hidden = false; $('notes-notice-text').textContent = text;
    $('notes-retry').hidden = !retry;
  }
  const normalize = value => value.trim() ? value : '';
  // Vditor appends a terminal newline; do not treat that alone as an edit.
  const comparable = value => normalize(value).replace(/\r\n/g, '\n').replace(/\n+$/, '');
  function read() { return composing ? markdown : normalize(editor ? editor.getValue() : fallback.value); }
  function changed(value = read()) {
    if (initializing || composing || remoteLoading) return;
    markdown = normalize(value);
    dirty = comparable(markdown) !== comparable(deployedMarkdown);
    status(dirty ? '有未提交修改，刷新或关闭页面可能丢失。' : '尚无修改');
  }
  function syncDraft() { changed(); }
  function replace(value) {
    markdown = value; fallback.value = value;
    if (editor) { initializing = true; editor.setValue(value, true); initializing = false; }
  }
  function access() {
    // Inert covers both Vditor contenteditables and its asynchronously created toolbar.
    host.inert = remoteLoading;
    fallback.readOnly = remoteLoading;
    host.setAttribute('aria-busy', String(remoteLoading));
    $('notes-edit').disabled = $('notes-source').disabled = remoteLoading || composing;
    $('notes-refresh').disabled = remoteLoading || composing;
    $('notes-github').disabled = remoteLoading || composing;
    excerptButton.disabled = remoteLoading;
  }
  async function loadRemote() {
    if (!resources.documents || remoteLoading || composing) return;
    syncDraft();
    remoteLoading = true; remoteState = 'unknown'; access();
    $('notes-remote-status').textContent = '部署版：正在加载…';
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 15000);
    try {
      const directory = localURL(resources.documents, manifestURL);
      const url = localURL(`${encodeURIComponent(paperId)}/notes.md`, directory);
      const response = await fetch(url, {cache: 'no-cache', signal: controller.signal});
      if (response.status === 404) {
        remoteState = 'missing';
        $('notes-remote-status').textContent = '部署版：尚未发布，已保留当前草稿。';
        return;
      }
      if (!response.ok) throw new Error(`请求失败（${response.status}）`);
      const value = await response.text();
      remoteState = 'exists';
      deployedMarkdown = value; replace(value); dirty = false; status('已载入部署版，尚无修改');
      $('notes-remote-status').textContent = '部署版：已载入，后续编辑仍需在 GitHub 提交。';
    } catch (error) {
      $('notes-remote-status').textContent = '部署版：加载失败，已保留当前草稿，可继续编辑并刷新重试。' + (error.name === 'AbortError' ? '请求超时。' : '');
    } finally {
      clearTimeout(timeout); remoteLoading = false; access();
    }
  }
  $('notes-remote').hidden = !resources.documents;
  $('notes-refresh').onclick = loadRemote;

  // Only public repository coordinates belong in the manifest; no credentials are used.
  const github = resources.github;
  if (github && [github.owner, github.repo, github.branch, github.directory].every(value => typeof value === 'string' && value)) {
    $('notes-remote').hidden = false; $('notes-refresh').hidden = !resources.documents;
    $('notes-refresh-help').hidden = !resources.documents;
    $('notes-github').hidden = false;
    const dialog = document.createElement('dialog');
    dialog.id = 'notes-handoff'; dialog.className = 'notes-handoff';
    dialog.setAttribute('aria-labelledby', 'notes-handoff-title');
    dialog.innerHTML = `<header><h2 id="notes-handoff-title">保存到 GitHub</h2><button id="notes-handoff-close" aria-label="关闭 GitHub 提交面板">关闭</button></header>
      <p id="notes-handoff-path"></p><p>这是打开面板时的笔记快照。请在 GitHub 检查内容并手动提交；完成 Pages 部署后再刷新远端。</p>
      <fieldset id="notes-handoff-choice" hidden><legend>部署版状态未知，请选择操作</legend><label><input type="radio" name="notes-target" value="new">创建新文件</label><label><input type="radio" name="notes-target" value="edit">编辑现有文件</label></fieldset>
      <p id="notes-handoff-help"></p><div class="notes-actions"><button id="notes-copy">复制全文</button><a id="notes-github-open" target="_blank" rel="noopener noreferrer" hidden>打开 GitHub</a></div>
      <p id="notes-copy-status" role="status" aria-live="polite"></p><label for="notes-handoff-source">笔记全文（可全选复制）</label><textarea id="notes-handoff-source" readonly spellcheck="false"></textarea>
      <p id="notes-handoff-alternative" hidden>如果新建页提示文件已存在：<a id="notes-github-edit" target="_blank" rel="noopener noreferrer">打开现有文件编辑页</a>，粘贴上方全文后提交。</p>
      <p id="notes-handoff-status" role="status" aria-live="polite"></p>`;
    document.body.append(dialog);
    const path = github.directory.replace(/\/$/, '') + `/${paperId}/notes.md`;
    $('notes-handoff-path').textContent = path;
    const repository = `https://github.com/${encodeURIComponent(github.owner)}/${encodeURIComponent(github.repo)}`;
    const editURL = `${repository}/edit/${encodeURIComponent(github.branch)}/${path.split('/').map(encodeURIComponent).join('/')}`;
    let snapshot = '', copyAttempt = 0;
    function choose(target) {
      const url = new URL(`${repository}/new/${encodeURIComponent(github.branch)}`);
      url.searchParams.set('filename', path);
      url.searchParams.set('value', snapshot);
      const prefill = target === 'new' && new TextEncoder().encode(url.href).length <= 6000;
      if (!prefill) url.searchParams.delete('value');
      $('notes-github-open').href = target === 'edit' ? editURL : url.href;
      $('notes-github-open').textContent = target === 'edit' ? '打开 GitHub 编辑页' : '打开 GitHub 新建页';
      $('notes-github-open').hidden = false;
      $('notes-handoff-alternative').hidden = target !== 'new';
      $('notes-github-edit').href = editURL;
      $('notes-handoff-help').textContent = target === 'edit'
        ? snapshot ? '先复制全文，再到 GitHub 编辑框中全选替换并提交。' : '当前笔记为空。请清空 GitHub 编辑框后提交空文件。'
        : prefill ? '链接将预填文件名和正文。如果 GitHub 未填入正文，请复制下方快照后粘贴。笔记正文会包含在链接中。'
        : '笔记超过链接预填长度，请先复制全文，再打开 GitHub 新建页粘贴并提交。';
    }
    $('notes-github').onclick = () => {
      if (remoteLoading || composing) return;
      syncDraft(); snapshot = read(); copyAttempt++;
      $('notes-handoff-source').value = snapshot;
      $('notes-copy-status').textContent = $('notes-handoff-status').textContent = '';
      $('notes-handoff-choice').hidden = remoteState !== 'unknown';
      dialog.querySelectorAll('input[name="notes-target"]').forEach(input => { input.checked = false; });
      if (remoteState === 'unknown') {
        $('notes-github-open').hidden = $('notes-handoff-alternative').hidden = true;
        $('notes-github-open').removeAttribute('href');
        $('notes-handoff-help').textContent = '尚未确认文件是否存在。请选择新建或编辑；也可以先复制笔记。';
      } else choose(remoteState === 'exists' ? 'edit' : 'new');
      dialog.showModal();
    };
    $('notes-handoff-choice').onchange = event => choose(event.target.value);
    $('notes-copy').onclick = async () => {
      const attempt = ++copyAttempt, value = snapshot;
      try {
        await navigator.clipboard.writeText(value);
        if (attempt === copyAttempt) $('notes-copy-status').textContent = value ? '已复制全文，请在 GitHub 粘贴并提交。' : '当前快照为空，请清空 GitHub 编辑框后提交。';
      } catch {
        if (attempt !== copyAttempt || !dialog.open) return;
        $('notes-copy-status').textContent = '自动复制失败，请在下方全选复制；空笔记请直接清空 GitHub 编辑框。';
        $('notes-handoff-source').focus(); $('notes-handoff-source').select();
      }
    };
    for (const id of ['notes-github-open', 'notes-github-edit']) $(id).onclick = () => {
      $('notes-handoff-status').textContent = '待在 GitHub 提交。提交并完成 Pages 部署后，再刷新远端；刷新会覆盖当前草稿。';
      $('notes-remote-status').textContent = '已打开 GitHub，待手动提交；部署完成后再刷新远端。';
    };
    $('notes-handoff-close').onclick = () => dialog.close();
    dialog.addEventListener('close', () => { copyAttempt++; $('notes-github').focus(); });
  }
  addEventListener('beforeunload', event => {
    syncDraft();
    if (dirty || composing) { event.preventDefault(); event.returnValue = ''; }
  });
  function theme() {
    if (editor) editor.setTheme(root.dataset.theme === 'dark' ? 'dark' : 'classic');
  }
  new MutationObserver(theme).observe(root, {attributes: true, attributeFilter: ['data-theme']});
  const assetLoads = new Map();
  function asset(path, type, id) {
    const url = localURL(path, localURL(resources.vendor, manifestURL)).href;
    if (assetLoads.has(url)) return assetLoads.get(url);
    const promise = new Promise((resolve, reject) => {
      const element = document.createElement(type === 'css' ? 'link' : 'script');
      if (id) element.id = id;
      if (type === 'css') { element.rel = 'stylesheet'; element.href = url; } else { element.src = url; element.async = false; }
      const timeout = setTimeout(() => finish(new Error('编辑器资源加载超时')), 15000);
      function finish(error) {
        clearTimeout(timeout); element.onload = element.onerror = null;
        if (error) { element.remove(); assetLoads.delete(url); reject(error); } else resolve();
      }
      element.onload = () => finish(); element.onerror = () => finish(new Error('编辑器资源加载失败'));
      document.head.append(element);
    });
    assetLoads.set(url, promise); return promise;
  }
  async function ensureEditor() {
    if (editor || loading) return loading;
    loading = (async () => {
      $('notes-engine').textContent = '加载编辑器…';
      try {
        await Promise.all([
          asset('dist/index.min.js', 'js'), asset('dist/index.css', 'css'),
          asset('dist/js/lute/lute.min.js', 'js', 'vditorLuteScript'),
          asset('dist/js/i18n/zh_CN.js', 'js', 'vditorI18nScriptzh_CN'),
          asset('dist/js/icons/ant.js', 'js', 'vditorIconScript'),
          asset('dist/js/katex/katex.min.js', 'js', 'vditorKatexScript'),
          asset('dist/js/katex/katex.min.css', 'css', 'vditorKatexStyle'),
        ]);
        await asset('dist/js/katex/mhchem.min.js', 'js', 'vditorKatexChemScript');
        // Start empty, then install the DOM filter before rendering user content.
        syncDraft(); host.hidden = false;
        initializing = true;
        await new Promise((resolve, reject) => {
          const timeout = setTimeout(() => reject(new Error('编辑器初始化超时')), 15000);
          const instance = new window.Vditor(host, {
            cdn: localURL(resources.vendor, manifestURL).href.replace(/\/$/, ''),
            cache: {enable: false}, mode, value: '', height: '100%', minHeight: 0,
            lang: 'zh_CN', i18n: window.VditorI18n, theme: root.dataset.theme === 'dark' ? 'dark' : 'classic',
            placeholder: '写下阅读心得，或选中原文后摘录到这里…',
            undoDelay: 100, typewriterMode: false, tab: '  ',
            toolbar: ['headings', 'bold', 'list', 'quote', 'undo', 'redo',
              {name: 'more', toolbar: ['italic', 'strike', 'ordered-list', 'check', 'link', 'table', 'code', 'inline-code',
                {name: 'notes-math', tip: '数学公式', icon: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M19 4H5l7 8-7 8h14v-2H9l6-6-6-6h10z"/></svg>', click: () => editor.insertMD('$$\nE = mc^2\n$$\n')}]}, 'edit-mode'],
            preview: {mode: 'editor', actions: [], hljs: {enable: false},
              markdown: {sanitize: true, codeBlockPreview: false, mathBlockPreview: true, toc: false},
              math: {engine: 'KaTeX'}, render: {media: {enable: false}}},
            hint: {emoji: {}, extend: []}, link: {isOpen: false}, image: {isPreview: false},
            input: value => changed(value),
            after: () => { clearTimeout(timeout); queueMicrotask(() => { editor = instance; resolve(); }); },
          });
        });
        // Lute's sanitizer permits iframe/image previews. Filter generated editor DOM
        // before it is attached, including paste and subsequent IR transformations.
        const lute = editor.vditor.lute;
        const safeHTML = html => {
          const template = document.createElement('template'); template.innerHTML = html;
          template.content.querySelectorAll('script,iframe,object,embed,base,link,meta,style,form,img,video,audio,source,svg').forEach(el => el.remove());
          for (const el of template.content.querySelectorAll('*')) {
            if (el.tagName === 'INPUT' && el.type !== 'checkbox') { el.remove(); continue; }
            for (const attr of [...el.attributes]) {
              if (/^on/i.test(attr.name) || ['srcdoc','style','id','src','srcset','background','poster','action','formaction'].includes(attr.name)) el.removeAttribute(attr.name);
              if (['href','xlink:href'].includes(attr.name)) {
                try { if (!['http:','https:','mailto:'].includes(new URL(attr.value, location.href).protocol)) el.removeAttribute(attr.name); }
                catch { el.removeAttribute(attr.name); }
              }
            }
          }
          return template.innerHTML;
        };
        for (const name of ['Md2VditorIRDOM','SpinVditorIRDOM','Md2VditorDOM','SpinVditorDOM','HTML2VditorDOM','HTML2VditorIRDOM','Md2HTML','VditorDOM2HTML','VditorIRDOM2HTML']) {
          if (typeof lute[name] === 'function') { const render = lute[name].bind(lute); lute[name] = (...args) => safeHTML(render(...args)); }
        }
        editor.setValue(markdown, true);
        editor.setPreviewMode('editor');
        for (const area of host.querySelectorAll('.vditor-ir,.vditor-sv')) {
          area.setAttribute('aria-label', area.classList.contains('vditor-sv') ? 'Markdown 笔记源码' : 'Markdown 笔记编辑区');
          area.setAttribute('aria-multiline', 'true');
          if (area.isContentEditable) area.setAttribute('role', 'textbox');
        }
        const focusEditor = document.activeElement === fallback;
        fallback.hidden = true; initializing = false;
        if (focusEditor && opened) editor.focus();
        $('notes-engine').textContent = 'Markdown';
        $('notes-notice').hidden = true;
        host.dataset.editorReady = 'true';
      } catch {
        if (editor) { try { editor.destroy(); } catch {} editor = null; }
        initializing = false; host.hidden = true; fallback.hidden = false; fallback.value = markdown;
        $('notes-engine').textContent = '纯文本模式';
        notice('编辑器加载失败，可继续编辑 Markdown；草稿仅保留在当前页面。', true);
      } finally { loading = null; }
    })();
    return loading;
  }
  $('notes-retry').onclick = ensureEditor;
  fallback.addEventListener('input', () => changed());
  panel.addEventListener('input', event => {
    if (event.target !== fallback) changed();
  });
  panel.addEventListener('compositionstart', () => { composing = true; access(); });
  panel.addEventListener('compositionend', () => { composing = false; access(); queueMicrotask(() => changed()); });
  function setMode(next) {
    if (composing) return;
    syncDraft(); mode = next;
    if (editor) {
      const control = host.querySelector(`[data-mode="${next}"]`);
      control.dispatchEvent(new Event(navigator.userAgent.includes('iPhone') ? 'touchstart' : 'click', {bubbles: true, cancelable: true}));
      editor.setPreviewMode('editor');
    }
    $('notes-edit').setAttribute('aria-pressed', String(next === 'ir'));
    $('notes-source').setAttribute('aria-pressed', String(next === 'sv'));
  }
  $('notes-edit').onclick = () => setMode('ir'); $('notes-source').onclick = () => setMode('sv');
  let preferredWidth = 400;
  let viewportHeight = innerHeight;
  try { preferredWidth = Number(localStorage.getItem(widthKey)) || 400; } catch {}
  function layout() {
    const sidebar = innerWidth >= 1440 ? parseFloat(getComputedStyle(root).getPropertyValue('--sidebar')) : 0;
    const max = Math.max(320, Math.min(640, innerWidth - sidebar - 560));
    const width = Math.max(320, Math.min(max, preferredWidth));
    root.style.setProperty('--notes-width', `${width}px`);
    $('notes-resize').setAttribute('aria-valuemin', '320'); $('notes-resize').setAttribute('aria-valuemax', String(max));
    $('notes-resize').setAttribute('aria-valuenow', String(Math.round(width)));
    const viewport = window.visualViewport;
    const height = viewport?.height || innerHeight;
    const focused = panel.contains(document.activeElement);
    if (!focused) viewportHeight = innerHeight;
    const keyboard = narrow() && height < viewportHeight * .8 && focused;
    panel.classList.toggle('notes-keyboard', keyboard);
    root.style.setProperty('--notes-height', `${height * (keyboard ? .7 : .5)}px`);
    panel.style.setProperty('--notes-bottom', `${Math.max(0, innerHeight - height - (viewport?.offsetTop || 0))}px`);
  }
  function open(value, focus = true) {
    const header = parseFloat(getComputedStyle(root).getPropertyValue('--header'));
    const visibleUnit = [...document.querySelectorAll('#paper [data-unit]')].find(el => el.getBoundingClientRect().bottom > header + 8);
    const offset = visibleUnit?.getBoundingClientRect().top;
    if (value && !opened) closeDirectory();
    opened = value; panel.hidden = !value; root.classList.toggle('notes-open', value);
    $('notes-button').setAttribute('aria-expanded', String(value));
    layout();
    if (visibleUnit) {
      window.scrollBy({top: visibleUnit.getBoundingClientRect().top - offset, behavior: 'instant'});
    }
    excerptButton.hidden = true;
    if (value) { layout(); ensureEditor(); if (focus) (editor ? editor : fallback).focus(); }
    else { syncDraft(); if (panel.contains(document.activeElement)) document.activeElement.blur(); if (focus) $('notes-button').focus(); }
  }
  $('notes-button').onclick = () => open(!opened);
  $('notes-close').onclick = () => open(false);
  document.addEventListener('reader:open-directory', () => { if (opened && innerWidth <= 1439) open(false, false); });
  panel.addEventListener('keydown', event => {
    if (event.key !== 'Escape' || event.defaultPrevented || composing) return;
    const popups = [...host.querySelectorAll('.vditor-hint,.vditor-panel--arrow,.vditor-wysiwyg__popover')].filter(el => el.getClientRects().length);
    event.preventDefault(); event.stopPropagation();
    if (popups.length) { popups.forEach(el => { el.style.display = 'none'; }); editor?.focus(); }
    else open(false);
  }, true);
  let resizing = false;
  $('notes-resize').addEventListener('pointerdown', event => { resizing = true; event.currentTarget.setPointerCapture(event.pointerId); event.preventDefault(); });
  $('notes-resize').addEventListener('pointermove', event => { if (resizing) { preferredWidth = innerWidth - event.clientX; layout(); } });
  function saveWidth() {
    preferredWidth = Number($('notes-resize').getAttribute('aria-valuenow'));
    try { localStorage.setItem(widthKey, String(preferredWidth)); } catch {}
  }
  $('notes-resize').addEventListener('pointerup', () => { resizing = false; saveWidth(); });
  $('notes-resize').addEventListener('pointercancel', () => { resizing = false; });
  $('notes-resize').addEventListener('keydown', event => {
    if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
    event.preventDefault(); preferredWidth = event.key === 'Home' ? 320 : event.key === 'End' ? 640 : Number($('notes-resize').getAttribute('aria-valuenow')) + (event.key === 'ArrowLeft' ? 20 : -20);
    layout(); saveWidth();
  });
  addEventListener('resize', layout); window.visualViewport?.addEventListener('resize', layout); window.visualViewport?.addEventListener('scroll', layout);
  panel.addEventListener('focusin', layout);
  panel.addEventListener('focusout', () => requestAnimationFrame(layout));
  addEventListener('pagehide', syncDraft); document.addEventListener('visibilitychange', () => { if (document.hidden) syncDraft(); });
  layout();
  const escapeMD = text => text.replace(/([\\`*_{}\[\]()#+\-.!|<>~$])/g, '\\$1');
  function captureSelection() {
    const selection = getSelection(), article = $('paper');
    if (!selection?.rangeCount || selection.isCollapsed || !article) { excerptButton.hidden = true; return; }
    const range = selection.getRangeAt(0);
    if (!article.contains(range.startContainer) || !article.contains(range.endContainer)) { excerptButton.hidden = true; return; }
    const text = selection.toString().trim();
    if (!text) { excerptButton.hidden = true; return; }
    let node = range.startContainer.nodeType === Node.ELEMENT_NODE ? range.startContainer : range.startContainer.parentElement;
    const section = node.closest('section,[id="abstract1"],.source-footer');
    let anchor = node.closest('[id]');
    while (anchor && (anchor.id.startsWith('search-') || anchor.id === 'paper')) anchor = anchor.parentElement?.closest('[id]');
    const target = anchor || section || article;
    const heading = section?.querySelector('h2,h3,h4');
    const label = heading?.querySelector(root.dataset.lang === 'en' ? '.en' : '.zh')?.textContent || heading?.textContent || title;
    selected = {text, id: target.id, label: label.replace(/\s+/g, ' ').trim()};
    const rect = range.getBoundingClientRect();
    excerptButton.hidden = false;
    excerptButton.style.left = `${Math.max(8, Math.min(innerWidth - 132, rect.left))}px`;
    excerptButton.style.top = `${Math.max(parseFloat(getComputedStyle(root).getPropertyValue('--header')) + 8, Math.min(innerHeight - 52, rect.bottom + 8))}px`;
  }
  document.addEventListener('selectionchange', () => requestAnimationFrame(captureSelection));
  excerptButton.addEventListener('pointerdown', event => event.preventDefault());
  excerptButton.onclick = async () => {
    if (!selected || remoteLoading) return;
    const snapshot = selected; selected = null; open(true, false);
    await ensureEditor();
    if (remoteLoading) return;
    const link = `${paperId}.html#${encodeURIComponent(snapshot.id)}`;
    const md = '\n\n' + snapshot.text.split(/\r?\n/).map(line => '> ' + escapeMD(line)).join('\n') + `\n\n[${escapeMD(snapshot.label)} · 返回原文](${link})\n\n`;
    if (editor) {
      editor.focus();
      const area = host.querySelector(editor.getCurrentMode() === 'sv' ? '.vditor-sv' : '.vditor-ir');
      if (area instanceof HTMLTextAreaElement) area.selectionStart = area.selectionEnd = area.value.length;
      else { const range = document.createRange(); range.selectNodeContents(area); range.collapse(false); getSelection().removeAllRanges(); getSelection().addRange(range); }
      editor.insertMD(md);
      area.scrollTop = area.scrollHeight;
    } else { fallback.focus(); fallback.setSelectionRange(fallback.value.length, fallback.value.length); document.execCommand('insertText', false, md); fallback.scrollTop = fallback.scrollHeight; }
    syncDraft(); excerptButton.hidden = true;
  };
  panel.addEventListener('click', event => {
    const link = event.target.closest('a[href]');
    const irLink = event.target.closest('.vditor-ir__link')?.closest('[data-type=a]');
    if (!link && !irLink) return;
    event.preventDefault();
    let url;
    try {
      // Note citations always resolve against the real paper shell, including in preview.
      url = new URL(link ? link.getAttribute('href') : irLink.querySelector('.vditor-ir__marker--link')?.textContent, new URL(`papers/${paperId}.html`, base));
    } catch { return; }
    if (!['http:', 'https:', 'mailto:'].includes(url.protocol)) return;
    const paperURL = new URL(`papers/${paperId}.html`, base);
    if (url.origin === paperURL.origin && url.pathname === paperURL.pathname && url.hash) {
      let id;
      try { id = decodeURIComponent(url.hash.slice(1)); } catch { status('原文链接格式无效'); return; }
      const target = document.getElementById(id);
      if (!target || !$('paper')?.contains(target)) { status('原文位置已变更，未找到该段落'); return; }
      if (narrow()) open(false, false);
      location.hash = url.hash; target.scrollIntoView({behavior: 'instant'});
      target.classList.add('notes-target'); setTimeout(() => target.classList.remove('notes-target'), 1800);
    } else window.open(url.href, '_blank', 'noopener,noreferrer');
  }, true);
  loadRemote();
}
