import json,tempfile,unittest
from pathlib import Path
from publication_colour_v2 import ROOT,plan,enrich_html,audit_html,enrich_read_up
from test_publication_colour import example
from test_read_ups import fixture
from read_ups import render_legacy
from research_feed import read
from submit_research import git
from content_release import preserve

class VersionTwoTests(unittest.TestCase):
    def test_generic_funding_does_not_infer_an_investment_industry(self):
        site=ROOT/'site'
        self.assertNotIn('sector.asset_management',plan('Reconstruction funds and a well-funded military',[],[],site)['ids'])
        self.assertIn('sector.asset_management',plan('Asset management industry',[],[],site)['ids'])
        self.assertIn('sector.asset_management',plan('Reconstruction funds',['sector.asset_management'],[],site)['ids'])
    def test_new_full_report_and_read_up_use_repeatable_v2(self):
        text,meta=example();text=text.replace('United States policy matters.','Reconstruction funds are separately identified.')
        output,meta=enrich_html(text,meta,ROOT/'site');self.assertNotIn('sector.asset_management',meta['tags']);self.assertEqual(enrich_html(output,meta,ROOT/'site')[0],output);audit_html(output,ROOT/'site')
        with tempfile.TemporaryDirectory() as tmp:
            bundle,_=fixture(Path(tmp),'v2');r=read(bundle/'record.json')
            output=enrich_read_up(r,render_legacy(r));self.assertIn(b'mih-colour-chip',output);self.assertEqual(output,enrich_read_up(r,render_legacy(r)))
    def test_v2_renderer_and_policy_are_frozen_after_first_release(self):
        paths=['scripts/publication_colour_v2.py','site/publication-colour-v2.css','site/data/publication-colour-catalogue-v2.json','site/data/publication-colour-policy-v2.json']
        with tempfile.TemporaryDirectory() as tmp:
            repo=Path(tmp)
            for name in paths:
                target=repo/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes((ROOT/name).read_bytes())
            git(repo,'init','-b','main');git(repo,'config','user.name','Private test');git(repo,'config','user.email','test@example.invalid');git(repo,'add','.');git(repo,'commit','-m','Published v2')
            base=git(repo,'rev-parse','HEAD').stdout.strip()
            for name in paths:
                with self.subTest(path=name):
                    git(repo,'reset','--hard',base);target=repo/name;target.write_bytes(target.read_bytes()+b'\n');git(repo,'add','.');git(repo,'commit','-m','Invalid rendering change')
                    with self.assertRaisesRegex(ValueError,'frozen'):preserve(repo,base,'HEAD')

if __name__=='__main__':unittest.main()
