from html.parser import HTMLParser
import html,unicodedata

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


