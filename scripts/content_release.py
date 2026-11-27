"""Validate and stage independent public content. No UI repository checkout or deploy."""
import argparse,json,shutil,subprocess,hashlib,re,sys
from pathlib import Path
from html.parser import HTMLParser
from research_feed import ROOT,read,canonical,require,compile_feed,digest
from import_hourly_news import validate,merge,empty_feed
from public_data_projection import private_url
from verify_research_destinations import verify_staged
from archive_navigation import decorate, restore
import read_ups

BASE='https://notwins.github.io/market-intelligence-content/'
HUB='https://notwins.github.io/market-intelligence-hub/'

def preserve(repo,before,after):
    if not before or set(before)=={'0'}:return
    def tree(ref):
        return {s.split('\t')[1]:s.split()[2] for s in subprocess.check_output(['git','ls-tree','-r',ref],cwd=repo,text=True).splitlines()}
    old,new=tree(before),tree(after)
    frozen={'scripts/publication_colour_v1.py','scripts/publication_colour.py','site/publication-colour-v1.css','site/data/publication-colour-catalogue-v1.json','site/data/publication-colour-policy.json'}
    if 'site/data/publication-colour-policy.json' in old:frozen.add('scripts/read_ups.py')
    for p in frozen:
        if p in old:require(new.get(p)==old[p],'Published v1 renderer/standard is frozen; introduce a new version: '+p)
    for p in {'scripts/publication_colour_v2.py','site/publication-colour-v2.css','site/data/publication-colour-catalogue-v2.json','site/data/publication-colour-policy-v2.json'}:
        if p in old:require(new.get(p)==old[p],'Published v2 renderer/standard is frozen; introduce a new version: '+p)
    for p,h in old.items():
        if p.startswith(('baseline/','site/research/','site/data/research-records/','site/data/read-up-records/','site/data/hourly-archive/')) or p=='site/data/research-register.json':
            require(new.get(p)==h,'Immutable publication changed: '+p)
    path='site/data/hourly-news.json'
    if path in old:
        a=json.loads(subprocess.check_output(['git','show',before+':'+path],cwd=repo))
        b=json.loads(subprocess.check_output(['git','show',after+':'+path],cwd=repo))
        rows={x['id']:x for x in b['editions']}
        require(all(rows.get(x['id'])==x for x in a['editions']),'Hourly history removed or changed')

def validate_site(site):
    site=Path(site);feed=compile_feed(site)
    read_ups.collect(site)
    registered={r['id'] for r in feed['records']}
    if (site/'research').exists():
        require(all(p.is_dir() and p.name in registered for p in (site/'research').iterdir()),'Unregistered report destination')
    news=read(site/'data/hourly-news.json')
    baseline=read(site.parent/'baseline/hourly-news.json')
    ids={e['id']:e for e in news['editions']}
    require(len(ids)==len(news['editions']),'Duplicate hourly edition')
    require(all(ids.get(e['id'])==e for e in baseline['editions']),'Public historical news changed')
    for e in news['editions']:validate(e)
    expected,_=merge(empty_feed(),{'editions':news['editions']})
    require(expected['editions']==news['editions'] and expected['last_complete_cutoff']==news['last_complete_cutoff'],'Incorrect hourly ordering or complete cutoff')
    baseline_ids={e['id'] for e in baseline['editions']}
    for e in news['editions']:
        if e['id'] not in baseline_ids:
            require(read(site/'data/hourly-archive'/(e['id']+'.json'))==e,'Missing or changed hourly archive')
    for p in site.rglob('*'):
        require(not p.is_symlink(),'No symlinks')
        if not p.is_file():continue
        try:text=p.read_text(encoding='utf-8')
        except UnicodeError:continue
        for url in re.findall(r'https?://[^\s<>"\']+',text):
            require(not private_url(url),'Private input URL in public content')
    return feed,news

class Text(HTMLParser):
    def __init__(self):super().__init__();self.parts=[];self.hidden=0
    def handle_starttag(self,tag,attrs):
        if tag in ('script','style'):self.hidden+=1
    def handle_endtag(self,tag):
        if tag in ('script','style'):self.hidden=max(0,self.hidden-1)
    def handle_data(self,data):
        if not self.hidden:self.parts.append(data)

def search(feed,news,site):
    from publication_colour_v2 import infer_labels
    rows=[]
    def add(key,kind,title,text,href,date,tags,reading=None):
        rows.append(dict(id='content-'+key,kind=kind,title=title,text=text,href=href,date=date,source=None,status='Verified dated public content',tags=tags,location={'label':'Research Explained' if kind=='Research edition' else 'V4 → Hourly news','href':href,'exact':kind=='Research edition'},source_access='public',reading=reading or []))
    for r in feed['records']:
        parser=Text();parser.feed((site/r['full_report_url']).read_text(encoding='utf-8'))
        add(r['id'],'Research edition',r['title'],r['summary']+' '+' '.join(parser.parts),BASE+r['full_report_url'],r['cutoff_sgt'],[feed['tags'][t]['label'] for t in r['tags']])
    # Search history includes earlier versions; runtime merges it with the legacy catalogue.
    for e in news['editions']:
        for s in e['stories']:
            add(s['story_id']+'-'+str(s['version']),'Hourly story',s['headline'],s['body']+' '+s['analysis'],HUB+'v4.html#hourly',e['report_at'],list(dict.fromkeys([s['topic']]+infer_labels(s['headline']+' '+s['body'],site))),[
                {'label':'Saved briefing','text':s['body']},{'label':'Saved analysis','text':s['analysis']}])
    for r in read_ups.collect(site)['entries']:
        add(r['id'],'Reuters Read-Up',r['title'],' '.join(r[k] for k in ('takeaway','happened','matters','watch')),BASE+read_ups.destination(r),r['published_at'],['Reuters Read-Up']+infer_labels(r['title']+' '+r['takeaway'],site))
    return {'schema_version':1,'entries':rows}

def build(output,repo=ROOT):
    repo=Path(repo);site=repo/'site';output=Path(output).resolve()
    require(not output.exists() and not output.is_relative_to(repo.resolve()),'Use a new staging directory outside this repository')
    feed,news=validate_site(site)
    shutil.copytree(site,output)
    read_ups.build(site,output)
    # Existing IDs retain v1; newly accepted briefs use the pinned v2 rules.
    from publication_colour_v2 import enrich_read_up
    prior=set(read(site/'data/publication-colour-policy-v2.json')['prior_read_ups'])
    for p in (site/'data/read-up-records').glob('*.json'):
        r=read(p)['record']
        if r['id']+'-r'+str(r['revision']) not in prior:
            (output/read_ups.destination(r)).write_bytes(enrich_read_up(r,read_ups.render_legacy(r)))
    (output/'data/research-feed.json').write_bytes(canonical(feed))
    (output/'data/site-search.json').write_bytes(canonical(search(feed,news,site)))
    revision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip()
    (output/'data/delivery.json').write_bytes(canonical({'schema_version':1,'source_revision':revision,'research_revision':feed['revision'],'hourly_cutoff':news['editions'][0]['cutoff'] if news['editions'] else None}))
    subprocess.run(['node',str(repo/'scripts/render_content_index.cjs'),str(output)],check=True)
    pages = sorted(output.rglob('*.html'))
    for page in pages:
        original = page.read_bytes()
        page.write_bytes(decorate(original))
        require(restore(page.read_bytes()) == original, 'Archive navigation changed content: '+str(page.relative_to(output)))
    verify_staged(output, source_site=site, archive_navigation=True)
    return {'result':'passed','reports':len(feed['records']),'hourly_editions':len(news['editions']),
            'source_revision':revision,'archive_navigation_pages':len(pages)}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--before');p.add_argument('--head');a=p.parse_args()
    if a.head or a.before:
        head=a.head or 'HEAD'
        before=a.before or subprocess.check_output(['git','rev-parse',head+'^'],cwd=ROOT,text=True).strip()
        preserve(ROOT,before,head)
    print(json.dumps(build(a.output),indent=2))

