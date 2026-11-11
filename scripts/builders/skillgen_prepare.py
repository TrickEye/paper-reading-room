"""Extract original units from the matching official arXiv HTML, without translating."""
import importlib.util,json,html,re
from pathlib import Path
SRC=Path(__file__).resolve().parents[2]/'data'/'skillgen'
spec=importlib.util.spec_from_file_location('base',Path(__file__).with_name('html_tree.py'));m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
def clean(n):
 if isinstance(n,str):return html.unescape(n)
 if n.tag=='math':return n.attr('alttext') or ''.join(clean(x) for x in n.children)
 if n.tag=='annotation':return ''
 return ''.join(clean(c) for c in n.children)
def txt(n):return ' '.join(clean(n).split())
def ancestors(n):
 while n.parent is not None:
  n=n.parent;yield n
s=(SRC/'arxiv.html').read_text();r=m.TreeParser(s).root;a=r.find_all(lambda n:n.tag=='article')[0]
records=[]
for i,n in enumerate(a.find_all(lambda n:n.tag in ['p','h1','h2','h3','h4','figcaption'] or n.has('ltx_bibitem')),1):
 if any(x.has('ltx_bibitem') or x.tag=='figcaption' for x in ancestors(n)):continue
 if n.tag=='p' and any(x.has('ltx_authors') for x in ancestors(n)):continue
 records.append({'id':n.attr('id') or 'unit-'+str(i),'kind':n.tag,'en':txt(n)})
for record in records:
 if record['id'].startswith('bib.'):
  entry=a.find_all(lambda n:n.attr('id')==record['id'])[0]
  record['en']=entry.find_all(lambda n:n.has('ltx_bib_title'))[0].text().strip()
(SRC/'translation-input.json').write_text(json.dumps(records,ensure_ascii=False,indent=2)+'\n')
extra=[]
for n in a.find_all(lambda n:n.has('ltx_listingline')):
 extra.append({'id':n.attr('id'),'kind':'algorithm-line','en':txt(n)})
for n in a.find_all(lambda n:n.tag in ['td','th'] and not any(x.has('ltx_equation') for x in ancestors(n))):
 t=txt(n)
 if re.search('[A-Za-z]',t):extra.append({'id':'cell-'+str(len(extra)+1),'kind':'cell','en':t})
extra=[x for x in extra if x['kind']=='algorithm-line' or not re.match(r'^[\d(]',x['en'])]
(SRC/'translation-extra-input.json').write_text(json.dumps(extra,ensure_ascii=False,indent=2)+'\n')
print(len(records),'main units;',len(extra),'extra units')
