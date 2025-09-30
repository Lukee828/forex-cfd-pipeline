# patched report script using default_paths

from pathlib import Path
import os

def detect_project_root(preset=r"C:\Users\speed\Desktop\Forex CFD's system"):
    env = os.environ.get("PROJECT_ROOT")
    if env and Path(env).exists():
        return Path(env)
    if preset and Path(preset).exists():
        return Path(preset)
    return Path.cwd()

def default_paths(preset=r"C:\Users\speed\Desktop\Forex CFD's system"):
    ROOT = detect_project_root(preset)
    data_1d = ROOT/"data"/"prices_1d"
    data_1h = ROOT/"data"/"prices_1h"
    folder = data_1d if data_1d.exists() else (data_1h if data_1h.exists() else ROOT/"data"/"prices_1d")
    cfg = ROOT/"config"/"baseline.yaml"
    costs = ROOT/"data"/"costs_per_symbol.csv"
    return ROOT, folder, cfg, costs
