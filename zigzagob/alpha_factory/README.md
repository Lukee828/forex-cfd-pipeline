# Alpha Factory v1.0 — Infrastructure Modules

Lean research infra used across Alpha Factory; dependency-light and covered by tests.

| Module | Purpose |
|:--|:--|
| eature_store.py | Versioned feature registry (DuckDB/SQLite) |
| lpha_registry.py | Track alpha runs, configs & feature links |
| isk_governor.py | Rolling DD / vol throttle & exposure cap |
| meta_allocator.py | EWMA / Bayesian sleeve allocator |
| esearch_scheduler.py | Interval & daily job scheduler + deep-merge overlays |
| drift_dashboard.py | PSI drift metrics, rolling stats, minimal HTML export |

## Quick Examples

### FeatureStore
~~~python
from zigzagob.alpha_factory.feature_store import FeatureStore
import pandas as pd
fs = FeatureStore('local.duckdb')
df = pd.DataFrame({
  'asof': pd.date_range('2024-01-01', periods=3, freq='D'),
  'symbol': ['EURUSD','XAUUSD','USDJPY'],
  'value': [1.0, 2.0, 3.0],
})
fs.register('my_feature', df)
print(fs.get('my_feature').head())
~~~

### RiskGovernor
~~~python
from zigzagob.alpha_factory.risk_governor import RiskGovernor, GovernorConfig
import pandas as pd, numpy as np
cfg = GovernorConfig(dd_limit=0.07, vol_target=0.12)
gov = RiskGovernor(cfg)
equity = (1 + pd.Series(np.random.normal(0, 0.01, 300))).cumprod()
thr = gov.compute(equity)['throttle']
~~~

### MetaAllocator (EWMA)
~~~python
from zigzagob.alpha_factory.meta_allocator import MetaAllocator, EWMAConfig
import pandas as pd, numpy as np
rets = pd.DataFrame(np.random.normal(0, 0.01, (100,3)), columns=list('ABC'))
alloc = MetaAllocator(mode='ewma', ewma_cfg=EWMAConfig())
weights = alloc.allocate(rets)
~~~

### ResearchScheduler
~~~python
from zigzagob.alpha_factory.research_scheduler import ResearchScheduler
import datetime as dt
def task(**kw): return {'ok':True, 'kw':kw}
sch = ResearchScheduler()
sch.add_job('pulse', task, {'every': 60}, params={'u':'majors'})
print(sch.tick(dt.datetime.utcnow()))
~~~

### Drift Dashboard
~~~python
from zigzagob.alpha_factory.drift_dashboard import compute_tabular_drift, simple_html_report
import pandas as pd, numpy as np
ref = pd.DataFrame({'x': np.random.normal(0,1,1000)})
cur = pd.DataFrame({'x': np.random.normal(0.3,1.2,1000)})
m = compute_tabular_drift(ref, cur)
simple_html_report(m, title='Drift Report', path='drift_report.html')
~~~

## Tests
~~~bash
pytest -q tests
~~~
