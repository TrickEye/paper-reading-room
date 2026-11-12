# 论文阅读室

智能体相关论文的阅读网站，保留逐段中英对照、独立原图和原始 PDF。支持目录跳转、全文搜索、字号调整、深色模式、原图放大与打印。

阅读页顶部的「笔记」可打开当前论文的 Markdown 长笔记。默认采用类似 Typora 的即时渲染，支持源码切换、表格、任务列表和数学公式；选中正文后可摘录文字并附上回跳链接；正文图片的悬停操作区和放大弹窗提供「摘录到笔记」，插入原图地址、当前阅读语言的图注和「返回原图」链接。触屏设备会直接显示图片摘录按钮，键盘聚焦图片也可访问。桌面采用可调宽右侧分栏，手机采用底部半屏抽屉。笔记草稿仅保存在当前页面内存，不读写 localStorage；主题、字号和面板宽度仍保留浏览器偏好。存在未提交修改时会请求浏览器显示离页提醒，刷新或关闭页面仍可能丢失草稿。

每篇论文的部署版笔记维护在 `public/notes/<paper-id>/notes.md`。进入论文页时会主动请求当前站点的对应文件：成功时用部署版覆盖当前草稿（包括空文件），404 时保留当前页面草稿，请求失败时可继续编辑并重试。「刷新远端」也会覆盖当前草稿；尚未提交的修改不会优先于已有部署版。浏览器中的旧版笔记记录不再读取或修改。

「保存到 GitHub」打开提交交接面板：短的新笔记通过链接预填文件名和正文；已有文件或长笔记通过复制全文、打开 GitHub 页面后手动粘贴提交。6000 字节是完整编码 URL 的保守阈值，正文预填不是 GitHub 正式承诺的接口，且内容会包含在 URL 中；始终可手动复制。空笔记更新时需清空 GitHub 编辑框。提交到 `main` 并完成 Pages 部署后再刷新远端，否则仍会读到旧部署版；打开 GitHub 不代表已经提交。笔记没有自动上传、附件或历史备份。图片摘录只保存 Markdown 地址引用，图片相对地址以 `notes.md` 所在目录解析；引用的稳定原图地址随论文构建更新，因此已有笔记会展示更新后的对应图片。

[在线阅读](https://trickeye.github.io/paper-reading-room/) · [GitHub 仓库](https://github.com/TrickEye/paper-reading-room)

已收录 ACE、SkillForge、Permission Denied、SkillCAT 和 SkillGen 五篇论文的双语全文。版本与内容范围见[阅读说明](docs/reading-guide.md)。

## 阅读器与内容分离

浏览器首先加载轻量 HTML 外壳和共用 CSS／JavaScript，再请求资源清单和当前论文的完整双语 JSON，按结构化单元渲染正文。原图是独立资源，接近视口时加载；PDF 只在点击后打开。语言切换、全文搜索和打印不再请求正文。

所有资源由 GitHub Pages 静态托管，无后端、外部字体或运行时 CDN。现有 `papers/<paper-id>.html` 链接与章节锚点保持不变。完整正文依赖 JavaScript；未启用时仍可打开原始 PDF。

## 目录

```text
public/                     GitHub Pages 发布目录，可独立复制到静态 HTTP 服务
  index.html                论文索引
  papers/                   每篇论文的轻量阅读外壳
  reader/                   固定 loader.js 与带内容摘要的共用 CSS、JavaScript
  content/manifest.json     论文与阅读器资源清单
  content/<paper-id>/       带内容摘要的 PaperDocument JSON、固定文件名的独立原图
  notes/<paper-id>/notes.md 手工维护的笔记源文件，可直接在 GitHub 网页提交
  pdfs/                     原始论文 PDF
reader/                     阅读器源代码、外壳模板、共用与论文特有样式
data/                      文稿、翻译、原图及来源记录
  ace/                      独立正文源 article.html、目录和无损提取的原图
  skillforge/               双语数据、完整表格、提示词和原图
  permission-denied/        同版官方原文、译文与原图
  skillcat/                 同版原文、译文、公式、算法与原图
  skillgen/                 同版全文、译文、原图、表格与附录
  reader-meta.json          阅读器标题、作者、默认模式与兼容偏好设置
scripts/                    Python 构建、内容审计及浏览器验收
skills/paper-reading-room/  可复用论文制作 skill
```

`public/` 只包含运行所需文件。论文制作源不直接发布；构建器从现有文稿格式转换到统一 `PaperDocument v1`。复杂富文本、表格与 MathML 在所属单元内保留 HTML，图片不嵌入 JSON。`public/notes/` 内的 Markdown 是手工维护的笔记源，构建会原样保留，不为笔记内容或文件存在状态生成清单，因此可以单独提交笔记，无需重建其他产物。详见[内容接口与构建说明](docs/reader-architecture.md)。

## 本地预览与维护

使用 Python 3.10 或更新版本，从仓库根目录运行本地开发服务：

```bash
python3 scripts/dev_server.py
```

打开 [本地索引](http://localhost:8000/)。本地服务在 localhost 提供阅读器和笔记直接保存接口，笔记写入 `public/notes/<paper-id>/notes.md`；GitHub Pages 上则使用「保存到 GitHub」。请通过 HTTP 访问，直接双击 `file://` 页面不能可靠请求论文 JSON；本项目不再生成单文件离线阅读页。

修改文稿、图片或阅读器后，重建全部发布产物并审计：

```bash
python3 -B scripts/build.py
```

仅检查已有产物与内容边界：

```bash
python3 -B scripts/check.py
python3 -B -m unittest discover -s tests -v
```

重建与静态检查只使用 Python 标准库，无需下载论文源码。修改源文件与生成结果应一并提交。SkillCAT 需要重新提取原文单元时，可先运行 `python3 -B scripts/builders/skillcat_prepare.py`，审校翻译覆盖情况后再重建。图片提取的可选依赖见 skill 的[提取说明](skills/paper-reading-room/references/extraction-and-verification.md)。

并行验证新阅读器时可运行 `python3 -B scripts/build.py --preview`，访问 `reader-preview.html?paper=ace` 并切换各篇；它不改写正式论文外壳。正常构建会移除临时预览入口。

可选的本地浏览器验收需要 Node.js 22 与 Playwright，不参与部署流程：

```bash
npm install --no-save --package-lock=false playwright@1.62.1
npx playwright install chromium
node scripts/browser_check.cjs
```

测试覆盖五篇全文的 DOM 内容基线、三种语言、搜索、移动目录、锚点及前进后退、图片放大、打印、资源失败重试与仓库子路径。可通过 `CHROME_EXECUTABLE` 指定已有 Chrome，通过 `PLAYWRIGHT_MODULE` 指定已有 Playwright 包，`BROWSER_OUTPUT_DIR` 指定截图／PDF 输出目录。默认产物写入系统临时目录。迁移内容指纹在 `tests/migration-baseline.json`；后续有意修订正文时需审阅并同步对应指纹。

## GitHub Pages

站点通过 GitHub Actions 直接发布仓库里已提交的 `public/`。推送到 `main` 或手动触发工作流后，仅检出仓库、上传静态文件并部署；不重新构建、不安装 Node／Playwright／系统库，也不运行单元测试或浏览器验收。修改阅读器或论文制作源后，需要在本地运行构建并将生成的 `public/` 产物一起提交；单独修改 `public/notes/` 内的笔记无需构建。检查和测试脚本保留为本地按需工具，PR 不触发部署。

站内 URL 使用相对路径，支持 `https://<owner>.github.io/<repo>/`、用户站点和自定义域名。固定的小型 `loader.js` 会重验证资源清单，再加载最新的摘要脚本和样式；旧缓存外壳也能找到当前资源。资源清单地址相对外壳解析，清单内地址相对清单解析，正文资源地址相对论文 JSON 解析。共用脚本、样式和 JSON 使用内容摘要文件名，未变化资源保持原地址。图片统一使用 `figure-01.svg` 等固定文件名，正文与笔记共用同一份原图，不生成带哈希文件名的图片或额外副本。

本地修改不会自动推送或发布；部署状态见仓库的 [Actions](https://github.com/TrickEye/paper-reading-room/actions)。

## 制作流程与来源

复用 [paper-reading-room skill](skills/paper-reading-room/SKILL.md) 添加论文时，先建立原文、译文、图表与来源清单，再编写适配器接入统一发布格式，同步索引、目录清单和阅读说明。后续维护修改源文稿后重建，不手改发布 JSON 或论文外壳。

中文译文由 AI 生成并审校，供阅读参考，未经论文作者背书。引用、公式和原始排版以原始 PDF 为准；原论文及图表权利归原作者或相应权利人，具体来源见阅读页末尾。
