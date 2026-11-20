"""Build the SkillLens paper from versioned arXiv HTML and paired translations."""

import html
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
from builders.html_tree import Node, TreeParser, clean_text, serialize
from paper_document import emit_paper

SLUG = 'skill-consumption'
SOURCE = ROOT / 'data' / SLUG
PROMPT_TABLES = {2, 3, 4, 5, 6, 9}
TABLE_PAGES = (6, 16, 17, 18, 19, 20, 20, 21, 21, 21, 22, 22, 23, 23, 24)
TABLE_HEADERS = {11: 2, 14: 1, 15: 1}
PROVIDERS = {'openai.png': 'GPT', 'gemini-color.png': 'Gemini', 'qwen-color.png': 'Qwen'}
CELL_TRANSLATIONS = {
    'Target': '目标', 'Base': '基线', 'Embodied: ALFWorld': '具身交互：ALFWorld',
    'Productivity: SpreadsheetBench': '生产力软件：SpreadsheetBench',
    'Coding: SWE-bench-Verified': '编程：SWE-bench-Verified',
    'Web Search: SEAL-0': '网页搜索：SEAL-0', 'Tool Calling: BFCL-v4': '工具调用：BFCL-v4',
    'Parameter': '参数', 'Value': '值', 'Max modes per trajectory': '每条轨迹的最大模式数',
    'Merge group size': '合并组大小', 'Max skill characters': '技能字符数上限',
    'Max skills per extraction': '每次提取的技能数上限', 'Temperature': '温度',
    'Format': '格式', 'Extractor': '提取器', 'Guidance': '引导', '𝚫 vs Original': '相对原始技能的 Δ',
    'Domain': '领域', 'No Skill': '无技能', 'Original': '原始技能',
    'Plausibility (7-dim)': '合理性（7 维）', 'Validated (3-dim)': '经验证（3 维）',
    'Plaus.': '合理性', 'Valid.': '经验证', 'Average (9 cells)': '平均（9 个单元格）',
    'Dimension': '维度', 'Better-rate': '胜出率',
    'Guided rubric judgment (3 validated dimensions)': '评分准则引导的判断（3 个经验证的维度）',
    'Failure Mechanism Encoding': '失败机制编码', 'Actionable Specificity': '可执行的具体性',
    'High-Risk Action Blacklist': '高风险操作黑名单',
}


def read_translations(name):
    records = {}
    for line in (SOURCE / name).read_text(encoding='utf-8').splitlines():
        key, value = line.split('\t', 1)
        if key in records or not value.strip():
            raise ValueError(f'{name}: duplicate or empty translation for {key}')
        records[key] = value
    return records


def esc(value):
    return html.escape(str(value), quote=True)


def plain(node):
    if isinstance(node, str):
        return html.unescape(node)
    if node.tag == 'annotation':
        return ''
    return ''.join(plain(child) for child in node.children)


def inline(node):
    """Keep the source's prose, links, typography, and MathML without arXiv layout."""
    if isinstance(node, str):
        return node
    if node.tag == 'math':
        return serialize(node)
    if node.tag == 'img':
        provider = PROVIDERS[Path(node.attr('src')).name]
        return f'<span class="model-provider">{provider}</span> '
    if node.has('ltx_role_footnote'):
        return '<sup><a href="#footnote1">1</a></sup>'
    if node.tag == 'br':
        return '<br> '
    body = ''.join(inline(child) for child in node.children)
    if node.tag == 'a':
        href = re.sub(r'^#(?:S\d+|A\d+)\.([FT]\d+)$', r'#\1', node.attr('href'))
        return f'<a href="{esc(href)}">{body}</a>'
    for prop, name in (('--ltx-bg-color', 'bg'), ('--ltx-fg-color', 'fg')):
        match = re.search(rf'{prop}:\s*(#[\da-fA-F]{{6}})', node.attr('style', ''))
        if match:
            body = f'<span class="source-{name}" style="{prop}:{match[1]}">{body}</span>'
    if node.has('ltx_font_bold'):
        body = f'<strong>{body}</strong>'
    if node.has('ltx_font_typewriter'):
        body = f'<code>{body}</code>'
    if node.tag in {'em', 'i', 'sup', 'sub', 'cite'}:
        return f'<{node.tag}>{body}</{node.tag}>'
    return body


def unit_attrs(uid):
    uid = esc(uid)
    return f'id="{uid}" data-unit="{uid}" data-searchable="true"'


def pair(zh, en, tag='span'):
    return (f'<{tag} class="zh translation" lang="zh-CN">{zh}</{tag}>'
            f'<{tag} class="en original" lang="en">{en}</{tag}>')


def zh_text(text):
    text = esc(text).replace(r'\n', '<br>')
    return re.sub(r'⟦([+-])(.+?)⟧', lambda m: (
        '<mark class="source-highlight source-highlight-' + ('good' if m[1] == '+' else 'bad') +
        '">' + m[2] + '</mark>'), text)


class Paper:
    def __init__(self):
        self.source = json.loads((SOURCE / 'source.json').read_text())
        self.figures = {item['figure']: item for item in json.loads((SOURCE / 'assets.json').read_text())}
        self.translations = read_translations('translations.tsv')
        self.table_translations = read_translations('table-translations.tsv')
        self.titles = read_translations('reference-titles.tsv')
        root = TreeParser((SOURCE / 'arxiv.html').read_text(encoding='utf-8')).root
        self.article = next(node for node in root.descendants() if node.has('ltx_document'))
        self.nodes = {node.attr('id'): node for node in self.article.descendants() if node.attr('id')}
        self.toc = []

    def heading(self, uid, level, english):
        label = self.translations.pop(uid)
        if level <= 3 and uid != 'paper-title':
            self.toc.append({'id': uid, 'label': label, 'level': level})
        return f'<h{level} {unit_attrs(uid + ".heading")}>{pair(esc(label), english)}</h{level}>'

    def paragraph(self, node, translations, class_name='ltx_p'):
        uid = node.attr('id')
        zh = zh_text(translations.pop(uid))
        citations = [inline(cite) for cite in node.descendants() if cite.tag == 'cite']
        if citations:
            zh += '<small class="source-citations">' + ' '.join(citations) + '</small>'
        notes = [note for note in node.descendants() if note.has('ltx_role_footnote')]
        if notes:
            zh += ' <sup><a href="#footnote1">1</a></sup>'
        result = f'<p class="{class_name}" {unit_attrs(uid)}>{pair(zh, inline(node))}</p>'
        for note in notes:
            note_id = note.attr('id')
            url = next(link for link in note.descendants() if link.tag == 'a')
            text = self.translations.pop(note_id)
            result += f'<p class="paper-footnote" {unit_attrs(note_id)}>{pair("1. " + esc(text), "1. " + inline(url))}</p>'
        return result

    def figure(self, node):
        number = int(re.search(r'F(\d+)$', node.attr('id'))[1])
        image = self.figures[number]
        filename = image['file']
        uid = f'F{number}'
        caption = next(child for child in node.children if isinstance(child, Node) and child.tag == 'figcaption')
        label = self.translations.pop(uid + '.caption')
        return (
            f'<figure id="{uid}" class="ltx_figure" data-source-page="{image["page"]}" data-original-image="{filename}">'
            f'<button class="figure-zoom" type="button" aria-label="放大图 {number}">'
            f'<img src="assets/{filename}" alt="{esc(label)}" width="{image["width"]}" '
            f'height="{image["height"]}" loading="lazy" decoding="async"></button>'
            f'<figcaption {unit_attrs(uid + ".caption")}>{pair(esc(label), inline(caption))}</figcaption></figure>'
        )

    def table_cell(self, node, heading):
        uid = node.attr('id')
        contents = node.find_all(
            lambda child: child.has('ltx_p') and child.attr('id') in self.table_translations
        )
        if contents:
            body = ''.join(self.paragraph(child, self.table_translations, 'table-paragraph') for child in contents)
        else:
            value = ' '.join(plain(node).split())
            translation = self.table_translations.pop(uid, None) or CELL_TRANSLATIONS.get(value)
            body = inline(node)
            if translation:
                chinese = zh_text(translation)
                if any(child.has('ltx_font_bold') for child in node.children if isinstance(child, Node)):
                    title, sep, rest = chinese.partition('：')
                    chinese = f'<strong>{title}</strong>{sep}{rest}'
                body = pair(chinese, body)
            elif value and not re.fullmatch(
                r'[#%✓✗—–−+.<>\d\-\s]+|EE|TE|p|σ-r|(?:ALFWorld|Gemini|Spreadsheet- Bench|SWE-bench)|'
                r'(?:CC Opus |CC Sonnet |Codex GPT-|GPT-|Qwen)?[\d.]+(?:-(?:mini|nano|Pro|FL|\d+B))?',
                value,
            ):
                raise ValueError(f'Untranslated table cell {uid}: {value}')
        tag = 'th' if heading or node.tag == 'th' else 'td'
        span = ''.join(f' {attr}="{int(node.attr(attr))}"' for attr in ('rowspan', 'colspan') if node.attr(attr))
        scope = ''
        if tag == 'th':
            scope = ' scope="col"' if heading else ' scope="row"'
            if node.attr('colspan'):
                scope = ' scope="colgroup"'
        return f'<{tag}{scope}{span}>{body}</{tag}>'

    def table(self, node):
        number = int(re.search(r'T(\d+)$', node.attr('id'))[1])
        uid = f'T{number}'
        caption = next(child for child in node.children if isinstance(child, Node) and child.tag == 'figcaption')
        label = zh_text(self.translations.pop(uid + '.caption'))
        if number in PROMPT_TABLES:
            # LaTeXML emits each boxed prompt as SVG layout containing real text.
            paragraphs = node.find_all(lambda child: child.has('ltx_p'))
            content = ''.join(self.paragraph(child, self.table_translations, 'prompt-paragraph') for child in paragraphs)
            grid = f'<table class="prompt-template"><tbody><tr><td>{content}</td></tr></tbody></table>'
        else:
            source = next(child for child in node.children if isinstance(child, Node) and child.tag == 'table')
            grouped_rows = {'thead': [], 'tbody': []}
            for i, row in enumerate(source.find_all(lambda child: child.tag == 'tr')):
                heading = row.parent.tag == 'thead' or i < TABLE_HEADERS.get(number, 0)
                cells = [cell for cell in row.children if isinstance(cell, Node)]
                group = 'thead' if heading else 'tbody'
                grouped_rows[group].append('<tr>' + ''.join(self.table_cell(cell, heading) for cell in cells) + '</tr>')
            grid = '<table>' + ''.join(f'<{tag}>{"".join(rows)}</{tag}>' for tag, rows in grouped_rows.items() if rows) + '</table>'
        return (
            f'<figure id="{uid}" class="ltx_table" data-source-page="{TABLE_PAGES[number - 1]}">'
            f'<div class="table-scroll" role="region" tabindex="0" aria-label="表 {number}">{grid}</div>'
            f'<figcaption {unit_attrs(uid + ".caption")}>{pair(label, inline(caption))}</figcaption></figure>'
        )

    def bibliography(self, node):
        entries = []
        for item in node.find_all(lambda child: child.has('ltx_bibitem')):
            uid = item.attr('id')
            # Preserve all author, venue, date and URL fields in the source citation.
            english = inline(item)
            label = esc(self.titles.pop(uid)) + '。'
            entries.append(f'<li class="ltx_bibitem" {unit_attrs(uid)}>{pair(label + english, english)}</li>')
        heading = self.heading('bib', 2, 'References')
        return f'<section id="bib" class="ltx_bibliography">{heading}<ol class="ltx_biblist">{"".join(entries)}</ol></section>'

    def body(self, node):
        if not isinstance(node, Node):
            return ''
        uid = node.attr('id')
        if node.has('ltx_bibliography'):
            return self.bibliography(node)
        if node.tag == 'section':
            title = next(child for child in node.children if isinstance(child, Node) and child.tag in {'h2', 'h3', 'h4'})
            level = int(title.tag[1])
            numbered = re.match(r'^(\d+(?:\.\d+)?|[A-H]\.\d+) ', self.translations[uid])
            english = (numbered[1] + ' ' if numbered else '') + inline(title)
            heading = self.heading(uid, level, english)
            content = ''.join(self.body(child) for child in node.children)
            return f'<section id="{uid}" class="{node.attr("class")}">{heading}{content}</section>'
        if node.tag == 'figure':
            return self.figure(node) if node.has('ltx_figure') else self.table(node)
        if node.has('ltx_equation'):
            math = next(child for child in node.descendants() if child.tag == 'math')
            number = next(child for child in node.descendants() if child.has('ltx_tag_equation'))
            return f'<div id="{uid}" class="equation" role="math">{serialize(math)} <span>{esc(clean_text(number))}</span></div>'
        if node.has('ltx_p') and clean_text(node):
            class_name = 'finding' if '.pic' in uid and not uid.startswith('p4.') else 'ltx_p'
            return self.paragraph(node, self.translations, class_name)
        content = ''.join(self.body(child) for child in node.children)
        if node.tag in {'ul', 'ol', 'li'}:
            return f'<{node.tag}>{content}</{node.tag}>'
        return content

    def build(self):
        title = self.heading('paper-title', 1, esc(clean_text(self.nodes['p3.1'])))
        authors = inline(self.nodes['p3.2'])
        affiliations = pair('¹ 复旦大学　² 微软研究院　³ 上海交通大学', inline(self.nodes['p3.3']))
        abstract_title = self.heading('abstract', 2, 'Abstract')
        abstract = ''.join(self.body(child) for child in self.nodes['p4.pic1.1'].children)
        body = ''.join(self.body(child) for child in self.article.children if isinstance(child, Node) and child.tag == 'section')
        if self.translations or self.table_translations or self.titles:
            raise ValueError(f'Unused translations: {list(self.translations)}, {list(self.table_translations)}, {list(self.titles)}')
        credit = pair(
            '原作由 Zisu Huang 等撰写，采用 CC BY 4.0 许可。中文译文为本阅读室制作的改编。',
            'Original by Zisu Huang et al., licensed under CC BY 4.0. The Chinese translation is an adaptation prepared for this reading room.',
        )
        article = (
            f'<article id="paper" class="ltx_document" lang="zh-CN">{title}'
            f'<div class="authors"><p>{authors}</p><p class="affiliations">{affiliations}</p></div>'
            '<div class="metadata"><span>arXiv:2605.23899v1</span><span>2026-05-22</span></div>'
            f'<section id="abstract" class="abstract">{abstract_title}{abstract}</section>{body}'
            '<footer id="source" class="source-footer">'
            f'<h2>{pair("原文来源", "Source")}</h2><p>{credit}</p>'
            f'<p><a href="https://arxiv.org/abs/{self.source["version"]}">arXiv</a> · '
            f'<a href="../pdfs/{self.source["pdf_file"]}">PDF</a> · '
            f'<a href="{self.source["license"]}">CC BY 4.0</a></p></footer></article>'
        )
        return emit_paper(SLUG, article, self.toc)


if __name__ == '__main__':
    print(Paper().build().relative_to(ROOT))
