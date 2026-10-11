"""Package and render verified analysis bundles without recalculating statistics."""
import argparse
import os
import json
import shutil
import subprocess
import tempfile
import platform
import importlib.metadata
from datetime import datetime, timezone
from pathlib import Path
from common import digest, write_json
HERE=Path(__file__).resolve().parent
PROJECT=HERE.parents[1]
TEMPLATE='report_public_health_expert.qmd'
PROVENANCE_SCHEMA='health-report-provenance/1.0'
FILTER_KEYS=['period_type','years','reference_year','index_base_year','geography','measures_preferred','compare_by',
             'classes_in_main_comparison','exclude_from_group_totals','sensitivity_exclude','source_priority',
             'group_source_systems','dimension_filters','needs_roles']

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

def _command(args):
    try: return subprocess.check_output(args,stderr=subprocess.STDOUT,text=True,cwd=PROJECT).strip()
    except (OSError,subprocess.CalledProcessError): return None

def _version(name):
    try: return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError: return None

def _retrieval(path):
    try: return json.loads(Path(path).read_text())
    except (OSError,ValueError): return None

def build_provenance(bundle,fmt,quarto='quarto',data_root=None,workflow_config=None,extra=None):
    """Machine-readable record of what was rendered, from which data, with which parameters."""
    bundle=Path(bundle); m=verify_bundle(bundle)
    cfg=json.loads((bundle/'stakeholder.json').read_text())
    snapshot=json.loads((bundle/'snapshot.json').read_text())
    import pandas as pd
    sources=pd.read_csv(bundle/'sources.csv',dtype=str).fillna('')
    used=sources[sources.used.str.lower().eq('true')]
    roots=[Path(data_root)] if data_root else []
    archive=(bundle.parents[2]/snapshot['snapshot_path']) if snapshot.get('snapshot_path') else None
    if archive is not None: roots.append(archive)
    datasets=[]
    for r in used.sort_values('source_file').itertuples():
        directory=Path(r.source_file).parent
        ret=next((x for x in (_retrieval(root/directory/'retrieval.json') for root in roots) if x),None) or {}
        datasets.append({'dataset_id':r.dataset_id,'export':directory.as_posix(),'topic':r.topic,'source_system':r.source_system,
                         'publishing_date':r.publishing_date or None,'retrieved_at_utc':ret.get('retrieved_at_utc'),
                         'csv_source_url':ret.get('csv_source_url'),'metadata_source_url':ret.get('metadata_source_url'),
                         'data_sha256':r.sha256,'metadata_sha256':r.metadata_sha256})
    dates=lambda k:sorted(d[k] for d in datasets if d[k])
    checks=pd.read_csv(bundle/'checks.csv',dtype=str).fillna('')
    toolchain=PROJECT/'workflow/toolchain.json'
    git_commit=_command(['git','rev-parse','HEAD'])
    git_status=_command(['git','status','--porcelain','--untracked-files=no'])
    record={
        'schema':PROVENANCE_SCHEMA,
        'rendered_at_utc':datetime.now(timezone.utc).isoformat(timespec='seconds'),
        'output':{'format':fmt,'documents':[f'report.{fmt}',f'methods.{fmt}'],
                  'shared_template':f'scripts/health_pipeline/{TEMPLATE}','shared_template_sha256':digest(HERE/TEMPLATE),
                  'presentation_helpers_sha256':{n:digest(HERE/'templates'/n) for n in ['report_helpers.R','audience_reports.R','methods.qmd','dashboard.css']}},
        'stakeholder':{'id':cfg['id'],'title':cfg['title'],'question':cfg['question'],'presentation':cfg.get('presentation'),
                       'outputs':cfg['outputs'],'parameters_sha256':digest(bundle/'stakeholder.json')},
        'filters':{k:cfg[k] for k in FILTER_KEYS if k in cfg},
        'effective_parameters':cfg,
        'data':{'publisher':'Federal Office of Public Health (FOPH/BAG), Infectious Disease Dashboard (IDD)',
                'api':'https://api.idd.bag.admin.ch/api/v1/export/latest/{dataset}/csv',
                'canonical_root':Path(data_root).as_posix() if data_root and not str(data_root).endswith('.json') else None,
                'snapshot_manifest':Path(data_root).as_posix() if data_root and str(data_root).endswith('.json') else None,
                'snapshot_id':m['snapshot_id'],'snapshot_path':snapshot.get('snapshot_path'),
                'datasets_in_snapshot':len(sources),'datasets_used':len(datasets),
                'publishing_date_range':[dates('publishing_date')[0],dates('publishing_date')[-1]] if dates('publishing_date') else None,
                'retrieved_at_utc_range':[dates('retrieved_at_utc')[0],dates('retrieved_at_utc')[-1]] if dates('retrieved_at_utc') else None,
                'used':datasets},
        'analysis_bundle':{'schema_version':m['schema_version'],'files':m['files']},
        'quality_checks':checks.status.value_counts().sort_index().to_dict(),
        'software':{'python':platform.python_version(),'platform':platform.platform(),
                    'python_packages':{n:_version(n) for n in ['pandas','numpy','pyarrow','jsonschema','snakemake']},
                    'quarto':_command([quarto,'--version']),'R':(_command(['Rscript','--version']) or '').splitlines()[-1:] or None,
                    'toolchain_contract':'workflow/toolchain.json','toolchain_contract_sha256':digest(toolchain) if toolchain.is_file() else None,
                    'r_lockfile_sha256':digest(PROJECT/'renv.lock') if (PROJECT/'renv.lock').is_file() else None,
                    'python_lockfile_sha256':digest(HERE/'requirements.lock.txt')},
        'code':{'git_commit':git_commit,'git_worktree_clean':None if git_status is None else git_status=='',
                'workflow_config':workflow_config},
    }
    if record['software']['R']: record['software']['R']=record['software']['R'][0]
    if extra: record['request']=extra
    return record

def render(bundle,output,fmt,quarto='quarto',provenance=None,provenance_out=None):
    output=Path(output).resolve(); output.parent.mkdir(parents=True,exist_ok=True)
    # Each format gets a separate build directory so concurrent rendering cannot race.
    with tempfile.TemporaryDirectory(prefix='health-report-') as tmp:
        package(bundle,tmp)
        if provenance is not None:
            # The template embeds this record in HTML as application/json.
            write_json(Path(tmp)/'provenance.json',provenance)
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
        if provenance is not None and provenance_out is not None:
            write_json(provenance_out,provenance)

if __name__=='__main__':
    ap=argparse.ArgumentParser(); ap.add_argument('action',choices=['package','html','pdf']); ap.add_argument('--bundle',required=True); ap.add_argument('--output',required=True); ap.add_argument('--quarto',default='quarto')
    ap.add_argument('--provenance',help='Write a machine-readable provenance sidecar here and embed it in HTML')
    ap.add_argument('--data-root',help='Canonical input root recorded in provenance')
    ap.add_argument('--workflow-config',help='Workflow configuration file recorded in provenance')
    a=ap.parse_args()
    if a.action=='package': package(a.bundle,a.output)
    else:
        record=None
        if a.provenance:
            wf=None
            if a.workflow_config and Path(a.workflow_config).is_file():
                wf={'path':a.workflow_config,'sha256':digest(a.workflow_config)}
            record=build_provenance(a.bundle,a.action,a.quarto,a.data_root,wf)
        render(a.bundle,a.output,a.action,a.quarto,record,a.provenance)
