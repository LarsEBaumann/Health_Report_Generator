#!/usr/bin/env python3
"""Calculate once; HTML, PDF and Shiny only present these versioned tables."""
import argparse
import json
from pathlib import Path
import pandas as pd
from common import digest, object_hash, write_json, verify_gate

SECTIONS = ['headline','group_index','group_totals','small_multiples','change_table','excluded','quality','sources']
FIELDS = {'id','title','question','needs_roles','period_type','years','reference_year','geography',
          'measures_preferred','compare_by','classes_in_main_comparison','exclude_from_group_totals',
          'outputs','index_base_year','sensitivity_exclude','source_priority','group_source_systems',
          'dimension_filters','exclusion_notes'}
LINEAGE_COLUMNS = ['metric_id','input_kind','input_id','source_file','source_row','source_column','sha256','metadata_sha256']


def load_config(path):
    c = json.loads(Path(path).read_text())
    import jsonschema
    schema = json.loads((Path(__file__).resolve().parents[2] / 'workflow/config.schema.json').read_text())
    try:
        jsonschema.validate(c, schema)
    except jsonschema.ValidationError as e:
        raise ValueError(f'Invalid stakeholder setting: {e.message}') from e
    unknown = set(c) - FIELDS
    if unknown: raise ValueError(f'Unsupported settings: {sorted(unknown)}')
    import re
    if not re.fullmatch(r'[a-zA-Z0-9_-]+', c['id']): raise ValueError('Unsafe stakeholder id')
    if c['period_type'] != 'year' or c['compare_by'] != 'pathogen_class':
        raise ValueError('Only yearly pathogen_class comparison is supported')
    if c['geography'] not in ['CH','CHFL']: raise ValueError('Choose explicit geography CH or CHFL')
    if set(c.get('needs_roles', [])) - {'time','measure','place'}: raise ValueError('Unsupported required roles')
    if not c.get('outputs') or set(c['outputs']) - set(SECTIONS): raise ValueError('Unsupported or empty report sections')
    if c['classes_in_main_comparison'] != ['viral','bacterial']: raise ValueError('This comparison supports viral and bacterial classes')
    y0,y1=c['years']
    if any(type(y) is not int for y in [y0,y1,c['reference_year'],c['index_base_year']]) or y0 > y1:
        raise ValueError('Years must be ordered integers')
    if not c['measures_preferred'] or set(c['measures_preferred']) - {'cases','consultations'}:
        raise ValueError('Unsupported count measure')
    if set(c['group_source_systems']) - set(c['source_priority']): raise ValueError('Group sources must be present in source_priority')
    if len(set(c['source_priority'])) != len(c['source_priority']): raise ValueError('Duplicate source priority')
    for topic, rule in c.get('dimension_filters', {}).items():
        if not rule.get('reason') or not rule.get('values'): raise ValueError(f'Filter needs values and rationale: {topic}')
    return c


def select_series(d, cfg, classes):
    years = sorted(set(range(cfg['years'][0],cfg['years'][1]+1)) | {cfg['reference_year'],cfg['index_base_year']})
    candidates, decisions = [], []
    def reject(ds, topic, source, reason):
        decisions.append(dict(dataset_id=ds, topic=topic, source_system=source, status='excluded', reason=reason))
    for ds,g in d.groupby('dataset_id', sort=True):
        topic,source=g.topic.iloc[0],g.source_system.iloc[0]
        cls=classes.get(topic,{}).get('pathogen_class','unclassified')
        if cls not in ['viral','bacterial','syndromic']:
            reject(ds,topic,source,f'{cls}: not a classified count series'); continue
        total = g.is_total.copy()
        # Explicit case-definition filters do not infer totals from singleton values.
        rule=cfg.get('dimension_filters',{}).get(topic)
        if rule:
            desired=rule['values']
            def match(raw):
                vals=json.loads(raw)
                return all(vals.get(k)==v for k,v in desired.items()) and all(
                    k.startswith('georegion') or k in desired or v=='all' for k,v in vals.items())
            total = g.groups_json.map(match)
        b=g[total & ~g.is_stat_row & (g.place == cfg['geography']) & g.place_type.isin(['CHFL','country'])]
        measure=next((m for m in cfg['measures_preferred'] if m in set(b.measure)),None)
        if measure is None:
            reject(ds,topic,source,f'No explicit {cfg["geography"]} total with a preferred count measure'); continue
        b=b[b.measure==measure]
        selected=[]; error=None
        for year in years:
            q=b[b.year==year]; annual=q[q.period_type=='year']; monthly=q[q.period_type=='month']
            if len(annual)>1:
                error=f'{year}: overlapping annual totals'; break
            if len(annual)==1:
                chosen=annual
            elif len(monthly)==12 and monthly.period_start.dt.month.nunique()==12:
                chosen=monthly
            else:
                error=f'{year}: missing annual value or 12 distinct months'; break
            if chosen.value.isna().any() or (chosen.value < 0).any():
                error=f'{year}: missing or negative count'; break
            if not chosen.data_complete.fillna(False).all():
                error=f'{year}: source does not confirm dataComplete'; break
            if chosen['pop'].isna().any() or (chosen['pop']<=0).any() or chosen['pop'].nunique()!=1:
                error=f'{year}: missing, nonpositive or inconsistent population denominator'; break
            selected.append((year,chosen))
        if error:
            reject(ds,topic,source,error); continue
        if source not in cfg['source_priority']:
            reject(ds,topic,source,'Source absent from explicit priority policy'); continue
        candidates.append(dict(dataset_id=ds,topic=topic,source_system=source,cls=cls,measure=measure,
                               label=classes[topic]['label'],selected=selected))
    used=[]
    for topic in sorted({c['topic'] for c in candidates}):
        group=[c for c in candidates if c['topic']==topic]
        rank=min(cfg['source_priority'].index(c['source_system']) for c in group)
        best=[c for c in group if cfg['source_priority'].index(c['source_system'])==rank]
        if len(best)!=1:
            raise ValueError(f'Ambiguous overlapping exports for {topic}; select a single release in the raw snapshot')
        chosen=best[0]; used.append(chosen)
        for c in group:
            yes=c is chosen
            decisions.append(dict(dataset_id=c['dataset_id'],topic=topic,source_system=c['source_system'],
                                  status='included' if yes else 'excluded',reason='Complete compatible series; explicit source priority' if yes else 'Lower-priority source'))
    return used,pd.DataFrame(decisions,columns=['dataset_id','topic','source_system','status','reason'])


def analyse(out, stakeholder, classes_file, dest):
    out,dest=Path(out),Path(dest); verify_gate(out)
    dest.mkdir(parents=True,exist_ok=True)
    (dest/'bundle.json').unlink(missing_ok=True)
    cfg=load_config(stakeholder)
    ct=pd.read_csv(classes_file).fillna('')
    if ct.topic.duplicated().any(): raise ValueError('Duplicate pathogen classifications')
    if not set(ct.pathogen_class) <= {'viral','bacterial','syndromic','surveillance_signal'}: raise ValueError('Invalid pathogen class')
    classes=ct.set_index('topic').to_dict('index')
    used,selection=select_series(pd.read_parquet(out/'harmonised.parquet'),cfg,classes)
    selection.to_csv(dest/'selection.csv',index=False)
    if not used: raise ValueError('No complete series eligible')
    metrics=[]; lineage=[]; series=[]; values={}
    def metric(mid,typ,subject,year,unit,value,formula='raw_sum',inputs=None):
        inputs=inputs or []
        value=float(value) if value is not None and pd.notna(value) else None
        if value is not None and not __import__('math').isfinite(value): raise ValueError(f'Nonfinite metric: {mid}')
        values[mid]=value
        metrics.append(dict(metric_id=mid,metric_type=typ,subject=subject,year=year,unit=unit,
                            value=value,formula=formula,inputs_json=json.dumps(inputs)))
        for i in inputs: lineage.append(dict(metric_id=mid,input_kind='metric',input_id=i))
    def raw(mid,rows,col):
        for r in rows.itertuples():
            lineage.append(dict(metric_id=mid,input_kind='raw',input_id='',source_file=r.source_file,
                                source_row=int(r.source_row),source_column=col,sha256=r.sha256,metadata_sha256=r.metadata_sha256))
    for u in used:
        for year,q in u['selected']:
            stem=f"{u['topic']}:{year}"; count=stem+':count'; pop=stem+':population'; inc=stem+':incidence'
            v=q.value.sum(); p=q['pop'].iloc[0]
            metric(count,'count',u['topic'],year,u['measure'],v); raw(count,q,'value')
            metric(pop,'population',u['topic'],year,'persons',p,'raw_identity'); raw(pop,q.iloc[:1],'pop')
            metric(inc,'incidence',u['topic'],year,'per 100000',v/p*1e5,'ratio_100000',[count,pop])
            series.append(dict(topic=u['topic'],label=u['label'],pathogen_class=u['cls'],dataset_id=u['dataset_id'],
                               source_system=u['source_system'],measure=u['measure'],geography=cfg['geography'],year=year,
                               value=v,population=p,incidence=values[inc],count_metric_id=count,incidence_metric_id=inc,
                               coverage='complete',aggregation='reported annual' if len(q)==1 else 'sum of 12 months'))
    sd=pd.DataFrame(series)
    years=sorted(sd.year.unique()); y0,y1=cfg['years']; ref=cfg['reference_year']; base=cfg['index_base_year']
    for u in used:
        for start,label in [(y0,'period_change'),(ref,'reference_change')]:
            ids=[f"{u['topic']}:{start}:count",f"{u['topic']}:{y1}:count"]
            a,b=[values[i] for i in ids]
            metric(f"{u['topic']}:{label}",label,u['topic'],y1,'percent',None if a==0 else (b-a)/a*100,'percent_change',ids)
    for cls in cfg['classes_in_main_comparison']:
        for variant,drop in [('main',set(cfg['exclude_from_group_totals'])),('sensitivity',set(cfg['exclude_from_group_totals'])|set(cfg['sensitivity_exclude']))]:
            members=[u['topic'] for u in used if u['cls']==cls and u['topic'] not in drop and u['source_system'] in cfg['group_source_systems'] and u['measure']=='cases']
            if not members: raise ValueError(f'No eligible members for {cls}/{variant}')
            subject=f'{cls}:{variant}'
            for year in years:
                ids=[f'{t}:{year}:count' for t in members]
                metric(f'{subject}:{year}:total','group_total',subject,year,'cases',sum(values[i] for i in ids),'sum',ids)
            baseline=f'{subject}:{base}:total'
            if values[baseline]<=0: raise ValueError(f'Nonpositive baseline for {subject}')
            for year in years:
                mid=f'{subject}:{year}:total'
                metric(f'{subject}:{year}:index','group_index',subject,year,f'{base}=100',values[mid]/values[baseline]*100,'ratio_100',[mid,baseline])
            for start,label in [(y0,'period_change'),(ref,'reference_change')]:
                ids=[f'{subject}:{start}:total',f'{subject}:{y1}:total']; a,b=[values[i] for i in ids]
                metric(f'{subject}:{label}',label,subject,y1,'percent',None if a==0 else (b-a)/a*100,'percent_change',ids)
    sd.to_csv(dest/'series.csv',index=False)
    pd.DataFrame(metrics).to_csv(dest/'metrics.csv',index=False)
    pd.DataFrame(lineage).reindex(columns=LINEAGE_COLUMNS).to_csv(dest/'lineage.csv',index=False)
    sources=pd.read_csv(out/'datasets.csv').fillna(''); sources['used']=sources.dataset_id.isin(sd.dataset_id)
    sources.to_csv(dest/'sources.csv',index=False)
    (dest/'checks.csv').write_bytes((out/'checks.csv').read_bytes())
    (dest/'snapshot.json').write_bytes((out/'harmonised_snapshot.json').read_bytes())
    write_json(dest/'stakeholder.json',cfg)
    (dest/'pathogen_class.csv').write_bytes(Path(classes_file).read_bytes())
    # Eligibility in a group is explicit and identical in every displayed year.
    selection['group_eligible']=selection.topic.isin([u['topic'] for u in used if u['cls'] in cfg['classes_in_main_comparison'] and u['source_system'] in cfg['group_source_systems'] and u['measure']=='cases' and u['topic'] not in cfg['exclude_from_group_totals']])
    selection.to_csv(dest/'selection.csv',index=False)
    names=['series.csv','metrics.csv','lineage.csv','selection.csv','sources.csv','checks.csv','snapshot.json','stakeholder.json','pathogen_class.csv']
    write_json(dest/'bundle.json',{'schema_version':'2.0','stakeholder':cfg['id'],
               'snapshot_id':json.loads((out/'harmonised_snapshot.json').read_text())['snapshot_id'],
               'files':{n:digest(dest/n) for n in names}})
    return dest

if __name__=='__main__':
    ap=argparse.ArgumentParser(); ap.add_argument('--out',default='out'); ap.add_argument('--stakeholder',required=True)
    ap.add_argument('--classes',default=str(Path(__file__).parent/'config/pathogen_class.csv')); ap.add_argument('--dest',required=True)
    a=ap.parse_args()
    analyse(a.out,a.stakeholder,a.classes,a.dest)
