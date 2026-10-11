"""Record artifacts, exact code/config hashes, and the actual build environment."""
import argparse
import importlib.metadata
import platform
import subprocess
from pathlib import Path
from common import digest,write_json

def command(args):
    try: return subprocess.check_output(args,stderr=subprocess.STDOUT,text=True).strip()
    except (OSError,subprocess.CalledProcessError): return 'unavailable'

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--out',required=True);ap.add_argument('--quarto',default='quarto');a=ap.parse_args()
    out=Path(a.out)
    artifacts=[p for p in out.rglob('*') if p.is_file() and 'snapshots' not in p.parts and p.name!='release.json']
    source=[p for root in [Path('scripts/health_pipeline'),Path('workflow'),Path('tests')] for p in root.rglob('*') if p.is_file() and not any(x in p.parts for x in ['example_output','__pycache__','.pytest_cache']) and p.suffix not in ['.pyc'] and p.name!='.DS_Store']
    source += [Path('Snakefile'),Path('renv.lock'),Path('.Rprofile')]
    write_json(out/'release.json',{'schema_version':'2.0','git_commit':command(['git','rev-parse','HEAD']),
        'git_status':command(['git','status','--porcelain']), 'python':platform.python_version(),'platform':platform.platform(),
        'tex':command([a.quarto,'list','tools']), 'quarto':command([a.quarto,'--version']),'R':command(['Rscript','-e','sessionInfo()']),
        'r_packages':command(['Rscript','-e','for(p in c("shiny","knitr","rmarkdown","jsonlite","digest")) cat(p,as.character(packageVersion(p)),"\\n")']),
        'python_packages':{d.metadata['Name']:d.version for d in importlib.metadata.distributions()},
        'code':{str(p):digest(p) for p in sorted(source)},
        'artifacts':{p.relative_to(out).as_posix():digest(p) for p in sorted(artifacts)}})
