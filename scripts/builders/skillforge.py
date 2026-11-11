"""Build the SkillForge PaperDocument from its bilingual editorial sources.

Run: python3 scripts/builders/skillforge.py
Sources: the bundled ACL Anthology PDF, bilingual JSON, and original figure assets.
"""
from pathlib import Path
import html,json,re
ROOT=Path(__file__).resolve().parents[2]
PUBLIC=ROOT/'public'
SRC=ROOT/'data'/'skillforge'
load=lambda name:json.loads((SRC/(name+'.json')).read_text())
e=html.escape
import sys
sys.path.insert(0,str(ROOT/'scripts'))
from paper_document import emit_paper,toc_from_html
main,app=load('main'),load('appendix')
figs={x['number']:x for x in load('figures')};assets={x['figure']:x for x in load('assets')};tables={x['number']:x for x in load('tables')}
nav=[]
for r in main+app:
 if r['kind'] in ['h2','h3']:
  if r['id']=='A1':nav.append('<a class="nav-main" href="#bib">参考文献</a>')
  nav.append(f'<a class="nav-{ "main" if r["kind"]=="h2" else "sub"}" href="#{r["id"]}">{e(r["zh"])}</a>')
nav.append('<a class="nav-main" href="#source">来源与翻译说明</a>')
units=0
section_map={'2':'S2','2.1':'S2.SS1','2.2':'S2.SS2','2.3':'S2.SS3','3':'S3','3.1':'S3.SS1','3.2':'S3.SS2','3.3':'S3.SS3',**{f'B.{i}':f'A2.SS{i}' for i in range(1,8)},'D.1':'A4.SS1','D.2':'A4.SS2'}
def rich(text):
 text=e(text)
 text=re.sub(r'(图\s*|Fig\.\s*|Figure\s*)(\d+)',lambda m:f'<a href="#F{m[2]}">{m[0]}</a>',text)
 text=re.sub(r'(表\s*|Table\s*)([1-4])',lambda m:f'<a href="#T{m[2]}">{m[0]}</a>',text)
 text=re.sub(r'§([BD]?\.?\d+(?:\.\d+)?)',lambda m:f'<a href="#{section_map[m[1]]}">{m[0]}</a>' if m[1] in section_map else m[0],text)
 # Restore mathematical typography without touching identifiers or source data.
 replacements={
  'T_val^[s]':'T<sub>val</sub><sup>[s]</sup>',
  'T_contrast':'T<sub>contrast</sub>', 'T_train':'T<sub>train</sub>', 'T_val':'T<sub>val</sub>', 'T_test':'T<sub>test</sub>',
  'δ̄^[s]':'δ̄<sup>[s]</sup>', 'r_t^∅':'r<sub>t</sub><sup>∅</sup>', 'r_t^s':'r<sub>t</sub><sup>s</sup>', 'r_t^c':'r<sub>t</sub><sup>c</sup>',
  'τ_t^{c₁}':'τ<sub>t</sub><sup>c₁</sup>', 'τ_t^{c₂}':'τ<sub>t</sub><sup>c₂</sup>', 'τ_t^{c_K}':'τ<sub>t</sub><sup>c<sub>K</sub></sup>',
  'c_t':'c<sub>t</sub>', 'u_s':'u<sub>s</sub>', 'd_t':'d<sub>t</sub>', 'S_t':'S<sub>t</sub>', 'F_t':'F<sub>t</sub>',
  'Passk':'Pass<sup>k</sup>', 'Pass5':'Pass<sup>5</sup>', 'Pass1':'Pass<sup>1</sup>'}
 for before,after in replacements.items():text=text.replace(before,after)
 return text

def pair(zh,en,code=False):
 tag='pre' if code else 'span';f=e if code else rich
 return f'<{tag} class="zh translation" lang="zh-CN">{f(zh)}</{tag}><{tag} class="en original" lang="en">{f(en)}</{tag}>'

def attrs(id=None):
 global units
 units+=1
 return f'data-unit="sf{units:03d}" id="{id or "sf"+str(units).zfill(3)}" data-searchable="true"'

def fig(n):
 r,a=figs[n],assets[n]
 return f'''<figure class="ltx_figure" id="F{n}" data-source-page="{a['page']}" data-original-image="{a['file']}"><button type="button" class="figure-zoom" aria-label="{e(r['zh'])} 点击放大查看原图"><img src="assets/{a['file']}" alt="{e(r['zh'])}" width="{a['width']}" height="{a['height']}" loading="lazy" decoding="async"></button><figcaption {attrs()}>{pair(r['zh'],r['en'])}</figcaption></figure>'''

def cell(v):return pair(*v) if isinstance(v,list) else e(f'{v:.3f}' if isinstance(v,float) else str(v))
def table(n):
 r=tables[n];out=[f'<figure class="ltx_table" id="T{n}"><div class="table-scroll" tabindex="0" role="region" aria-label="表 {n}，可横向滚动"><table><thead>']
 if n==1:
  out.append('<tr>')
  for j,v in enumerate(r['headers']):out.append(f'<th scope="{ "col" if j<2 else "colgroup"}" { "rowspan=2" if j<2 else "colspan=2"}>{cell(v)}</th>')
  out.append('</tr><tr>'+('<th scope="col">Pass@1</th><th scope="col">RC</th>'*3)+'</tr>')
 else:out.append('<tr>'+''.join('<th scope="col">'+cell(v)+'</th>' for v in r['headers'])+'</tr>')
 out.append('</thead><tbody>')
 for i,row in enumerate(r['rows']):
  out.append('<tr>')
  for j,v in enumerate(row):
   if n==1 and j==0:
    if i%3==0:out.append('<th scope="rowgroup" rowspan="3">'+cell(v)+'</th>')
    continue
   tag='th' if j==0 or (n==1 and j==1) else 'td'
   best=n==1 and j>=2 and v==max(row[2+(j-2)%2::2])
   out.append(f'<{tag}'+(' scope="row"' if tag=='th' else '')+(' class="best"' if best else '')+'>'+cell(v)+f'</{tag}>')
  out.append('</tr>')
 out.append('</tbody></table></div>')
 out.append(f'<figcaption {attrs()}>{pair(r["zh"],r["en"])}</figcaption>')
 # The original table has two body columns under a combined printed label. Supply an explicit header without altering source values.
 if n==2:out.append('<p class="table-note">'+pair('数值、合计与成功率均按原表保留。','Values, totals, and success rates are reproduced as printed.')+'</p>')
 out.append('</figure>');return ''.join(out)

# Mathematical expressions are language-independent and displayed once, with actual subscripts/superscripts.
def eq(text):
 E={
 'T_contrast': 'T<sub>contrast</sub> = {t ∈ T<sub>train</sub> | ∃ c<sub>i</sub>, c<sub>j</sub> : r<sub>t</sub><sup>cᵢ</sup> = 1 ∧ r<sub>t</sub><sup>cⱼ</sup> = 0}',
 'S_t': 'S<sub>t</sub> = {τ<sub>t</sub><sup>c</sup> | r<sub>t</sub><sup>c</sup> = 1},　F<sub>t</sub> = {τ<sub>t</sub><sup>c</sup> | r<sub>t</sub><sup>c</sup> = 0}',
 'g_t':'g<sub>t</sub> = G(d<sub>t</sub>, {τ<sub>1</sub><sup>+</sup>, …, τ<sub>m</sub><sup>+</sup>}, {τ<sub>1</sub><sup>−</sup>, …, τ<sub>m</sub><sup>−</sup>})',
 'δ_t':'δ<sub>t</sub><sup>[s]</sup> = r<sub>t</sub><sup>s</sup> − r<sub>t</sub><sup>∅</sup>,　δ<sub>t</sub><sup>[s]</sup> ∈ {−1, 0, +1}',
 'δ̄^':'δ̄<sup>[s]</sup> = <span class="frac"><span>1</span><span>|T<sub>val</sub><sup>[s]</sup>|</span></span> ∑<sub>t ∈ T<sub>val</sub><sup>[s]</sup></sub> δ<sub>t</sub><sup>[s]</sup>',
 'C*':'C* = {s ∈ C | u<sub>s</sub> ≥ 5 ∧ δ̄<sup>[s]</sup> &gt; 0}',
 'AUC_i':'AUC<sub>i</sub> = <span class="frac"><span>1</span><span>5</span></span> ∑<sub>k=1</sub><sup>5</sup> Pass<sub>i</sub><sup>k</sup>'}
 for key,value in E.items():
  if text.startswith(key):
   number=re.search(r'\(([1-5])\)$',text)
   return value+(f'<span class="eq-no">({number[1]})</span>' if number else '')
 return None

current=False;sub=False
out=['<article class="ltx_document" lang="zh-CN" id="paper"><p class="eyebrow">RESEARCH PAPER / EMNLP 2026</p>']
out.append('<h1 '+attrs('paper-title')+'>'+pair('SkillForge：从成功—失败边界学习，实现一致的长程智能体','SkillForge: Learning from Success–Failure Boundaries for Consistent Long-Horizon Agents')+'</h1>')
out.append('''<p class="paper-original-title">SkillForge: Learning from Success–Failure Boundaries for Consistent Long-Horizon Agents</p><div class="authors"><p>Guangya Wan<sup>*1,2</sup>, Hao Wang<sup>1</sup>, Xiao Ling<sup>1</sup>, Mingyang Ling<sup>1</sup>, Xiaoqi Ren<sup>1</sup>, Sheng Li<sup>2</sup></p><p class="affiliations">'''+pair('¹ Google Cloud AI　·　² 弗吉尼亚大学\n* 本工作在 Google 实习期间完成。','¹ Google Cloud AI · ² University of Virginia\n* Work done during internship at Google.')+'''</p></div><div class="metadata"><span>EMNLP 2026 · ACL Anthology: 2026.emnlp-main.1954</span><span>25 页 · 16 图 · 4 表</span><span>DOI: 10.18653/2026.emnlp-main.1954</span></div>''')
out.append('<aside class="translation-note"><strong>中文全文阅读版</strong><p>'+pair('依据原始论文逐段翻译；中英对照模式按“中文一段、英文原文一段”排列，正文、附录、图注及表注均保留对应原文。图像使用论文独立原图，图内文字保留原样；提示词另附完整文字对照。作者名、模型名、API、标识符及数据保留原写法。','Paragraph-aligned Chinese translation of the original paper, including the main text, appendices, figure captions, and table captions. Original figures and data are preserved; prompt figures also have bilingual text transcriptions.')+'</p></aside>')

def close():
 global current,sub
 if sub:out.append('</section>');sub=False
 if current:out.append('</section>');current=False

def render(r):
 global current,sub
 kind=r['kind']
 if kind=='h2':
  close();out.append(f'<section id="{r["id"]}" class="ltx_section">');current=True
  out.append('<h2 '+attrs()+'>'+pair(r['zh'],r['en'])+'</h2>')
 elif kind=='h3':
  if sub:out.append('</section>')
  out.append(f'<section id="{r["id"]}" class="ltx_subsection"><h3 '+attrs()+'>'+pair(r['zh'],r['en'])+'</h3>');sub=True
 elif kind=='code':out.append('<div class="code-pair" '+attrs()+'>'+pair(r['zh'],r['en'],True)+'</div>')
 elif kind=='equation' and eq(r['en']):out.append('<div class="equation" '+attrs()+' role="math" aria-label="'+e(r['en'])+'">'+eq(r['en'])+'</div>')
 else:out.append('<p class="'+('paper-note' if kind=='note' else 'ltx_p')+'" '+attrs()+'>'+pair(r['zh'],r['en'])+'</p>')

for r in main:
 render(r)
 z=r['en']
 if z.startswith('A key insight to answer'):out.append(fig(1))
 if z.startswith('This section presents the core'):out.append(fig(2))
 if z.startswith('S_t ='):
  out.append('<p class="paper-note" '+attrs()+'>'+pair('¹ 我们改变解码配置（见附录 B），以提高混合结果任务的产出；附录图 15 展示由此产生的分歧。','¹ We vary decoding configurations (see Appendix B) to increase the yield of mixed-outcome tasks; Fig. 15 in Appendix illustrates a resulting divergences.')+'</p>')
 if z.startswith('Overall performance and consistency.'):out.append(table(1))
 if z.startswith('Beyond this,'):out.append(fig(3))
 if z.startswith('Ablation Studies.'):out.append(fig(4))
 if z.startswith('Case Study: Workflow'):out.append(fig(5))
 if z.startswith('Robustness to Approximate'):out.append(fig(6))
close()
out.append('<section class="ltx_bibliography" id="bib"><h2 '+attrs()+'>'+pair('参考文献','References')+'</h2><ol class="ltx_biblist">')
for r in load('references'):out.append('<li class="ltx_bibitem" '+attrs(r['id'])+'>'+pair(r['zh'],r['en'])+'</li>')
out.append('</ol></section><div class="part-divider">SUPPLEMENTARY MATERIAL<span>附录 / Appendices</span></div>')
# Keep prompts in Appendix C with each figure's own text immediately below it.
for r in app:
 if r.get('id')=='A4':
  for n in range(8,13):
   out.append(fig(n));pr=next(x for x in load('prompts') if x['figure']==n)
   out.append('<div class="code-pair prompt-transcript" '+attrs()+'>'+pair(pr['zh'],pr['en'],True)+'</div>')
 render(r)
 z=r['en']
 if z.startswith('and compare methods against'):out.append(table(4))
 if z.startswith('Per-Skill Diagnostics'):out.append(table(2))
 if z.startswith('Together, these results indicate that contrastive grounding'):out.append(table(3))
 if z.startswith('The appropriate depth and format'):out.append(fig(7))
close()
out.append('<section class="ltx_appendix" id="A4.cases"><h3 '+attrs()+'>'+pair('论文中的案例图','Case figures from the paper')+'</h3>')
for n in range(13,17):out.append(fig(n))
out.append('</section>')
out.append('<footer class="source-footer" id="source"><p class="eyebrow">SOURCE &amp; ATTRIBUTION</p><h2>'+pair('来源与翻译说明','Source and translation notes')+'</h2><p>'+pair('原作：Guangya Wan、Hao Wang、Xiao Ling、Mingyang Ling、Xiaoqi Ren、Sheng Li。EMNLP 2026，第 44486–44510 页。','Original work by Guangya Wan, Hao Wang, Xiao Ling, Mingyang Ling, Xiaoqi Ren, and Sheng Li. EMNLP 2026, pages 44486–44510.')+'</p><p><a href="https://aclanthology.org/2026.emnlp-main.1954/">ACL Anthology</a> · <a href="https://doi.org/10.18653/2026.emnlp-main.1954">DOI</a> · <a href="../pdfs/Skill-Forge-2026.emnlp-main.1954.pdf">原始 PDF / Original PDF</a></p><p>'+pair('本阅读版的改动为中文翻译、段落配对及网页排版；中文译文由 AI 生成，原作者未对译文背书。16 幅图均来自原始 PDF：8 幅直接提取原始内嵌图片，8 幅将矢量图或提示词框单独渲染；均不含周围正文或页码。表格的数值、舍入和原文中的表述按原作保留。','This edition adds an AI-generated Chinese translation, paragraph alignment, and web layout. The original authors have not endorsed the translation. All 16 figures come from the original PDF: 8 directly extracted embedded images and 8 isolated renderings of vector figures or prompt boxes. Table values, rounding, and source statements are preserved as printed.')+'</p><p>'+pair('更新日期：2026 年 11 月 9 日。全部图像已内嵌，正文与图表均可离线阅读；原始 PDF 在 pdfs/ 目录提供。','Updated November 9, 2026. All images are embedded for offline reading; the original PDF is provided in the pdfs/ directory.')+'</p></footer></article>')
emit_paper('skillforge','\n'.join(out),toc_from_html(''.join(nav)))
print(f'Built SkillForge document: {units} paired/content units, 16 figures, 4 tables, 49 references.')
