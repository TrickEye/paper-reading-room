---
name: paper-reading-room
description: 将论文链接或本地 PDF 制作、修订为共用阅读器使用的双语 PaperDocument JSON 与独立原图，并接入项目索引。适用于全文翻译、逐段对照及论文内容数据维护；仅要求论文摘要或观点解读时不使用。
---

# 论文双语阅读室

目标：从可核验的论文原文制作可追溯、可维护的双语网页。本项目采用共用阅读器、统一 PaperDocument JSON 与独立原图；以 `reader/` 的现有界面和 `docs/reader-architecture.md` 的数据接口为准。用户指定的范围、版本及排版优先。

## 四项不可替代的内容要求

1. **忠实翻译。** “逐字翻译”在此指逐句完整、忠实对应原意，并保持原段落边界；允许中文所需的语序调整，不允许摘要、润色扩写或模型推断。保留否定、条件、比较对象、限定语、数字、引用和论断强度。不要用模型生成的英文概述冒充原文。无法确定的文字回查原文；不得猜补。
2. **逐段配对。** 默认每个原文段落对应一个中文段落，页面按“中文一段 → 对应英文一段”排列。不能先放整节中文再放整节英文，不能用按 PDF 页折叠的英文文本替代逐段对照。标题、列表项、图注、表注、脚注及代码／提示词块也有对应关系；语言无关的公式和数值可以共享。
3. **独立原图。** 优先获取同一版本官方 HTML／源文件的原始图片，或直接提取 PDF 内嵌图片。PDF 中的矢量图、组合图和提示词框，可单独保留矢量或准确裁出图区域后渲染。**禁止把整页 PDF 截图放在图的位置，也禁止重画、AI 生成替代原图。** 裁图不含周围正文、页眉页脚或页码，不截断图内标题、图例和子图。图注在图外单独中英配对。图内原文保留；原文中的提示词另提供完整双语文字。
4. **完整表格。** 还原成可选择文本的 HTML 表格，覆盖全部行列、分组、单位、脚注及表注。数据按原作保留，包括精度、区间、正负号、加粗和缺失值。不得只摘关键结果、截图替代表格、补造数据，或擅自重算并改正原作。

这些要求适用于所承诺的翻译范围。若用户仅指定某一节，仅处理该节；没有允许省略时，不把附录、局限、声明或提示词压缩成“概要”。

## 工作流程

### 1. 定位项目与确认原文

- 本仓库的发布边界是 `public/`：索引为 `public/index.html`，阅读页为 `public/papers/<paper-id>.html`，PDF 为 `public/pdfs/`；源数据及原图放 `data/<paper-id>/`，生成器放 `scripts/builders/`，说明放 `docs/`。共用阅读器源在 `reader/`，发布内容在 `public/content/`，发布脚本与样式在 `public/reader/`；不要把制作文件放入站点发布目录。
- 阅读页返回索引用 `../index.html`，PDF 用 `../pdfs/<file>.pdf`；索引到论文用 `papers/<paper-id>.html`。使用相对 URL，兼容本地 HTTP 与 GitHub Pages 仓库子路径，不使用以 `/` 开头的站内 URL。外壳、资源清单与论文 JSON 各自的 URL 基准见架构说明。

- 检查项目规则、`public/index.html`、阅读说明和通过 HTTP 加载的参考阅读页，识别现有语言切换、目录、搜索、字号、主题、图片放大、打印及移动端行为。只读取必要片段，避免将内嵌 base64 图片输出到上下文。
- 从用户链接读取论文元数据并解析正式 PDF 下载地址；下载后验证确为 PDF、可解析且页数合理。保留原始 PDF，记录最终下载 URL、论文标识、版本、日期及 SHA-256。不要混用不同版本的正文、图表和附录。
- 环境有工作区依赖定位工具时先定位 Python、PDF 与浏览器工具；不要把本机运行时绝对路径写成 skill 的必备依赖。

### 2. 建立源内容清单，再翻译

- 按原作列出章节、段落、附录、公式、图、表、脚注、参考文献及提示词，记录页码／来源定位。PDF 页是定位信息，不是段落边界；跨页段落需接回，跨栏和浮动图表须恢复阅读顺序。
- 以英文原文为不可随意改写的源字段，再增加中文字段。先检查英文完整性，再逐段翻译；维护术语一致性。遇到公式、代码或复杂表格必须回看原始页面。
- 实现双语数据及生成器时，读 [references/content-and-layout.md](references/content-and-layout.md)。该文件说明稳定 ID、源定位、公式和现有 ACE 界面的对接要求。

### 3. 提取图表并生成网页

- 每幅图记录图号、源页、源资源或裁图边界、方法、文件名和尺寸；不能假定 PDF 中“第 N 张图片”就是论文“图 N”。复杂子图优先保留完整组合图。
- 批量提取时可使用 `scripts/extract_figures.py`；先人工确定图与资源／边界的对应关系。调用和提取方案见 [references/extraction-and-verification.md](references/extraction-and-verification.md)。
- 沿用共用阅读器视觉与交互结构；在 `data/reader-meta.json` 与适配器中配置标题、作者、元数据、目录和 PDF 路径。禁止从 ACE 发布外壳截取 CSS、脚本或模板，也不复制 ACE 正文。SkillForge 现有 `data/skillforge/` 是实现示例，**其中的 16 图、4 表、49 条参考文献不是新论文的默认数量**。
- 以双语源文稿和原图通过适配器输出统一 PaperDocument JSON，使用 `scripts/paper_document.py` 的 `emit_paper` 接口。正文按结构化单元组织，复杂富文本可保留局部 HTML／MathML；图片引用独立资源，禁止把整篇塞入单个 HTML 字段或重新嵌入 Base64。后续修改制作源并完整重建，不手改发布 JSON／外壳。
- 新增论文或修订输出格式前，读 [references/publication-contract.md](references/publication-contract.md)：它给出当前适配器接口、源图片路径、配置字段、完整构建及从资源清单定位审计输入的可执行示例。下文仓库路径均相对仓库根目录；skill 内参考链接相对本 skill。

### 4. 接入已有索引

- 在现有 `public/index.html` 中新增或更新该论文卡片，不另建替代索引；保留其他论文卡片与布局。更新数量、名称、作者、出处、阅读页和 PDF 相对链接；不要重复收录同一版本。
- 同步 `data/catalog.json` 的论文 ID、PDF、图表数量和生成器，并维护 `docs/reading-guide.md`。只有实际完成时才标“全文”“全部原图”“完整附录”，不能根据预期宣称完成。用户没有要求发布时，交付本地文件即可。
- 同步 `data/reader-meta.json` 和 `reader/<paper-id>.css`（无额外样式时也保留空文件）。新增论文须加入浏览器测试清单；四篇迁移基线只保护已有内容，不能替代新论文的原文核验及浏览器验收。

### 5. 验收后交付

- 依据清单核对译文覆盖率；逐段对照英文审校，重点复查否定、条件、数字、提升百分比与百分点、实验比较、局限和公式。**DOM 配对完整不等于译文忠实。**
- 执行下方检查脚本，随后在浏览器检查中文／英文／逐段对照三种模式、目录、搜索、原图放大、字号、深色、打印布局，以及桌面和窄屏。确认图片真正解码成功、整页不横向溢出，宽表仅在自身容器内滚动。视觉检查也要看正文、长图、表和代码块，不能只看首页。
- 检查索引仍可打开新旧论文及 PDF。若有无法取得或核实的内容，明确标记缺口与范围，不能用摘要或推断填满后宣称完成。
- 运行 `python3 -B scripts/build.py` 重建并检查完整正文与发布资源；已有产物可运行 `python3 -B scripts/check.py`。新增论文仍须完成原文和浏览器验收。最后给出阅读页链接、已完成范围和实际验证结果；保留双语数据、生成器及原图来源记录。

```bash
python3 skills/paper-reading-room/scripts/audit_reading_page.py 'public/papers/<paper-id>.html' \
  --document 'public/content/<paper-id>/paper.<实际摘要>.json' \
  --source-dir 'data/<paper-id>' --index public/index.html
```

`--source-dir` 用于含 `assets.json`、`tables.json` 等本项目约定数据的目录；没有该目录时可省略，并用 `--expected-figures`、`--expected-tables` 传入从原作清单核实的数量。`--document` 指向资源清单中该论文的实际 JSON；不能只审计无正文的 HTML 外壳。浏览器验收运行 `node scripts/browser_check.cjs`，依赖安装方式见 README。脚本仅做结构、资源和数据核对，不判断翻译质量或裁图边界是否正确。检查方法和失败后的处理见 [references/extraction-and-verification.md](references/extraction-and-verification.md)。
