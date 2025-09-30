
# Quant Stack – All-in Patch (MVP finish)

## What's inside
- True portfolio MTD gating (global soft/hard stops)
- Multi-sleeve combiner (TSMOM + XSec + MR)
- Per-symbol **entry/exit** costs via `data/costs_per_symbol.csv`
- Metrics & report:
  - `metrics_summary.py` (CAGR, vol, Sharpe, Sortino, MaxDD, MAR, trade stats)
  - `make_monthly_summary.py` (monthly & YTD table CSV)
  - `make_report_html.py` (equity, drawdown, monthly heatmap, sleeve attribution, metrics, **monthly table**)
- Path helpers and data lister
- xsec month-end tz-safe fix

## Quick start
1) Run backtest:
```
python -m src.exec.backtest_pnl_demo --cfg config/base.yaml --folder data\prices_1d --costs_csv data\costs_per_symbol.csv --target_ann_vol 0.12 --vol_lookback 20 --max_leverage 3.0 --mtd_soft -0.06 --mtd_hard -0.10 --w_tsmom 1.0 --w_xsec 0.8 --w_mr 0.6
```

2) Metrics & summaries:
```
python -m src.exec.metrics_summary --equity_csv data\pnl_demo_equity.csv --trades_csv data\pnl_demo_trades.csv
python -m src.exec.make_monthly_summary --equity_csv data\pnl_demo_equity.csv --out_csv reports\monthly_summary.csv
```

3) One-click HTML:
```
python -m src.exec.make_report_html --equity_csv data\pnl_demo_equity.csv --attrib_csv data\pnl_demo_attrib_sleeve.csv --monthly_csv reports\monthly_summary.csv --out_html reports\report_latest.html
```

4) Data lister (see what's available):
```
python -m src.exec.list_data --root data
```

## Files added/updated in this patch
- src/exec/backtest_pnl_demo.py
- src/exec/metrics_summary.py
- src/exec/make_monthly_summary.py
- src/exec/make_report_html.py
- src/exec/list_data.py
- src/sleeves/xsec_mom_simple.py (tz-safe month-end)
- data/costs_per_symbol.csv (entry/exit legs)
- README_RUNBOOK.md
