\
@echo off
cd /d "C:\Users\speed\Desktop\Forex CFD's system"
python -m src.exec.run_all --cfg config\baseline.yaml --folder data\prices_1d --costs_csv data\costs_per_symbol.csv --target_ann_vol 0.12 --vol_lookback 20 --max_leverage 3.0 --mtd_soft -0.06 --mtd_hard -0.10 --w_tsmom 1.0 --w_xsec 0.8 --w_mr 0.6 --nav 1000000
python -m src.exec.paper_log --equity_csv data\pnl_demo_equity.csv --log_csv logs\paper_nav.csv
