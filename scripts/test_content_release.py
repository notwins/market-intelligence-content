import json,shutil,tempfile,unittest
from pathlib import Path
from content_release import ROOT,validate_site,build,preserve
from research_feed import canonical
from test_research_feed import bundle
from submit_research import accept,git

class IndependentReleaseTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.base=Path(self.tmp.name);self.repo=self.base/'content';self.repo.mkdir()
        for folder in ['site','baseline','scripts']:shutil.copytree(ROOT/folder,self.repo/folder,ignore=shutil.ignore_patterns('__pycache__'))
        git(self.repo,'init','-b','main');git(self.repo,'config','user.name','Test');git(self.repo,'config','user.email','test@example.invalid');git(self.repo,'add','.');git(self.repo,'commit','-m','Initial content')
    def tearDown(self):self.tmp.cleanup()
    def test_new_report_search_and_independent_ui_rollback(self):
        ui=self.base/'ui';ui.mkdir();(ui/'index.html').write_text('UI A')
        p,v=bundle(self.base);accept(self.repo,p,v)
        result=build(self.base/'deployed-content',self.repo);self.assertEqual(result['reports'],1)
        report=self.base/'deployed-content/research/test-alpha-2026-11-14/index.html';original=report.read_bytes()
        (ui/'index.html').write_text('UI B');(ui/'index.html').write_text('UI A')
        self.assertEqual(report.read_bytes(),original)
        catalog=json.loads((self.base/'deployed-content/data/site-search.json').read_text())
        self.assertTrue(any(e['href'].endswith('/research/test-alpha-2026-11-14/index.html') for e in catalog['entries']))
    def test_unregistered_files_and_failed_build_preserve_deployment(self):
        output=self.base/'live';build(output,self.repo);before=(output/'data/research-feed.json').read_bytes()
        p=self.repo/'site/research/unregistered/index.html';p.parent.mkdir(parents=True);p.write_text('Unreviewed')
        with self.assertRaisesRegex(ValueError,'Unregistered'):build(self.base/'failed',self.repo)
        self.assertFalse((self.base/'failed').exists());self.assertEqual((output/'data/research-feed.json').read_bytes(),before)
    def test_history_mutation_rejected(self):
        p,v=bundle(self.base);accept(self.repo,p,v);git(self.repo,'add','.');git(self.repo,'commit','-m','Report');before=git(self.repo,'rev-parse','HEAD').stdout.strip()
        (self.repo/'site/research/test-alpha-2026-11-14/index.html').write_text('Changed');git(self.repo,'add','.');git(self.repo,'commit','-m','Invalid')
        with self.assertRaises(ValueError):preserve(self.repo,before,'HEAD')
    def test_legacy_identity_baseline_is_immutable(self):
        before=git(self.repo,'rev-parse','HEAD').stdout.strip()
        (self.repo/'site/data/research-register.json').write_bytes(canonical({'entries':[]}))
        git(self.repo,'add','.');git(self.repo,'commit','-m','Invalid identity deletion')
        with self.assertRaises(ValueError):preserve(self.repo,before,'HEAD')

if __name__=='__main__':unittest.main()
