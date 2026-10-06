"""Package and render verified analysis bundles without recalculating statistics."""
import argparse
import os
import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from common import digest, write_json
HERE=Path(__file__).resolve().parent

def verify_bundle(bundle):
    bundle=Path(bundle); m=json.loads((bundle/'bundle.json').read_text())
    for n,h in m['files'].items():
        if digest(bundle/n)!=h: raise ValueError(f'Bundle integrity failed: {n}')
    return m

def package(bundle,dest):
    bundle,dest=Path(bundle),Path(dest); m=verify_bundle(bundle)
    dest.mkdir(parents=True,exist_ok=True)
    for n in [*m['files'],'bundle.json']:
        shutil.copyfile(bundle/n,dest/n)
    shutil.copyfile(HERE/'report_public_health_expert.qmd',dest/'report.qmd')
    for n in ['report_helpers.R','audience_reports.R','app.R','dashboard.css','methods.qmd']:
        shutil.copyfile(HERE/'templates'/n,dest/n)
    write_json(dest/'package.json',{'schema_version':'2.0','files':{p.name:digest(p) for p in sorted(dest.iterdir()) if p.is_file() and p.name!='package.json'}})

def render(bundle,output,fmt,quarto='quarto'):
    output=Path(output).resolve(); output.parent.mkdir(parents=True,exist_ok=True)
    # Each format gets a separate build directory so concurrent rendering cannot race.
    with tempfile.TemporaryDirectory(prefix='health-report-') as tmp:
        package(bundle,tmp)
        env = os.environ.copy()
        project = HERE.parents[1]
        env['HEALTH_REPORT_PROJECT'] = str(project)
        env['R_PROFILE_USER'] = str(project / '.Rprofile')
        for document in ['report','methods']:
            command = [quarto,'render',f'{document}.qmd','--to',fmt]
            if document == 'methods':
                command += ['-P', 'download_prefix:data/']
            subprocess.run(command,cwd=tmp,check=True,env=env)
        # Publish the pair only after both have rendered successfully.
        shutil.copyfile(Path(tmp)/f'report.{fmt}',output)
        shutil.copyfile(Path(tmp)/f'methods.{fmt}',output.parent/f'methods.{fmt}')

if __name__=='__main__':
    ap=argparse.ArgumentParser(); ap.add_argument('action',choices=['package','html','pdf']); ap.add_argument('--bundle',required=True); ap.add_argument('--output',required=True); ap.add_argument('--quarto',default='quarto')
    a=ap.parse_args()
    if a.action=='package': package(a.bundle,a.output)
    else: render(a.bundle,a.output,a.action,a.quarto)
