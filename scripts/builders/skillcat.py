#!/usr/bin/env python3
"""Build SkillCAT PaperDocument from matching v2 sources and translations."""
from pathlib import Path
import copy,hashlib,html,json,re
from html_tree import Node,TreeParser,serialize,tag,text_node
ROOT=Path(__file__).resolve().parents[2]
PUBLIC=ROOT/'public'
SRC=ROOT/'data'/'skillcat'
PDF=PUBLIC/'pdfs'/'SkillCAT-2606.13317v2.pdf'
VERSION='2606.13317v2'
def save(name,value):
 (SRC/(name+'.json')).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
def ancestors(n):
 while n.parent is not None:
  n=n.parent;yield n
def clean(n):
 if isinstance(n,str):return html.unescape(n)
 if n.tag=='annotation':return ''
 return ''.join(clean(c) for c in n.children)
def txt(n):return ' '.join(clean(n).split())
def source_nodes(a):
 return a.find_all(lambda n:n.tag in ['p','h1','h2','h3','h4','figcaption'] or n.has('ltx_bibitem'))
def strip_ids(n):
 for x in [n]+list(n.descendants()):
  x.attrs=[(k,v) for k,v in x.attrs if k!='id'];x.created=True
 return n
def translated(zh,n):
 # Preserve the exact original MathML for mathematical expressions in Chinese.
 out=html.escape(zh,quote=False)
 expr={}
 for x in n.find_all(lambda x:x.tag=='math'):
  tex=x.attr('alttext')
  if not tex:continue
  markup=serialize(strip_ids(copy.deepcopy(x)))
  expr[html.escape(tex,quote=False)]=markup
  for alias in json.loads((SRC/'math-aliases.json').read_text()).get(tex,[]):expr[html.escape(alias,quote=False)]=markup
  expr[html.escape(re.sub(r'\\+',lambda _:chr(92),tex),quote=False)]=markup
 if expr:
  # One substitution pass prevents matching variable names inside inserted MathML.
  pattern='|'.join(r'(?<![A-Za-z0-9])'+re.escape(t)+r'(?![A-Za-z0-9])' for t in sorted(expr,key=len,reverse=True))
  out=re.sub(pattern,lambda match:expr[match.group()],out)
 return TreeParser(out).root.children

def pair(n,uid,zh):
 original=n.children
 z=tag('span',[('class','zh translation'),('lang','zh-CN')],translated(zh,n))
 e=tag('span',[('class','en original'),('lang','en')],original)
 n.children=[z,e];z.parent=n;e.parent=n;n.set_attr('data-unit',uid);n.set_attr('data-searchable','true')
 for math in n.find_all(lambda x:x.tag=='math'):
  for ann in list(math.find_all(lambda x:x.tag=='annotation')):
   ann.parent.children.remove(ann)

def grid(table):
 rows=[r for b in table.children if isinstance(b,Node) and b.tag=='tbody' for r in b.children if isinstance(r,Node) and r.tag=='tr']
 occupied={};out=[]
 for y,row in enumerate(rows):
  x=0
  for c in [c for c in row.children if isinstance(c,Node) and c.tag in ['td','th']]:
   while (y,x) in occupied:x+=1
   v=next((d for d in c.children if isinstance(d,Node) and d.has('en')),c)
   for yy in range(y,y+int(c.attr('rowspan','1'))):
    for xx in range(x,x+int(c.attr('colspan','1'))):occupied[yy,xx]=txt(v)
   x+=int(c.attr('colspan','1'))
  out.append([occupied.get((y,xx),'') for xx in range(max((xx for yy,xx in occupied if yy==y),default=-1)+1)])
 return out

def main():
 translations=json.loads((SRC/'translations.json').read_text())
 extras=json.loads((SRC/'translations-extra.json').read_text())
 expected=json.loads((SRC/'translation-input.json').read_text())
 extra_expected=json.loads((SRC/'translation-extra-input.json').read_text())
 assert set(translations)=={x['id'] for x in expected},'main translation coverage'
 assert {x['id'] for x in extra_expected}<=set(extras),'extra translation coverage'
 raw=(SRC/'arxiv.html').read_text();r=TreeParser(raw).root
 a=r.find_all(lambda n:n.tag=='article' and n.has('ltx_document'))[0]
 # Build one stable unit for each source paragraph, heading, caption and bibliography entry.
 records=[];headings=[]
 for i,n in enumerate(source_nodes(a),1):
  if any(x.has('ltx_bibitem') or x.tag=='figcaption' for x in ancestors(n)):continue
  if n.tag=='p' and any(x.has('ltx_authors') for x in ancestors(n)):continue
  uid=n.attr('id') or 'unit-'+str(i)
  section=next((x.attr('id') for x in ancestors(n) if x.tag=='section'),'front')
  record={'id':uid,'kind':n.tag,'source':{'section':section,'version':VERSION},'en':next(x['en'] for x in expected if x['id']==uid),'zh':translations[uid]}
  records.append(record)
  if n.tag in ['h2','h3']:
   parent=next((x for x in ancestors(n) if x.attr('id')),None)
   target=parent.attr('id') if parent else 'heading-'+uid
   if not parent:n.set_attr('id',target)
   headings.append((n.tag,target,translations[uid]))
  pair(n,uid,translations[uid])
  if n.tag=='h1':n.set_attr('id','paper-title')
 save('main',records)
 save('references',[x for x in records if x['id'].startswith('bib.')])
 # Algorithm and table translations are separate source units; numbers are shared.
 for n in a.find_all(lambda n:n.has('ltx_listingline')):pair(n,n.attr('id'),extras[n.attr('id')])
 cell_map={x['en']:extras[x['id']] for x in extra_expected if x['kind']=='cell'}
 tables=[]
 for num,f in enumerate(a.find_all(lambda n:n.tag=='figure' and n.has('ltx_table')),1):
  sid=f.attr('id');f.set_attr('id','T'+str(num));f.children.insert(0,tag('span',[('id',sid),('class','source-anchor')]))
  t=f.find_all(lambda n:n.tag=='table')[0]
  for i,c in enumerate(t.find_all(lambda n:n.tag in ['td','th'])):
   # txt(TeX alt) from the pristine source matches the extra input extraction.
   def textext(n):
    if isinstance(n,str):return html.unescape(n)
    if n.tag=='math':return n.attr('alttext') or txt(n)
    return ''.join(textext(ch) for ch in n.children)
   value=' '.join(textext(c).split())
   if value in cell_map:pair(c,f'T{num}.cell{i}',cell_map[value])
   c.set_attr('data-searchable','true')
   if c.tag=='th':c.set_attr('scope','col')
  for ann in list(t.find_all(lambda n:n.tag=='annotation')):ann.parent.children.remove(ann)
  tables.append({'number':num,'source_id':sid,'rows':grid(t),'source_html':serialize(t)})
  parent=t.parent;wrap=tag('div',[('class','table-scroll'),('tabindex','0'),('role','region'),('aria-label',f'表 {num}，可横向滚动')]);parent.replace(t,wrap);wrap.children=[t];t.parent=wrap
 save('tables',tables)
 # Native display equations are shared language-independent units, not data tables.
 equations=[]
 for n in a.find_all(lambda n:n.tag=='table' and n.has('ltx_equation')):
  equations.append({'id':n.attr('id'),'mathml':serialize(n)})
  n.tag='div';n.raw_end=None;n.add_class('equation');n.set_attr('role','math');n.set_attr('data-unit',n.attr('id'))
  for d in n.descendants():
   if d.tag in ['tbody','tr','td']:d.add_class('equation-'+d.tag);d.tag='div';d.raw_end=None
 save('equations',equations)
 figures=[];assets=[]
 for num,f in enumerate(a.find_all(lambda n:n.tag=='figure' and n.has('ltx_figure')),1):
  sid=f.attr('id');old=f.find_all(lambda n:n.tag in ['img','object'])[0]
  original_url='https://arxiv.org/html/'+(old.attr('src') or old.attr('data'))
  ext='png' if num<3 else 'svg';filename=f'figure-{num:02d}.{ext}';path=SRC/'assets'/filename;data=path.read_bytes()
  if ext=='png':
   import struct
   w,h=struct.unpack('>II',data[16:24])
  else:
   match=re.search(r'<svg[^>]*width="([\d.]+)pt"[^>]*height="([\d.]+)pt"',data.decode());w,h=[round(float(v)*4/3) for v in match.groups()]
  cap=f.find_all(lambda n:n.tag=='figcaption')[0]
  image=tag('img',[('src','assets/'+filename),('alt',translations[cap.attr('data-unit')]),('width',w),('height',h),('loading','lazy'),('decoding','async')])
  f.children=[tag('span',[('id',sid),('class','source-anchor')]),tag('button',[('type','button'),('class','figure-zoom'),('aria-label',f'放大图 {num}')],[image]),cap]
  for ch in f.children:ch.parent=f
  f.set_attr('id',f'F{num}');f.set_attr('data-source-page',[1,3,6,7][num-1]);f.set_attr('data-original-image',filename)
  assets.append({'figure':num,'file':filename,'source_page':[1,3,6,7][num-1],'source_url':original_url,'width':w,'height':h,'method':'matching official arXiv HTML standalone original graphic','sha256':hashlib.sha256(data).hexdigest()})
  figures.append({'number':num,'source_id':sid,'en':next(x['en'] for x in expected if x['id']==cap.attr('data-unit')),'zh':translations[cap.attr('data-unit')]})
 save('assets',assets);save('figures',figures)
 # Front matter, source notes, and the existing ACE reading interface.
 a.set_attr('id','paper');a.set_attr('lang','zh-CN')
 abstract=a.find_all(lambda n:n.attr('id')=='abstract1')[0]
 for old in list(abstract.find_all(lambda n:n.has('ltx_title_abstract'))):old.parent.children.remove(old)
 abstract.children.insert(0,tag('h2',[],[tag('span',[('class','zh')],['摘要']),tag('span',[('class','en')],['Abstract'])]))
 note=TreeParser('<div class="metadata">arXiv:2606.13317v2 · cs.CL · 2026-07-29 · 9 页 / pages</div><aside class="translation-note"><strong>中文全文 · 逐段中英对照</strong><p>按同版原文完整翻译，保留 4 幅独立原图、2 张完整表格、6 个公式、算法及 34 条参考文献。中文由 AI 翻译并经主代理审校，供阅读参考；原始 PDF 为引用依据。</p></aside>').root.children
 affiliation=a.find_all(lambda n:n.attr('id')=='p1')[0]
 affiliation.parent.children.remove(affiliation);a.insert_before(abstract,affiliation)
 for n in note:a.insert_before(abstract,n)
 digest=hashlib.sha256(PDF.read_bytes()).hexdigest()
 footer=f'<footer class="source-footer" id="source"><p class="eyebrow">SOURCE & ATTRIBUTION</p><h2>来源与翻译说明</h2><p>Kunfeng Chen, Qihuang Zhong, Juhua Liu, Bo Du · 武汉大学 / Wuhan University · 南洋理工大学 / Nanyang Technological University.</p><p>译注：原文摘要等处写“49.69%”，结论明确写“49.69 percentage points”；译文分别保留为“49.69%”和“49.69 个百分点”，未统一改写。</p><p>原文版本：arXiv:2606.13317v2（2026 年 7 月 29 日），9 页。本版本没有附录。正文、图表注、算法行、参考文献题名均提供中文与英文对照。图内英文保留原样，数值及原作表述按原文保留。</p><p>翻译由 Luna 子代理完成并经主代理审校，网页由主代理制作。译文未经论文作者背书。</p><p><a href="https://arxiv.org/abs/{VERSION}">arXiv 摘要</a> · <a href="https://arxiv.org/html/{VERSION}">同版官方 HTML</a> · <a href="https://arxiv.org/src/{VERSION}">作者源码</a> · <a href="../pdfs/{PDF.name}">本地 PDF</a> · <a href="../index.html">论文索引</a></p><p>下载归档日期：2026-11-10<br>PDF SHA-256：<code>{digest}</code></p><p>源数据、术语表与图表记录保存在仓库 data/skillcat/，重建脚本位于 scripts/。</p></footer>'
 a.children.extend(TreeParser(footer).root.children)
 source_record={'title':expected[0]['en'],'authors':['Kunfeng Chen','Qihuang Zhong','Juhua Liu','Bo Du'],'arxiv_id':'2606.13317','version':'v2','version_date':'2026-07-29','download_date':'2026-11-10','pdf_pages':9,'pdf_url':'https://arxiv.org/pdf/'+VERSION,'pdf_file':PDF.name,'pdf_sha256':digest,'html_sha256':hashlib.sha256((SRC/'arxiv.html').read_bytes()).hexdigest(),'inventory':{'figures':4,'tables':2,'equations':6,'algorithms':1,'algorithm_html_lines':29,'references':34,'appendices':0}}
 archive=SRC/'source.tar'
 if archive.exists():source_record['source_archive_sha256']=hashlib.sha256(archive.read_bytes()).hexdigest()
 save('source',source_record)
 nav='<a href="#abstract1" class="nav-main">摘要 / Abstract</a>'
 for level,target,label in headings:nav+=f'<a class="nav-{"main" if level=="h2" else "sub"}" href="#{target}">{html.escape(label)}</a>'
 nav+='<a href="#alg1" class="nav-main">算法 1 · SkillCAT 流程</a><a href="#source" class="nav-main">来源与翻译说明</a>'
 import sys
 sys.path.insert(0,str(ROOT/'scripts'))
 from paper_document import emit_paper,toc_from_html
 emit_paper('skillcat',serialize(a),toc_from_html(nav))
 print('Built SkillCAT document:',len(records),'main units,',len(extra_expected),'algorithm/table units; 4 figures, 2 tables, 34 references.')
if __name__=='__main__':main()
