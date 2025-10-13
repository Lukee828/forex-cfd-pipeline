import os
import numpy as np
import pandas as pd


class EngineLoop:
    """
    Minimal, robust engine:
      - Computes equal-weighted basket log-returns from closes.
      - Strategy.on_bar(window, i) -> {"signal": +1/-1} (or {} to keep pos).
      - Equity starts at 1.0 and compounds multiplicatively: E *= (1 + r*pos - cost).
    """

    def __init__(self, feed, strategy, trading_bps: float = 0.0):
        self.feed = feed
        self.strategy = strategy
        self.trading_bps = float(trading_bps)

    def run(
        self, max_steps: int = None, out_csv: str = os.path.join("runs", "equity.csv")
    ) -> pd.Series:
        # Get closes for selected symbols (DataFrame: index=time, columns=symbols)
        closes = self.feed.get_closes(limit=max_steps)
        if isinstance(closes, pd.Series):
            closes = closes.to_frame("Close")

        # Clean closes
        closes = (
            closes.sort_index().astype(float).replace([np.inf, -np.inf], np.nan).ffill().bfill()
        )
        if closes.isna().any().any():
            closes = closes.dropna()

        if closes.shape[0] < 3:
            equity = pd.Series([1.0] * closes.shape[0], index=closes.index, name="equity")
            os.makedirs(os.path.dirname(out_csv), exist_ok=True)
            equity.to_frame().to_csv(out_csv)
            return equity

        # Equal-weight log-returns across symbols
        # (use log so pos switches don’t create drift from arithmetic chaining)
        basket = closes.mean(axis=1)
        logr = np.log(basket / basket.shift(1)).replace([np.inf, -np.inf], np.nan)
        logr = logr.fillna(0.0)

        # Roll through bars, ask strategy for signal
        equity_vals = []
        pos_prev = 0
        eq = 1.0

        # rolling window series we pass to the strategy (basket closes)
        for i in range(len(basket)):
            px_window = basket.iloc[: i + 1]
            sig_dict = self.strategy.on_bar(px_window, i) or {}
            pos_next = int(sig_dict.get("signal", pos_prev))  # stay if no signal

            # costs when changing position (turnover = |pos_next - pos_prev|)
            turnover = abs(pos_next - pos_prev)
            cost = turnover * (self.trading_bps / 1e4)

            r = float(logr.iloc[i])  # per-bar log return
            # convert log-return to arithmetic approx for compounding with costs
            arith = np.expm1(r)

            eq = eq * (1.0 + pos_prev * arith - cost)
            # avoid degenerate negatives (still keep > 0 for summarizer)
            if not np.isfinite(eq) or eq <= 0:
                eq = max(1e-8, eq if np.isfinite(eq) else 1e-8)

            equity_vals.append(eq)
            pos_prev = pos_next

        equity = pd.Series(equity_vals, index=basket.index, name="equity")
        os.makedirs(os.path.dirname(out_csv), exist_ok=True)
        equity.to_frame().to_csv(out_csv)
        return equity
