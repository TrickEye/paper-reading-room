# 论文阅读室

在线站点以论文索引作为首页。本地请通过 HTTP 服务访问 `public/`（例如 `python3 -m http.server 8000 --directory public`）。阅读器先加载外壳，再请求当前论文的完整双语 JSON；原图独立懒加载，PDF 按需打开。每篇均提供目录、全文搜索、字号、主题、原图放大和打印；完整正文需要 JavaScript。

## 已收录论文

### Agentic Context Engineering

- `public/papers/ace.html`：正文、图注、表格、附录文字与参考文献题名的中文译文，并附英文对照；14 幅独立原图按需加载。
- `public/pdfs/Agentic-Context-Engineering-2510.04618.pdf`：原始英文论文，arXiv:2510.04618v3，ICLR 2026。

### SkillForge

- `public/papers/skillforge.html`：中文全文与逐段英文对照，含完整正文、附录 A–D、49 条参考文献及题名翻译、16 幅独立原图、4 张完整数据表，以及 5 份提示词的文字对照。中英对照模式按“中文一段、英文原文一段”排列。
- `public/pdfs/Skill-Forge-2026.emnlp-main.1954.pdf`：从 ACL Anthology 下载的原始英文论文，25 页。
- 来源：[ACL Anthology 论文页面](https://aclanthology.org/2026.emnlp-main.1954/)，DOI: 10.18653/2026.emnlp-main.1954。

SkillForge 页面中的中文译文由 AI 生成，供阅读参考；原始 PDF 是引用、公式和排版的权威来源，作者未对译文背书。

SkillForge 原图均从原始 PDF 获取：8 幅直接提取内嵌原始图片，8 幅对 PDF 内的矢量图或提示词框单独渲染，未使用整页截图。表格数值、舍入及原文表述按论文保留。网页通过统一 JSON 加载正文，独立原图按需请求。

`data/skillforge/` 保存逐段双语数据、图表数据、原图及提取记录；SkillForge 适配器输出统一 PaperDocument；运行 `python3 -B scripts/build.py` 重建全部发布资源。

### Permission Denied

- `public/papers/permission-denied.html`：正文、附录 A–G、27 条参考文献题名均提供逐段中文与英文原文对照；保留 4 幅同版 arXiv HTML 的独立 SVG 原图和 15 张完整、可选择文本的表格。页面内含目录、全文搜索、阅读模式、字号、深色主题、原图放大和打印功能。
- `public/pdfs/Permission-Denied-2608.02670v1.pdf`：原始英文论文，arXiv:2608.02670v1，24 页，提交日期为 2026 年 8 月 2 日。
- `data/permission-denied/`：保存同版官方 HTML、图像资源、逐段译文、完整表格数据及来源记录。运行 `python3 -B scripts/build.py` 可重建统一内容数据及阅读外壳。
- PDF SHA-256：`977a1cf9a99bca08c87d8a5281e35ea84856049303401329135cdae1b4a32d67`。

Permission Denied 阅读页中的中文译文由 AI 生成，供阅读参考；原始 PDF 是原文和排版的权威来源，作者未对译文背书。四幅图使用同版 arXiv HTML 提供的独立 SVG 文件；表格均保留全部行列和原始数据，没有用截图替代。

### SkillCAT

- `public/papers/skillcat.html`：正文、图表注、算法行与 34 条参考文献题名的中文翻译，按原单元提供英文对照；保留 4 幅同版官方独立原图、2 张全部行列的可选择文本表格及 6 个公式。本版本没有附录。
- `public/pdfs/SkillCAT-2606.13317v2.pdf`：原始英文论文，arXiv:2606.13317v2，9 页，版本日期为 2026 年 7 月 29 日。
- `data/skillcat/`：保存同版官方 HTML、原图及来源记录、原文单元、Luna 翻译数据、术语表和图表数据。运行 `python3 -B scripts/build.py` 可重建统一 JSON、独立图片和阅读外壳。
- 来源：[arXiv 同版论文页面](https://arxiv.org/abs/2606.13317v2)。PDF SHA-256 记录在 `data/skillcat/source.json` 和阅读页末尾。

SkillCAT 中文译文由 Luna 子代理生成并经主代理审校，网页由主代理制作。图片以独立资源加载；公式保留原始 MathML，不依赖外部排版服务；作者未对译文背书，引用和排版以原始 PDF 为依据。

### SkillGen

- `public/papers/skillgen.html`：完整中文译文与逐段英文对照，覆盖正文、附录 A–D、图表注、算法 1 的全部 20 行，以及 37 条参考文献题名。保留同版官方 8 幅独立原图和 4 张完整、可选择文本的数据表，18 个显示公式块使用原始 MathML。
- `public/pdfs/SkillGen-2605.10999v1.pdf`：用户提供的原始英文论文，arXiv:2605.10999v1，20 页，版本日期为 2026 年 5 月 9 日。
- `data/skillgen/`：同版官方 HTML、逐段翻译、图表数据、原图、目录、公式、术语表与 PDF SHA-256 来源记录；`scripts/builders/skillgen.py` 可重建阅读内容。
- 来源：[arXiv 同版论文页面](https://arxiv.org/abs/2605.10999v1)。中文由 AI 翻译并审校，未经作者背书。原图内英文保留；表格数值及原作表述按原文保留，引用以原始 PDF 为准。

### Skill Transfer

- `public/papers/skill-transfer.html`：作者预印本的中文译文与逐段英文对照，覆盖正文、参考文献题名及附录 A–D；保留 3 幅从同一 PDF 单独裁出的原图、7 张完整可选择文本的表格、算法 1 和附录的四份示例。原图内英文按原作保留。
- `public/pdfs/Skill-Transfer-preprint.pdf`：作者项目提供的 20 页英文预印本；PDF 的创建元数据显示 2026 年 9 月 23 日，仓库未提供单独的版本号。
- `data/skill-transfer/`：保存逐段双语文稿、PDF 抽取文本、图表数据、原图裁取边界和来源记录。`scripts/builders/skill_transfer.py` 生成统一 PaperDocument。
- 来源：[作者项目](https://github.com/Yifan-Lan/Skill-Transfer)。PDF SHA-256：`65d0e1d491971607e8a83b17fb12d768f2b96871a14d503bc86b8c3f6623d891`。中文译文由 AI 制作，未经作者背书；引用、代码及公式以原始 PDF 为准。

### MASA

- `public/papers/masa.html`：arXiv v1 的中文全文与逐段英文对照，覆盖正文、局限性、伦理考量、46 条参考文献题名和附录 A–J；保留 5 幅官方独立原图、9 张可选择文本的编号表、7 个显示公式、2 个算法及完整模型卡示例。
- `public/pdfs/MASA-2605.30723v1.pdf`：用户提供的 20 页英文 PDF，arXiv:2605.30723v1，版本日期为 2026 年 5 月 29 日。
- `data/masa/`：同版官方 HTML、逐段译文、表格和算法译文、原图、来源及图表清单。`scripts/builders/masa.py` 可重建统一内容数据。
- 来源：[arXiv 同版论文页面](https://arxiv.org/abs/2605.30723v1)。中文由 AI 翻译并审校，未经作者背书；图内英文与表格原始数值按原作保留，引用和排版以原始 PDF 为准。

### From Raw Experience to Skill Consumption

- `public/papers/skill-consumption.html` 提供摘要、正文第 1–7 节、附录 A–H 和 29 条参考文献题名的中文译文与逐段英文对照。保留 5 幅同版独立原图、5 个 MathML 显示公式，以及 15 个可选择文本的编号表，其中 6 个是完整的提示词模板。
- `public/pdfs/From-Raw-Experience-to-Skill-Consumption-2605.23899v1.pdf` 为 arXiv v1 原始 PDF，共 24 页，提交日期为 2026 年 5 月 22 日。
- `data/skill-consumption/` 保存同版官方 HTML、逐段译文、提示词和表格译文、原图、来源及校验值。`scripts/builders/skill_consumption.py` 可重建统一阅读数据。表 1 用文字标注原作图标对应的模型系列，便于搜索和使用屏幕阅读器。
- 中文译文是对原作的改编，引用以原始 PDF 为准。[arXiv 同版论文](https://arxiv.org/abs/2605.23899v1) · [CC BY 4.0 许可](https://creativecommons.org/licenses/by/4.0/)

### WikiSkill

- `public/papers/wikiskill.html` 提供摘要、正文第 1–7 节、局限性、AI 使用披露、附录 A–E 和 46 条参考文献题名的中文译文与逐段英文对照。页面包含 3 幅同版独立原图、7 张可选择文本的完整表格、8 个 MathML 显示公式、1 个逐行对照算法和 7 份完整系统提示词。
- `public/pdfs/WikiSkill-2608.27454v1.pdf` 为 28 页 arXiv v1 原始 PDF。arXiv 提交日期为 2026 年 8 月 27 日，PDF 标注日期为 2026 年 8 月 28 日。
- `data/wikiskill/` 保存同版 HTML、逐段译文、算法与提示词译文、原图及来源校验值。运行 `python3 -B scripts/build.py` 可重建阅读资源。算法按原始 PDF 将输入单列，并从第 1 行给过程编号。原始提示词取自官方 HTML 附带的纯文本，保留缩进、变量和标记。
- 来源：[arXiv 同版论文](https://arxiv.org/abs/2608.27454v1) · [CC BY 4.0 许可](https://creativecommons.org/licenses/by/4.0/)。

## 可复用制作流程

仓库保留 skill、原始论文 PDF、轻量阅读外壳和索引、统一论文 JSON、共用阅读器，以及重建所需的双语文稿、独立原图、样式、来源记录及脚本。ACE 的维护入口为 `data/ace/article.html`、`toc.json` 和 `assets/`，不再作为其他论文的外壳模板。下载源码归档、重复的 LaTeX 文件和图表 PDF、临时审计报告与 Python 缓存已清理；重建无需重新下载源码归档。来源记录中的归档摘要属于历史下载记录，不表示归档仍保存在本地。

[`skills/paper-reading-room/SKILL.md`](../skills/paper-reading-room/SKILL.md) 保存论文下载、忠实翻译、逐段中英对照、独立原图提取、完整表格还原、网页生成及索引维护流程，并附提取与审计脚本。后续任务可从仓库根目录指定“使用 `skills/paper-reading-room/SKILL.md` 处理这篇论文”，或在已加载该 skill 的环境中使用 `$paper-reading-room`。


阅读器的数据接口、相对 URL 约定和新增论文接入方式见[架构说明](reader-architecture.md)。历史来源说明中的制作日期与译者记录保留原样。
