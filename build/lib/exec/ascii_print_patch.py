# PATCH: ASCII-only prints to avoid Windows cp1250 UnicodeEncodeError
# Replace the corresponding print block in your backtester with this safe version.


def _print_summary(merged):
    start = merged.index.min()
    end = merged.index.max()
    cumret = merged["portfolio_equity"].iloc[-1] - 1.0
    nsyms = len([c for c in merged.columns if c.startswith("equity_")])
    # ASCII arrow '->' instead of unicode
    print(f"Backtest period: {start.date()} -> {end.date()} | Symbols: {nsyms}")
    print(f"Portfolio cum return (after costs): {cumret:.2%}")
    print(f"Final equity: {merged['portfolio_equity'].iloc[-1]:.4f}")
    print("Saved equity to data/pnl_demo_equity.csv")
