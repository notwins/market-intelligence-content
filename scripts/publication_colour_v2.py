"""Version-2 publication enrichment. Private copies only; no network or approval fabrication."""
from pathlib import Path
from html.parser import HTMLParser
from html import escape, unescape
import json, os, re, shutil, subprocess
from functools import lru_cache
from urllib.parse import quote

ROOT=Path(__file__).resolve().parents[1]
VOID={'area','base','br','col','embed','hr','img','input','link','meta','param','source','track','wbr'}
HUB='https://notwins.github.io/market-intelligence-hub/'

class Parsed(HTMLParser):
    def __init__(self,text):
        super().__init__(convert_charrefs=False)
        self.text=text;self.lines=[0];self.nodes=[];self.stack=[];self.parts=[]
        for m in re.finditer('\n',text):self.lines.append(m.end())
        self.feed(text);self.close()
    def pos(self):
        line,col=self.getpos();return self.lines[line-1]+col
    def handle_starttag(self,tag,attrs):
        start=self.pos();n={'tag':tag,'attrs':dict(attrs),'start':start,'open_end':start+len(self.get_starttag_text()),'parents':list(self.stack)}
        self.nodes.append(n)
        if tag not in VOID:self.stack.append(n)
        else:n['close_start']=n['end']=n['open_end']
    def handle_startendtag(self,tag,attrs):
        self.handle_starttag(tag,attrs)
        if tag not in VOID:
            n=self.stack.pop();n['close_start']=n['end']=n['open_end']
    def handle_endtag(self,tag):
        for i in range(len(self.stack)-1,-1,-1):
            if self.stack[i]['tag']==tag:
                n=self.stack[i];n['close_start']=self.pos();n['end']=self.text.index('>',self.pos())+1
                del self.stack[i:];return
    def handle_data(self,text):self.parts.append({'start':self.pos(),'end':self.pos()+len(text),'text':text,'parents':list(self.stack)})

def edits(text,changes):
    last=len(text)+1
    for start,end,value in sorted(changes,reverse=True):
        if end>last:raise ValueError('Overlapping HTML edits')
        text=text[:start]+value+text[end:];last=start
    return text

def read(path):return json.loads(Path(path).read_text(encoding='utf-8'))
@lru_cache(maxsize=8)
def catalogue(site):return read(Path(site)/'data/publication-colour-catalogue-v2.json')
@lru_cache(maxsize=8)
def patterns(site):
    return [(t,a,re.compile(re.escape(a['text']),0 if a['case_sensitive'] else re.I)) for t in catalogue(site)['tags'] for a in t['aliases']]
def matches(text,site):
    financial=re.compile(r'\b(?:shares?|stocks?|bonds?|equity|equities|earnings|revenue|issuer|investors?|dividend|securities|market capitalisation|market capitalization|NASDAQ|NYSE|SGX|HKEX)\b',re.I)
    candidates=[]
    for tag,alias,pattern in patterns(site):
        for m in pattern.finditer(text):
            start,end=m.span()
            if (start and (text[start-1].isalnum() or text[start-1]=='_')) or (end<len(text) and (text[end].isalnum() or text[end]=='_')):continue
            if tag['category']=='Companies / tickers' and not re.match(r'^(NASDAQ|NYSE|SGX|HKEX):',m[0]) and not financial.search(text[max(0,start-100):end+100]):continue
            candidates.append({'id':tag['id'],'start':start,'end':end,'text':m[0],'priority':tag['priority']})
    candidates.sort(key=lambda m:(-(m['end']-m['start']),-m['priority'],m['start'],m['id']))
    chosen=[]
    for m in candidates:
        if any(n['id']!=m['id'] and all(n[k]==m[k] for k in ('start','end','priority')) for n in candidates):continue
        if not any(m['start']<n['end'] and n['start']<m['end'] for n in chosen):chosen.append(m)
    return sorted(chosen,key=lambda m:(m['start'],-m['end']))
def plan(text,existing,segments,site):
    cat=catalogue(site);tags={t['id']:t for t in cat['tags']};ids=list(dict.fromkeys(i for i in existing if i in tags))
    for m in matches(text,site):
        if len(ids)<5 and m['id'] not in ids:ids.append(m['id'])
    rows=[]
    for segment in segments:
        hits=[]
        for m in matches(segment,site):
            if m['id'] not in ids:continue
            token=m['text'];url=cat['securities'].get(token) if re.fullmatch(r'(NASDAQ|NYSE|SGX|HKEX):[A-Z0-9.]+',token) else None
            if not url:url=HUB+'search.html?q='+quote('tag:"'+tags[m['id']]['label'].replace('\\','\\\\').replace('"','\\"')+'"',safe='')
            hits.append({**m,'href':url})
        rows.append(hits)
    return {'ids':ids,'segments':rows,'labels':[tags[i]['label'] for i in ids]}

@lru_cache(maxsize=4096)
def infer_labels(text,site):
    if not (Path(site)/'data/publication-colour-policy.json').exists():return []
    return plan(text,[],[],site)['labels']

def _strip(text):
    doc=Parsed(text);changes=[]
    for n in doc.nodes:
        mode=n['attrs'].get('data-mih-auto')
        if mode not in ('row','style','term'):continue
        if 'end' not in n:raise ValueError('Unclosed generated colour element')
        if any(p['attrs'].get('data-mih-auto') in ('row','style') for p in n['parents']):continue
        if mode=='term':
            changes.extend([(n['start'],n['open_end'],''),(n['close_start'],n['end'],'')])
        else:changes.append((n['start'],n['end'],''))
    return edits(text,changes)

def _visible(n):
    return not any(p['tag'] in {'script','style','nav','footer','header','aside','table','svg','canvas','button','a','code','pre','template'} or
        'hidden' in p['attrs'] or p['attrs'].get('aria-hidden')=='true' or
        re.search(r'display\s*:\s*none|visibility\s*:\s*hidden',p['attrs'].get('style',''),re.I)
        for p in n['parents'])

def enrich_html(text,metadata,site,require_contract=True):
    """Idempotent: reconstruct only our own markup; preserve manual semantics and links."""
    text=_strip(text);doc=Parsed(text);cat=catalogue(site);tags={t['id']:t for t in cat['tags']}
    contracts=[n for n in doc.nodes if n['attrs'].get('id')=='mih-research-contract']
    if require_contract and len(contracts)!=1:raise ValueError('Automatic HTML enrichment requires one V3 report contract')
    contract=None
    if contracts:
        if len(contracts)!=1:raise ValueError('Duplicate research contract')
        node=contracts[0];contract=json.loads(text[node['open_end']:node['close_start']])
        contract['semantic_tags']=[t for t in contract.get('semantic_tags',[]) if not t.get('element_id','').startswith('mih-auto-')]
    ids=[n['attrs']['id'] for n in doc.nodes if 'id' in n['attrs']]
    if len(ids)!=len(set(ids)) or any(i.startswith('mih-auto-') for i in ids):raise ValueError('Duplicate or reserved automatic HTML id')
    existing=metadata.get('tags',[])
    if not isinstance(existing,list) or any(i not in tags for i in existing):raise ValueError('Unknown explicit canonical tag')
    manual=[t['id'] for t in (contract or {}).get('semantic_tags',[])]
    explicit=list(dict.fromkeys(existing+manual))
    if len(explicit)>12:raise ValueError('More than 12 explicit tags; review metadata')
    title_id=(contract or {}).get('title_id')
    title=next((n for n in doc.nodes if n['attrs'].get('id')==title_id),None) if title_id else next((n for n in doc.nodes if n['tag']=='h1'),None)
    if title is None or 'end' not in title:raise ValueError('Missing closed article title')
    excluded={(contract or {}).get('cutoff_id'),(contract or {}).get('limitations_id'),*(contract or {}).get('source_ids',[])}
    parts=[p for p in doc.parts if _visible(p) and any(n['tag'] in ('p','li') for n in p['parents']) and
           not any(n['attrs'].get('id') in excluded or 'data-mih-semantic' in n['attrs'] or
               'color' in n['attrs'].get('style','').lower() or 'mu-card-tags' in n['attrs'].get('class','')
               for n in p['parents'])]
    source=' '.join([metadata.get('title',''),metadata.get('summary',''),*(unescape(p['text']) for p in parts)])
    result=plan(source,explicit,[p['text'] for p in parts],site);selected=result['ids']
    if not selected:raise ValueError('No unambiguous canonical tag; supply reviewed metadata tags before publication')
    def style(t):return ';'.join(f'{k}:{t[v]}' for k,v in [(' --tag-text'.strip(),'text'),('--tag-bg','background'),('--tag-dark-text','dark_text'),('--tag-dark-bg','dark_background')])
    def href(t):return HUB+'search.html?q='+quote('tag:"'+t['label'].replace('\\','\\\\').replace('"','\\"')+'"',safe='')
    declared=[]
    def anchor(tag_id,label,eid,url,chip=False):
        t=tags[tag_id]
        if contract is not None:declared.append({'id':tag_id,'element_id':eid,'context':'Canonical tag selected by explicit metadata or conservative whole-phrase rule v2; final bundle requires review.',
            'light':t['text'],'dark':t['dark_text'],'lightChip':t['background'],'darkChip':t['dark_background']})
        return '<a '+('data-mih-auto="term" ' if not chip else '')+'id="'+eid+'" data-mih-semantic="'+escape(tag_id,quote=True)+'" class="'+('mih-colour-chip' if chip else 'mih-colour-term')+'" style="'+style(t)+'" href="'+escape(url,quote=True)+'">'+escape(label)+'</a>'
    changes=[]
    # Reuse an existing manually managed tag row rather than create a duplicate.
    rows=[n for n in doc.nodes if set(n['attrs'].get('class','').split())&{'mu-card-tags','tags','v2-meta','tag-row'} or 'data-mih-tag-row' in n['attrs']]
    if len(rows)>1:raise ValueError('Multiple semantic tag rows need editorial reconciliation')
    if rows:
        row=rows[0]
        if 'end' not in row:raise ValueError('Unclosed existing tag row')
        registered={t['id'] for t in (contract or {}).get('semantic_tags',[]) if any(n['attrs'].get('id')==t['element_id'] and row in n['parents'] for n in doc.nodes)}
        # Unknown/unmarked custom rows cannot be safely guessed or duplicated.
        if not registered:raise ValueError('Existing tag row has no canonical markers; map it before automatic enrichment')
        # Current reports use reviewed <span> chips in .tags and .v2-meta.
        # Convert those spans in place, preserving their IDs and contract entries.
        for n in doc.nodes:
            tag_id=n['attrs'].get('data-mih-semantic')
            if row not in n['parents'] or tag_id not in registered:continue
            if n['tag'] not in ('a','span') or any(p['tag']=='a' for p in n['parents']):raise ValueError('Existing semantic chip needs manual link review')
            attrs=dict(n['attrs']);attrs['class']=' '.join(dict.fromkeys(attrs.get('class','').split()+['mih-colour-chip']))
            original_style=re.sub(r'--tag-(?:text|bg|dark-text|dark-bg)\s*:[^;]+;?','',attrs.get('style','')).strip(';')
            attrs['style']=(original_style+';' if original_style else '')+style(tags[tag_id])
            attrs.setdefault('href',href(tags[tag_id]))
            opening='<a '+ ' '.join(k if v is None else k+'="'+escape(v,quote=True)+'"' for k,v in attrs.items())+'>'
            changes.extend([(n['start'],n['open_end'],opening),(n['close_start'],n['end'],'</a>')])
        missing=[i for i in selected[:5] if i not in registered]
        addition=''.join(anchor(i,tags[i]['label'],'mih-auto-tag-'+str(k),href(tags[i]),True) for k,i in enumerate(missing,1))
        # Generated additions are separately owned so an identical rerun can rebuild them.
        if addition:changes.append((row['close_start'],row['close_start'],'<span data-mih-auto="row">'+addition+'</span>'))
    else:
        chips=''.join(anchor(i,tags[i]['label'],'mih-auto-tag-'+str(k),href(tags[i]),True) for k,i in enumerate(selected[:5],1))
        changes.append((title['end'],title['end'],'<div data-mih-auto="row" data-mih-auto-row="1" aria-label="Article topics">'+chips+'</div>'))
    seen=set(manual);count=0;budget=max(0,3-len(manual))
    for part,hits in zip(parts,result['segments']):
        for m in hits:
            if count>=budget or m['id'] in seen:continue
            count+=1;seen.add(m['id'])
            changes.append((part['start']+m['start'],part['start']+m['end'],anchor(m['id'],m['text'],'mih-auto-term-'+str(count),m['href'])))
    css=(ROOT/'site/publication-colour-v2.css').read_text(encoding='utf-8')
    head=next((n for n in doc.nodes if n['tag']=='head' and 'close_start' in n),None)
    if head is None:raise ValueError('Complete HTML head required')
    changes.append((head['close_start'],head['close_start'],'<style id="mih-auto-style" data-mih-auto="style">'+css+'</style>'))
    if contract is not None:
        contract['semantic_tags']+=declared;n=contracts[0]
        changes.append((n['open_end'],n['close_start'],json.dumps(contract,ensure_ascii=False,indent=2).replace('<','\\u003c')))
    output=edits(text,changes)
    audit_html(output,site,require_contract)
    return output,{**metadata,'tags':selected}

def audit_html(text,site,require_contract=True):
    doc=Parsed(text);styles=[n for n in doc.nodes if n['attrs'].get('id')=='mih-auto-style']
    if len(styles)!=1 or text[styles[0]['open_end']:styles[0]['close_start']]!=(ROOT/'site/publication-colour-v2.css').read_text(encoding='utf-8'):raise ValueError('Missing/changed version-2 semantic style; run prepare again')
    chips=[n for n in doc.nodes if 'mih-colour-chip' in n['attrs'].get('class','').split()]
    if not chips:raise ValueError('Missing visible colour tags')
    tags={t['id']:t for t in catalogue(site)['tags']}
    for n in chips+[n for n in doc.nodes if 'mih-colour-term' in n['attrs'].get('class','').split()]:
        t=tags.get(n['attrs'].get('data-mih-semantic'))
        if not t or any(p['tag']=='a' for p in n['parents']):raise ValueError('Unknown semantic identity or nested link')
        for k,v in [(' --tag-text'.strip(),'text'),('--tag-bg','background'),('--tag-dark-text','dark_text'),('--tag-dark-bg','dark_background')]:
            if f'{k}:{t[v]}' not in n['attrs'].get('style',''):raise ValueError('Missing canonical applied colour')
        url=n['attrs'].get('href','')
        if not (url.startswith(HUB+'search.html?q=') or url in catalogue(site)['securities'].values()):raise ValueError('Invalid semantic link')
    if require_contract:
        from validate_research_contracts import validate_document
        validate_document(text,read(Path(site)/'data/colour-templates-v3.json'))

def enrich_folder(report_dir,metadata,output,site):
    from research_feed import safe_name,require
    src=Path(report_dir).resolve();out=Path(output)
    require(src.is_dir() and not src.is_symlink() and not out.exists(),'Real source and new private output required')
    files=list(src.iterdir());require(all(p.is_file() and not p.is_symlink() and safe_name(p.name) for p in files),'Only manifested public file types are accepted')
    require(any(p.name=='index.html' for p in files),'Full report required')
    out.mkdir(parents=True)
    enriched,meta=enrich_html((src/'index.html').read_text(encoding='utf-8'),metadata,site)
    (out/'index.html').write_text(enriched,encoding='utf-8',newline='\n')
    for p in files:
        if p.name=='index.html':continue
        if p.suffix=='.html':
            value,_=enrich_html(p.read_text(encoding='utf-8'),meta,site)
            (out/p.name).write_text(value,encoding='utf-8',newline='\n')
        else:shutil.copyfile(p,out/p.name)
    return out,meta

def enrich_read_up(record,legacy):
    site=ROOT/'site';policy=site/'data/publication-colour-policy.json'
    if not policy.exists() or record['id']+'-r'+str(record['revision']) in read(policy)['legacy_read_ups']:return legacy
    text,_=enrich_html(legacy.decode('utf-8'),{'title':record['title'],'summary':record['takeaway'],'tags':[]},site,False)
    return text.encode('utf-8')
