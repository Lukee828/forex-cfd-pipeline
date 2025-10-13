from dataclasses import dataclass
from typing import List, Dict


@dataclass
class SelectionResult:
    core: List[str]
    satellite: List[str]
    excluded: Dict[str, str]


def select(config, prices=None, costs=None, dispersion_df=None) -> SelectionResult:
    core = config["symbols"]["core"]
    satellite = config["symbols"]["satellite"]
    excluded = {}
    # Placeholder: no exclusions until metrics are wired
    return SelectionResult(core=core, satellite=satellite, excluded=excluded)
