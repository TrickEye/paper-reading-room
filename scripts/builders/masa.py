"""Build the bilingual MASA page from the official arXiv v1 HTML and reviewed translations."""
from __future__ import annotations

import base64
import html
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
from builders.html_tree import TreeParser, Node, clean_text, serialize
from paper_document import emit_paper

SLUG = 'masa'
SOURCE = ROOT / 'data' / SLUG


def read_tsv(name):
    result = {}
    for line in (SOURCE / name).read_text(encoding='utf-8').splitlines():
        if not line.strip() or line.startswith('#'):
            continue
        key, value = line.split('\t', 1)
        if key in result:
            raise ValueError(f'duplicate translation: {key}')
        result[key] = value
    return result


translations = read_tsv('translations.tsv')
table_translations = read_tsv('table-translations.tsv')
reference_titles = read_tsv('reference-titles.tsv')
algorithm_zh = json.loads((SOURCE / 'algorithms.json').read_text(encoding='utf-8'))
source_tree = TreeParser((SOURCE / 'arxiv.html').read_text(encoding='utf-8')).root
article = next(n for n in source_tree.descendants() if n.tag == 'article' and n.has('ltx_document'))
out = []
toc = []
used = set()


def esc(value):
    return html.escape(str(value), quote=True)


def children_html(node):
    raw = ''.join(serialize(child) for child in node.children)
    # Official HTML points to figure/table IDs scoped by source section; the
    # reading page uses stable figure and table numbers shared by the index.
    return re.sub(r'href="#(?:S\d+|A\d+)\.([FT]\d+)"', r'href="#\1"', raw)


def pair(zh, en, *, trusted_en=False, trusted_zh=False, tag='span'):
    return (f'<{tag} class="zh translation" lang="zh-CN">{zh if trusted_zh else esc(zh)}</{tag}>'
            f'<{tag} class="en original" lang="en">{en if trusted_en else esc(en)}</{tag}>')


def translated(key):
    used.add(key)
    if key not in translations or not translations[key].strip():
        raise ValueError(f'missing MASA translation: {key}')
    return translations[key]


def attrs(uid):
    return f'id="{esc(uid)}" data-unit="{esc(uid)}" data-searchable="true"'


def direct_child(node, *tags):
    return next((c for c in node.children if isinstance(c, Node) and c.tag in tags), None)


def render_paragraph(node):
    uid = node.attr('id')
    en = children_html(node).strip()
    if not clean_text(node):
        return
    parent = node.parent
    marker = ''
    if parent and parent.tag == 'li':
        label = next((c for c in parent.children if isinstance(c, Node) and c.has('ltx_tag_item')), None)
        marker = (clean_text(label) + ' ') if label else '• '
    zh = esc(translated(uid))
    citations = [clean_text(c) for c in node.descendants() if c.tag == 'cite']
    if citations:
        zh += '<small class="source-citations">［原文引用：' + esc('；'.join(citations)) + '］</small>'
    out.append(f'<p class="ltx_p" {attrs(uid)}>{esc(marker)}{pair(zh, en, trusted_en=True, trusted_zh=True)}</p>')


def render_equation(node):
    uid = node.attr('id')
    math = next((n for n in node.descendants() if n.tag == 'math'), None)
    if not math:
        raise ValueError(f'{uid}: missing MathML')
    tag = next((n for n in node.descendants() if n.has('ltx_tag_equation')), None)
    number = clean_text(tag) if tag else ''
    out.append(f'<div id="{esc(uid)}" class="equation" role="math">{serialize(math)} <span class="equation-number">{esc(number)}</span></div>')


FIGURE_PAGES = {1: 1, 2: 3, 3: 8, 4: 13, 5: 19}
TABLE_PAGES = {1: 6, 2: 7, 3: 12, 4: 17, 5: 18, 6: 18, 7: 15, 8: 18, 9: 20}
FIGURE_EXT = {1: 'svg', 2: 'png', 3: 'svg', 4: 'svg', 5: 'svg'}


def render_figure(node):
    number = int(re.search(r'F(\d+)$', node.attr('id')).group(1))
    graphic = next((n for n in node.descendants() if n.tag in ('object', 'img')), None)
    caption = next((n for n in node.children if isinstance(n, Node) and n.tag == 'figcaption'), None)
    if not graphic or not caption:
        raise ValueError(f'figure {number}: missing graphic or caption')
    key = f'F{number}.caption'
    out.append(f'<figure id="F{number}" class="ltx_figure" data-source-page="{FIGURE_PAGES[number]}" data-original-image="figure-{number:02}.{FIGURE_EXT[number]}">'
               f'<button class="figure-zoom" type="button" aria-label="放大图 {number}">'
               f'<img src="assets/figure-{number:02}.{FIGURE_EXT[number]}" alt="{esc(translated(key))}" '
               f'width="{esc(graphic.attr("width"))}" height="{esc(graphic.attr("height"))}" loading="lazy" decoding="async"></button>'
               f'<figcaption {attrs(key)}>{pair(translations[key], clean_text(caption))}</figcaption></figure>')


CELL_TERMS = {
    'Model': '模型', 'Method': '方法', 'Pick': '拾取', 'Look': '查看', 'Clean': '清洁',
    'Heat': '加热', 'Cool': '冷却', 'Pick2': '双物体拾取', 'SR ↑\\uparrow': '成功率 ↑',
    'Steps ↓\\downarrow': '步数 ↓', 'Score ↑\\uparrow': '得分 ↑',
    'No Skill': '无技能', '+ Base Skill': '＋基础技能', '+ DS-Adapter': '＋DS-Adapter',
    '+ MASA': '＋MASA', 'Single-Hop QA': '单跳问答', 'Multi-Hop QA': '多跳问答',
    'Avg.': '平均', 'Variant': '变体', 'Full pipeline': '完整流程',
    'w/o Task-specific': '无任务专用阶段', 'w/o General': '无通用阶段',
    'Cross-env': '跨环境', 'Cross-task': '跨任务',
    'w/ Model Card': '有模型卡', 'w/o Model Card': '无模型卡',
    'Granularity': '粒度', 'Skill Text': '技能文本', 'Concise': '精简',
    'Moderate': '中等', 'Detailed': '详细', 'Skill': '技能', 'Overall': '总体',
    'CoT (%)': '思维链占比（%）', 'Action Len.': '动作长度',
    '73 chars': '73 字符', '1,021 chars': '1,021 字符',
    '574 chars': '574 字符', '491 chars': '491 字符',
    'Per-Category SR (%)': '逐品类成功率（%）', 'Apparel': '服装',
    'Other': '其他', 'Footwear': '鞋类', 'Home': '家居', 'Elec.': '电子产品',
    'Access.': '配饰', 'Beauty': '美妆', 'Evolved Skill Text': '演化技能文本',
    'Failure Mode': '失败模式', 'Strategy': '策略',
    'Picks visually similar colors by guessing': '靠猜测选择视觉上相似的颜色',
    'Strict binary match: exact or leave': '严格二元匹配：完全一致，否则离开',
    'Abandons products too easily (0 credit)': '过早放弃商品（得零分）',
    'Flexible match: buy anyway for partial credit': '灵活匹配：仍购买以争取部分得分',
    'Wastes steps deliberating on bad products': '在不合适的商品上耗费步骤反复斟酌',
    'Fast-fail: 1-step exit if no exact match': '快速失败：无完全匹配便一步退出',
    'Mishandles coded names (e.g. d01green)': '错误处理编码后的名称（如 d01green）',
    'Algorithmic: substring matching with preference rule': '算法式策略：按偏好规则匹配子串',
}


def cell_html(cell, table_number, row_index, col_index):
    value = clean_text(cell)
    key = f'T{table_number}.{row_index}.{col_index}'
    zh = table_translations.get(key) or CELL_TERMS.get(value)
    if value and zh is None and not re.fullmatch(r'[\d\s.,%+−\-/↑↓⋆†]+', value) and not re.fullmatch(r'(?:Qwen3|Gemma3)-[\dA-Z]+|\d+B|(?:NQ|TriviaQA|PopQA|HotpotQA|2Wiki|MuSiQue|Bamboogle)[†⋆]?', value) and value not in ('ALFWorld', 'WebShop'):
        raise ValueError(f'untranslated table cell {key}: {value[:100]}')
    content = pair(zh, children_html(cell), trusted_en=True) if zh else children_html(cell)
    tag = cell.tag
    extra = ''.join(f' {name}="{esc(cell.attr(name))}"' for name in ('rowspan', 'colspan') if cell.attr(name))
    return f'<{tag}{extra}>{content}</{tag}>'


def render_table(node):
    number = int(re.search(r'T(\d+)$', node.attr('id')).group(1))
    caption = next((n for n in node.children if isinstance(n, Node) and n.tag == 'figcaption'), None)
    if not caption:
        raise ValueError(f'table {number}: missing caption')
    tables = [n for n in node.descendants() if n.tag == 'table' and not any(a.tag == 'table' for a in ancestors(n, node))]
    if not tables:
        raise ValueError(f'table {number}: no source grid')
    out.append(f'<figure id="T{number}" class="ltx_table" data-source-page="{TABLE_PAGES[number]}">'
               f'<div class="table-scroll" role="region" tabindex="0" aria-label="表 {number}"><table><tbody>')
    row_index = 0
    for panel_index, table in enumerate(tables):
        if len(tables) > 1:
            panel = ['通用技能', '任务专用技能'] if number == 4 else ['演化流程', '改写器模型卡']
            label = panel[panel_index]
            columns = max(len([c for c in row.children if isinstance(c, Node) and c.tag in ('td', 'th')])
                          for row in table.descendants() if row.tag == 'tr')
            out.append(f'<tr class="table-subheading"><th colspan="{columns}">{pair(f"({chr(97+panel_index)}) {label}", f"({chr(97+panel_index)}) {clean_text(node.find_all(lambda x:x.tag == "figcaption")[panel_index])}")}</th></tr>')
        for row in table.descendants():
            if row.tag != 'tr':
                continue
            cells = [c for c in row.children if isinstance(c, Node) and c.tag in ('td', 'th')]
            out.append('<tr>' + ''.join(cell_html(c, number, row_index, j) for j, c in enumerate(cells)) + '</tr>')
            row_index += 1
    key = f'T{number}.caption'
    out.append(f'</tbody></table></div><figcaption {attrs(key)}>{pair(translated(key), clean_text(caption))}</figcaption></figure>')


def ancestors(node, stop):
    node = node.parent
    while node is not None and node is not stop:
        yield node
        node = node.parent


def render_algorithm(node):
    aid = node.attr('id')
    label = next(n for n in node.descendants() if n.has('ltx_caption'))
    lines = [n for n in node.descendants() if n.has('ltx_listingline')]
    chinese = '\n'.join(algorithm_zh[aid])
    if len(lines) != len(chinese.splitlines()):
        raise ValueError(f'{aid}: translated line count differs')
    # Keep the source MathML in the English algorithm. Its alttext is LaTeX,
    # which would otherwise appear as literal backslash commands in the reader.
    english = ''.join(f'<div class="algorithm-line">{children_html(line).strip()}</div>' for line in lines)
    out.append(f'<figure id="{esc(aid)}" class="algorithm"><figcaption {attrs(aid + ".caption")}>{pair(translated(aid + ".caption"), clean_text(label))}</figcaption>'
               f'<div class="code-pair" {attrs(aid + ".code")}>'
               f'<pre class="zh translation" lang="zh-CN">{esc(chinese)}</pre>'
               f'<div class="en original algorithm-source" lang="en">{english}</div></div></figure>')


def render_listing(node):
    link = next((n for n in node.descendants() if n.tag == 'a' and (n.attr('href') or '').startswith('data:text/plain;base64,')), None)
    if not link:
        raise ValueError('model card listing missing source')
    english = base64.b64decode(link.attr('href').split(',', 1)[1]).decode('utf-8')
    chinese = (SOURCE / 'model-card-zh.txt').read_text(encoding='utf-8')
    out.append(f'<div class="code-pair" {attrs(node.attr("id"))}>{pair(chinese, english, tag="pre")}</div>')


def render_bibliography(node):
    out.append('<section id="bib" class="ltx_bibliography"><h2 ' + attrs('bib.heading') + '>' + pair('参考文献', 'References') + '</h2><ol class="ltx_biblist">')
    toc.append({'id': 'bib', 'label': '参考文献', 'level': 2})
    for item in node.descendants():
        if not item.has('ltx_bibitem'):
            continue
        uid = item.attr('id')
        english = clean_text(item)
        if uid not in reference_titles:
            raise ValueError(f'missing reference title translation: {uid}')
        chinese = reference_titles[uid] + '。原始引文：' + english
        out.append(f'<li class="ltx_bibitem" {attrs(uid)}>{pair(chinese, english)}</li>')
    out.append('</ol></section>')


def render(node, depth=2):
    if isinstance(node, str):
        return
    if node.tag == 'section' and node.has('ltx_bibliography'):
        render_bibliography(node)
        return
    if node.tag == 'section' and any(node.has(cls) for cls in ('ltx_section', 'ltx_appendix', 'ltx_subsection', 'ltx_paragraph')):
        uid = node.attr('id')
        heading = direct_child(node, 'h2', 'h3', 'h4')
        level = 2 if node.has('ltx_section') or node.has('ltx_appendix') else 3 if node.has('ltx_subsection') else 4
        out.append(f'<section id="{esc(uid)}" class="{esc(node.attr("class", ""))}">')
        if heading:
            out.append(f'<h{level} {attrs(uid + ".heading")}>{pair(translated(uid), clean_text(heading))}</h{level}>')
            if level <= 3:
                toc.append({'id': uid, 'label': translations[uid], 'level': level})
        for child in node.children:
            if child is not heading:
                render(child, level)
        out.append('</section>')
        return
    if node.has('ltx_abstract'):
        out.append('<section id="abstract1"><h2>' + pair('摘要', 'Abstract') + '</h2>')
        for child in node.children:
            render(child, 2)
        out.append('</section>')
        return
    if node.tag == 'figure' and node.has('ltx_figure'):
        render_figure(node); return
    if node.tag == 'figure' and node.has('ltx_table'):
        if '.st' not in (node.attr('id') or ''):
            render_table(node)
        return
    if node.tag == 'figure' and node.has('ltx_float_algorithm'):
        render_algorithm(node); return
    if node.tag == 'table' and node.has('ltx_equation') and node.attr('id'):
        render_equation(node); return
    if node.has('ltx_listing') and node.attr('id') and node.tag == 'div':
        render_listing(node); return
    if node.tag == 'p' and node.has('ltx_p'):
        render_paragraph(node); return
    for child in node.children:
        render(child, depth)


out.extend([
    '<article class="ltx_document" id="paper" lang="zh-CN">',
    '<p class="eyebrow">RESEARCH PAPER / arXiv · 2026</p>',
    '<h1 ' + attrs('paper-title') + '>' + pair('技能并非一体适用：大语言模型智能体的模型感知技能对齐',
       'Skill is Not One-Size-Fits-All: Model-Aware Skill Alignment for LLM Agents') + '</h1>',
    '<p class="paper-original-title">Skill is Not One-Size-Fits-All: Model-Aware Skill Alignment for LLM Agents</p>',
    '<div class="authors"><p>Jianxiang Yu · Jiapeng Zhu · Bochen Lin · Qier Cui · Zichen Ding · Xiang Li <sup>†</sup></p><p class="affiliations">East China Normal University · Shanghai, China · † Corresponding author</p></div>',
    '<div class="metadata"><span>arXiv:2605.30723v1 · 2026-05-29</span><span>20 页 · 5 图 · 9 表 · 2 个算法</span></div>',
    '<aside class="translation-note"><strong>中文阅读版</strong><p>' + pair('依据 arXiv v1 官方 HTML 和同版 PDF 逐段翻译；图像取自官方 HTML，表格保留原始数值。',
       'Paragraph-aligned translation based on the official arXiv v1 HTML and matching PDF. Figures come from the official HTML; table values are preserved.') + '</p></aside>',
])
for child in article.children:
    if isinstance(child, Node) and child.tag not in ('h1',) and not child.has('ltx_authors'):
        render(child)
out.append('<footer class="source-footer" id="source"><h2>' + pair('来源与翻译说明', 'Source and translation notes') + '</h2>'
           '<p><a href="https://arxiv.org/abs/2605.30723v1">arXiv 同版页面 / arXiv v1</a> · '
           '<a href="https://github.com/jianxiangyu/MASA_">作者代码 / Author code</a> · '
           '<a href="../pdfs/MASA-2605.30723v1.pdf">原始 PDF / Original PDF</a></p>'
           '<p>' + pair('中文译文由 AI 制作，未经论文作者背书；引用、公式与原始排版请以原始 PDF 为准。',
             'The AI-generated Chinese translation is not endorsed by the authors; cite the original PDF for wording, equations, and layout.') + '</p></footer></article>')
unused = set(translations) - used
if unused:
    raise ValueError(f'unused MASA translations: {sorted(unused)[:15]}')
emit_paper(SLUG, '\n'.join(out), toc)
print(f'Built MASA: {len(used)} translated units, 5 figures, 9 tables, 2 algorithms, {len(reference_titles)} references')
