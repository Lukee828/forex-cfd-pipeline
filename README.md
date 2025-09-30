

## Direct download using `dukascopy-python`
```bash
pip install dukascopy-python
python -m src.data.dukascopy_downloader --symbol EURUSD --tf 1h --start 2022-01-01 --end 2022-12-31 --out data/prices_1h/EURUSD.parquet
```
If your package exposes a different API, edit `_fetch_with_library` in `src/data/dukascopy_downloader.py` (it already tries several common patterns).
Generated on 2025-09-28T11:07:20.867016Z
