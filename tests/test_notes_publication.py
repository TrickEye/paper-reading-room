"""A notes-only web commit must not change generated publication files."""
import hashlib
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import paper_document


class NotesPublication(unittest.TestCase):
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
