import tempfile,unittest,shutil
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from test_research_feed import seed as original_seed,bundle as original_bundle,save
from research_feed import read,collect,digest
from publication_colour import ROOT,enrich_html,audit_html
from submit_research import git
from submit_research_batch import submit_batch

def seed(repo):
    original_seed(repo)
    for name in ['colour-templates-v3.json','external-source-standard.json','publication-colour-catalogue-v1.json','publication-colour-policy.json']:
        shutil.copyfile(ROOT/'site/data'/name,repo/'site/data'/name)
    git(repo,'add','.');git(repo,'commit','-m','Enable colour policy in private test repository')

def bundle(root,name):
    folder,receipt=original_bundle(root,name);record=read(folder/'record.json');path=folder/'files/index.html'
    text,meta=enrich_html(path.read_text(encoding='utf-8'),record,ROOT/'site')
    path.write_text(text,encoding='utf-8');record['tags']=meta['tags'];record['assets']['index.html']=record['full_report_sha256']=digest(path.read_bytes());save(folder,record)
    return folder,receipt

class BatchTests(unittest.TestCase):
    def test_ten_ready_bundles_one_commit_duplicate_retry_and_bad_bundle_held(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);repo=root/'repo';repo.mkdir();seed(repo)
            remote=root/'remote.git';git(None,'clone','--bare',str(repo),str(remote));base=git(remote,'rev-parse','main').stdout.strip()
            jobs=[]
            for i in range(10):
                b,r=bundle(root,'article'+str(i));jobs.append({'bundle':str(b),'review':str(r)})
            jobs.append({'bundle':str(root/'missing'),'review':str(root/'missing-review')})
            result=submit_batch(remote,jobs,publish=True)
            self.assertEqual(len(result['accepted']),10,result);self.assertEqual(len(result['held']),1);self.assertFalse(result['live_verified'])
            self.assertEqual(git(remote,'rev-list','--count',base+'..main').stdout.strip(),'1')
            second=submit_batch(remote,jobs,publish=True);self.assertEqual(len(second['duplicates']),10);self.assertFalse(second['committed'])
            checkout=root/'check';git(None,'clone','--config','core.autocrlf=false',str(remote),str(checkout));self.assertEqual(len(collect(checkout/'site')[0]),10)
            for item in (checkout/'site/research').glob('*/index.html'):audit_html(item.read_text(encoding='utf-8'),checkout/'site')
    def test_racing_batches_keep_every_ready_article(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);repo=root/'repo';repo.mkdir();seed(repo);remote=root/'remote.git';git(None,'clone','--bare',str(repo),str(remote))
            jobs=[]
            for i in range(10):
                b,r=bundle(root,'parallel'+str(i));jobs.append({'bundle':str(b),'review':str(r)})
            with ThreadPoolExecutor(max_workers=2) as pool:
                results=list(pool.map(lambda group:submit_batch(remote,group,publish=True),[jobs[:5],jobs[5:]]))
            self.assertTrue(all(r['committed'] for r in results),results);checkout=root/'check';git(None,'clone','--config','core.autocrlf=false',str(remote),str(checkout));self.assertEqual(len(collect(checkout/'site')[0]),10)

if __name__=='__main__':unittest.main()
