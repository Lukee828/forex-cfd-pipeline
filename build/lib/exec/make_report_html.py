# make_report_html.py — report with dual (IS/OOS) robustness comparison

import argparse
import pandas as pd
import numpy as np
import math
import plotly.graph_objects as go
import plotly.express as px
from pathlib import Path
from datetime import datetime

# ---------- shared root helpers ----------
from pathlib import Path as _P
import os as _os

PRESET_ROOT = r"C:\Users\speed\Desktop\Forex CFD's system"


def detect_project_root(preset: str = PRESET_ROOT) -> _P:
    env = _os.environ.get("PROJECT_ROOT")
    if env and _P(env).exists():
        return _P(env)
    if preset and _P(preset).exists():
        return _P(preset)
    return _P.cwd()


def default_paths():
    ROOT = detect_project_root()
    d1 = ROOT / "data" / "prices_1d"
    dH = ROOT / "data" / "prices_1h"
    folder = d1 if d1.exists() else (dH if dH.exists() else d1)
    cfg = ROOT / "config" / "baseline.yaml"
    costs = ROOT / "data" / "costs_per_symbol.csv"
    return ROOT, folder, cfg, costs


# ---------- metrics & helpers ----------
def portfolio_metrics(port):
    ret = port.pct_change().dropna()
    years = (port.index[-1] - port.index[0]).days / 365.25 if len(port) > 1 else np.nan
    cagr = port.iloc[-1] ** (1 / years) - 1 if (isinstance(years, float) and years > 0) else np.nan
    vol = ret.std() * math.sqrt(252) if len(ret) > 2 else np.nan
    downside = ret[ret < 0].std() * math.sqrt(252) if len(ret) > 2 else np.nan
    sharpe = (cagr - 0.0) / vol if (isinstance(vol, float) and vol > 0) else np.nan
    sortino = (cagr - 0.0) / downside if (isinstance(downside, float) and downside > 0) else np.nan
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
    if df.empty or not {"maxdd", "sharpe"}.issubset(df.columns):
        return pd.DataFrame()
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


def load_summary(path):
    p = Path(path) if path else None
    if p and p.exists():
        df = pd.read_csv(p)
        # normalize expected columns
        for c in [
            "run",
            "loo",
            "lookbacks",
            "w_tsmom",
            "w_xsec",
            "w_mr",
            "w_volcarry",
            "vc_top_q",
            "vc_bot_q",
            "vc_lookback",
            "target_vol",
            "vol_lookback",
            "max_leverage",
            "cagr",
            "vol",
            "sharpe",
            "maxdd",
            "mar",
        ]:
            if c not in df.columns:
                # don't force-create; plots/tables will only include what exists
                pass
        return df
    return pd.DataFrame()


# ---------- report ----------
def make_report(
    equity_csv=None,
    attrib_csv=None,
    monthly_csv=None,
    out_html=None,
    robustness_summary_csv=None,
    pareto_top_n=10,
    robustness_summary_csv_is=None,
    robustness_summary_csv_oos=None,
):
    ROOT, _, _, _ = default_paths()
    equity_csv = equity_csv or (ROOT / "data" / "pnl_demo_equity.csv")
    attrib_csv = attrib_csv or (ROOT / "data" / "pnl_demo_attrib_sleeve.csv")
    out_html = out_html or (
        ROOT / "reports" / f"report_{datetime.now().strftime('%Y%m%d_%H%M')}.html"
    )

    # --- equity & drawdown & monthly heatmap ---
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
    fig_dd.update_layout(title="Portfolio Drawdown", xaxis_title="UTC Date", yaxis_title="Drawdown")

    # month-end resample ('ME' is the non-deprecated code)
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

    # --- metrics table ---
    metrics = portfolio_metrics(port)

    def fmt(x):
        if x is None or (isinstance(x, float) and (np.isnan(x) or np.isinf(x))):
            return "-"
        return f"{x:.2%}" if isinstance(x, float) and abs(x) < 2 else f"{x:,.2f}"

    metrics_html = (
        "<table border='1' cellpadding='6' cellspacing='0'>"
        "<tr><th>CAGR</th><th>Vol</th><th>Sharpe</th><th>Sortino</th><th>MaxDD</th></tr>"
        f"<tr><td>{fmt(metrics['cagr'])}</td><td>{fmt(metrics['vol'])}</td><td>{fmt(metrics['sharpe'])}</td>"
        f"<td>{fmt(metrics['sortino'])}</td><td>{fmt(metrics['maxdd'])}</td></tr></table>"
    )

    # --- load robustness summaries (legacy single, or IS/OOS dual) ---
    df_single = load_summary(robustness_summary_csv)
    df_is = load_summary(robustness_summary_csv_is)
    df_oos = load_summary(robustness_summary_csv_oos)

    # pareto tables
    pareto_html_single = ""
    pareto_html_is = ""
    pareto_html_oos = ""
    overlay_html = ""

    # columns to show if present
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

    def select_cols(df):
        return [c for c in base_cols + maybe_cols + tail_cols if c in df.columns]

    # single-summary (backwards compat)
    if not df_is.empty or not df_oos.empty:
        # dual mode
        if not df_is.empty:
            pf_is = pareto_front(df_is, xcol="maxdd", ycol="sharpe", top_n=pareto_top_n)
            if not pf_is.empty:
                pareto_html_is = pf_is[select_cols(pf_is)].to_html(
                    index=False,
                    float_format=lambda x: (f"{x:.4f}" if isinstance(x, float) else str(x)),
                )
        if not df_oos.empty:
            pf_oos = pareto_front(df_oos, xcol="maxdd", ycol="sharpe", top_n=pareto_top_n)
            if not pf_oos.empty:
                pareto_html_oos = pf_oos[select_cols(pf_oos)].to_html(
                    index=False,
                    float_format=lambda x: (f"{x:.4f}" if isinstance(x, float) else str(x)),
                )

        # overlay scatter Sharpe vs |MaxDD|
        if not df_is.empty or not df_oos.empty:
            fig_sc = go.Figure()
            if not df_is.empty:
                d1 = df_is.copy()
                d1["|maxdd|"] = d1["maxdd"].abs()
                fig_sc.add_trace(
                    go.Scatter(
                        x=d1["|maxdd|"],
                        y=d1["sharpe"],
                        mode="markers",
                        name="IS",
                        hovertext=[str(r) for _, r in d1[select_cols(d1)].iterrows()],
                    )
                )
            if not df_oos.empty:
                d2 = df_oos.copy()
                d2["|maxdd|"] = d2["maxdd"].abs()
                fig_sc.add_trace(
                    go.Scatter(
                        x=d2["|maxdd|"],
                        y=d2["sharpe"],
                        mode="markers",
                        name="OOS",
                        hovertext=[str(r) for _, r in d2[select_cols(d2)].iterrows()],
                    )
                )
            fig_sc.update_layout(
                title="Sharpe vs |MaxDD| (IS vs OOS)",
                xaxis_title="|Max Drawdown|",
                yaxis_title="Sharpe",
            )
            from plotly.io import to_html as _to_html

            overlay_html = _to_html(fig_sc, include_plotlyjs=False, full_html=False)
    else:
        # single summary mode
        if not df_single.empty:
            pf = pareto_front(df_single, xcol="maxdd", ycol="sharpe", top_n=pareto_top_n)
            if not pf.empty:
                pareto_html_single = pf[select_cols(pf)].to_html(
                    index=False,
                    float_format=lambda x: (f"{x:.4f}" if isinstance(x, float) else str(x)),
                )

    # assemble HTML
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
    if overlay_html:
        parts += ["<h2>Robustness: Sharpe vs |MaxDD| (IS vs OOS)</h2>", overlay_html]
    if pareto_html_single:
        parts += ["<h2>Pareto Top Candidates</h2>", pareto_html_single]
    if pareto_html_is or pareto_html_oos:
        if pareto_html_is:
            parts += ["<h2>Pareto (In-Sample)</h2>", pareto_html_is]
        if pareto_html_oos:
            parts += ["<h2>Pareto (Out-of-Sample)</h2>", pareto_html_oos]

    Path(out_html).parent.mkdir(parents=True, exist_ok=True)
    with open(out_html, "w", encoding="utf-8") as f:
        f.write("\n".join(parts))
    print("Saved report to", out_html)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--equity_csv", default=None)
    ap.add_argument("--attrib_csv", default=None)
    ap.add_argument("--monthly_csv", default=None)

    # single-summary (legacy)
    ap.add_argument("--robustness_summary_csv", default=None)
    ap.add_argument("--pareto_top_n", type=int, default=10)

    # NEW: dual summaries (IS & OOS)
    ap.add_argument("--robustness_summary_csv_is", default=None)
    ap.add_argument("--robustness_summary_csv_oos", default=None)

    ap.add_argument("--out_html", default=None)
    args = ap.parse_args()

    make_report(
        args.equity_csv,
        args.attrib_csv,
        args.monthly_csv,
        args.out_html,
        robustness_summary_csv=args.robustness_summary_csv,
        pareto_top_n=args.pareto_top_n,
        robustness_summary_csv_is=args.robustness_summary_csv_is,
        robustness_summary_csv_oos=args.robustness_summary_csv_oos,
    )


if __name__ == "__main__":
    main()
