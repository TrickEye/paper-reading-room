"""Build the bilingual Skill Transfer preprint from its audited source units."""
from pathlib import Path
import html
import json
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
from paper_document import emit_paper

SLUG = 'skill-transfer'
SOURCE = ROOT / 'data' / SLUG


def read(name):
    return json.loads((SOURCE / name).read_text(encoding='utf-8'))


def esc(value):
    return html.escape(str(value), quote=True)


def pair(zh, en, tag='span'):
    return (f'<{tag} class="zh translation" lang="zh-CN">{esc(zh)}</{tag}>'
            f'<{tag} class="en original" lang="en">{esc(en)}</{tag}>')


def attr(unit):
    return f'id="{esc(unit)}" data-unit="{esc(unit)}" data-searchable="true"'


figures = {f['number']: f for f in read('figures.json')}
tables = {t['number']: t for t in read('tables.json')}
units = read('units.json')
refs = read('references.json')
out = ['<article class="ltx_document" lang="zh-CN" id="paper">',
       '<p class="eyebrow">RESEARCH PAPER / PREPRINT · 2026</p>',
       '<h1 ' + attr('paper-title') + '>' + pair('技能迁移：将强智能体的技能适配给弱智能体',
                                           'Skill Transfer: Adapting Agent Skills from Strong to Weak Agents') + '</h1>',
       '<p class="paper-original-title">Skill Transfer: Adapting Agent Skills from Strong to Weak Agents</p>',
       '<div class="authors"><p>Yifan Lan · Hanyu Wang · Lu Lin · Jinghui Chen</p><p class="affiliations">The Pennsylvania State University</p></div>',
       '<div class="metadata"><span>Preprint · 2026</span><span>20 页 · 3 图 · 7 表</span></div>',
       '<aside class="translation-note"><strong>中文阅读版</strong><p>' + pair('依据作者预印本逐段翻译；图像来自同一 PDF，表格保留原始数值。',
       'Paragraph-aligned translation of the authors’ preprint. Figures come from the same PDF; table values are preserved.') + '</p></aside>']

section_open = False
sub_open = False
toc = []


def close_sections():
    global section_open, sub_open
    if sub_open:
        out.append('</section>')
        sub_open = False
    if section_open:
        out.append('</section>')
        section_open = False


def render_figure(number):
    f = figures[number]
    w, h = f['width'], f['height']
    out.append(f'<figure id="F{number}" class="ltx_figure" data-source-page="{f["page"]}" data-original-image="figure-{number:02}.png">'
               f'<button class="figure-zoom" type="button" aria-label="放大图 {number}">'
               f'<img src="assets/figure-{number:02}.png" alt="{esc(f["alt"])}" width="{w}" height="{h}" loading="lazy" decoding="async"></button>'
               f'<figcaption {attr("F" + str(number) + ".caption")}>{pair(f["zh"], f["en"])}</figcaption></figure>')


def cell(value, heading=False, extra=''):
    tag = 'th' if heading else 'td'
    attrs = ''
    if isinstance(value, dict):
        attrs = ''.join(f' {key}="{int(value[key])}"' for key in ('rowspan', 'colspan') if key in value)
        value = value['text']
    if isinstance(value, list):
        body = pair(value[0], value[1])
    else:
        body = esc(value)
    return f'<{tag}' + (' scope="col"' if heading else '') + attrs + extra + f'>{body}</{tag}>'


def render_table(number):
    t = tables[number]
    out.append(f'<figure id="T{number}" class="ltx_table"><div class="table-scroll" role="region" tabindex="0" aria-label="表 {number}"><table><thead>')
    for row in t['head']:
        out.append('<tr>' + ''.join(cell(v, True) for v in row) + '</tr>')
    out.append('</thead><tbody>')
    rows = t['rows']
    # Tables 3–5 group agents over multiple method rows. Expandable rowspans
    # preserve the exact source grid used by the content audit.
    rankings = {}
    if number in (3, 4, 5):
        for group in {row[0] for row in rows if row[0].startswith('Weak')}:
            members = [row for row in rows if row[0] == group]
            for col in range(2, len(members[0])):
                values = sorted({float(row[col]) for row in members},
                                reverse=(col not in ({4, 9, 13} if number == 3 else {4} if number == 4 else {5})))
                rankings[group, col] = (values[0], values[1] if len(values) > 1 else None)
    for i, row in enumerate(rows):
        cells = []
        for col, value in enumerate(row):
            if number in (3, 4, 5) and col == 0:
                if i and rows[i-1][0] == value:
                    continue
                span = sum(1 for r in rows[i:] if r[0] == value)
                cells.append(cell({'text': value, 'rowspan': span}))
                continue
            extra = ''
            if (row[0], col) in rankings:
                best, second = rankings[row[0], col]
                score = float(value)
                if score == best:
                    extra = ' class="best"'
                elif score == second and number == 3:
                    extra = ' class="second"'
            cells.append(cell(value, extra=extra))
        out.append('<tr>' + ''.join(cells) + '</tr>')
    out.append(f'</tbody></table></div><figcaption {attr("T" + str(number) + ".caption")}>{pair(t["zh"], t["en"])}</figcaption></figure>')


for u in units:
    kind, uid = u['kind'], u['id']
    if kind == 'h2':
        close_sections()
        out.append(f'<section id="{esc(uid)}" class="ltx_section"><h2 {attr(uid + ".heading")}>{pair(u["zh"], u["en"])}</h2>')
        section_open = True
        toc.append({'id': uid, 'label': u['zh'], 'level': 2})
    elif kind == 'h3':
        if sub_open:
            out.append('</section>')
        out.append(f'<section id="{esc(uid)}" class="ltx_subsection"><h3 {attr(uid + ".heading")}>{pair(u["zh"], u["en"])}</h3>')
        sub_open = True
        toc.append({'id': uid, 'label': u['zh'], 'level': 3})
    elif kind == 'figure':
        render_figure(u['number'])
    elif kind == 'table':
        render_table(u['number'])
    elif kind == 'equation':
        out.append(f'<div class="equation" id="{esc(uid)}" role="math" aria-label="{esc(u["en"])}">{esc(u["en"])}</div>')
    elif kind == 'code':
        out.append(f'<div class="code-pair" {attr(uid)}>{pair(u["zh"], u["en"], "pre")}</div>')
    elif kind == 'references':
        close_sections()
        out.append('<section class="ltx_bibliography" id="bib"><h2 ' + attr('bib.heading') + '>' + pair('参考文献', 'References') + '</h2><ol class="ltx_biblist">')
        for r in refs:
            out.append(f'<li class="ltx_bibitem" {attr(r["id"])}>{pair(r["zh"], r["en"])}</li>')
        out.append('</ol></section>')
        toc.append({'id': 'bib', 'label': '参考文献', 'level': 2})
    else:
        tag = 'li' if kind == 'li' else 'p'
        out.append(f'<{tag} class="ltx_p" {attr(uid)}>{pair(u["zh"], u["en"])}</{tag}>')
close_sections()

out.append('<footer class="source-footer" id="source"><h2>' + pair('来源与翻译说明', 'Source and translation notes') + '</h2>'
           '<p><a href="https://github.com/Yifan-Lan/Skill-Transfer">作者项目 / Author repository</a> · '
           '<a href="../pdfs/Skill-Transfer-preprint.pdf">原始 PDF / Original PDF</a></p>'
           '<p>' + pair('原作作者：Yifan Lan、Hanyu Wang、Lu Lin、Jinghui Chen。中文译文由 AI 制作，未经作者背书；引用请以原始 PDF 为准。',
                          'Original authors: Yifan Lan, Hanyu Wang, Lu Lin, and Jinghui Chen. The AI-generated Chinese translation is not endorsed by the authors; cite the original PDF.') + '</p></footer></article>')
emit_paper(SLUG, '\n'.join(out), toc)
print(f'Built {SLUG}: {len(units)} units, {len(figures)} figures, {len(tables)} tables, {len(refs)} references')
