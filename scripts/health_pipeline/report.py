#!/usr/bin/env python3
"""Compatibility entry point: validate, analyse once, render the shared QMD."""
import argparse
from pathlib import Path
from analyse import analyse,load_config
from publish import render,package
HERE=Path(__file__).resolve().parent
if __name__=='__main__':
    ap=argparse.ArgumentParser(); ap.add_argument('--stakeholder',default=str(HERE/'config/stakeholders/public_health_expert.json'))
    ap.add_argument('--classes',default=str(HERE/'config/pathogen_class.csv')); ap.add_argument('--out',default='out'); ap.add_argument('--quarto',default='quarto')
    a=ap.parse_args(); cfg=load_config(a.stakeholder); bundle=Path(a.out)/'reports'/cfg['id']/'data'
    analyse(a.out,a.stakeholder,a.classes,bundle)
    package(bundle,bundle.parent/'app')
    render(bundle,bundle.parent/'report.html','html',a.quarto)
