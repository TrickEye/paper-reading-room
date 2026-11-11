# Local editor distribution

Vditor 4.0.1 files are copied without modification from the official npm release.
`vditor-4.0.1/checksums.json` records the verified tarball SHA-512 and individual
SHA-256 hashes. The Python build copies and audits this fixed subset; it does not
install packages or use the network. Keep the upstream directory structure for
Vditor's dynamic local resource URLs.

Included: Vditor (MIT), its bundled Lute parser (MulanPSL-2.0), bundled KaTeX 0.16.9
(MIT), Chinese localization, icons, and minimal style resources. License files and
source links are retained alongside the distribution. KaTeX's mhchem extension
is the copy distributed with Vditor. No editor source or example HTML is published.

Code block previews and multimedia are disabled by the integration. The editor
DOM sanitizer lives in the notes controller, outside the vendor distribution.
