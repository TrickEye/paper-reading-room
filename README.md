# 论文阅读室

四篇智能体相关论文的离线双语阅读页，保留逐段中英对照、原版图表和原始 PDF。支持目录跳转、全文搜索、字号调整、深色模式、原图放大与打印。

[在线阅读](https://trickeye.github.io/paper-reading-room/) · [GitHub 仓库](https://github.com/TrickEye/paper-reading-room)

打开 [public/index.html](public/index.html) 即可阅读；无需安装依赖。已收录 ACE、SkillForge、Permission Denied 和 SkillCAT，版本与内容范围见[阅读说明](docs/reading-guide.md)。

## 目录

```text
public/                     GitHub Pages 发布目录，可独立复制或离线使用
  index.html                论文索引
  papers/                   双语 HTML 阅读页，使用简短英文文件名
  pdfs/                     原始论文 PDF
data/
  catalog.json              论文 ID、PDF 文件、图表数量及生成器清单
  skillforge/               双语数据、表格和独立原图
  permission-denied/        同版原文、译文、图表和来源记录
  skillcat/                 同版原文、译文、图表、术语表和阅读样式
scripts/
  build.py                  重建并检查全部可生成的阅读页
  check.py                  检查发布路径、链接、图表、双语结构和 PDF 摘要
  builders/                 各论文生成器及 SkillCAT 原文预处理工具
skills/paper-reading-room/  可复用论文制作 skill，附提取和结构审计工具
docs/reading-guide.md       论文版本、翻译范围与来源说明
.github/workflows/pages.yml GitHub Actions 验证和 Pages 部署
```

`public/` 只包含阅读所需的文件；数据和制作工具留在仓库中，不随 Pages 站点发布。图像、脚本、样式与 MathML 已嵌入阅读页，浏览不依赖外部服务。ACE 页面是现有阅读器参考，当前直接维护 HTML；另外三篇从 `data/` 重建。

## 本地预览与维护

直接双击 `public/index.html` 可离线阅读。需要 HTTP 预览时，使用 Python 3.10 或更新版本：

```bash
python3 -m http.server 8000 --directory public
```

打开 <http://localhost:8000/>。在仓库中修改译文、图表或生成器后，运行：

```bash
python3 -B scripts/build.py
```

仅检查现有产物：

```bash
python3 -B scripts/check.py
```

重建和检查只使用 Python 标准库，无需下载源归档。重建会更新 `public/papers/` 及相应派生 JSON；修改与生成结果应一并提交。SkillCAT 的原文单元需要重新提取时，可运行 `python3 -B scripts/builders/skillcat_prepare.py`，随后审校翻译覆盖情况再重建。提取新论文原图所需的可选依赖见 skill 的[提取与验收说明](skills/paper-reading-room/references/extraction-and-verification.md)。

## GitHub Pages

本站通过 GitHub Actions 发布 `public/`，地址为 <https://trickeye.github.io/paper-reading-room/>。Pages 发布来源使用 **GitHub Actions**；推送 `main` 分支，或在 Actions 中手动运行工作流，即可更新站点。PR 只执行重建与验证；`main` 验证通过后部署。

工作流检查生成结果是否已提交，防止数据与 HTML 不一致。站内链接使用相对路径，同时兼容 `https://<owner>.github.io/<repo>/` 项目站点、用户站点和自定义域名，无需修改 base URL。发布包不包含 `data/`、`scripts/` 或 `skills/`。

配置参考：[GitHub Pages 自定义工作流](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages)。部署状态与日志见仓库的 [Actions](https://github.com/TrickEye/paper-reading-room/actions)。

## 制作流程与来源

复用 [skills/paper-reading-room/SKILL.md](skills/paper-reading-room/SKILL.md) 制作新论文时，将阅读页放进 `public/papers/`，PDF 放进 `public/pdfs/`，源数据放进 `data/<paper-id>/`，生成器放进 `scripts/builders/`，并同步索引、清单和阅读说明。

中文译文由 AI 生成并审校，供阅读参考，未经论文作者背书。引用、公式和原始排版以各论文 PDF 为准；原论文及图表的权利归原作者或相应权利人，具体来源见阅读页末尾。
