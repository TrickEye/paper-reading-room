"""PaperDocument v1: source adapters, validation and deterministic publication.

URLs inside rich HTML and block attributes are relative to the paper JSON.
The three existing builders keep their editorial sources and emit article trees.
"""
from pathlib import Path
import base64
import hashlib
import html
import json
import posixpath
import re
from urllib.parse import unquote, urlsplit

from builders.html_tree import Node, TreeParser, serialize, clean_text, VOID

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / 'public'
CONTENT = PUBLIC / 'content'
KINDS = {'article': 'document', 'section': 'section', 'footer': 'source',
         'ul': 'list', 'ol': 'list', 'li': 'reference', 'figure': 'figure',
         'table': 'table', 'math': 'math', 'pre': 'code', 'p': 'paragraph',
         'h1': 'heading', 'h2': 'heading', 'h3': 'heading', 'h4': 'heading',
         'h5': 'heading', 'h6': 'heading', 'figcaption': 'caption'}
CONTAINERS = {'article', 'section', 'footer', 'div', 'aside', 'ul', 'ol', 'figure', 'button'}
FORBIDDEN = {'script', 'iframe', 'object', 'embed', 'base', 'link', 'style', 'form', 'input'}
STYLE_PROPERTIES = {'list-style-type', 'padding-left', 'padding-right', 'width', 'float',
                    '--ltx-bg-color', '--ltx-fg-color'}


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, separators=(',', ':')) + '\n', encoding='utf-8')


def validate_html(source):
    tree = TreeParser(source).root
    for node in tree.descendants():
        if node.tag in FORBIDDEN:
            raise ValueError(f'Forbidden rich HTML tag: {node.tag}')
        for key, value in node.attrs:
            if key.startswith('on') or key in {'srcdoc', 'formaction', 'action'}:
                raise ValueError(f'Forbidden HTML attribute: {key}')
            if key in {'href', 'src', 'data', 'xlink:href'}:
                compact = re.sub(r'[\x00-\x20\x7f]', '', html.unescape(value or ''))
                url = urlsplit(compact)
                if url.scheme.lower() not in {'', 'https', 'http', 'mailto'} or url.netloc and not url.scheme:
                    raise ValueError(f'Forbidden resource URL: {key}')
                if not url.scheme and unquote(url.path).startswith('/'):
                    raise ValueError('Root-relative URL breaks project Pages')
            if key == 'style':
                for declaration in (value or '').split(';'):
                    if not declaration.strip():
                        continue
                    prop, sep, val = declaration.partition(':')
                    if not sep or prop.strip() not in STYLE_PROPERTIES or re.search(r'url\s*\(|expression|@import|[\\<>]', val, re.I):
                        raise ValueError(f'Forbidden inline style: {prop}')
    return tree


def toc_from_html(source):
    return [{'id': n.attr('href')[1:], 'label': clean_text(n),
             'level': 2 if n.has('nav-main') else 3}
            for n in TreeParser(source).root.descendants() if n.tag == 'a']


def emit_paper(slug, article_html, toc):
    """Convert a builder's article (not its shell) into the common document model."""
    catalog = json.loads((ROOT / 'data/catalog.json').read_text())
    paper = next(p for p in catalog if p['id'] == slug)
    meta = json.loads((ROOT / 'data/reader-meta.json').read_text())[slug].copy()
    meta['pdf'] = '../../pdfs/' + paper['pdf']
    source = ROOT / 'data' / slug / 'source.json'
    meta['source'] = json.loads(source.read_text()) if source.exists() else {}
    meta['version'] = meta['source'].get('version', 'publisher-final')
    tree = TreeParser(article_html).root
    article = next(n for n in tree.descendants() if n.tag == 'article')
    assets = []
    asset_source = ROOT / 'data' / slug / 'assets.json'
    provenance = {a['figure']: a for a in json.loads(asset_source.read_text())} if asset_source.exists() else {}
    directory = CONTENT / slug
    directory.mkdir(parents=True, exist_ok=True)
    for i, node in enumerate([n for n in article.descendants() if n.tag == 'img'], 1):
        src = node.attr('src')
        if src.startswith('data:'):
            header, encoded = src.split(',', 1)
            raw = base64.b64decode(encoded, validate=True)
            ext = 'svg' if 'svg' in header else 'jpg' if 'jpeg' in header else 'png'
        else:
            target = (ROOT / 'data' / slug / src).resolve()
            if not target.is_relative_to(ROOT / 'data' / slug):
                raise ValueError('Source asset leaves its paper directory')
            raw, ext = target.read_bytes(), target.suffix[1:]
        sha = digest(raw)
        filename = f'assets/figure-{i:02d}.{sha[:16]}.{ext}'
        path = directory / filename
        path.parent.mkdir(exist_ok=True)
        path.write_bytes(raw)
        asset = {'id': f'figure-{i:02d}', 'url': filename, 'width': int(node.attr('width')),
                 'height': int(node.attr('height')), 'sha256': sha}
        parent = node.parent
        while parent and parent.tag != 'figure':
            parent = parent.parent
        if parent:
            asset['source'] = {**provenance.get(i, {}), **{k: v for k, v in parent.attrs if k.startswith('data-')}}
        assets.append(asset)
        node.set_attr('src', filename)
        node.asset_id = asset['id']
    # Source article links originally resolve from public/papers/. Normalize them
    # to public/content/<slug>/, independently of the shell URL.
    for node in article.descendants():
        href = node.attr('href')
        if href and not href.startswith('#') and not urlsplit(href).scheme:
            path, mark, fragment = href.partition('#')
            node.set_attr('href', posixpath.relpath(posixpath.normpath('papers/' + path), 'content/' + slug) + (mark + fragment if mark else ''))
    validate_html(serialize(article))

    def convert(node):
        if isinstance(node, str):
            return {'type': 'text', 'text': html.unescape(node)}
        attrs = dict(node.attrs)
        common = {'tag': node.tag, 'attrs': attrs}
        if node.tag == 'img':
            common['attrs'].pop('src', None)
            return {'type': 'image', **common, 'assetId': node.asset_id}
        langs = {lang: next((n for n in node.children if isinstance(n, Node) and n.has(lang)), None) for lang in ('zh', 'en')}
        if node.attr('data-unit') and all(langs.values()) and all(
            child in langs.values() or isinstance(child, str) and not html.unescape(child).strip()
            for child in node.children
        ):
            return {'type': 'bilingual', 'kind': KINDS.get(node.tag, 'unit'), **common,
                    'order': [next((lang for lang, child in langs.items() if n is child), None)
                              if isinstance(n, Node) else {'text': html.unescape(n)} for n in node.children],
                    **{lang: {'tag': child.tag, 'attrs': dict(child.attrs),
                              'html': ''.join(serialize(c) for c in child.children)} for lang, child in langs.items()}}
        if node.tag in CONTAINERS or any(n.tag == 'img' for n in node.descendants()):
            return {'type': 'container', 'kind': KINDS.get(node.tag, 'group'), **common,
                    'children': [convert(n) for n in node.children]}
        return {'type': 'rich', 'kind': KINDS.get(node.tag, 'inline'), **common,
                'html': ''.join(serialize(n) for n in node.children)}

    title = next(n for n in article.descendants() if n.tag == 'h1')
    meta['titles'] = {lang: clean_text(next((n for n in title.descendants() if n.has(lang)), title)) for lang in ('zh', 'en')}
    doc = {'schemaVersion': 1, 'id': slug, 'meta': meta, 'toc': toc,
           'assets': assets, 'blocks': [convert(article)]}
    validate_document(doc)
    raw = (json.dumps(doc, ensure_ascii=False, separators=(',', ':')) + '\n').encode()
    output = directory / f'paper.{digest(raw)[:16]}.json'
    output.write_bytes(raw)
    # Remove only this builder's obsolete, generated content versions.
    for old in directory.glob('paper.*.json'):
        if old != output:
            old.unlink()
    used = {a['url'] for a in assets}
    for old in (directory / 'assets').glob('*'):
        if old.relative_to(directory).as_posix() not in used:
            old.unlink()
    return output


def validate_document(doc):
    if doc.get('schemaVersion') != 1 or not doc.get('id') or not doc.get('blocks'):
        raise ValueError('Invalid PaperDocument envelope')
    asset_ids = [a['id'] for a in doc['assets']]
    if len(asset_ids) != len(set(asset_ids)):
        raise ValueError('Duplicate asset ID')
    def check(block):
        typ = block.get('type')
        if typ == 'text':
            if not isinstance(block.get('text'), str):
                raise ValueError('Invalid text block')
            return
        tag = block['tag']
        if not re.fullmatch('[a-z][a-z0-9-]*', tag):
            raise ValueError('Invalid block tag')
        validate_html('<' + tag + ''.join(f' {k}="{html.escape(str(v or ""), quote=True)}"' for k, v in block['attrs'].items()) + '></' + tag + '>')
        if typ == 'container':
            for child in block['children']:
                check(child)
        elif typ == 'bilingual':
            for lang in ('zh', 'en'):
                child = block[lang]
                check({'type': 'rich', **child})
                if not clean_text(TreeParser(child['html']).root):
                    raise ValueError('Empty bilingual content')
        elif typ == 'rich':
            validate_html(block['html'])
        elif typ == 'image':
            if block['assetId'] not in asset_ids:
                raise ValueError('Unknown image asset')
        else:
            raise ValueError(f'Unknown block type: {typ}')
    for block in doc['blocks']:
        check(block)


def render_article(doc):
    """Independent static reconstruction for structural audits, never published."""
    assets = {a['id']: a for a in doc['assets']}
    def render(block):
        typ = block['type']
        if typ == 'text':
            return html.escape(block['text'], quote=False)
        attrs = block['attrs'].copy()
        if typ == 'image':
            attrs['src'] = assets[block['assetId']]['url']
        start = '<' + block['tag'] + ''.join(f' {k}="{html.escape(str(v), quote=True)}"' if v is not None else f' {k}' for k, v in attrs.items()) + '>'
        if block['tag'] in VOID:
            return start
        if typ == 'container':
            body = ''.join(render(c) for c in block['children'])
        elif typ == 'bilingual':
            body = ''.join(render({'type': 'rich', **block[item]}) if isinstance(item, str)
                           else html.escape(item['text'], quote=False) for item in block['order'])
        else:
            body = block['html']
        return start + body + '</' + block['tag'] + '>'
    return ''.join(render(b) for b in doc['blocks'])


def scope_css(source, slug):
    """Prefix selector rules, preserving media rules and root language selectors."""
    def process(text):
        result, offset = [], 0
        while offset < len(text):
            opening = text.find('{', offset)
            if opening < 0:
                result.append(text[offset:])
                break
            selector = text[offset:opening].strip()
            depth, end = 1, opening + 1
            while depth:
                if text[end] == '{': depth += 1
                elif text[end] == '}': depth -= 1
                end += 1
            body = text[opening + 1:end - 1]
            if selector.startswith('@'):
                result.append(selector + '{' + process(body) + '}')
            else:
                selectors = []
                for sel in selector.split(','):
                    sel = sel.strip()
                    prefix = f'html[data-paper="{slug}"]'
                    if sel.startswith('html'):
                        sel = prefix + sel[4:]
                    elif sel.startswith('[data-lang'):
                        sel = prefix + sel
                    else:
                        sel = prefix + ' ' + sel
                    selectors.append(sel)
                result.append(','.join(selectors) + '{' + body + '}')
            offset = end
        return '\n'.join(result)
    return process(source)


def publish(preview=False):
    catalog = json.loads((ROOT / 'data/catalog.json').read_text())
    reader = ROOT / 'reader'
    css = (reader / 'base.css').read_text() + '\n' + (reader / 'states.css').read_text()
    css += '\n'.join(scope_css((reader / f'{p["id"]}.css').read_text(), p['id']) for p in catalog if p['id'] != 'ace')
    resources = PUBLIC / 'reader'
    resources.mkdir(exist_ok=True)
    (resources / 'loader.js').write_bytes((reader / 'loader.js').read_bytes())
    names = {}
    for ext, raw in [('css', css.encode()), ('js', (reader / 'reader.js').read_bytes())]:
        path = resources / f'reader.{digest(raw)[:16]}.{ext}'
        path.write_bytes(raw)
        names[ext] = path.relative_to(PUBLIC).as_posix()
    manifest = {'schemaVersion': 1, 'reader': {**{k: '../' + v for k, v in names.items()}, 'loader': '../reader/loader.js'}, 'papers': {}}
    for paper in catalog:
        path, = (CONTENT / paper['id']).glob('paper.*.json')
        doc = json.loads(path.read_text())
        manifest['papers'][paper['id']] = {'url': path.relative_to(CONTENT).as_posix(),
            'title': doc['meta']['title'], 'brand': doc['meta']['brand'], 'pdf': '../pdfs/' + paper['pdf'],
            'defaultMode': doc['meta']['defaultMode'], 'storageKey': doc['meta']['storageKey']}
    write_json(CONTENT / 'manifest.json', manifest)
    template = (reader / 'shell.html').read_text()
    def shell(slug, at_root=False):
        meta = json.loads((ROOT / 'data/reader-meta.json').read_text())[slug]
        paper = next(p for p in catalog if p['id'] == slug)
        prefix = '' if at_root else '../'
        values = {'PAPER': slug, 'MANIFEST': prefix + 'content/manifest.json',
            'BRAND': meta['brand'], 'INDEX': prefix + 'index.html', 'PDF': prefix + 'pdfs/' + paper['pdf'],
            'MODE': meta['defaultMode'], 'DESCRIPTION': meta['description'], 'TITLE': meta['title'],
            'CSS': prefix + names['css'], 'JS': prefix + 'reader/loader.js'}
        text = template
        for key, value in values.items():
            text = text.replace('@' + key + '@', html.escape(value, quote=True))
        return text
    if preview:
        (PUBLIC / 'reader-preview.html').write_text(shell('ace', True))
    else:
        for paper in catalog:
            (PUBLIC / 'papers' / (paper['id'] + '.html')).write_text(shell(paper['id']))
        (PUBLIC / 'reader-preview.html').unlink(missing_ok=True)
    for path in resources.glob('reader.*.*'):
        if path.relative_to(PUBLIC).as_posix() not in names.values():
            path.unlink()
    return manifest
