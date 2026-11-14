"""Accept ready full-report bundles in one commit. No timer, daemon or credentials.

Default prepare-only. The private manifest lists bundle/review absolute paths.
Independent producers prepare concurrently; one call groups the ready work.
"""
import argparse,json,shutil,tempfile
from pathlib import Path
from research_feed import read,validate_report,validate_review,collect,require
from submit_research import accept,git

def submit_batch(remote,jobs,output=None,publish=False,attempts=12):
    require(isinstance(jobs,list) and 1<=len(jobs)<=100,'Provide 1-100 ready bundles')
    require(publish or output is not None,'Prepare-only requires a new output directory')
    if output:require(not Path(output).exists(),'Output already exists')
    require(all(isinstance(j,dict) and set(j)=={'bundle','review'} for j in jobs),'Only bundle and private review paths')
    with tempfile.TemporaryDirectory(prefix='mih-batch-') as tmp:
        repo=Path(tmp)/'candidate';git(None,'clone','--quiet','--config','core.autocrlf=false','--branch','main',str(remote),str(repo))
        for attempt in range(attempts):
            if attempt:
                git(repo,'fetch','--quiet','origin','main');git(repo,'reset','--hard','origin/main');git(repo,'clean','-fd')
            base=git(repo,'rev-parse','HEAD').stdout.strip();site=repo/'site'
            standard=read(site/'data/colour-templates-v3.json');tags={t['id']:t for t in read(site/'data/external-source-standard.json')['tags']}
            held=[];accepted=[];duplicate=[];paths=[]
            for j in jobs:
                try:
                    bundle=Path(j['bundle']);r=read(bundle/'record.json')
                    validate_report(r,bundle/'files',standard,tags);validate_review(r,read(j['review']))
                    prior=site/'data/research-records'/(r['id']+'.json')
                    if prior.exists():
                        require(read(prior)['record']==r,'Conflicting edition ID; use reviewed revision');duplicate.append(r['id']);continue
                    require(not (site/'research'/r['id']).exists(),'Destination already exists')
                    existing,_=collect(site);legacy=read(site/'data/research-register.json')['entries']
                    require(r['id'] not in {x['id'] for x in legacy},'Legacy identity already exists')
                    require(r['full_report_sha256'] not in {x['record']['full_report_sha256'] for x in existing}|{x.get('sha256') for x in legacy},'Duplicate report bytes')
                    if (site/'data/publication-colour-policy.json').exists():
                        from publication_colour_v2 import audit_html
                        for name in r['assets']:
                            if name.endswith('.html'):audit_html((bundle/'files'/name).read_text(encoding='utf-8'),site)
                except (ValueError,KeyError,TypeError,OSError) as exc:
                    held.append({'bundle':str(j['bundle']),'reason':str(exc)});continue
                # All checks precede writes. Unexpected write failure aborts the candidate,
                # preserving remote main and every producer's private source bundle.
                added,_=accept(repo,bundle,j['review']);paths.extend(added);accepted.append(r['id'])
            result={'accepted':accepted,'duplicates':duplicate,'held':held,'base':base,'committed':False,'live_verified':False}
            if not paths:return {**result,'outcome':'no-change'}
            git(repo,'add','--',*paths);require(set(git(repo,'diff','--cached','--name-only').stdout.splitlines())==set(paths),'Unowned mutation')
            git(repo,'-c','user.name=Research publisher','-c','user.email=research-publisher@users.noreply.github.com','commit','-m','Add '+str(len(accepted))+' reviewed research editions')
            result['candidate']=git(repo,'rev-parse','HEAD').stdout.strip()
            if not publish:
                shutil.copytree(repo,output);return {**result,'outcome':'prepared'}
            push=git(repo,'push','--porcelain','origin','HEAD:refs/heads/main',check=False)
            if not push.returncode:return {**result,'outcome':'committed','committed':True}
            git(repo,'fetch','--quiet','origin','main')
            require(git(repo,'rev-parse','FETCH_HEAD').stdout.strip()!=base,'Push failed without a competing update')
    raise RuntimeError('Content main kept advancing; retain original bundles and retry')

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--remote',required=True);p.add_argument('--manifest',required=True,type=Path);p.add_argument('--output',type=Path);p.add_argument('--publish',action='store_true');a=p.parse_args()
    print(json.dumps(submit_batch(a.remote,read(a.manifest),a.output,a.publish),indent=2))
