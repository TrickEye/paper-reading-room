# 新版论文数据的制作与接入

本文的路径与命令相对仓库根目录执行。制作源可以沿用逐段 JSON，也可以保留与原文对应的 HTML；发布边界固定为 `PaperDocument v1`、独立原图和轻量阅读外壳。完整块类型与运行时行为以仓库 `docs/reader-architecture.md` 为准。

## 交付物与配置

新增论文需要同步以下入口，不能只写一个 HTML 页面：

| 入口 | 当前约定 |
|---|---|
| `data/<paper-id>/` | 原文、译文、图表、目录及来源记录；原图放 `assets/` |
| `public/pdfs/<filename>.pdf` | 同版原始 PDF，保存原始字节 |
| `data/catalog.json` | 增加 `id`、`pdf`、真实 `figures`／`tables` 数量、`builder` 脚本名 |
| `data/reader-meta.json` | 增加同 ID 的阅读器元数据，字段见下例 |
| `scripts/builders/<builder>.py` | 读取该论文源数据，构造正文和目录，再调用 `emit_paper` |
| `reader/<paper-id>.css` | 当前构建器对非 ACE 论文都会读取此文件；无专有样式时创建空文件 |
| 索引、阅读说明、浏览器测试 | 更新既有索引卡片、内容范围和新论文验收；不改动其他论文正文 |

`reader-meta.json` 的新条目示例（值以实际论文为准）：

```json
{
  "title": "论文简称 · 中文全文与逐段对照",
  "description": "依据同版原文制作的双语阅读页。",
  "brand": "论文简称",
  "authors": ["原作者姓名"],
  "defaultMode": "dual",
  "storageKey": "ace-reader-",
  "summary": "原图保留 · 按需加载"
}
```

目前除 SkillCAT 外共用 `ace-reader-` 偏好键。入口脚本有相应兼容映射；不要只修改元数据就宣称新增论文具有独立偏好。若另有独立偏好的产品需求，应同时调整阅读器与加载入口。

`source.json` 至少保存已核实的版本、PDF 来源地址、PDF 文件名与 `pdf_sha256`；摘要按实际 PDF 字节计算。存在该文件时，站点检查器会核对 `pdf_sha256`。`assets.json` 保存实际图号、源文件名、尺寸、来源页／方法及图片摘要；不确定的来源定位应明确缺口，不猜填。

## 适配器接口

`emit_paper(paper_id, article_html, toc)` 的输入是完整正文树，不包含 `<html>`、`<head>`、网页外壳、CSS 或脚本。正文根节点必须为 `<article id="paper">`，包含对应原文的双语 `h1`。段落、图注、表注和代码按各自单元配对，并保留稳定 ID、`data-unit` 及检索标记。

简单论文可采用下面的适配器；复杂论文仍可从现有逐段数据构造正文树：

```python
from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from paper_document import emit_paper

PAPER_ID = "new-paper"
source = ROOT / "data" / PAPER_ID
emit_paper(
    PAPER_ID,
    (source / "article.html").read_text(encoding="utf-8"),
    json.loads((source / "toc.json").read_text(encoding="utf-8")),
)
```

`toc.json` 是有序列表，例如 `[{"id":"S1","label":"1 引言","level":2}]`；每个目标必须存在于正文中。二级目录用 `level:3`。

图片输入写 `src="assets/figure-01.svg"`，相对 `data/<paper-id>/`；`width`、`height` 为正整数。图号清单与正文图片顺序须一致。构建器复制原字节、计算摘要并生成发布地址，源文件不使用摘要名或 Base64。图表的编号、来源属性、完整表格结构与双语配对详见 [content-and-layout.md](content-and-layout.md)。

正文中的 `#锚点` 保留。PDF 和返回索引的源链接仍按阅读页位置写作 `../pdfs/<filename>.pdf`、`../index.html`；导出器会转换为相对论文 JSON 的地址。不要提前手写 `../../pdfs/`，否则会被再次转换。样式在 `reader/` 维护，不放入论文内容。

## 构建、审计与交付

```bash
python3 -B scripts/build.py
python3 -B -m unittest discover -s tests -v
```

完整构建会输出并审计：

- `public/content/<paper-id>/paper.<摘要>.json`：顶层含 `schemaVersion:1`、`id`、`meta`、`toc`、`assets`、`blocks`。
- `public/content/<paper-id>/assets/`：带摘要名的独立原图。
- `public/content/manifest.json`：该论文实际 JSON、PDF 与阅读器资源地址。
- `public/papers/<paper-id>.html`：引用共用阅读器的轻量外壳。

只运行单篇适配器会更新论文 JSON，但不会同步资源清单与外壳；交付前必须运行完整构建。不要手改生成结果，也不要假定文件摘要保持不变。

需要单篇审计时，从清单读取当前地址（把命令参数替换为实际论文 ID）：

```bash
python3 -B - new-paper <<'PY'
import json
from pathlib import Path
import subprocess
import sys

root = Path.cwd()
slug = sys.argv[1]
manifest_path = root / "public/content/manifest.json"
manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
document = manifest_path.parent / manifest["papers"][slug]["url"]
subprocess.run([
    sys.executable, "-B", "skills/paper-reading-room/scripts/audit_reading_page.py",
    f"public/papers/{slug}.html", "--document", str(document),
    "--source-dir", f"data/{slug}", "--index", "public/index.html",
], check=True)
PY
```

浏览器自动验收运行 `node scripts/browser_check.cjs`，依赖安装方式见仓库 README。当前脚本的 `expected` 列表及 `tests/migration-baseline.json` 面向既有四篇；新增论文时必须显式扩展测试及经核验的内容基线，不能只跑原四篇就宣称新论文已验收。基线来自审校通过的源内容及实际渲染结果；已有论文的基线不能为消除失败而批量重写。

仍须通过 HTTP 核对新论文的三种语言、MathML、完整表格、全部原图解码／放大、代码、搜索、目录、手机布局、打印和仓库子路径；静态审计不证明译文忠实或排版正确。测试需要临时服务时，仅在验收期间启动，结束后关闭。

交付时报告实际输出 JSON、资源清单、图表／单元数量与已执行的检查。更新制作源和产物后，不自动推送或发布；发布遵循用户当前授权。
