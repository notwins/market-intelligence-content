import json,copy,tempfile,unittest,subprocess,os
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from publication_colour import ROOT,enrich_html,audit_html,plan,enrich_folder
from prepare_research_bundle import prepare
from research_feed import read,canonical,digest,validate_report
from contract_fixtures import fixture,render

SITE=ROOT/'site'
def example(name='Example'):
    c,body=fixture();c['cutoff']='2026-11-15T00:00:00+08:00'
    body=body.replace('2026-11-07T12:00:00+08:00',c['cutoff']).replace('>Report<','>'+name+'<').replace('Evidence-supported conclusion','NVIDIA Corporation shares and fixed income in Singapore. United States policy matters.')
    return '<!doctype html><html><head><meta charset="utf-8"><title>Private synthetic fixture</title></head><body>'+render(c,body)+'</body></html>',{'title':name+' fixed income','summary':'NVIDIA Corporation shares in Singapore','cutoff_sgt':c['cutoff'],'category':'Credit','tags':[]}

class Colours(unittest.TestCase):
    def test_repeat_repair_and_preserve_links(self):
        text,meta=example();text=text.replace('</body>','<p><a href="https://example.org/existing">NVIDIA Corporation shares</a></p></body>')
        out,m=enrich_html(text,meta,SITE);second,m2=enrich_html(out,m,SITE)
        self.assertEqual(out,second);self.assertEqual(m,m2);self.assertEqual(out.count('data-mih-auto-row="1"'),1)
        self.assertIn('<a href="https://example.org/existing">NVIDIA Corporation shares</a>',out)
        self.assertLessEqual(out.count('data-mih-auto="term"'),3);audit_html(out,SITE)
        damaged=out.replace('--tag-text:#6D28D9','--tag-text:#000000')
        with self.assertRaises(ValueError):audit_html(damaged,SITE)
        repaired,_=enrich_html(damaged,m,SITE);self.assertEqual(out,repaired)
    def test_unmapped_unknown_and_unsafe_rows_fail(self):
        text,meta=example();meta['tags']=['not-a-tag']
        with self.assertRaises(ValueError):enrich_html(text,meta,SITE)
        text,meta=example();text=text.replace('</body>','<div class="mu-card-tags">Custom unlabeled row</div></body>')
        with self.assertRaisesRegex(ValueError,'canonical markers'):enrich_html(text,meta,SITE)
        with self.assertRaisesRegex(ValueError,'contract'):enrich_html('<html>arbitrary upload</html>',{},SITE)
    def test_parallel_ten_preparations_hash_final_bytes_and_leave_originals(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp);jobs=[];before={}
            for i in range(10):
                folder=base/('source'+str(i));folder.mkdir();text,meta=example('Example '+str(i));(folder/'index.html').write_text(text,encoding='utf-8');before[i]=(folder/'index.html').read_bytes();jobs.append((i,folder,meta))
            def run(job):
                i,folder,meta=job;out=base/('bundle'+str(i));result=prepare(folder,meta,'standalone',out,slug='example-'+str(i));r=read(out/'record.json')
                self.assertEqual(r['full_report_sha256'],digest((out/'files/index.html').read_bytes()));self.assertTrue(r['tags']);self.assertFalse(result['published']);self.assertEqual((folder/'index.html').read_bytes(),before[i]);return r['id']
            with ThreadPoolExecutor(max_workers=10) as pool:ids=list(pool.map(run,jobs))
            self.assertEqual(len(set(ids)),10)
    def test_python_browser_matcher_agree(self):
        samples=['FedEx USD BOC DE apple fruit','NVIDIA Corporation shares in Singapore','Singapore Airlines shares','NASDAQ:GOOG and NASDAQ:GOOGL shares','😀 United States fixed income']
        for value in samples:
            request={'text':value,'existing':[],'segments':[value]}
            p=subprocess.run([os.environ.get('MIH_NODE','node'),str(ROOT/'scripts/publication_colour_plan.cjs'),str(SITE/'data/publication-colour-catalogue.json')],input=json.dumps(request),capture_output=True,text=True,encoding='utf-8',check=True)
            # URI encoders differ only for RFC3986 punctuation, not these fixture labels.
            self.assertEqual(json.loads(p.stdout),plan(value,[],[value],SITE))
    def test_source_tags_do_not_colour_citations_or_code(self):
        text,meta=example();text=text.replace('</body>','<pre>NVIDIA Corporation shares</pre><script>let x="Singapore";</script></body>')
        out,_=enrich_html(text,meta,SITE);self.assertIn('<pre>NVIDIA Corporation shares</pre>',out);self.assertIn('<script>let x="Singapore";</script>',out)
    def test_published_renderer_palette_and_legacy_policy_cannot_change(self):
        from content_release import preserve
        from submit_research import git
        paths=['scripts/publication_colour_v1.py','scripts/publication_colour.py','scripts/read_ups.py','site/publication-colour-v1.css','site/data/publication-colour-catalogue-v1.json','site/data/publication-colour-policy.json']
        with tempfile.TemporaryDirectory() as tmp:
            for i,name in enumerate(paths):
                with self.subTest(path=name):
                    repo=Path(tmp)/str(i);repo.mkdir()
                    for p in paths:
                        target=repo/p;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes((ROOT/p).read_bytes())
                    git(repo,'init','-b','main');git(repo,'config','user.name','Private test');git(repo,'config','user.email','test@example.invalid');git(repo,'add','.');git(repo,'commit','-m','Published v1 fixture')
                    before=git(repo,'rev-parse','HEAD').stdout.strip();preserve(repo,before,before)
                    target=repo/name;target.write_bytes(target.read_bytes()+b'\n');git(repo,'add','.');git(repo,'commit','-m','Invalid historical rendering change')
                    with self.assertRaisesRegex(ValueError,'frozen'):preserve(repo,before,'HEAD')

if __name__=='__main__':unittest.main()
