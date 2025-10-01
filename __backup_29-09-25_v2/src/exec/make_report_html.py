import argparse
import pandas as pd
import numpy as np
import math
import plotly.graph_objects as go
import plotly.express as px
from pathlib import Path
from datetime import datetime

# ---------- Root helpers ----------
import os

PRESET_ROOT = r"C:\Users\speed\Desktop\Forex CFD's system"


def detect_project_root(preset: str = PRESET_ROOT) -> Path:
    env = os.environ.get("PROJECT_ROOT")
    if env and Path(env).exists():
        return Path(env)
    if preset and Path(preset).exists():
        return Path(preset)
    return Path.cwd()


def default_paths():
    ROOT = detect_project_root()
    d1 = ROOT / "data" / "prices_1d"
    dH = ROOT / "data" / "prices_1h"
    folder = d1 if d1.exists() else (dH if dH.exists() else d1)
    cfg = ROOT / "config" / "baseline.yaml"
    costs = ROOT / "data" / "costs_per_symbol.csv"
    return ROOT, folder, cfg, costs


def portfolio_metrics(port):
    ret = port.pct_change().dropna()
    years = (port.index[-1] - port.index[0]).days / 365.25 if len(port) > 1 else np.nan
    cagr = (
        port.iloc[-1] ** (1 / years) - 1
        if (isinstance(years, float) and years > 0)
        else np.nan
    )
    vol = ret.std() * math.sqrt(252) if len(ret) > 2 else np.nan
    downside = ret[ret < 0].std() * math.sqrt(252) if len(ret) > 2 else np.nan
    sharpe = (cagr - 0.0) / vol if (isinstance(vol, float) and vol > 0) else np.nan
    sortino = (
        (cagr - 0.0) / downside
        if (isinstance(downside, float) and downside > 0)
        else np.nan
    )
    dd = port / port.cummax() - 1.0
    maxdd = dd.min() if len(dd) else np.nan
    dd_end = dd.idxmin() if len(dd) else None
    dd_start = port.loc[:dd_end].idxmax() if dd_end is not None else None
    return dict(
        cagr=cagr,
        vol=vol,
        sharpe=sharpe,
        sortino=sortino,
        maxdd=maxdd,
        dd_start=dd_start,
        dd_end=dd_end,
    )


def pareto_front(df, xcol="maxdd", ycol="sharpe", top_n=10):
    dx = df[xcol].abs()
    dy = df[ycol]
    order = np.lexsort((-dy.values, dx.values))
    mask = [False] * len(df)
    best_s = -1e9
    best_d = 1e9
    for i in order:
        d = float(dx.iloc[i])
        s = float(dy.iloc[i])
        if d <= best_d and s >= best_s:
            mask[i] = True
            best_d = d
            best_s = s
    pf = df[mask].sort_values([ycol, xcol], ascending=[False, True]).head(top_n)
    return pf


def make_report(
    equity_csv=None,
    attrib_csv=None,
    monthly_csv=None,
    out_html=None,
    robustness_summary_csv=None,
    pareto_top_n=10,
):
    ROOT, _, _, _ = default_paths()
    equity_csv = equity_csv or (ROOT / "data" / "pnl_demo_equity.csv")
    attrib_csv = attrib_csv or (ROOT / "data" / "pnl_demo_attrib_sleeve.csv")
    out_html = out_html or (
        ROOT / "reports" / f"report_{datetime.now().strftime('%Y%m%d_%H%M')}.html"
    )

    eq = pd.read_csv(equity_csv, parse_dates=["ts"]).set_index("ts")
    port = eq["portfolio_equity"]

    fig_eq = go.Figure()
    fig_eq.add_trace(go.Scatter(x=eq.index, y=port, name="Portfolio"))
    for c in eq.columns:
        if c.startswith("equity_"):
            fig_eq.add_trace(go.Scatter(x=eq.index, y=eq[c], name=c))
    fig_eq.update_layout(
        title="Equity Curves", xaxis_title="UTC Date", yaxis_title="Equity (base=1.0)"
    )

    dd = port / port.cummax() - 1.0
    fig_dd = go.Figure()
    fig_dd.add_trace(go.Scatter(x=dd.index, y=dd.values, name="Drawdown"))
    fig_dd.update_layout(
        title="Portfolio Drawdown", xaxis_title="UTC Date", yaxis_title="Drawdown"
    )

    # mret = (1+port.pct_change().fillna(0)).resample('M').prod()-1
    mret = (1 + port.pct_change().fillna(0)).resample("ME").prod() - 1
    heat = mret.to_frame("ret").reset_index()
    heat["Year"] = heat["ts"].dt.year
    heat["Month"] = heat["ts"].dt.month_name().str[:3]
    pivot = heat.pivot(index="Year", columns="Month", values="ret").fillna(0)
    months = [
        "Jan",
        "Feb",
        "Mar",
        "Apr",
        "May",
        "Jun",
        "Jul",
        "Aug",
        "Sep",
        "Oct",
        "Nov",
        "Dec",
    ]
    pivot = pivot.reindex(columns=[m for m in months if m in pivot.columns])
    fig_hm = px.imshow(
        pivot,
        text_auto=".1%",
        aspect="auto",
        origin="lower",
        labels=dict(color="Return"),
    )
    fig_hm.update_layout(title="Monthly Return Heatmap")

    metrics = portfolio_metrics(port)
    metrics_html = (
        "<table border='1' cellpadding='6' cellspacing='0'>"
        "<tr><th>CAGR</th><th>Vol</th><th>Sharpe</th><th>Sortino</th><th>MaxDD</th></tr>"
        f"<tr><td>{metrics['cagr']:.2%}</td><td>{metrics['vol']:.2%}</td><td>{metrics['sharpe']:.2f}</td>"
        f"<td>{metrics['sortino']:.2f}</td><td>{metrics['maxdd']:.2%}</td></tr></table>"
    )

    pareto_html = ""
    if robustness_summary_csv and Path(robustness_summary_csv).exists():
        sdf = pd.read_csv(robustness_summary_csv)
        if {"maxdd", "sharpe"}.issubset(sdf.columns):
            pf = pareto_front(sdf, xcol="maxdd", ycol="sharpe", top_n=pareto_top_n)
            base_cols = ["run", "loo", "lookbacks", "w_tsmom", "w_xsec", "w_mr"]
            maybe_cols = ["w_volcarry", "vc_top_q", "vc_bot_q", "vc_lookback"]
            tail_cols = [
                "target_vol",
                "vol_lookback",
                "max_leverage",
                "cagr",
                "vol",
                "sharpe",
                "maxdd",
                "mar",
            ]
            cols = [c for c in base_cols + maybe_cols + tail_cols if c in sdf.columns]
            pareto_html = pf[cols].to_html(
                index=False,
                float_format=lambda x: f"{x:.4f}" if isinstance(x, float) else str(x),
            )

    from plotly.io import to_html

    parts = [
        "<h1>Backtest Report</h1>",
        metrics_html,
        "<h2>Equity</h2>",
        to_html(fig_eq, include_plotlyjs="cdn", full_html=False),
        "<h2>Drawdown</h2>",
        to_html(fig_dd, include_plotlyjs=False, full_html=False),
        "<h2>Monthly Heatmap</h2>",
        to_html(fig_hm, include_plotlyjs=False, full_html=False),
    ]
    if pareto_html:
        parts += ["<h2>Pareto Top Candidates</h2>", pareto_html]

    Path(out_html).parent.mkdir(parents=True, exist_ok=True)
    with open(out_html, "w", encoding="utf-8") as f:
        f.write("\n".join(parts))
    print("Saved report to", out_html)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--equity_csv", default=None)
    ap.add_argument("--attrib_csv", default=None)
    ap.add_argument("--monthly_csv", default=None)
    ap.add_argument("--robustness_summary_csv", default=None)
    ap.add_argument("--pareto_top_n", type=int, default=10)
    ap.add_argument("--out_html", default=None)
    args = ap.parse_args()
    make_report(
        args.equity_csv,
        args.attrib_csv,
        args.monthly_csv,
        args.out_html,
        robustness_summary_csv=args.robustness_summary_csv,
        pareto_top_n=args.pareto_top_n,
    )


if __name__ == "__main__":
    main()
