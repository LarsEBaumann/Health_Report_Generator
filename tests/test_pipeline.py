import json, shutil, subprocess, sys
from pathlib import Path
import pandas as pd
import pytest
from harmonise import main as harmonise
from inventory import verify
from checks import validate
from analyse import analyse,load_config
from common import verify_gate
from publish import package,verify_bundle
YEARS=[2019,2021,2022,2023,2024,2025]

@pytest.fixture
def project(tmp_path):
    raw=tmp_path/'raw'; cfg=tmp_path/'stakeholder.json'; classes=tmp_path/'classes.csv'; out=tmp_path/'out'
    for topic,scale in [('virus',1),('bacterium',2)]:
        p=raw/topic;p.mkdir(parents=True)
        meta={'metaVariables':{'topic':topic,'source':'mandatory_reporting_system','valueCategory':{'column':'valueCategory'}},
              'temporalVariables':{'column':'temporal','typeColumn':'temporal_type'},
              'groupingVariables':{'georegion':{'column':'georegion','typeColumn':'georegion_type','allValue':'all'},'sex':{'column':'sex','allValue':'all'}},
              'valueVariables':{'value':{},'pop':{}},'entryVariables':{'dataComplete':{}}}
        (p/'metadata.json').write_text(json.dumps(meta))
        pd.DataFrame([dict(valueCategory='cases',temporal=str(y),temporal_type='year',georegion='CHFL',georegion_type='CHFL',sex='all',value=(y-2009)*scale,pop=100000,dataComplete='TRUE') for y in YEARS]).to_csv(p/'data.csv',index=False)
    template=Path(__file__).resolve().parents[1]/'scripts/health_pipeline/config/stakeholders/public_health_expert.json'
    c=json.loads(template.read_text());c.update(id='test',exclude_from_group_totals=[],sensitivity_exclude=[],dimension_filters={})
    cfg.write_text(json.dumps(c));classes.write_text('topic,pathogen_class,label\nvirus,viral,Virus\nbacterium,bacterial,Bacterium\n')
    return raw,out,cfg,classes

def run(project):
    raw,out,cfg,classes=project
    harmonise([str(raw),'--out',str(out)]);validate(out)
    dest=out/'bundle';analyse(out,cfg,classes,dest)
    return dest

def edit_csv(project,fn,topic='virus'):
    p=project[0]/topic/'data.csv';fn(pd.read_csv(p)).to_csv(p,index=False)

def test_hand_calculated_metrics_and_all_lineage(project):
    bundle=run(project);m=pd.read_csv(bundle/'metrics.csv').set_index('metric_id');links=pd.read_csv(bundle/'lineage.csv').fillna('')
    assert m.loc['virus:2025:count','value']==16
    assert m.loc['virus:period_change','value']==pytest.approx((16-12)/12*100)
    assert m.loc['viral:main:2025:index','value']==160
    snapshot=json.loads((bundle/'snapshot.json').read_text());root=project[1]/snapshot['snapshot_path']
    for mid,r in m.iterrows():
        rows=links[links.metric_id==mid]
        if r.formula.startswith('raw_'):
            vals=[float(pd.read_csv(root/x.source_file).iloc[int(x.source_row)-2][x.source_column]) for x in rows.itertuples()]
            expected=sum(vals) if r.formula=='raw_sum' else vals[0]
        else:
            vals=[m.loc[x,'value'] for x in json.loads(r.inputs_json)]
            if r.formula=='sum':expected=sum(vals)
            elif r.formula=='ratio_100':expected=vals[0]/vals[1]*100
            elif r.formula=='ratio_100000':expected=vals[0]/vals[1]*100000
            else:expected=(vals[1]-vals[0])/vals[0]*100
        assert r.value==pytest.approx(expected),mid

def test_women_only_never_total(project):
    edit_csv(project,lambda d:d.assign(sex='female'))
    harmonise([str(project[0]),'--out',str(project[1])]);validate(project[1])
    d=pd.read_parquet(project[1]/'harmonised.parquet');assert not d[d.topic=='virus'].is_total.any()
    with pytest.raises(ValueError,match='No eligible members'):analyse(project[1],project[2],project[3],project[1]/'bundle')

@pytest.mark.parametrize('damage',['missing_baseline','incomplete_source','missing_population','missing_year'])
def test_incomplete_comparison_is_not_published(project,damage):
    def change(d):
        if damage=='missing_baseline':return d[d.temporal!=2019]
        if damage=='missing_year':return d[d.temporal!=2023]
        d['dataComplete']=d.dataComplete.astype(object)
        d.loc[d.temporal==2025,'dataComplete' if damage=='incomplete_source' else 'pop']='FALSE' if damage=='incomplete_source' else 0
        return d
    edit_csv(project,change)
    with pytest.raises(ValueError,match='No eligible members'):run(project)
    assert not (project[1]/'bundle/bundle.json').exists()

@pytest.mark.parametrize('complete',[False,True])
def test_monthly_completeness(project,complete):
    def monthly(d):
        rows=[]
        for r in d.to_dict('records'):
            for month in range(1,13 if complete or r['temporal']!=2025 else 12):
                rows.append({**r,'temporal':f"{r['temporal']}-M{month:02d}",'temporal_type':'month','value':month})
        return pd.DataFrame(rows)
    edit_csv(project,monthly)
    if not complete:
        with pytest.raises(ValueError,match='No eligible members'):run(project)
    else:
        bundle=run(project);m=pd.read_csv(bundle/'metrics.csv').set_index('metric_id');assert m.loc['virus:2025:count','value']==78
        l=pd.read_csv(bundle/'lineage.csv');assert len(l[l.metric_id=='virus:2025:count'])==12

@pytest.mark.parametrize('damage',['negative','duplicate','invalid_date','invalid_value','missing_metadata','truncated_metadata','dropped_sex'])
def test_bad_input_blocks_gate(project,damage):
    raw,out,*_=project
    if damage.endswith('metadata'):
        p=raw/'virus/metadata.json'
        if damage=='missing_metadata':p.unlink()
        else:p.write_text('{"broken":')
    else:
        def change(d):
            if damage=='duplicate':return pd.concat([d,d.iloc[:1]])
            if damage=='dropped_sex':return d.drop(columns='sex')
            col='temporal' if damage=='invalid_date' else 'value';d[col]=d[col].astype(object)
            d.loc[0,col]={'negative':-1,'invalid_date':'not-a-date','invalid_value':'oops'}[damage];return d
        edit_csv(project,change)
    harmonise([str(raw),'--out',str(out)])
    with pytest.raises(ValueError,match='blocking'):validate(out)
    assert not (out/'validated.json').exists()

def test_failure_removes_old_success_marker(project):
    run(project);out=project[1];d=pd.read_parquet(out/'harmonised.parquet');d.loc[0,'value']=-10;d.to_parquet(out/'harmonised.parquet',index=False)
    with pytest.raises(ValueError):validate(out)
    assert not (out/'validated.json').exists()

def test_stale_gate_is_rejected(project):
    run(project);p=project[1]/'checks.csv';p.write_text(p.read_text()+'\n')
    with pytest.raises(ValueError,match='stale'):verify_gate(project[1])

def test_conflicting_metadata_not_deduplicated(project):
    raw,out,*_=project;shutil.copytree(raw/'virus',raw/'copy')
    p=raw/'copy/metadata.json';m=json.loads(p.read_text());m['metaVariables']['topic']='another';p.write_text(json.dumps(m))
    harmonise([str(raw),'--out',str(out)])
    with pytest.raises(ValueError,match='blocking'):validate(out)
    assert (pd.read_csv(out/'datasets.csv').status=='ok').sum()==3

def test_overlapping_exports_rejected(project):
    raw,out,cfg,classes=project;shutil.copytree(raw/'virus',raw/'copy')
    p=raw/'copy/data.csv';d=pd.read_csv(p);d['value']+=1;d.to_csv(p,index=False)
    with pytest.raises(ValueError,match='Ambiguous overlapping'):run(project)

def test_exact_duplicates_skipped(project):
    shutil.copytree(project[0]/'virus',project[0]/'copy');run(project)
    assert (pd.read_csv(project[1]/'datasets.csv').status=='duplicate_skipped').sum()==1

def test_snapshot_relocation_and_tamper_detection(project,tmp_path):
    run(project);copy=tmp_path/'moved';shutil.copytree(project[1],copy)
    root,m=verify(copy/'snapshot.json');assert root.exists()
    p=root/m['files'][0]['path'];p.write_bytes(p.read_bytes()+b' ')
    with pytest.raises(ValueError,match='checksum'):verify(copy/'snapshot.json')

def test_repeatable_tables_and_portable_paths(project,tmp_path):
    first=run(project);other=tmp_path/'second'
    harmonise(['--snapshot',str(project[1]/'snapshot.json'),'--out',str(other)]);validate(other)
    analyse(other,project[2],project[3],other/'bundle')
    for name in ['series.csv','metrics.csv','lineage.csv','selection.csv','bundle.json']:assert (first/name).read_bytes()==(other/'bundle'/name).read_bytes()
    l=pd.read_csv(first/'lineage.csv').dropna(subset=['source_file']);assert not l.source_file.str.startswith('/').any()

def test_zero_group_baseline_blocks(project):
    edit_csv(project,lambda d:d.assign(value=[0,12,13,14,15,16]))
    with pytest.raises(ValueError,match='Nonpositive baseline'):run(project)

@pytest.mark.parametrize('setting,value',[('geography','national'),('period_type','month'),('compare_by','age'),('outputs',['unknown']),('unknown_setting',True)])
def test_unsupported_config_rejected(project,setting,value):
    p=project[2];c=json.loads(p.read_text());c[setting]=value;p.write_text(json.dumps(c))
    with pytest.raises(ValueError):load_config(p)

def test_bundle_package_integrity(project):
    b=run(project);dest=project[1]/'app';package(b,dest)
    for n in ['series.csv','metrics.csv','lineage.csv']:assert (b/n).read_bytes()==(dest/n).read_bytes()
    (b/'metrics.csv').write_text('corrupt')
    with pytest.raises(ValueError,match='integrity'):verify_bundle(b)

def test_checks_cli_exit_code(project):
    run(project);d=pd.read_parquet(project[1]/'harmonised.parquet');d.loc[0,'value']=-1;d.to_parquet(project[1]/'harmonised.parquet')
    p=subprocess.run([sys.executable,str(Path(__file__).resolve().parents[1]/'scripts/health_pipeline/checks.py'),'--out',str(project[1])],capture_output=True)
    assert p.returncode!=0
