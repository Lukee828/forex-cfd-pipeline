# ... rest of imports and code above ...


def safe_print_summary(merged):
    start = merged.index.min()
    end = merged.index.max()
    cumret = merged["portfolio_equity"].iloc[-1] - 1.0
    nsyms = len([c for c in merged.columns if c.startswith("equity_")])
    print(f"Backtest period: {start.date()} -> {end.date()} | Symbols: {nsyms}")
    print(f"Portfolio cum return (after costs): {cumret:.2%}")
    print(f"Final equity: {merged['portfolio_equity'].iloc[-1]:.4f}")
    print("Saved equity to data/pnl_demo_equity.csv")


# At the bottom of your main(), replace the old block with:
# safe_print_summary(merged)
