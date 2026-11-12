#!/usr/bin/env python3
"""Build SkillGen bilingual full text from matching v1 sources and translations."""
from pathlib import Path
import copy,hashlib,html,json,re
from html_tree import Node,TreeParser,serialize,tag,text_node
ROOT=Path(__file__).resolve().parents[2]
PUBLIC=ROOT/'public'
SRC=ROOT/'data'/'skillgen'
PDF=PUBLIC/'pdfs'/'SkillGen-2605.10999v1.pdf'
VERSION='2605.10999v1'
# Chinese translations use explicit markers so their notes follow the same
# block layout as the source-language footnotes instead of reading as prose.
TRANSLATED_FOOTNOTES={
 'S1.p5.1': {'1':'代码见 <a href="https://github.com/yccm/SkillGen" class="ltx_ref ltx_url ltx_font_typewriter">https://github.com/yccm/SkillGen</a>。'},
 'S3.SS3.p8.2': {'2':'这里，g_{\\mathrm{abs}}\\in\\mathbb{Z}_{\\geq 0} 是净修复数的绝对下限，g_{\\mathrm{rel}}\\in[0,1] 是以构建期验证子集比例表示的相对下限。门控是一种简单的构建期保障：绝对项防止部署按数量计收益微不足道的候选技能，相对项要求收益随验证子集规模增长，最后的下限 1 要求构建期净增益严格为正。'},
 'A3.SS5.p1.1': {'3':'<a href="https://openai.com/api/pricing" class="ltx_ref ltx_url ltx_font_typewriter">https://openai.com/api/pricing</a>，访问于 2026 年 4 月。'},
}
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
def translated(zh,n,uid):
 # Preserve the exact original MathML for mathematical expressions in Chinese.
 out=html.escape(zh,quote=False)
 for number,content in TRANSLATED_FOOTNOTES.get(uid,{}).items():
  marker=html.escape(f'[[footnote:{number}]]',quote=False)
  note=(f'<span class="ltx_note ltx_role_footnote translation-footnote">'
        f'<sup class="ltx_note_mark">{number}</sup><span class="ltx_note_outer">'
        f'<span class="ltx_note_content"><sup class="ltx_note_mark">{number}</sup>{content}'
        f'</span></span></span>')
  assert marker in out, f'missing translated footnote marker {number} in {uid}'
  out=out.replace(marker,note,1)
 expr={}
 for x in n.find_all(lambda x:x.tag=='math'):
  tex=x.attr('alttext')
  if not tex:continue
  markup=serialize(strip_ids(copy.deepcopy(x)))
  expr[html.escape(tex,quote=False)]=markup
  expr[html.escape(' '.join(tex.split()),quote=False)]=markup
  for alias in json.loads((SRC/'math-aliases.json').read_text()).get(tex,[]):expr[html.escape(alias,quote=False)]=markup
  expr[html.escape(re.sub(r'\\+',lambda _:chr(92),tex),quote=False)]=markup
 if expr:
  # One substitution pass prevents matching variable names inside inserted MathML.
  pattern='|'.join(r'(?<![A-Za-z0-9])'+re.escape(t)+r'(?![A-Za-z0-9])' for t in sorted(expr,key=len,reverse=True))
  out=re.sub(pattern,lambda match:expr[match.group()],out)
 return TreeParser(out).root.children

def pair(n,uid,zh):
 original=n.children
 z=tag('span',[('class','zh translation'),('lang','zh-CN')],translated(zh,n,uid))
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
 assert set(extras)=={x['id'] for x in extra_expected},'extra translation coverage'
 byid={x['id']:x for x in expected}
 a=TreeParser((SRC/'arxiv.html').read_text()).root.find_all(lambda n:n.tag=='article' and n.has('ltx_document'))[0]
 records=[];headings=[]
 for i,n in enumerate(source_nodes(a),1):
  if any(x.has('ltx_bibitem') or x.tag=='figcaption' for x in ancestors(n)):continue
  if n.tag=='p' and any(x.has('ltx_authors') for x in ancestors(n)):continue
  uid=n.attr('id') or 'unit-'+str(i)
  records.append({'id':uid,'kind':n.tag,'source':{'section':next((x.attr('id') for x in ancestors(n) if x.tag=='section'),'front'),'version':VERSION},'en':byid[uid]['en'],'zh':translations[uid]})
  if n.tag in ['h2','h3','h4']:
   parent=next((x for x in ancestors(n) if x.attr('id')),None)
   target=parent.attr('id') if parent else 'heading-'+uid
   if not parent:n.set_attr('id',target)
   headings.append({'id':target,'label':translations[uid],'level':2 if n.tag=='h2' else 3})
  if n.has('ltx_bibitem'):
   title=n.find_all(lambda n:n.has('ltx_bib_title'))[0]
   pair(title,uid,translations[uid])
  else:pair(n,uid,translations[uid])
  if n.tag=='h1':n.set_attr('id','paper-title')
 save('main',[x for x in records if not x['id'].startswith('bib.')])
 save('references',[x for x in records if x['id'].startswith('bib.')])
 for n in a.find_all(lambda n:n.has('ltx_listingline')):pair(n,n.attr('id'),extras[n.attr('id')])
 cell_map={x['en']:extras[x['id']] for x in extra_expected if x['kind']=='cell'}
 tables=[]
 def textext(n):
  if isinstance(n,str):return html.unescape(n)
  if n.tag=='math':return n.attr('alttext') or txt(n)
  return ''.join(textext(ch) for ch in n.children)
 for num,f in enumerate(a.find_all(lambda n:n.tag=='figure' and n.has('ltx_table')),1):
  sid=f.attr('id');f.set_attr('id','T'+str(num));f.children.insert(0,tag('span',[('id',sid),('class','source-anchor')]))
  t=f.find_all(lambda n:n.tag=='table')[0]
  for i,c in enumerate(t.find_all(lambda n:n.tag in ['td','th'])):
   value=' '.join(textext(c).split())
   if value in cell_map and re.search('[A-Za-z]',value):pair(c,f'T{num}.cell{i}',cell_map[value])
   c.set_attr('data-searchable','true')
   if c.tag=='th':c.set_attr('scope','col')
  for ann in list(t.find_all(lambda n:n.tag=='annotation')):ann.parent.children.remove(ann)
  tables.append({'number':num,'source_id':sid,'rows':grid(t),'source_html':serialize(t)})
  parent=t.parent;wrap=tag('div',[('class','table-scroll'),('tabindex','0'),('role','region'),('aria-label',f'表 {num}，可横向滚动')]);parent.replace(t,wrap);wrap.children=[t];t.parent=wrap
 save('tables',tables)
 equations=[]
 for n in a.find_all(lambda n:n.tag=='table' and (n.has('ltx_equation') or n.has('ltx_equationgroup'))):
  equations.append({'id':n.attr('id'),'mathml':serialize(n)})
  n.tag='div';n.raw_end=None;n.add_class('equation');n.set_attr('role','math')
  for d in n.descendants():
   if d.tag in ['tbody','tr','td']:d.add_class('equation-'+d.tag);d.tag='div';d.raw_end=None
 save('equations',equations)
 figures=[];assets=[]
 pages=[3,7,8,8,8,9,9,19]
 for num,f in enumerate(a.find_all(lambda n:n.tag=='figure' and n.has('ltx_figure')),1):
  sid=f.attr('id');old=f.find_all(lambda n:n.tag in ['img','object'])[0]
  original_url='https://arxiv.org/html/'+(old.attr('src') or old.attr('data'))
  ext='png' if num in [1,4] else 'svg';filename=f'figure-{num:02d}.{ext}';path=SRC/'assets'/filename;data=path.read_bytes()
  if ext=='png':
   import struct
   w,h=struct.unpack('>II',data[16:24])
  else:
   view=re.search(r'viewBox="([^"]+)"',data.decode())
   if view:_,_,w,h=map(float,view.group(1).split());w,h=round(w),round(h)
   else:
    match=re.search(r'<svg[^>]*width="([\d.]+)pt"[^>]*height="([\d.]+)pt"',data.decode());w,h=[round(float(v)*4/3) for v in match.groups()]
  cap=f.find_all(lambda n:n.tag=='figcaption')[0]
  image=tag('img',[('src','assets/'+filename),('alt',translations[cap.attr('data-unit')]),('width',w),('height',h),('loading','lazy'),('decoding','async')])
  f.children=[tag('span',[('id',sid),('class','source-anchor')]),tag('button',[('type','button'),('class','figure-zoom'),('aria-label',f'放大图 {num}')],[image]),cap]
  for ch in f.children:ch.parent=f
  f.set_attr('id',f'F{num}');f.set_attr('data-source-page',pages[num-1]);f.set_attr('data-original-image',filename)
  assets.append({'figure':num,'file':filename,'source_page':pages[num-1],'source_url':original_url,'width':w,'height':h,'method':'matching official arXiv HTML standalone original graphic','sha256':hashlib.sha256(data).hexdigest()})
  figures.append({'number':num,'source_id':sid,'en':byid[cap.attr('data-unit')]['en'],'zh':translations[cap.attr('data-unit')]})
 save('assets',assets);save('figures',figures)
 # Preserve author names while pairing the affiliation and contribution notes.
 authors=a.find_all(lambda n:n.has('ltx_authors'))[0]
 person=authors.find_all(lambda n:n.has('ltx_personname'))[0]
 institution=next(i for i,ch in enumerate(person.children) if isinstance(ch,Node) and ch.tag=='br')
 affiliation=tag('span',[('class','affiliations')],person.children[institution:])
 person.children=person.children[:institution]+[affiliation];affiliation.parent=person
 pair(affiliation,'front.affiliations','¹ 慕尼黑大学慕尼黑机器学习中心；² 圣母大学；³ 微软研究院。')
 contribution=authors.find_all(lambda n:n.attr('id')=='id6.1')[0]
 pair(contribution,'front.contribution','同等贡献。联系邮箱：yuchen.ma@lmu.de 和 yhuang37@nd.edu。')
 # The HTML's literal footnotemark artifact is a typesetting error, not prose.
 artifact=authors.find_all(lambda n:n.attr('id')=='footnotex1')[0]
 artifact.parent.children.remove(artifact)
 # Remove only presentational declarations outside the publication HTML contract.
 allowed={'--ltx-bg-color','--ltx-fg-color','width','padding-left','padding-right','list-style-type','float'}
 for n in a.descendants():
  if n.attr('style'):
   style=';'.join(x for x in n.attr('style').split(';') if x.partition(':')[0].strip() in allowed)
   n.attrs=[(k,v) for k,v in n.attrs if k!='style'];n.created=True
   if style:n.set_attr('style',style)
 for ann in list(a.find_all(lambda n:n.tag=='annotation')):ann.parent.children.remove(ann)
 a.set_attr('id','paper');a.set_attr('lang','zh-CN')
 abstract=a.find_all(lambda n:n.attr('id')=='abstract1')[0]
 for old in list(abstract.find_all(lambda n:n.has('ltx_title_abstract'))):old.parent.children.remove(old)
 abstract.children.insert(0,tag('h2',[],[tag('span',[('class','zh')],['摘要']),tag('span',[('class','en')],['Abstract'])]))
 note=TreeParser('<aside class="translation-note"><strong>中文全文 · 逐段中英对照</strong><p>依据所提供的 arXiv:2605.10999v1 原始论文翻译，含正文、附录 A–D、8 幅原图、4 张完整表格、算法与 37 条参考文献题名。公式保留原始 MathML，图内英文保留原样。中文由 AI 翻译，供阅读参考；引用及原始排版以 PDF 为准。</p></aside>').root.children
 for n in note:a.insert_before(abstract,n)
 digest=hashlib.sha256(PDF.read_bytes()).hexdigest()
 footer=f'<footer class="source-footer" id="source"><h2>来源与翻译说明</h2><p>原文：arXiv:{VERSION}，2026 年 5 月 9 日，20 页。中文全文由 AI 翻译，未经作者背书。原图来自同版官方 HTML，表格保留原始全部行列和数值。参考文献保留作者与出处并翻译题名。原作中可能存在的表述差异按原文保留。</p><p><a href="https://arxiv.org/abs/{VERSION}">arXiv 摘要</a> · <a href="https://arxiv.org/html/{VERSION}">官方 HTML</a> · <a href="../pdfs/{PDF.name}">原始 PDF</a> · <a href="../index.html">论文索引</a></p><p>PDF SHA-256：<code>{digest}</code></p></footer>'
 a.children.extend(TreeParser(footer).root.children)
 toc=[{'id':'abstract1','label':'摘要','level':2}]+headings+[{'id':'alg1','label':'算法 1 · SkillGen','level':2},{'id':'source','label':'来源与翻译说明','level':2}]
 save('toc',toc)
 (SRC/'article.html').write_text(serialize(a),encoding='utf-8')
 record=json.loads((SRC/'source.json').read_text());record.update({'content_scope':'Full bilingual text including appendices A–D, algorithm and bibliography titles.','translation_status':'complete','html_sha256':hashlib.sha256((SRC/'arxiv.html').read_bytes()).hexdigest(),'inventory':{'figures':8,'tables':4,'equations':len(equations),'algorithms':1,'references':len([x for x in records if x['id'].startswith('bib.')]),'appendices':4}});record.pop('guide_language',None);save('source',record)
 import sys
 sys.path.insert(0,str(ROOT/'scripts'))
 from paper_document import emit_paper
 emit_paper('skillgen',serialize(a),toc)
 print('Built SkillGen:',len(records),'main units;',len(equations),'equations; 8 figures; 4 tables.')
if __name__=='__main__':main()
