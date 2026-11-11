# 共用阅读器与 PaperDocument v1

本项目的运行边界是 `public/`。阅读器由静态 HTML、CSS、JavaScript 组成，论文内容来自同站点的 JSON；图片与 PDF 是独立静态文件。没有服务器端 API、前端框架或运行时 CDN。

## 源文件、构建与发布

`reader/` 保存外壳模板、交互与样式。`base.css` 为各篇共用样式，论文特有样式由构建器加上 `html[data-paper="<id>"]` 范围，避免互相覆盖。`states.css` 提供加载、错误和图片重试反馈。

现有三篇保留各自的文稿格式；适配器整理完正文树后调用 `emit_paper(id, article_html, toc)`。该接口只接收正文与目录，不接收完整网页；中间的 HTML 在内存中转换成结构化单元，不作为完整正文片段发布。ACE 的独立源保存在 `data/ace/article.html`、`toc.json` 和 `assets/`。任何生成器均不读取发布的 ACE 外壳。

`python3 -B scripts/build.py` 依次执行适配器、输出独立图片与论文 JSON、生成共用资源与资源清单、生成四个外壳，最后审计。发布数据和源文件一并提交。各论文适配器单独运行只更新对应内容；日常维护使用完整构建命令，以同步资源清单和外壳。

输出示例：

```text
papers/ace.html
reader/loader.js
reader/reader.<sha256前16位>.css
reader/reader.<sha256前16位>.js
content/manifest.json
content/ace/paper.<sha256前16位>.json
content/ace/assets/figure-01.<sha256前16位>.svg
pdfs/Agentic-Context-Engineering-2510.04618.pdf
```

摘要取文件的实际 UTF-8 字节或原始图片字节计算，无构建时间戳。构建会清除自己管理的过期版本，保证产物确定。资源清单请求采用 HTTP 重验证，其余资源沿用浏览器缓存。外壳引用固定的 `reader/loader.js`。该小入口重验证资源清单，修正缓存外壳中的样式地址，再导入当前的摘要脚本；因此旧外壳不依赖已被清理的旧摘要脚本。加载清单、样式或主模块失败均提供重试；不自动刷新整页或静默展示不完整正文。

## PaperDocument

每篇的顶层字段为：

```json
{
  "schemaVersion": 1,
  "id": "ace",
  "meta": {
    "title": "ACE 智能体上下文工程 · 中文全文",
    "titles": {"zh": "中文标题", "en": "Original title"},
    "authors": ["Author"],
    "version": "v3",
    "source": {},
    "pdf": "../../pdfs/Agentic-Context-Engineering-2510.04618.pdf",
    "defaultMode": "zh",
    "storageKey": "ace-reader-"
  },
  "toc": [{"id": "S1", "label": "1 引言", "level": 2}],
  "assets": [{"id": "figure-01", "url": "assets/figure-01.HASH.svg", "width": 1000, "height": 600, "sha256": "完整摘要", "source": {}}],
  "blocks": []
}
```

`blocks` 是递归内容树，外层为一个 `article#paper`，无网页外壳、CSS 或脚本。节点保留 `tag`、`attrs` 及稳定的原锚点／`data-unit`。节点类型如下：

| `type` | 额外字段与行为 |
|---|---|
| `container` | `kind`、`children`；章节、列表、图、页尾及必要分组容器 |
| `bilingual` | `kind`、`zh`、`en`、`order`；每个语言对象含 `tag`、`attrs`、`html`，保留原配对标签与精确空白 |
| `rich` | `kind`、`html`；单个标题、段落、表格、公式或参考文献的局部富文本 |
| `image` | `assetId`；引用图片清单，`src` 由阅读器生成 |
| `text` | `text`；保留结构间的原始文本和空白，不含标签字段 |

`bilingual.order` 按原顺序包含 `"zh"`、`"en"` 和可选的 `{"text":"空白"}`；两种语言各出现一次。正文共享公式不强行复制为两种语言。复杂单元可保留局部 HTML／MathML，嵌套表格内的语言标签继续由共用阅读模式样式控制。跨行跨列、脚注、引用、代码换行和全部旧锚点保持不变。

`kind` 描述用途（例如 `heading`、`paragraph`、`section`、`list`、`figure`、`table`、`math`、`code`、`reference`、`source`），不承载事件或脚本。局部富文本不得升级为一个包含整篇论文的字段。

## 请求、链接与交互

外壳中的 `data-paper` 标明论文 ID，`data-manifest` 标明资源清单。清单记录共用资源以及各论文的内容地址、标题、品牌、PDF、默认模式与偏好键。

- 外壳相对清单地址解析；清单内地址相对清单 URL 解析。
- 图片和正文内本地文件链接相对论文 JSON URL 解析；构建将旧的 `papers/` 相对链接转换到新的内容目录。
- `#fragment` 保持当前阅读外壳地址，不跳到 JSON 文件。禁止根路径 URL、`<base>` 和仓库名硬编码。
- PDF 与原图不进入正文请求；JSON 同时包含中英文。切换语言不请求正文，也不重新创建整个 DOM。
- 正文挂载完成后再绑定目录目标、搜索、进度与图片放大。初次带锚点访问和刷新时，在 DOM 就绪后定位；前进后退由地址片段事件恢复。
- 字号、主题、语言可在加载时操作。保留旧偏好键：ACE、SkillForge 和 Permission Denied 使用 `ace-reader-`，SkillCAT 使用 `skillcat-reader-`。无已存偏好时，ACE 默认中文，其余默认逐段对照。
- 打印按钮等待全部正文图片解码成功；失败则不打印并提示重试。浏览器原生打印通过 `beforeprint` 尽力触发图片加载，但无法异步阻塞原生打印对话框。

JSON 请求检查 HTTP 状态、解析结果、格式版本与论文 ID；失败可重试。图片有各自的重试按钮。加载错误不移除原始 PDF 或索引入口。

富文本只来自仓库构建结果。构建拒绝脚本、事件属性、可执行 URL、外部样式和危险行内 CSS；运行时在挂载前再次拒绝活动元素和可执行链接。解析使用原节点上下文，保留表格结构和 MathML 命名空间，不把公式当作普通 HTML 标签逐个创建。

## 新论文与验收

新增论文先完成原文、翻译、图表与来源核对，再加入 `data/catalog.json`、`reader-meta.json` 和正文适配器。图片源放在对应论文数据目录，保留原字节和来源摘要。更新现有索引与阅读说明；不要复制共用阅读器或直接维护发布 JSON。

`check.py` 读取 JSON 重建完整正文供既有审计器检查，验证双语单元、完整表格、参考文献、原图字节、PDF 摘要、锚点、发布边界和版本摘要；不会把没有正文的外壳误判为内容完整。可单篇审计：

```bash
python3 skills/paper-reading-room/scripts/audit_reading_page.py public/papers/ace.html \
  --document public/content/ace/paper.ACTUAL_HASH.json \
  --source-dir data/ace --index public/index.html
```

`tests/migration-baseline.json` 记录迁移前浏览器 DOM 的内容指纹，覆盖所有锚点、逐单元文本、完整表格、MathML、代码与全文文本。`browser_check.cjs` 对实际渲染结果做逐类比对，另覆盖交互、请求隔离、错误恢复、打印和项目子路径，并输出桌面／手机／图表／打印截图及 PDF。后续有意修改文稿时，先审校源内容，再同步受影响的指纹；不要把更新基线当作跳过差异调查的方式。

本次迁移不提供全文静态 SEO、段落编辑／批注、章节分批加载、Service Worker 或单文件离线导出。

## 阅读笔记

`reader/notes.js` 是独立笔记控制器，布局样式合入共用 CSS。资源清单提供可选的 `notes: {js, vendor, documents, github}`：`js` 为带内容摘要的模块，`vendor` 为带校验清单摘要的目录 URL，`documents` 为 `../notes/`，这些地址均相对清单解析。`github` 为公开的 `{owner, repo, branch, directory}`，当前值为 `TrickEye`、`paper-reading-room`、`main`、`public/notes/`。旧清单缺少新增配置时仍可使用内存笔记编辑。阅读器载入控制器后创建默认隐藏的面板；仅第一次打开时请求 Vditor 4.0.1、Lute、中文语言包、图标和 KaTeX。关闭面板保留实例。编辑器资源失败时降级为纯 Markdown 文本框，可继续编辑并重试加载。

固定版本发布资源保存在 `reader/vendor/vditor-4.0.1/`，`checksums.json` 记录官方 npm tarball 的 SHA-512、各文件 SHA-256 与许可证来源。构建校验并原样复制所需文件，不运行 npm，不联网下载。发布审计验证目录摘要、全部文件及意外资源；不发布上游示例 HTML 或源码。代码块预览关闭，数学预览启用；编辑器使用本地资源地址。Lute 内置安全过滤之外，编辑器 DOM 转换边界进一步移除活动 HTML、图片和危险链接属性，笔记 HTML 不进入论文正文。

笔记仅保存在控制器内存，既不读取旧版 `paper-reader:<站点路径>:notes:v1:<paperId>` 记录，也不新增、删除或修改该记录；不再提供本地自动保存和跨标签页冲突处理。关闭面板保留本页草稿，刷新和跨论文导航重新加载部署版。主题、字号和 `paper-reader:<站点路径>:notes-width` 等界面偏好仍使用 localStorage。

输入更新草稿状态；关闭面板、切换模式、页面隐藏和离页前同步当前编辑器值。以已加载部署版为基线检测未提交修改，忽略编辑器自动追加的末尾换行；输入法组合期间禁止刷新远端和提交交接。存在修改或组合输入时用 `beforeunload` 请求浏览器显示离页提醒；用户可以选择放弃，移动端进程回收等情况也不保证触发提醒，因此它不等于持久保存。打开 GitHub 不清除未提交状态，成功载入部署版或撤销到原内容才恢复无修改状态。

控制器初始化即以 `cache: no-cache` 请求同站点 `notes/<paper-id>/notes.md`，15 秒超时；文件成功返回（包括空内容）时覆盖当前草稿，404 保留当前草稿，其他失败显示状态并允许继续编辑和重试。请求期间编辑区只读／inert，编辑模式、摘录和提交暂不可用。手动刷新具有相同的覆盖语义；切回本页不会自动请求，以免在 GitHub 提交后尚未部署时载入旧内容。部署版加载状态与内存草稿状态分别显示。

GitHub 提交只通过网页交接，不持有令牌或调用写 API。提交面板固定打开时的 Markdown 快照：部署版不存在且编码后完整 URL 不超过 6000 字节时，使用 `/new/main?filename=public/notes/<paper-id>/notes.md&value=...` 预填；更新使用 `/edit/main/public/notes/<paper-id>/notes.md`，长的新文件只预填文件路径，两者均提示复制全文后手动粘贴。状态未知时要求显式选择新建或编辑；新建也提供编辑页备用链接。复制失败时可手动全选快照，空内容更新提示清空编辑框。正文预填是未正式承诺的页面行为，并会把正文放进 URL，6000 字节仅为保守阈值。GitHub 链接独立点击打开，页面只记录“待手动提交”；需提交并完成 Pages 部署后再刷新远端。

`public/notes/` 是手工维护的发布源文件目录，构建不会生成、改写或清理 Markdown，也不会把笔记列表、正文或摘要加入资源清单。GitHub 网页可以只提交笔记文件，重新构建仍保持其他产物一致；笔记初始不存在属于正常情况，不要求占位文件。

摘录保存实际选中文字，追加 Markdown 引用和论文外壳相对链接；优先引用已有正文锚点，跳过临时搜索 ID，不改写论文数据。跨段选择定位起点。移动端回跳收起抽屉；桌面面板开关尽量保持当前可见内容单元位置。笔记不参与全文搜索、阅读进度或打印。新增浏览器用例在 `scripts/browser_notes.cjs`，由共用验收入口执行；真实软键盘体验仍需 iOS Safari 和 Android Chrome 实机核验。
