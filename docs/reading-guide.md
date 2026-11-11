# 论文阅读室

在线站点以论文索引作为首页。本地请通过 HTTP 服务访问 `public/`（例如 `python3 -m http.server 8000 --directory public`）。阅读器先加载外壳，再请求当前论文的完整双语 JSON；原图独立懒加载，PDF 按需打开。每篇均提供目录、全文搜索、字号、主题、原图放大和打印；完整正文需要 JavaScript。

## 已收录论文

### Agentic Context Engineering

- `public/papers/ace.html`：正文、图注、表格、附录文字与参考文献题名的中文译文，并附英文对照；14 幅独立原图按需加载。
- `public/pdfs/2510.04618.pdf`：原始英文论文，arXiv:2510.04618v3，ICLR 2026。

### SkillForge

- `public/papers/skillforge.html`：中文全文与逐段英文对照，含完整正文、附录 A–D、49 条参考文献及题名翻译、16 幅独立原图、4 张完整数据表，以及 5 份提示词的文字对照。中英对照模式按“中文一段、英文原文一段”排列。
- `public/pdfs/2026.emnlp-main.1954.pdf`：从 ACL Anthology 下载的原始英文论文，25 页。
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

## 可复用制作流程

仓库保留 skill、原始论文 PDF、轻量阅读外壳和索引、统一论文 JSON、共用阅读器，以及重建所需的双语文稿、独立原图、样式、来源记录及脚本。ACE 的维护入口为 `data/ace/article.html`、`toc.json` 和 `assets/`，不再作为其他论文的外壳模板。下载源码归档、重复的 LaTeX 文件和图表 PDF、临时审计报告与 Python 缓存已清理；重建无需重新下载源码归档。来源记录中的归档摘要属于历史下载记录，不表示归档仍保存在本地。

[`skills/paper-reading-room/SKILL.md`](../skills/paper-reading-room/SKILL.md) 保存论文下载、忠实翻译、逐段中英对照、独立原图提取、完整表格还原、网页生成及索引维护流程，并附提取与审计脚本。后续任务可从仓库根目录指定“使用 `skills/paper-reading-room/SKILL.md` 处理这篇论文”，或在已加载该 skill 的环境中使用 `$paper-reading-room`。


阅读器的数据接口、相对 URL 约定和新增论文接入方式见[架构说明](reader-architecture.md)。历史来源说明中的制作日期与译者记录保留原样。
