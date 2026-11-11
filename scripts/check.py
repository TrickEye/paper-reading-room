#!/usr/bin/env python3
"""Audit shells, complete PaperDocument content, resource paths and PDF hashes."""
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import subprocess
import sys
from urllib.parse import unquote, urlsplit

from paper_document import render_article, validate_document, validate_html

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / 'public'
AUDITOR = ROOT / 'skills/paper-reading-room/scripts/audit_reading_page.py'


class Links(HTMLParser):
    def __init__(self, source):
        super().__init__(convert_charrefs=True)
        self.ids, self.links, self.has_base = set(), [], False
        self.feed(source)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if attrs.get('id'):
            self.ids.add(attrs['id'])
        self.has_base |= tag == 'base'
        for name in ('href', 'src', 'data'):
            if attrs.get(name):
                self.links.append(attrs[name])
    handle_startendtag = handle_starttag


def resolve(value, base):
    url = urlsplit(value)
    if url.scheme or url.netloc:
        return None
    decoded = unquote(url.path)
    if decoded.startswith('/'):
        raise ValueError(f'Root-relative publication URL: {value}')
    path = (base / decoded).resolve() if decoded else base
    if not path.is_relative_to(PUBLIC):
        raise ValueError(f'URL leaves public/: {value}')
    if not path.is_file():
        raise ValueError(f'Missing publication resource: {path.relative_to(PUBLIC)}')
    return path


def check():
    errors = []
    catalog = json.loads((ROOT / 'data/catalog.json').read_text())
    manifest_file = PUBLIC / 'content/manifest.json'
    manifest = json.loads(manifest_file.read_text())
    assert manifest['schemaVersion'] == 1
    assert set(manifest['papers']) == {p['id'] for p in catalog}
    expected = {PUBLIC / 'index.html'} | {PUBLIC / 'papers' / (p['id'] + '.html') for p in catalog}
    preview = PUBLIC / 'reader-preview.html'
    if preview.exists():
        expected.add(preview)
    pages = {p: Links(p.read_text()) for p in PUBLIC.rglob('*.html')}
    assert set(pages) == expected, 'Publication HTML pages differ from the catalog'
    for path in PUBLIC.rglob('*'):
        if path.is_symlink():
            errors.append(f'Symlink in publication: {path.relative_to(PUBLIC)}')
    for kind, value in manifest['reader'].items():
        target = resolve(value, manifest_file.parent)
        if kind == 'loader':
            assert target.read_bytes() == (ROOT / 'reader/loader.js').read_bytes(), 'Loader output differs from source'
        else:
            assert hashlib.sha256(target.read_bytes()).hexdigest()[:16] in target.name, 'Reader hash mismatch'
    notes = resolve(manifest['notes']['js'], manifest_file.parent)
    assert hashlib.sha256(notes.read_bytes()).hexdigest()[:16] in notes.name, 'Notes hash mismatch'
    assert notes.read_bytes() == (ROOT / 'reader/notes.js').read_bytes()
    assert manifest['notes']['documents'] == '../notes/'
    assert manifest['notes']['github'] == {'owner': 'TrickEye', 'repo': 'paper-reading-room',
                                         'branch': 'main', 'directory': 'public/notes/'}
    vendor = resolve(manifest['notes']['vendor'] + 'checksums.json', manifest_file.parent)
    assert hashlib.sha256(vendor.read_bytes()).hexdigest()[:16] in vendor.parent.name, 'Vendor directory hash mismatch'
    checksums = json.loads(vendor.read_text())
    for name, sha in checksums['files'].items():
        target = resolve(name, vendor.parent)
        assert hashlib.sha256(target.read_bytes()).hexdigest() == sha, f'Vendor checksum mismatch: {name}'
    assert {p.relative_to(vendor.parent).as_posix() for p in vendor.parent.rglob('*') if p.is_file()} == set(checksums['files']) | {'checksums.json'}, 'Unexpected vendor resources'
    content_pages = {}
    for paper in catalog:
        slug = paper['id']
        shell = PUBLIC / 'papers' / (slug + '.html')
        entry = manifest['papers'][slug]
        path = resolve(entry['url'], manifest_file.parent)
        doc = json.loads(path.read_text())
        assert doc['id'] == slug
        validate_document(doc)
        assert hashlib.sha256(path.read_bytes()).hexdigest()[:16] in path.name, 'Paper hash mismatch'
        assert len(list(path.parent.glob('paper.*.json'))) == 1, 'Stale paper versions'
        article = render_article(doc)
        validate_html(article)
        document = Links(article)
        assert all(item['id'] in document.ids for item in doc['toc']), 'Broken TOC target'
        content_pages[shell] = document.ids
        for asset in doc['assets']:
            image = resolve(asset['url'], path.parent)
            assert hashlib.sha256(image.read_bytes()).hexdigest() == asset['sha256'], 'Image hash mismatch'
        pdf = resolve(doc['meta']['pdf'], path.parent)
        assert pdf == PUBLIC / 'pdfs' / paper['pdf'] and pdf.read_bytes().startswith(b'%PDF-')
        assert resolve(entry['pdf'], manifest_file.parent) == pdf
        source = ROOT / 'data' / slug
        metadata = source / 'source.json'
        if metadata.exists():
            source_record = json.loads(metadata.read_text())
            assert hashlib.sha256(pdf.read_bytes()).hexdigest() == source_record['pdf_sha256'], 'PDF SHA-256 mismatch'
        for link in document.links:
            url = urlsplit(link)
            if url.scheme or url.netloc:
                continue
            if not url.path:
                assert not url.fragment or unquote(url.fragment) in document.ids, f'Broken content anchor: {link}'
            else:
                resolve(link, path.parent)
        command = [sys.executable, '-B', str(AUDITOR), str(shell), '--document', str(path),
            '--source-dir', str(source), '--index', str(PUBLIC / 'index.html'),
            '--expected-figures', str(paper['figures']), '--expected-tables', str(paper['tables'])]
        result = subprocess.run(command, text=True, capture_output=True)
        if result.returncode:
            errors.append(f'{slug}: {result.stdout.strip()} {result.stderr.strip()}')
        else:
            report = json.loads(result.stdout)
            print(f"PASS {slug}: {report['units']} bilingual units, {report['figures']} figures, {report['tables']} tables; JSON {path.stat().st_size / 1024:.1f} KiB")
            if report['warnings']:
                print(f"  Note: {len(report['warnings'])} existing source-provenance warnings")
    for path, document in pages.items():
        if document.has_base:
            errors.append(f'{path.name}: base URL is forbidden')
        for link in document.links:
            url = urlsplit(link)
            if url.scheme or url.netloc:
                continue
            target = path if not url.path else resolve(link, path.parent)
            if url.fragment and target in pages:
                ids = pages[target].ids | content_pages.get(target, set())
                if target == preview:
                    ids |= content_pages[PUBLIC / 'papers/ace.html']
                if unquote(url.fragment) not in ids:
                    errors.append(f'{path.name}: broken anchor {link}')
        if path.parent.name == 'papers' and not preview.exists():
            source = path.read_text()
            assert '<article' not in source and 'data:image' not in source, 'Shell embeds paper content'
            assert 'data-manifest="../content/manifest.json"' in source
            assert path.stat().st_size < 10000, 'Shell exceeds 10 KB'
    assert (PUBLIC / '.nojekyll').is_file()
    if errors:
        raise ValueError('\n'.join(errors))
    print('PASS publication: complete content audited; resource hashes and portable URLs verified.')


def main():
    try:
        check()
    except (ValueError, AssertionError, OSError, KeyError, TypeError) as error:
        print(f'FAIL {error}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
