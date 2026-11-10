#!/usr/bin/env python3
"""Check publishable links, bilingual page structure, assets, tables and PDF hashes."""
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import subprocess
import sys
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "public"
AUDITOR = ROOT / "skills/paper-reading-room/scripts/audit_reading_page.py"


class Links(HTMLParser):
    def __init__(self, path):
        super().__init__(convert_charrefs=True)
        self.ids = set()
        self.links = []
        self.has_base = False
        self.feed(path.read_text(encoding="utf-8"))

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if attrs.get("id"):
            self.ids.add(attrs["id"])
        if tag == "base":
            self.has_base = True
        for name in ("href", "src", "data"):
            if attrs.get(name):
                self.links.append(attrs[name])

    handle_startendtag = handle_starttag


def main():
    errors = []
    pages = {path.resolve(): Links(path) for path in PUBLIC.rglob("*.html")}
    for path in PUBLIC.rglob("*"):
        if path.is_symlink():
            errors.append(f"Symlink in publication directory: {path.relative_to(ROOT)}")
    for path, document in pages.items():
        label = path.relative_to(ROOT)
        if document.has_base:
            errors.append(f"{label}: base URL breaks portable relative links")
        for link in document.links:
            url = urlsplit(link)
            if url.scheme or url.netloc:
                continue
            decoded = unquote(url.path)
            if decoded.startswith("/"):
                errors.append(f"{label}: root-relative link breaks project Pages: {link}")
                continue
            target = (path.parent / decoded).resolve() if decoded else path
            if not target.is_relative_to(PUBLIC):
                errors.append(f"{label}: link leaves public/: {link}")
                continue
            if target.is_dir():
                target /= "index.html"
            if not target.is_file():
                errors.append(f"{label}: missing local target: {link}")
            elif url.fragment and target in pages and unquote(url.fragment) not in pages[target].ids:
                errors.append(f"{label}: missing anchor: {link}")

    catalog = json.loads((ROOT / "data/catalog.json").read_text(encoding="utf-8"))
    expected_pages = {PUBLIC / "index.html"}
    for paper in catalog:
        slug = paper["id"]
        page = PUBLIC / "papers" / f"{slug}.html"
        expected_pages.add(page)
        pdf = PUBLIC / "pdfs" / paper["pdf"]
        if not pdf.is_file() or not pdf.read_bytes().startswith(b"%PDF-"):
            errors.append(f"{slug}: missing or invalid original PDF")
        source = ROOT / "data" / slug
        metadata = source / "source.json"
        if metadata.is_file() and pdf.is_file():
            record = json.loads(metadata.read_text(encoding="utf-8"))
            if hashlib.sha256(pdf.read_bytes()).hexdigest() != record.get("pdf_sha256"):
                errors.append(f"{slug}: original PDF SHA-256 differs from source record")
        command = [
            sys.executable, "-B", str(AUDITOR), str(page),
            "--index", str(PUBLIC / "index.html"),
            "--expected-figures", str(paper["figures"]),
            "--expected-tables", str(paper["tables"]),
        ]
        if source.is_dir():
            command += ["--source-dir", str(source)]
        result = subprocess.run(command, text=True, capture_output=True)
        if result.returncode:
            errors.append(f"{slug}: {result.stdout.strip()} {result.stderr.strip()}")
        else:
            report = json.loads(result.stdout)
            print(f"PASS {slug}: {report['units']} bilingual units, "
                  f"{report['figures']} figures, {report['tables']} tables")
            if report["warnings"]:
                print(f"  Note: {len(report['warnings'])} source-provenance warnings; "
                      "run the skill auditor for details.")
    if set(pages) != expected_pages:
        errors.append("public/ HTML pages differ from data/catalog.json and index.html")
    if not (PUBLIC / ".nojekyll").is_file():
        errors.append("Missing public/.nojekyll")
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    print(f"PASS {len(pages)} HTML pages: local links and anchors stay inside public/; "
          "project Pages paths are portable.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
