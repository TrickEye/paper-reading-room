"""Meaningful content-boundary checks; full DOM equivalence is tested in Chrome."""
import copy
import json
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from paper_document import validate_document, validate_html


class ContentValidation(unittest.TestCase):
    def test_active_content_is_rejected(self):
        for source in ['<script>alert(1)</script>', '<p onclick="alert(1)">text</p>',
                       '<a href="javascript:alert(1)">text</a>',
                       '<a href="java&#x09;script:alert(1)">text</a>',
                       '<iframe src="https://example.org"></iframe>',
                       '<span style="width:expression(alert(1))">text</span>',
                       '<span style="width:url(https://example.org)">text</span>']:
            with self.subTest(source=source), self.assertRaises(ValueError):
                validate_html(source)

    def test_project_paths_and_local_math_are_accepted(self):
        validate_html('<p><a href="../../pdfs/paper.pdf#page=2">PDF</a><math><mfrac><mi>x</mi><mn>2</mn></mfrac></math></p>')
        with self.assertRaises(ValueError):
            validate_html('<img src="/assets/figure.svg">')

    def test_unknown_format_or_asset_cannot_pass(self):
        root=Path(__file__).resolve().parents[1]
        manifest=json.loads((root/'public/content/manifest.json').read_text())
        doc=json.loads((root/'public/content'/manifest['papers']['ace']['url']).read_text())
        bad=copy.deepcopy(doc);bad['schemaVersion']=2
        with self.assertRaises(ValueError):validate_document(bad)
        bad=copy.deepcopy(doc);bad['assets']=[]
        with self.assertRaises(ValueError):validate_document(bad)
        bad=copy.deepcopy(doc);bad['blocks'][0]['type']='unknown'
        with self.assertRaises(ValueError):validate_document(bad)


if __name__=='__main__':unittest.main()
