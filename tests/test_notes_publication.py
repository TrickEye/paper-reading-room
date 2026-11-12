"""A notes-only web commit must not change generated publication files."""
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import paper_document


class NotesPublication(unittest.TestCase):
    def test_image_references_follow_updated_originals(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            data = root / 'data/demo'
            data.mkdir(parents=True)
            (root / 'data/catalog.json').write_text(json.dumps([{'id': 'demo', 'pdf': 'demo.pdf'}]))
            (root / 'data/reader-meta.json').write_text(json.dumps({'demo': {}}))
            image = data / 'figure.svg'
            article = '<article id="paper"><h1>Demo</h1><figure id="F1"><img src="figure.svg" width="4" height="3"></figure></article>'
            publication = root / 'public'
            with patch.object(paper_document, 'ROOT', root), patch.object(paper_document, 'CONTENT', publication / 'content'):
                image.write_bytes(b'<svg xmlns="http://www.w3.org/2000/svg" width="4" height="3"/>')
                first = paper_document.emit_paper('demo', article, [])
                original = json.loads(first.read_text())['assets'][0]
                legacy_image = first.parent / 'assets/figure-01.0123456789abcdef.svg'
                legacy_image.write_bytes(image.read_bytes())
                image.write_bytes(b'<svg xmlns="http://www.w3.org/2000/svg" width="4" height="3"><rect width="4" height="3"/></svg>')
                second = paper_document.emit_paper('demo', article, [])
                updated = json.loads(second.read_text())['assets'][0]
                self.assertEqual(original['url'], 'assets/figure-01.svg')
                self.assertEqual(original['url'], updated['url'])
                self.assertNotEqual(original['sha256'], updated['sha256'])
                self.assertNotIn('referenceUrl', updated)
                self.assertEqual((second.parent / original['url']).read_bytes(), image.read_bytes())
                self.assertEqual(list((second.parent / 'assets').iterdir()), [second.parent / updated['url']])
                self.assertEqual(paper_document.emit_paper('demo', article, []), second)

    def test_notes_survive_build_without_changing_generated_output(self):
        source = paper_document.PUBLIC
        with tempfile.TemporaryDirectory() as directory:
            publication = Path(directory)
            content = publication / 'content'
            (publication / 'papers').mkdir()
            for document in (source / 'content').glob('*/paper.*.json'):
                target = content / document.relative_to(source / 'content')
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(document, target)
            def generated():
                return {str(p.relative_to(publication)): hashlib.sha256(p.read_bytes()).hexdigest()
                        for p in publication.rglob('*') if p.is_file() and 'notes' not in p.relative_to(publication).parts}
            with patch.object(paper_document, 'PUBLIC', publication), patch.object(paper_document, 'CONTENT', content):
                paper_document.publish()
                before = generated()
                note = publication / 'notes/ace/notes.md'
                note.parent.mkdir(parents=True)
                for raw in ['# 中文笔记\r\n\r\n$x^2$\n'.encode(), b'']:
                    note.write_bytes(raw)
                    paper_document.publish()
                    self.assertEqual(note.read_bytes(), raw)
                    self.assertEqual(generated(), before)


if __name__ == '__main__':
    unittest.main()
