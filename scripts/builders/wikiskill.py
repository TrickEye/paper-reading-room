"""Build WikiSkill from its versioned LaTeXML source and reviewed translations."""

import base64
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
from builders.html_tree import Node, TreeParser, clean_text, serialize
from builders.skill_consumption import esc, inline, pair, plain, unit_attrs
from paper_document import emit_paper

SLUG = 'wikiskill'
SOURCE = ROOT / 'data' / SLUG
TABLE_PAGES = (8, 10, 11, 13, 20, 20, 22)
TABLE_HEADER_ROWS = (1, 1, 3, 2, 1, 1, 1)
MATH_MARKER = re.compile(r'⟦(\d+)⟧')
CITATION_MARKER = re.compile(r'〔(\d+)〕')
CELL_LABELS = {
    'Model': '模型', 'Method': '方法', 'Avg.': '平均', 'No skill': '无技能',
    'Skill Source': '技能来源', 'None': '无',
    'WikiSkill Components': 'WikiSkill 组件', 'Benchmarks': '基准',
    'Inference Agent': '推理智能体', 'Skill Proposer': '技能提议者', 'Wiki Access': 'Wiki 访问权限',
    'Category': '类别', 'Skills': '技能', 'Wiki Patterns': 'Wiki 模式',
    'Create (Proposed / Accepted)': '创建（提出 / 接受）',
    'Edit (Proposed / Accepted)': '编辑（提出 / 接受）',
    'Create': '创建', 'Edit': '编辑', 'Avg. Length': '平均长度',
    'By Model (All-Dataset Average)': '按模型（所有数据集平均）',
    'By Benchmark (All-Model Average)': '按基准（所有模型平均）',
    'By Model': '按模型', 'By Benchmark': '按基准',
    'Early (Iter 0–1)': '早期（迭代 0–1）', 'Mid (Iter 2–4)': '中期（迭代 2–4）',
    'Late (Iter 5–7)': '后期（迭代 5–7）',
    'Benchmark': '基准', 'Interaction': '交互', 'Train': '训练', 'Val': '验证', 'Test': '测试',
    'Environment Tools': '环境工具', 'Single-Step': '单步', 'Multi-Step': '多步',
    'None (Direct Reasoning)': '无（直接推理）', 'Admissible Actions': '允许的动作',
    'Framework': '框架', 'Per-Iteration Formula': '每轮迭代公式', 'Complexity': '复杂度',
}
SHARED_LABELS = {
    'WikiSkill', 'Trace2Skill', 'SkillOpt', 'EvoSkill', 'LiveMath', 'SealQA', 'SpreadSheet', 'OfficeQA', 'ALFWorld',
    'Qwen-3.5-4B', 'Qwen-3.5-9B', 'Qwen-3.6-27B', 'Gemma-4-31B', 'Gemini-3.5-Flash',
    'bash', 'glob, grep, read', 'web_search, read_file',
}


def read_tsv(filename):
    entries = {}
    for line in (SOURCE / filename).read_text(encoding='utf-8').splitlines():
        uid, value = line.split('\t', 1)
        if uid in entries or not value.strip():
            raise ValueError(f'{filename}: duplicate or empty translation for {uid}')
        entries[uid] = value
    return entries


def translated_html(node, translation):
    math = node.find_all(lambda c: c.tag == 'math')
    used = sorted(int(marker) for marker in MATH_MARKER.findall(translation))
    if used != list(range(1, len(math) + 1)):
        raise ValueError(f'{node.attr("id") or node.parent.attr("id")}: mismatched inline formulas {used}')

    def replace(match):
        # Source IDs are reserved for the original rendering.
        return re.sub(r' id="[^"]+"', '', serialize(math[int(match[1]) - 1]))

    citations = node.find_all(lambda c: c.tag == 'cite')
    cited = sorted(int(marker) for marker in CITATION_MARKER.findall(translation))
    if cited != list(range(1, len(citations) + 1)):
        raise ValueError(f'{node.attr("id") or node.parent.attr("id")}: mismatched citations {cited}')
    result = MATH_MARKER.sub(replace, esc(translation))
    return CITATION_MARKER.sub(lambda match: inline(citations[int(match[1]) - 1]), result)


def paired_unit(tag, uid, chinese, english, cls=''):
    return f'<{tag} class="{cls}" {unit_attrs(uid)}>{pair(chinese, english)}</{tag}>'


def span_size(cell, dimension):
    value = cell.attr(dimension)
    if value:
        return int(value)
    match = re.search(rf'\bltx_{dimension}_(\d+)\b', cell.attr('class', ''))
    return int(match[1]) if match else 1


def render_cell(cell, header):
    label = ' '.join(plain(cell).split())
    english = inline(cell)
    icons = [c for c in cell.descendants() if c.has('fa-check') or c.has('fa-times')]
    if icons:
        enabled = icons[0].has('fa-check')
        symbol, description = ('✓', '可访问 / Access enabled') if enabled else ('✗', '无访问权限 / Access disabled')
        english = f'<span role="img" aria-label="{description}">{symbol}</span>'
    if label in CELL_LABELS:
        content = pair(esc(CELL_LABELS[label]), english)
    else:
        if (label and label not in SHARED_LABELS and not cell.find_all(lambda c: c.tag == 'math')
                and not re.fullmatch(r'[\d%+./−\-–\s]+', label)):
            raise ValueError(f'Untranslated cell {cell.attr("id")}: {label}')
        content = english

    attrs = ''.join(f' {dimension}="{size}"' for dimension in ('rowspan', 'colspan')
                    if (size := span_size(cell, dimension)) > 1)
    is_group = span_size(cell, 'colspan') > 1
    tag = 'th' if header or is_group else 'td'
    if tag == 'th':
        scope = 'colgroup' if is_group else 'col'
        attrs += f' scope="{scope}"' if header else ''
    background = re.search(r'--ltx-bg-color:\s*(#[\da-fA-F]{6})', cell.attr('style', ''))
    if background:
        attrs += f' class="source-bg" style="--ltx-bg-color:{background[1]}"'
    return f'<{tag}{attrs}>{content}</{tag}>'


class WikiSkill:
    def __init__(self):
        self.metadata = json.loads((SOURCE / 'source.json').read_text(encoding='utf-8'))
        self.assets = {a['figure']: a for a in json.loads((SOURCE / 'assets.json').read_text(encoding='utf-8'))}
        self.translations = read_tsv('translations.tsv')
        self.listings = read_tsv('listings.tsv')
        self.reference_titles = read_tsv('reference-titles.tsv')
        source_tree = TreeParser((SOURCE / 'arxiv.html').read_text(encoding='utf-8')).root
        self.source = next(node for node in source_tree.descendants() if node.has('ltx_document'))
        self.toc = []

    def unit(self, node, key, tag, uid=None, cls=''):
        zh = translated_html(node, self.translations.pop(key))
        english = inline(node).strip()
        return paired_unit(tag, uid or key, zh, english, cls)

    def heading(self, node, uid, level):
        if level in (2, 3):
            self.toc.append({'id': uid, 'label': self.translations[uid], 'level': level})
        return self.unit(node, uid, f'h{level}', uid + '.heading')

    def figure(self, node):
        number = int(node.attr('id').rsplit('F', 1)[1])
        uid = f'F{number}'
        asset = self.assets[number]
        image = asset['file']
        caption = next(c for c in node.descendants() if c.tag == 'figcaption')
        label = self.translations[uid + '.caption'].split('｜', 1)[1].split('。', 1)[0]
        return (f'<figure id="{uid}" class="ltx_figure" data-source-page="{asset["page"]}" data-original-image="{image}">'
                f'<button class="figure-zoom" type="button" aria-label="放大图 {number}">'
                f'<img src="assets/{image}" alt="{esc(label)}" width="{asset["width"]}" height="{asset["height"]}" '
                'loading="lazy" decoding="async"></button>'
                + self.unit(caption, uid + '.caption', 'figcaption') + '</figure>')

    def table(self, node):
        number = int(node.attr('id').rsplit('T', 1)[1])
        uid = f'T{number}'
        grid = next(c for c in node.descendants() if c.has('ltx_tabular'))
        caption = next(c for c in node.descendants() if c.tag == 'figcaption')
        rows = grid.find_all(lambda c: c.has('ltx_tr') or c.tag == 'tr')
        sections = {'thead': [], 'tbody': []}
        for index, row in enumerate(rows):
            header = index < TABLE_HEADER_ROWS[number - 1]
            cells = [c for c in row.children if isinstance(c, Node)]
            case = 'thead' if header else 'tbody'
            sections[case].append('<tr>' + ''.join(render_cell(c, header) for c in cells) + '</tr>')
        table = '<table>' + ''.join(
            f'<{section}>{"".join(items)}</{section}>' for section, items in sections.items()) + '</table>'
        return (f'<figure id="{uid}" class="ltx_table" data-source-page="{TABLE_PAGES[number - 1]}">'
                f'<div class="table-scroll" role="region" tabindex="0" aria-label="表 {number}">{table}</div>'
                + self.unit(caption, uid + '.caption', 'figcaption') + '</figure>')

    def prompt(self, node):
        link = next(c.attr('href') for c in node.descendants()
                    if c.tag == 'a' and c.attr('href', '').startswith('data:text/plain;base64,'))
        # The attached listing retains literal punctuation and original indentation.
        english = base64.b64decode(link.split(',', 1)[1], validate=True).decode('utf-8')
        lines = node.find_all(lambda c: c.has('ltx_listingline'))
        chinese = []
        for line, original in zip(lines, english.split('\n'), strict=True):
            uid = line.attr('id')
            if not original.strip():
                chinese.append(original)
                continue
            indent = original[:len(original) - len(original.lstrip())]
            chinese.append(indent + self.listings.pop(uid))
        uid = node.attr('id')
        translation = '\n'.join(chinese)
        return f'<div class="code-pair" {unit_attrs(uid)}>{pair(esc(translation), esc(english), "pre")}</div>'

    def algorithm(self, node):
        caption = next(c for c in node.descendants() if c.tag == 'figcaption')
        lines = []
        for index, line in enumerate(node.find_all(lambda c: c.has('ltx_listingline'))):
            uid = line.attr('id')
            zh = translated_html(line, self.listings.pop(uid))
            # The PDF marks the first line as Require and numbers the procedure from 1.
            en = ''.join(inline(c) for c in line.children if not
                         (isinstance(c, Node) and c.has('ltx_tag_listingline'))).strip(' \n\r\t')
            if index == 0:
                en = '<strong>Require:</strong> ' + en
            else:
                indentation = en[:len(en) - len(en.lstrip())]
                zh, en = f'{index}: ' + indentation + zh, f'{index}: ' + en
            lines.append(paired_unit('div', uid, zh, en, 'algorithm-line'))
        return ('<figure id="alg1" class="algorithm" data-source-page="19">'
                + self.unit(caption, 'alg1.caption', 'figcaption') + ''.join(lines) + '</figure>')

    def bibliography(self, node):
        title = next(c for c in node.children if isinstance(c, Node) and c.tag == 'h2')
        items = []
        for item in node.find_all(lambda c: c.has('ltx_bibitem')):
            uid = item.attr('id')
            english = inline(item)
            chinese = esc(self.reference_titles.pop(uid)) + '。' + english
            items.append(paired_unit('li', uid, chinese, english, 'ltx_bibitem'))
        return ('<section id="bib" class="ltx_bibliography">' + self.heading(title, 'bib', 2)
                + '<ol class="ltx_biblist">' + ''.join(items) + '</ol></section>')

    def body(self, node):
        if isinstance(node, str):
            return ''
        uid = node.attr('id')
        if node.has('ltx_bibliography'):
            return self.bibliography(node)
        if node.tag == 'section' or node.has('ltx_abstract'):
            heading = next(c for c in node.children if isinstance(c, Node) and re.fullmatch(r'h[2-6]', c.tag))
            anchor = 'abstract' if node.has('ltx_abstract') else uid
            level = 2 if anchor == 'abstract' else int(heading.tag[1])
            content = self.heading(heading, anchor, level)
            content += ''.join(self.body(c) for c in node.children if c is not heading)
            return f'<section id="{esc(anchor)}" class="{esc(node.attr("class"))}">{content}</section>'
        if node.tag == 'figure':
            if node.has('ltx_figure'):
                return self.figure(node)
            if node.has('ltx_table'):
                return self.table(node)
            if node.has('ltx_float_algorithm'):
                return self.algorithm(node)
            raise ValueError(f'Unrecognized figure {uid}')
        if node.has('ltx_equation'):
            math = next(c for c in node.descendants() if c.tag == 'math')
            number = next(c for c in node.descendants() if c.has('ltx_tag_equation'))
            return f'<div id="{esc(uid)}" class="equation" role="math">{serialize(math)} <span>{esc(clean_text(number))}</span></div>'
        if node.has('ltx_listing'):
            return self.prompt(node)
        if node.has('ltx_p') and clean_text(node):
            return self.unit(node, uid, 'p', cls='ltx_p')
        content = ''.join(self.body(c) for c in node.children)
        if node.tag in ('ol', 'ul', 'li'):
            return f'<{node.tag}>{content}</{node.tag}>'
        return content

    def build(self):
        title = next(c for c in self.source.children if isinstance(c, Node) and c.tag == 'h1')
        names = ' · '.join(f'{esc(author)}<sup>{"1,2" if author == "Tu Vu" else "1"}</sup>'
                           for author in self.metadata['authors'])
        affiliations = pair('¹ Google Research　² 弗吉尼亚理工大学', '¹ Google Research　² Virginia Tech')
        addresses = 'lytang@google.com, ttvu@google.com'
        contact = pair(f'通讯作者：{addresses}', f'Corresponding author(s): {addresses}')
        copyright = pair('© 2026 Google。保留所有权利。', '© 2026 Google. All rights reserved')
        front = (self.heading(title, 'paper-title', 1) + f'<div class="authors"><p>{names}</p>'
                 f'<p class="affiliations">{affiliations}</p><p>{contact}</p><p>{copyright}</p></div>'
                 f'<div class="metadata"><span>arXiv:{self.metadata["version"]}</span>'
                 f'<span>{self.metadata["pdf_display_date"]}</span></div>')
        body = ''.join(self.body(c) for c in self.source.children if isinstance(c, Node) and
                       (c.tag in ('section', 'figure') or c.has('ltx_abstract')))
        if self.translations or self.listings or self.reference_titles:
            raise ValueError(f'Unused translations: {list(self.translations)}, {list(self.listings)}, {list(self.reference_titles)}')
        credit = pair('中文译文依据 arXiv v1 制作。引用请以原作 PDF 为准。',
                      'Chinese translation based on arXiv v1. Cite the original PDF.')
        footer = (f'<footer id="source" class="source-footer"><h2>{pair("原文来源", "Source")}</h2><p>{credit}</p>'
                  f'<p><a href="https://arxiv.org/abs/{self.metadata["version"]}">arXiv</a> · '
                  f'<a href="../pdfs/{self.metadata["pdf_file"]}">PDF</a> · '
                  f'<a href="{self.metadata["license"]}">CC BY 4.0</a></p></footer>')
        return emit_paper(SLUG, '<article id="paper" class="ltx_document" lang="zh-CN">' + front + body + footer + '</article>', self.toc)


if __name__ == '__main__':
    print(WikiSkill().build().relative_to(ROOT))
