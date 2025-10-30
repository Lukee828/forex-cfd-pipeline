"""
alpha_factory.conformal_gate
Phase 6 (Conformal Meta-Gate)

This module provides a selective trading gate using rolling conformal calibration.
It attempts to only APPROVE trades whose predicted win probability is high enough
to satisfy a target coverage level. Others are ABSTAINED.
"""

from __future__ import annotations

from typing import Dict, Any, Optional
from dataclasses import dataclass, field
import json
import pathlib
import datetime as dt

# We assume sklearn is available in the research / nightly environment.
# If not present in production yet, runtime can operate in "passthrough" mode.
try:
    from sklearn.linear_model import LogisticRegression
    import numpy as np

    SKLEARN_OK = True
except Exception:  # pragma: no cover
    LogisticRegression = None  # type: ignore
    np = None  # type: ignore
    SKLEARN_OK = False


@dataclass
class ConformalModelBundle:
    """Serializable snapshot of the gate state."""

    as_of: str
    coverage_target: float
    tau: float
    feature_names: list[str]
    coef: Optional[list[float]] = None
    intercept: Optional[float] = None
    n_calib: int = 0
    note: str = ""
    # You can later add metrics like abstain_rate, win_rate_accept, etc.


@dataclass
class ConformalGate:
    coverage_target: float = 0.9
    calibration_window: int = 2000
    min_samples: int = 300
    abstain_policy: str = "skip"
    bundle: Optional[ConformalModelBundle] = field(default=None)
    _clf: Optional[LogisticRegression] = field(default=None, repr=False)

    # ---------- Public API ----------

    def fit_from_history(
        self,
        features: "np.ndarray",
        labels: "np.ndarray",
        feature_names: list[str],
    ) -> None:
        """
        Train logistic model, compute conformal threshold tau.
        We expect `features` shape (N, F), labels shape (N,).
        We will:
            - split into train / calib
            - train on train
            - compute tau on calib
            - store bundle
        """
        if not SKLEARN_OK:
            # fallback: mark bundle as passthrough (always ACCEPT)
            self.bundle = ConformalModelBundle(
                as_of=dt.datetime.utcnow().isoformat(),
                coverage_target=self.coverage_target,
                tau=1.0,  # huge tau => always accept
                feature_names=feature_names,
                coef=None,
                intercept=None,
                n_calib=0,
                note="SKLEARN_NOT_AVAILABLE",
            )
            return

        # Trim to calibration_window most recent samples
        if features.shape[0] > self.calibration_window:
            features = features[-self.calibration_window :]
            labels = labels[-self.calibration_window :]

        n = features.shape[0]
        if n < self.min_samples:
            # not enough data to calibrate => passthrough
            self.bundle = ConformalModelBundle(
                as_of=dt.datetime.utcnow().isoformat(),
                coverage_target=self.coverage_target,
                tau=1.0,
                feature_names=feature_names,
                coef=None,
                intercept=None,
                n_calib=0,
                note=f"NOT_ENOUGH_SAMPLES:{n}",
            )
            return

        # simple split: last 20% calib, first 80% train
        split_idx = int(n * 0.8)
        X_train = features[:split_idx]
        y_train = labels[:split_idx]
        X_calib = features[split_idx:]
        y_calib = labels[split_idx:]

        clf = LogisticRegression(
            max_iter=200,
            class_weight="balanced",
        )
        clf.fit(X_train, y_train)

        p_hat = clf.predict_proba(X_calib)[:, 1]  # prob of success

        # build nonconformity scores
        # alpha_i = max( p_hat_i    if y_i==0,
        #                1-p_hat_i  if y_i==1 )
        miss_when_bad = np.where(y_calib == 0, p_hat, 0.0)
        miss_when_good = np.where(y_calib == 1, 1.0 - p_hat, 0.0)
        alpha = np.maximum(miss_when_bad, miss_when_good)

        # choose tau at coverage_target quantile
        # Example: coverage_target=0.9 => keep 90% easiest => 90th pct
        q = np.quantile(alpha, self.coverage_target)

        self._clf = clf
        self.bundle = ConformalModelBundle(
            as_of=dt.datetime.utcnow().isoformat(),
            coverage_target=self.coverage_target,
            tau=float(q),
            feature_names=feature_names,
            coef=clf.coef_[0, :].tolist(),
            intercept=float(clf.intercept_[0]),
            n_calib=len(alpha),
            note="OK",
        )

    def score_live_trade(self, feature_row: Dict[str, float]) -> Dict[str, Any]:
        """
        Given a dict of feature_name -> value for ONE trade candidate,
        return decision metadata.
        If bundle.tau is large (1.0 passthrough), we auto-ACCEPT.
        """
        if self.bundle is None:
            return {
                "decision": "ACCEPT",
                "reason": "NO_BUNDLE",
                "p_win": None,
                "alpha_new": None,
                "tau": None,
                "coverage_target": self.coverage_target,
            }

        # Map dict to array in feature_names order
        order = self.bundle.feature_names
        x = [feature_row.get(name, 0.0) for name in order]

        # Compute p_win
        if self._clf is None or not SKLEARN_OK or self.bundle.coef is None:
            # linear fallback from saved coef if needed in future
            p_win = None
        else:
            import numpy as _np  # local alias to avoid top-level clash

            arr = _np.array(x).reshape(1, -1)
            p_win = float(self._clf.predict_proba(arr)[:, 1])

        # Compute alpha_new (conservatively)
        if p_win is None:
            alpha_new = 0.0  # we have no model, default ACCEPT
        else:
            alpha_new = max(p_win, 1.0 - p_win)

        tau = self.bundle.tau

        if alpha_new <= tau:
            decision = "ACCEPT"
        else:
            decision = "ABSTAIN"

        return {
            "decision": decision,
            "p_win": p_win,
            "alpha_new": alpha_new,
            "tau": tau,
            "coverage_target": self.bundle.coverage_target,
            "as_of": self.bundle.as_of,
            "note": self.bundle.note,
        }

    # ---------- Persistence helpers ----------

    def save_bundle(self, root_dir: str | pathlib.Path) -> pathlib.Path:
        """
        Write current bundle (JSON) to artifacts/conformal/.
        Returns the path written.
        """
        if self.bundle is None:
            raise RuntimeError("No bundle to save.")

        root = pathlib.Path(root_dir)
        root.mkdir(parents=True, exist_ok=True)

        ts = self.bundle.as_of.replace(":", "-")
        out_path = root / f"conformal_{ts}.json"

        with out_path.open("w", encoding="utf-8") as f:
            json.dump(self.bundle.__dict__, f, ensure_ascii=False, indent=2)

        # also write latest_summary.json for dashboard
        latest = root / "latest_summary.json"
        summary = {
            "as_of": self.bundle.as_of,
            "coverage_target": self.bundle.coverage_target,
            "tau": self.bundle.tau,
            "n_calib": self.bundle.n_calib,
            "note": self.bundle.note,
        }
        with latest.open("w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)

        return out_path

    @staticmethod
    def load_latest(root_dir: str | pathlib.Path) -> "ConformalGate":
        """
        Load latest bundle (by mtime) from artifacts/conformal/.
        For runtime scoring in live path or paper sim path.
        """
        root = pathlib.Path(root_dir)
        cand = sorted(root.glob("conformal_*.json"), key=lambda p: p.stat().st_mtime)
        if not cand:
            return ConformalGate()  # empty passthrough

        with cand[-1].open("r", encoding="utf-8") as f:
            raw = json.load(f)

        gate = ConformalGate(
            coverage_target=raw.get("coverage_target", 0.9),
        )
        gate.bundle = ConformalModelBundle(**raw)

        # We do NOT rebuild sklearn clf here yet. Phase 6 runtime path
        # can either (a) call this from research/scheduler side
        # or (b) accept "p_win=None" mode in production.
        return gate
