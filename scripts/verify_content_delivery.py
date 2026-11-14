"""Read back the exact independent publication after Pages deploys."""
import argparse,json,subprocess,time
from urllib.request import Request,urlopen
from research_feed import ROOT,compile_feed,read
from content_release import search

def verify(base,attempts=12):
    expected=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    feed=compile_feed(ROOT/'site');news=read(ROOT/'site/data/hourly-news.json')
    targets={'data/research-feed.json':feed,'data/hourly-news.json':news,'data/site-search.json':search(feed,news,ROOT/'site')}
    last=None
    for attempt in range(attempts):
        try:
            def get(path):
                with urlopen(Request(base.rstrip('/')+'/'+path+'?revision='+expected,headers={'Cache-Control':'no-cache'}),timeout=20) as response:return json.load(response)
            assert get('data/delivery.json')['source_revision']==expected,'Old content artifact is still served'
            for path,value in targets.items():assert get(path)==value,'Published data mismatch: '+path
            return {'source_revision':expected,'reports':len(feed['records']),'hourly_editions':len(news['editions']),'live_data':'exact match'}
        except Exception as exc:
            last=exc
            if attempt+1<attempts:time.sleep(5)
    raise RuntimeError('Live content verification failed') from last

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--base-url',required=True);a=p.parse_args();print(json.dumps(verify(a.base_url),indent=2))
