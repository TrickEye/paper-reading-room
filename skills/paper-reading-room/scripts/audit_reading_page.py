#!/usr/bin/env python3
"""Read-only structural audit of an ACE-style bilingual paper page (Python standard library).

Does NOT certify translation fidelity, paragraph granularity, crop accuracy, or source completeness.
--source-dir accepts this project's assets.json, figures.json, tables.json, references.json.
"""
import argparse
import base64
from collections import Counter
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import sys
import unicodedata
from urllib.parse import unquote, urlsplit


class Node:
    def __init__(self, tag='', attrs=(), parent=None):
        self.tag, self.attrs, self.parent = tag, dict(attrs), parent
        self.children, self.parts = [], []

    def has(self, cls):
        return cls in self.attrs.get('class', '').split()

    def descendants(self):
        for child in self.children:
            yield child
            yield from child.descendants()

    def text(self):
        return ''.join(p.text() if isinstance(p, Node) else p for p in self.parts)


class Document(HTMLParser):
    void = set('area base br col embed hr img input link meta param source track wbr'.split())

    def __init__(self, content):
        super().__init__(convert_charrefs=True)
        self.root = Node()
        self.stack = [self.root]
        self.feed(content)

    def handle_starttag(self, tag, attrs):
        node = Node(tag, attrs, self.stack[-1])
        self.stack[-1].children.append(node)
        self.stack[-1].parts.append(node)
        if tag not in self.void:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in self.void:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, 0, -1):
            if self.stack[i].tag == tag:
                del self.stack[i:]
                break

    def handle_data(self, data):
        self.stack[-1].parts.append(data)


def normalized(value):
    return ' '.join(unicodedata.normalize('NFC', str(value)).split())


def english(node):
    matches = [n for n in node.descendants() if n.has('en')]
    return normalized(' '.join(n.text() for n in matches) if matches else node.text())


def local_target(url, base):
    parsed = urlsplit(url)
    if parsed.scheme or parsed.netloc or not parsed.path:
        return None
    return base / unquote(parsed.path)


def grid(table):
    """Expand row and column spans in tbody, retaining bilingual English text."""
    bodies = [n for n in table.children if n.tag == 'tbody']
    rows = [n for b in bodies for n in b.children if n.tag == 'tr']
    occupied, result = {}, []
    for i, row in enumerate(rows):
        col = 0
        for cell in [n for n in row.children if n.tag in {'th', 'td'}]:
            while (i, col) in occupied:
                col += 1
            rowspan, colspan = int(cell.attrs.get('rowspan', 1)), int(cell.attrs.get('colspan', 1))
            if min(rowspan, colspan) < 1:
                raise ValueError('nonpositive table span')
            for y in range(i, i + rowspan):
                for x in range(col, col + colspan):
                    if (y, x) in occupied:
                        raise ValueError('overlapping table spans')
                    occupied[y, x] = english(cell)
            col += colspan
        columns = [x for y, x in occupied if y == i]
        result.append([occupied.get((i, x), '') for x in range(max(columns, default=-1) + 1)])
    return result


def audit(args):
    errors, warnings = [], []
    resource_base = args.html.parent
    if getattr(args, 'document', None):
        sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'scripts'))
        from paper_document import render_article, validate_document
        record = json.loads(args.document.read_text(encoding='utf-8'))
        validate_document(record)
        content = render_article(record)
        resource_base = args.document.parent
    else:
        content = args.html.read_text(encoding='utf-8')
    document = Document(content)
    nodes = list(document.root.descendants())
    ids = Counter(n.attrs['id'] for n in nodes if n.attrs.get('id'))
    errors.extend(f'duplicate id: {key}' for key, count in ids.items() if count > 1)
    by_id = {n.attrs['id']: n for n in nodes if n.attrs.get('id')}
    units = [n for n in nodes if 'data-unit' in n.attrs]
    if not units:
        errors.append('no data-unit content units; paragraph alignment cannot be audited')
    unit_ids = Counter(n.attrs['data-unit'] for n in units)
    errors.extend(f'duplicate data-unit: {key}' for key, count in unit_ids.items() if count > 1)
    for node in units:
        if node.attrs.get('role') == 'math' or node.has('equation'):
            continue
        zh = [c for c in node.children if c.has('zh')]
        en = [c for c in node.children if c.has('en')]
        if len(zh) != 1 or len(en) != 1 or not all(c.text().strip() for c in zh + en):
            errors.append(f'unit {node.attrs["data-unit"]}: requires one nonempty direct zh/en pair')
    for node in nodes:
        if node.has('original-page') or node.has('source-page'):
            errors.append('legacy whole-page figure or page-folded source container remains')
        if node.tag == 'a' and 'href' in node.attrs:
            href = node.attrs['href']
            if href.startswith('#') and unquote(href[1:]) not in ids:
                errors.append(f'broken anchor: {href}')
            target = local_target(href, resource_base)
            if target is not None and not target.exists():
                errors.append(f'missing linked file: {target.name}')
    figures = [n for n in nodes if n.tag == 'figure' and n.has('ltx_figure')]
    tables = [n for n in nodes if n.tag == 'table']
    image_data = {}
    for figure in figures:
        fid = figure.attrs.get('id', '(no id)')
        images = [n for n in figure.descendants() if n.tag == 'img']
        captions = [n for n in figure.descendants() if n.tag == 'figcaption']
        if not images or not captions:
            errors.append(f'{fid}: missing image or caption')
        if not figure.attrs.get('data-source-page') or not figure.attrs.get('data-original-image'):
            warnings.append(f'{fid}: source-page/original-image provenance missing in HTML')
        for image in images:
            if not image.attrs.get('alt', '').strip():
                errors.append(f'{fid}: image alt missing')
            if not all(image.attrs.get(k, '').isdigit() and int(image.attrs[k]) > 0 for k in ['width', 'height']):
                errors.append(f'{fid}: positive image dimensions missing')
            src = image.attrs.get('src', '')
            try:
                if src.startswith('data:'):
                    header, data = src.split(',', 1)
                    if ';base64' not in header:
                        raise ValueError('image data URL is not base64')
                    raw = base64.b64decode(data, validate=True)
                else:
                    target = local_target(src, resource_base)
                    if target is None:
                        raise ValueError('remote/missing image prevents offline use')
                    raw = target.read_bytes()
                if not raw:
                    raise ValueError('empty image')
                image_data[fid] = raw
            except (ValueError, OSError) as error:
                errors.append(f'{fid}: {error}')
    # Check runtime/style resources, not external attribution hyperlinks.
    for node in nodes:
        url = node.attrs.get('src') if node.tag == 'script' else node.attrs.get('href') if node.tag == 'link' and node.attrs.get('rel') == 'stylesheet' else None
        if url:
            target = local_target(url, resource_base)
            if target is None and not url.startswith('data:'):
                errors.append('remote script/stylesheet prevents guaranteed offline use')
            elif target is not None and not target.exists():
                errors.append(f'missing runtime resource: {target.name}')
    style_text = '\n'.join(n.text() for n in nodes if n.tag == 'style')
    if re.search(r'(?:url\(\s*[\'\"]?|@import\s+[\'\"])(?:https?:)?//', style_text):
        errors.append('remote CSS resource prevents guaranteed offline use')
    expected_figures, expected_tables = args.expected_figures, args.expected_tables
    if args.source_dir:
        def read(name):
            file = args.source_dir / (name + '.json')
            return json.loads(file.read_text(encoding='utf-8')) if file.exists() else None
        assets, figure_records, table_records, refs = (read(x) for x in ['assets', 'figures', 'tables', 'references'])
        if assets is not None:
            expected_figures = len(assets) if expected_figures is None else expected_figures
            if len({str(a['figure']) for a in assets}) != len(assets):
                errors.append('duplicate figures in assets manifest')
            for asset in assets:
                fid = asset.get('id', 'F' + str(asset['figure']))
                raw = image_data.get(fid)
                target = args.source_dir / 'assets' / asset['file']
                if not target.exists():
                    target = args.source_dir / asset['file']
                if raw is None or not target.exists() or raw != target.read_bytes():
                    errors.append(f'{fid}: HTML image differs from or lacks manifest asset')
                if raw is not None and asset.get('sha256') and hashlib.sha256(raw).hexdigest() != asset['sha256']:
                    errors.append(f'{fid}: SHA-256 mismatch')
        if figure_records is not None and len(figure_records) != len(figures):
            errors.append('figure caption records do not match figure count')
        if table_records is not None:
            expected_tables = len(table_records) if expected_tables is None else expected_tables
            for record in table_records:
                tid = 'T' + str(record['number'])
                node = by_id.get(tid)
                candidates = [n for n in node.descendants() if n.tag == 'table'] if node else []
                if len(candidates) != 1:
                    errors.append(f'{tid}: expected exactly one table')
                    continue
                def value(v):
                    if isinstance(v, list):
                        v = v[1]
                    # Legacy SkillForge stores measurements as floats with three displayed decimals.
                    return normalized(f'{v:.3f}' if isinstance(v, float) else v)
                wanted = [[value(v) for v in row] for row in record['rows']]
                if grid(candidates[0]) != wanted:
                    errors.append(f'{tid}: rendered body differs from full source rows/values/spans')
        if refs is not None and len([n for n in nodes if n.has('ltx_bibitem')]) != len(refs):
            errors.append('reference count differs from source records')
        for name in ['main', 'appendix', 'references', 'figures', 'prompts']:
            records = read(name)
            for i, record in enumerate(records or []):
                if not all(isinstance(record.get(lang), str) and record[lang].strip() for lang in ['en', 'zh']):
                    errors.append(f'{name}[{i}]: empty/missing source or translation')
    for expected, actual, label in [(expected_figures, len(figures), 'figures'), (expected_tables, len(tables), 'tables')]:
        if expected is not None and expected != actual:
            errors.append(f'{label}: expected {expected}, got {actual}')
    if expected_figures is None or expected_tables is None:
        warnings.append('missing expected counts: source completeness is not checked')
    if args.index:
        index_nodes = list(Document(args.index.read_text(encoding='utf-8')).root.descendants())
        targets = [local_target(n.attrs.get('href', ''), args.index.parent) for n in index_nodes if n.tag == 'a']
        if args.html.resolve() not in [p.resolve() for p in targets if p is not None]:
            errors.append('index does not link to this reading page')
        for target in targets:
            if target is not None and not target.exists():
                errors.append(f'index has missing local target: {target.name}')
    return dict(status='FAIL' if errors else 'PASS', units=len(units), figures=len(figures),
                tables=len(tables), errors=errors, warnings=warnings,
                limits='Requires source-by-source editorial review and browser/visual verification.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('html', type=Path)
    parser.add_argument('--source-dir', type=Path)
    parser.add_argument('--document', type=Path, help='Audit the full PaperDocument JSON belonging to this shell')
    parser.add_argument('--index', type=Path)
    parser.add_argument('--expected-figures', type=int)
    parser.add_argument('--expected-tables', type=int)
    args = parser.parse_args()
    try:
        report = audit(args)
    except (ValueError, OSError, KeyError, TypeError) as error:
        parser.exit(1, f'Audit failed to read inputs: {error}\n')
    print(json.dumps(report, ensure_ascii=False, indent=2))
    sys.exit(1 if report['errors'] else 0)


if __name__ == '__main__':
    main()
