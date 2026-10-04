#!/usr/bin/env python3
"""Run correctness regressions instead of treating pipeline completion as success."""
import subprocess
import sys
from pathlib import Path
if __name__=='__main__':
    root=Path(__file__).resolve().parents[2]
    sys.exit(subprocess.call([sys.executable,'-m','pytest',str(root/'tests'),'-q']))
