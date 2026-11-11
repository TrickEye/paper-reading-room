#!/usr/bin/env python3
"""Build Permission Denied PaperDocument from arXiv v1 HTML and source assets."""
from __future__ import annotations

import hashlib
from html.parser import HTMLParser
from pathlib import Path
import html
import json
import re
import subprocess
import sys
import unicodedata

ROOT = Path(__file__).resolve().parents[2]
PUBLIC = ROOT / "public"
SRC = ROOT / "data" / "permission-denied"
PDF = PUBLIC / "pdfs" / "Permission-Denied-2608.02670v1.pdf"
HTML_SOURCE = SRC / "arxiv.html"
PDF_URL = "https://arxiv.org/pdf/2608.02670v1"
HTML_URL = "https://arxiv.org/html/2608.02670v1"
EPRINT_URL = "https://arxiv.org/e-print/2608.02670v1"


class Node:
    def __init__(self, tag="", attrs=(), raw_start=None, raw_end=None, parent=None):
        self.tag = tag
        self.attrs = list(attrs)
        self.raw_start = raw_start
        self.raw_end = raw_end
        self.parent = parent
        self.children = []
        self.created = raw_start is None

    def attr(self, name, default=None):
        return next((v for k, v in self.attrs if k == name), default)

    def set_attr(self, name, value):
        self.attrs = [(k, v) for k, v in self.attrs if k != name]
        self.attrs.append((name, str(value)))
        self.created = True

    def add_class(self, value):
        classes = self.attr("class", "").split()
        for item in value.split():
            if item not in classes:
                classes.append(item)
        self.set_attr("class", " ".join(classes))

    def has(self, cls):
        return cls in self.attr("class", "").split()

    def descendants(self):
        for child in self.children:
            if isinstance(child, Node):
                yield child
                yield from child.descendants()

    def text(self):
        return "".join(child.text() if isinstance(child, Node) else child for child in self.children)

    def find_all(self, predicate):
        return [n for n in self.descendants() if predicate(n)]

    def replace(self, old, new):
        for i, child in enumerate(self.children):
            if child is old:
                self.children[i] = new
                if isinstance(new, Node):
                    new.parent = self
                old.parent = None
                return
        raise ValueError(f"node not found under {self.tag}")

    def insert_before(self, old, new):
        for i, child in enumerate(self.children):
            if child is old:
                self.children.insert(i, new)
                if isinstance(new, Node):
                    new.parent = self
                return
        raise ValueError(f"node not found under {self.tag}")


VOID = set("area base br col embed hr img input link meta param source track wbr".split())


class TreeParser(HTMLParser):
    def __init__(self, source):
        super().__init__(convert_charrefs=False)
        self.root = Node("root")
        self.stack = [self.root]
        self.feed(source)

    def handle_starttag(self, tag, attrs):
        node = Node(tag, attrs, self.get_starttag_text(), parent=self.stack[-1])
        self.stack[-1].children.append(node)
        if tag not in VOID:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        node = Node(tag, attrs, self.get_starttag_text(), parent=self.stack[-1])
        self.stack[-1].children.append(node)
        node.raw_end = ""

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, 0, -1):
            if self.stack[i].tag == tag:
                self.stack[i].raw_end = f"</{tag}>"
                del self.stack[i:]
                break

    def handle_data(self, data):
        self.stack[-1].children.append(data)

    def handle_entityref(self, name):
        self.stack[-1].children.append(f"&{name};")

    def handle_charref(self, name):
        self.stack[-1].children.append(f"&#{name};")

    def handle_comment(self, data):
        self.stack[-1].children.append(f"<!--{data}-->")

    def handle_decl(self, decl):
        self.stack[-1].children.append(f"<!{decl}>")


def serialize(node):
    if isinstance(node, str):
        return node
    if node.tag == "root":
        return "".join(serialize(c) for c in node.children)
    if node.created:
        attrs = "".join(
            f' {k}="{html.escape(str(v), quote=True)}"' if v is not None else f" {k}"
            for k, v in node.attrs
        )
        start = f"<{node.tag}{attrs}>"
    else:
        start = node.raw_start or f"<{node.tag}>"
    body = "".join(serialize(c) for c in node.children)
    if node.tag in VOID or node.raw_end == "":
        return start
    return start + body + (node.raw_end or f"</{node.tag}>")


def clean_text(node):
    value = html.unescape(node.text())
    value = unicodedata.normalize("NFC", value)
    return " ".join(value.split())


def tag(name, attrs=(), children=()):
    node = Node(name, attrs)
    node.children = list(children)
    for child in node.children:
        if isinstance(child, Node):
            child.parent = node
    return node


def text_node(value):
    return html.escape(str(value), quote=False)


def load_translations():
    paras = {}
    for path in sorted(SRC.glob("paragraph-translations-*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        overlap = set(paras) & set(data)
        if overlap:
            raise ValueError(f"duplicate paragraph translations: {sorted(overlap)}")
        paras.update(data)
    meta = json.loads((SRC / "translations-meta.json").read_text(encoding="utf-8"))
    tables = json.loads((SRC / "table-translations.json").read_text(encoding="utf-8"))["cells"]
    return paras, meta, tables


def pair_node(unit_id, zh, en_children):
    zh_node = tag("span", [("class", "zh translation"), ("lang", "zh-CN")], [text_node(zh)])
    en_node = tag("span", [("class", "en original"), ("lang", "en")], en_children)
    wrapper = tag("span", [("data-unit", unit_id), ("class", "bilingual-inline")], [zh_node, en_node])
    return wrapper


def set_pair_children(node, unit_id, zh):
    original = node.children
    node.children = [
        tag("span", [("class", "zh translation"), ("lang", "zh-CN")], [text_node(zh)]),
        tag("span", [("class", "en original"), ("lang", "en")], original),
    ]
    for child in node.children:
        child.parent = node
    node.set_attr("data-unit", unit_id)


def collect_sections(root):
    return root.find_all(lambda n: n.tag == "section" and n.attr("id"))


def ancestors(node):
    current = node.parent
    while current is not None:
        yield current
        current = current.parent


def source_tables(root):
    return root.find_all(lambda n: n.tag == "figure" and n.has("ltx_table"))


def source_figures(root):
    return root.find_all(lambda n: n.tag == "figure" and n.has("ltx_figure"))


def convert_equation_tables(root):
    """Keep aligned display math while preventing it from being counted as a data table."""
    equations = root.find_all(lambda n: n.tag == "table" and n.has("ltx_equation"))
    for equation in equations:
        equation.tag = "div"
        equation.add_class("equation-table")
        equation.set_attr("role", "math")
        for node in list(equation.descendants()):
            if node.tag in {"thead", "tbody", "tfoot"}:
                node.tag = "div"
                node.add_class("equation-body")
            elif node.tag == "tr":
                node.tag = "div"
                node.add_class("equation-row")
            elif node.tag in {"td", "th"}:
                node.tag = "div"
                node.add_class("equation-cell")
    return len(equations)


def table_grid(table):
    """Expand row/column spans from tbody, matching the audit script's comparison."""
    bodies = [n for n in table.children if isinstance(n, Node) and n.tag == "tbody"]
    rows = [r for b in bodies for r in b.children if isinstance(r, Node) and r.tag == "tr"]
    occupied, result = {}, []
    for i, row in enumerate(rows):
        col = 0
        cells = [c for c in row.children if isinstance(c, Node) and c.tag in {"td", "th"}]
        for cell in cells:
            while (i, col) in occupied:
                col += 1
            rowspan = int(cell.attr("rowspan", 1))
            colspan = int(cell.attr("colspan", 1))
            value = clean_text(cell)
            for y in range(i, i + rowspan):
                for x in range(col, col + colspan):
                    occupied[y, x] = value
            col += colspan
        columns = [x for y, x in occupied if y == i]
        result.append([occupied.get((i, x), "") for x in range(max(columns, default=-1) + 1)])
    return result


def build_source_records(root, paras, meta):
    source_ps = root.find_all(lambda n: n.tag == "p" and n.attr("id") and n.attr("id") in paras)
    found = {p.attr("id") for p in source_ps}
    missing = set(paras) - found
    if missing:
        raise ValueError(f"translated paragraph IDs absent from arXiv HTML: {sorted(missing)}")
    all_paras = []
    appendices = []
    for p in source_ps:
        section = next((a.attr("id") for a in ancestors(p) if a.tag == "section"), "")
        record = {"id": p.attr("id"), "kind": "p", "source": {"section": section, "source_version": "arXiv:2608.02670v1"}, "en": clean_text(p), "zh": paras[p.attr("id")]}
        (appendices if section in {f"Sx{i}" for i in range(9, 16)} else all_paras).append(record)
    (SRC / "main.json").write_text(json.dumps(all_paras, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (SRC / "appendix.json").write_text(json.dumps(appendices, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    figures = []
    for n, fig in enumerate(source_figures(root), 1):
        cap = next((x for x in fig.descendants() if x.tag == "figcaption"), None)
        if not cap:
            raise ValueError(f"figure {n} has no caption")
        figures.append({"number": n, "source_id": fig.attr("id"), "en": clean_text(cap), "zh": meta["figure_captions"][fig.attr("id")]})
    (SRC / "figures.json").write_text(json.dumps(figures, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    table_records = []
    for n, fig in enumerate(source_tables(root), 1):
        table = next((x for x in fig.descendants() if x.tag == "table"), None)
        cap = next((x for x in fig.descendants() if x.tag == "figcaption"), None)
        if not table or not cap:
            raise ValueError(f"table {n} is missing table or caption")
        table_records.append({"number": n, "source_id": fig.attr("id"), "rows": table_grid(table), "en": clean_text(cap), "zh": meta["table_captions"][fig.attr("id")]})
    (SRC / "tables.json").write_text(json.dumps(table_records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    refs = []
    for li in root.find_all(lambda n: n.tag == "li" and n.has("ltx_bibitem")):
        bib_id = li.attr("id")
        title_zh = meta["reference_titles"].get(bib_id)
        if not title_zh:
            raise ValueError(f"missing Chinese reference title: {bib_id}")
        refs.append({"id": bib_id, "en": clean_text(li), "zh": title_zh})
    (SRC / "references.json").write_text(json.dumps(refs, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def svg_dimensions(path):
    text = path.read_text(encoding="utf-8")
    m = re.search(r'<svg\b[^>]*\bwidth="([0-9.]+)pt"[^>]*\bheight="([0-9.]+)pt"', text)
    if not m:
        raise ValueError(f"cannot read SVG dimensions: {path}")
    width_pt, height_pt = map(float, m.groups())
    return round(width_pt * 4 / 3), round(height_pt * 4 / 3)


def image_source_url(path):
    return "assets/" + path.name


def decorate_paragraphs(root, paras):
    used = set()
    for p in list(root.find_all(lambda n: n.tag == "p" and n.attr("id") in paras)):
        pid = p.attr("id")
        parent = p.parent
        p.add_class("en")
        p.add_class("original")
        p.set_attr("lang", "en")
        p.set_attr("data-searchable", "true")
        zh = tag("p", [("class", "zh translation"), ("lang", "zh-CN"), ("data-searchable", "true")], [text_node(paras[pid])])
        wrapper = tag("div", [("class", "bilingual-unit"), ("data-unit", pid), ("id", "unit-" + re.sub(r"[^A-Za-z0-9_-]", "-", pid))], [zh, p])
        parent.replace(p, wrapper)
        used.add(pid)
    if used != set(paras):
        raise ValueError(f"paragraph translation mismatch, unused IDs: {sorted(set(paras) - used)}")


def decorate_headings(root, meta):
    used = set()
    article = root.find_all(lambda n: n.tag == "article" and n.has("ltx_document"))[0]
    for h in article.find_all(lambda n: n.tag in {"h1", "h2", "h3", "h4", "h5", "h6"} and any(c in n.attr("class", "").split() for c in ["ltx_title", "ltx_title_document", "ltx_title_abstract"])):
        en = clean_text(h)
        zh = meta["title_zh"] if h.tag == "h1" else meta["headings"].get(en)
        if not zh:
            raise ValueError(f"missing heading translation: {en!r}")
        if h.tag == "h1":
            h.set_attr("id", "paper-title")
        set_pair_children(h, "heading-" + (h.attr("id") or re.sub(r"[^A-Za-z0-9_-]", "-", en)), zh)
        used.add(en)
    return article


def decorate_footnotes(root, meta):
    for note in root.find_all(lambda n: n.attr("id", "").startswith("footnote") and n.has("ltx_note")):
        fid = note.attr("id")
        content = next((x for x in note.descendants() if x.has("ltx_note_content")), None)
        if content and fid in meta["footnotes"]:
            set_pair_children(content, fid, meta["footnotes"][fid])


def decorate_references(article, meta):
    for li in article.find_all(lambda n: n.tag == "li" and n.has("ltx_bibitem")):
        bib_id = li.attr("id")
        li.set_attr("data-searchable", "true")
        title = meta["reference_titles"][bib_id]
        zh = tag("p", [("class", "ltx_bib_title translation"), ("lang", "zh-CN"), ("data-searchable", "true")], [text_node("中文题名：" + title)])
        li.children.append(zh)
        zh.parent = li


def table_caption_pair(fig, number, meta, source_id):
    cap = next(x for x in fig.descendants() if x.tag == "figcaption")
    original = cap.children
    cap.children = [
        tag("span", [("class", "zh translation"), ("lang", "zh-CN")], [text_node(meta["table_captions"][source_id])]),
        tag("span", [("class", "en original"), ("lang", "en")], original),
    ]
    cap.set_attr("data-unit", f"T{number}.caption")
    cap.set_attr("data-searchable", "true")
    for child in cap.children:
        child.parent = cap


def decorate_tables(root, meta, table_translations):
    records = []
    for number, fig in enumerate(source_tables(root), 1):
        source_id = fig.attr("id")
        fig.set_attr("id", f"T{number}")
        fig.add_class("ltx_table")
        anchor = tag("span", [("id", source_id), ("class", "source-anchor"), ("aria-hidden", "true")], [])
        fig.insert_before(fig.children[0] if fig.children else None, anchor) if fig.children else fig.children.append(anchor)
        anchor.parent = fig
        table = next(x for x in fig.descendants() if x.tag == "table")
        table.set_attr("data-table-number", number)
        translations = table_translations.get(str(number), {})
        row_idx = 0
        for row in table.find_all(lambda n: n.tag == "tr"):
            cells = [c for c in row.children if isinstance(c, Node) and c.tag in {"td", "th"}]
            for col_idx, cell in enumerate(cells):
                cell.set_attr("data-searchable", "true")
                value = translations.get(str(row_idx), {}).get(str(col_idx))
                if value:
                    original = cell.children
                    cell.children = [
                        tag("span", [("class", "zh translation"), ("lang", "zh-CN")], [text_node(value)]),
                        tag("span", [("class", "en original"), ("lang", "en")], original),
                    ]
                    for child in cell.children:
                        child.parent = cell
            row_idx += 1
        # Put each complete source table in an accessible, locally scrolling container.
        table_parent = table.parent
        wrapper = tag("div", [("class", "table-scroll"), ("tabindex", "0"), ("role", "region"), ("aria-label", f"表 {number}，可横向滚动")], [table])
        table_parent.replace(table, wrapper)
        table_caption_pair(fig, number, meta, source_id)
        records.append(fig)
    return records


def decorate_figures(root, meta, source_pages):
    assets = []
    for number, fig in enumerate(source_figures(root), 1):
        source_id = fig.attr("id")
        filename = f"figure-{number:02d}.svg"
        path = SRC / "assets" / filename
        width, height = svg_dimensions(path)
        caption = meta["figure_captions"][source_id]
        old_caption = next(x for x in fig.descendants() if x.tag == "figcaption")
        en_children = old_caption.children
        cap = tag("figcaption", [("data-unit", f"F{number}.caption"), ("data-searchable", "true")], [
            tag("span", [("class", "zh translation"), ("lang", "zh-CN")], [text_node(caption)]),
            tag("span", [("class", "en original"), ("lang", "en")], en_children),
        ])
        old_children = fig.children
        fig.children = []
        fig.set_attr("id", f"F{number}")
        fig.set_attr("data-source-page", source_pages[number - 1])
        fig.set_attr("data-original-image", filename)
        fig.add_class("ltx_figure")
        fig.children.append(tag("span", [("id", source_id), ("class", "source-anchor"), ("aria-hidden", "true")], []))
        img = tag("img", [
            ("src", image_source_url(path)), ("alt", caption), ("width", width), ("height", height),
            ("loading", "lazy"), ("decoding", "async")
        ], [])
        button = tag("button", [("type", "button"), ("class", "figure-zoom"), ("aria-label", f"放大图 {number}")], [img])
        fig.children.extend([button, cap])
        for child in fig.children:
            child.parent = fig
        assets.append({
            "figure": number, "file": filename, "source_page": source_pages[number - 1],
            "method": "原 arXiv HTML 中的独立 SVG 图形文件，未重绘或裁切",
            "width": width, "height": height,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "source_url": HTML_URL
        })
    (SRC / "assets.json").write_text(json.dumps(assets, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def build_nav(article, meta):
    items = ['<a href="#abstract1" class="nav-main">摘要 / Abstract</a>']
    seen = {"abstract1"}
    for h in article.find_all(lambda n: n.tag in {"h2", "h3", "h4"} and n.attr("data-unit", "").startswith("heading-")):
        section = next((a for a in ancestors(h) if a.tag in {"section", "div"} and a.attr("id")), None)
        target = section.attr("id") if section else h.attr("id")
        if not target or target in seen:
            continue
        seen.add(target)
        label = meta["headings"].get(clean_text(next((x for x in h.children if isinstance(x, Node) and x.has("en")), h)), clean_text(h))
        cls = "nav-main" if h.tag == "h2" else "nav-sub"
        items.append(f'<a href="#{html.escape(target, quote=True)}" class="{cls}">{html.escape(label)}</a>')
    items.append('<a href="#source" class="nav-main">来源与翻译说明</a>')
    return "".join(items)


def decorate_abstract(article, meta):
    abstract = next((n for n in article.find_all(lambda n: n.tag == "div" and n.attr("id") == "abstract1")), None)
    if not abstract:
        raise ValueError("abstract container missing")
    p = next((n for n in abstract.descendants() if n.tag == "p" and n.attr("id") == "abstract1.1"), None)
    if not p:
        raise ValueError("abstract paragraph missing")
    parent = p.parent
    p.add_class("en")
    p.add_class("original")
    p.set_attr("lang", "en")
    p.set_attr("data-searchable", "true")
    zh = tag("p", [("class", "zh translation"), ("lang", "zh-CN"), ("data-searchable", "true")], [text_node(meta["abstract_zh"])])
    wrapper = tag("div", [("class", "bilingual-unit"), ("data-unit", "abstract1.1"), ("id", "unit-abstract")], [zh, p])
    parent.replace(p, wrapper)


def add_front_matter(article, meta):
    title = article.find_all(lambda n: n.tag == "h1" and n.attr("id") == "paper-title")[0]
    authors = next((n for n in article.children if isinstance(n, Node) and n.has("ltx_authors")), None)
    details = tag("div", [("class", "paper-meta")], [
        tag("p", [("class", "affiliations")], [text_node("Accomplish AI · 前三位作者贡献相同 / Accomplish AI · The first three authors contributed equally.")]),
        tag("p", [("class", "metadata")], [text_node("arXiv:2608.02670v1 · cs.CR · 2026 年 8 月 2 日 · 24 页 / August 2, 2026 · 24 pages")]),
    ])
    article.insert_before(authors, details) if authors else article.insert_before(title, details)
    # The author names are source material and need no translation.
    if authors:
        authors.add_class("authors")


def add_notes_and_footer(article, meta):
    note = tag("aside", [("class", "translation-note")], [
        tag("strong", [], [text_node("中文全文阅读版 / Bilingual full-text edition")]),
        tag("p", [], [
            tag("span", [("class", "zh translation"), ("lang", "zh-CN")], [text_node("正文与附录按原段落逐段配对；图表使用同版 arXiv 原始图形文件和完整可选择文本表格。引用、标识符、模型名、路径、命令和数值按原文保留。译文由 AI 生成，仅供阅读参考。")]),
            tag("span", [("class", "en original"), ("lang", "en")], [text_node("Main text and appendices are paired paragraph by paragraph. Figures use the standalone graphics from the same arXiv version; tables retain all selectable source cells. Citations, identifiers, model names, paths, commands, and values are preserved. The AI-generated translation is for reading assistance.")]),
        ]),
    ])
    abstract = next(n for n in article.children if isinstance(n, Node) and n.attr("id") == "abstract1")
    article.insert_before(abstract, note)
    footer = tag("footer", [("class", "source-footer"), ("id", "source")], [
        tag("p", [("class", "eyebrow")], [text_node("SOURCE & ATTRIBUTION")]),
        tag("h2", [], [
            tag("span", [("class", "zh translation"), ("lang", "zh-CN")], [text_node("来源与翻译说明")]),
            tag("span", [("class", "en original"), ("lang", "en")], [text_node("Source and translation notes")]),
        ]),
        tag("p", [], [
            tag("span", [("class", "zh translation"), ("lang", "zh-CN")], [text_node("原文：Dotan Davidovich、Yair Amar、Hai Rozencwajg、Or Hiltch，Accomplish AI。arXiv:2608.02670v1，2026 年 8 月 2 日。原始 PDF 为 24 页，SHA-256：")]),
            tag("span", [("class", "en original"), ("lang", "en")], [text_node("Original paper by Dotan Davidovich, Yair Amar, Hai Rozencwajg, and Or Hiltch, Accomplish AI. arXiv:2608.02670v1, August 2, 2026. The 24-page PDF SHA-256 is ")])
        ]),
        tag("p", [], [
            tag("span", [("class", "zh translation"), ("lang", "zh-CN")], [text_node("PDF SHA-256：")]),
            tag("span", [("class", "en original"), ("lang", "en")], [text_node("PDF SHA-256: ")]),
            text_node(hashlib.sha256(PDF.read_bytes()).hexdigest())
        ]),
        tag("p", [], [text_node("arXiv HTML · "), tag("a", [("href", HTML_URL)], [text_node(HTML_URL)]), text_node(" · e-print 源码 · "), tag("a", [("href", EPRINT_URL)], [text_node(EPRINT_URL)]), text_node(" · "), tag("a", [("href", "../pdfs/Permission-Denied-2608.02670v1.pdf")], [text_node("本地原始 PDF / local PDF")])]),
        tag("p", [], [
            tag("span", [("class", "zh translation"), ("lang", "zh-CN")], [text_node("四幅图均为同版 arXiv HTML 提供的独立 SVG 资源；15 张表直接保留为可选择文本的 HTML，并对照该版源文件记录表格数据。正文、图注、表注和参考文献题名均提供中文。")]),
            tag("span", [("class", "en original"), ("lang", "en")], [text_node("All four figures are standalone SVG assets supplied by the matching arXiv HTML. All 15 tables remain selectable HTML and are recorded against the matching source. Chinese is provided for the prose, figure and table captions, and bibliography titles.")]),
        ]),
    ])
    article.children.append(footer)
    footer.parent = article


def main():
    if not PDF.exists() or not HTML_SOURCE.exists():
        raise SystemExit("Missing local PDF or official arXiv HTML source.")
    paras, meta, table_translations = load_translations()
    source = HTML_SOURCE.read_text(encoding="utf-8")
    start = source.find('<article class="ltx_document')
    end = source.find("</article>", start)
    if start < 0 or end < 0:
        raise ValueError("could not locate the official HTML article")
    article_source = source[start:end + len("</article>")]
    root = TreeParser(article_source).root
    article = root.find_all(lambda n: n.tag == "article" and n.has("ltx_document"))[0]
    # Keep a pristine tree for machine-readable source records and exact table grids.
    pristine = TreeParser(article_source).root
    build_source_records(pristine, paras, meta)

    convert_equation_tables(root)
    decorate_paragraphs(root, paras)
    article = decorate_headings(root, meta)
    decorate_abstract(article, meta)
    add_front_matter(article, meta)
    decorate_footnotes(article, meta)
    decorate_references(article, meta)
    table_records = decorate_tables(root, meta, table_translations)
    decorate_figures(root, meta, [4, 5, 6, 7])
    add_notes_and_footer(article, meta)

    # Add exact source, version, and checksum metadata for future revisions.
    source_record = {
        "arxiv_id": "2608.02670",
        "version": "v1",
        "submitted_date": "2026-08-02",
        "pdf_url": PDF_URL,
        "html_url": HTML_URL,
        "eprint_url": EPRINT_URL,
        "pdf_file": PDF.name,
        "pdf_sha256": hashlib.sha256(PDF.read_bytes()).hexdigest(),
        "source_html_sha256": hashlib.sha256(HTML_SOURCE.read_bytes()).hexdigest(),
    }
    source_archive = SRC / "source.tar"
    if source_archive.exists():
        source_record["source_archive_sha256"] = hashlib.sha256(source_archive.read_bytes()).hexdigest()
    (SRC / "source.json").write_text(json.dumps(source_record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    sys.path.insert(0, str(ROOT / 'scripts'))
    from paper_document import emit_paper, toc_from_html
    article.set_attr("id", "paper")
    article.set_attr("lang", "zh-CN")
    emit_paper('permission-denied', serialize(article), toc_from_html(build_nav(article, meta)))
    print(f"Built Permission Denied document: {len(paras)} paired prose paragraphs, 4 figures, {len(table_records)} tables, 27 references.")


if __name__ == "__main__":
    main()
