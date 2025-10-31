import os
import time
import json
from datetime import datetime, timezone
import MetaTrader5 as mt5

ART_DIR = os.path.join("artifacts", "live")
NEXT_ORDER_PATH = os.path.join(ART_DIR, "next_order.json")
JOURNAL_PATH = os.path.join(ART_DIR, "journal.ndjson")
LIVE_SWITCH_PATH = os.path.join("ai_lab", "live_switch.json")

# -------------------------------------------------
# tunables / hard safety thresholds
# -------------------------------------------------
MAX_SPREAD_PIPS = 1.5        # max spread allowed before / after fill
MAX_LATENCY_SEC = 1.0        # max acceptable roundtrip latency (s)
MAX_SLIPPAGE_PIPS = 0.5      # max acceptable abs slippage in pips
MAX_LOTS = 0.35              # absolute clamp per ticket

ALLOWED_SYMBOLS = {
    "EURUSD": {
        "sides": ["BUY"],    # whitelist direction
        "max_lots": MAX_LOTS,
    }
}

# -------------------------------------------------
# helper: safe session guard + safe risk governor
# (these are NEW, but fail-open / no-break)
# -------------------------------------------------
def _safe_session_ok_now() -> bool:
    """
    Ask alpha_factory.sessions.ok_to_trade_now() if it exists.
    If module or function is missing -> return True (allow trading).
    If it exists but raises -> return False (block).
    This gives you a hook for session freeze / news embargo.
    """
    try:
        from alpha_factory import sessions  # type: ignore
    except Exception:
        return True  # module not there -> allow
    try:
        return bool(sessions.ok_to_trade_now())
    except Exception:
        return False  # if it blows up, safest is block


def _safe_risk_can_trade() -> tuple[bool, str | None]:
    """
    Ask alpha_factory.risk_governor.live_can_trade() if available.
    Expect it to return (ok: bool, reason: str|None).
    If module missing -> (True, None).
    If call explodes -> (False, "RISK_GOV_ERROR").
    This becomes your drawdown / exposure stop.
    """
    try:
        from alpha_factory import risk_governor  # type: ignore
    except Exception:
        return True, None  # no governor yet -> allow
    try:
        res = risk_governor.live_can_trade()
        # be tolerant about shape
        if isinstance(res, tuple) and len(res) >= 1:
            ok = bool(res[0])
            reason = res[1] if len(res) > 1 else None
            return ok, reason
        # weird return -> treat as reject
        return False, "RISK_GOV_BAD_SHAPE"
    except Exception as e:
        return False, f"RISK_GOV_ERROR:{e}"

# -------------------------------------------------
# low-level utils
# -------------------------------------------------
def _now_utc_iso():
    # always Zulu for clarity, include timezone
    return datetime.now(timezone.utc).isoformat()


def _append_ndjson(row: dict):
    """
    Append a JSON line to journal.ndjson in artifacts/live.
    Creates folders/files if missing.
    """
    os.makedirs(ART_DIR, exist_ok=True)
    with open(JOURNAL_PATH, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False))
        fh.write("\n")


def _ensure_mt5():
    """
    Idempotent safety gate.
    - Make sure MT5 is initialized.
    - Make sure terminal + account are available.
    - Make sure trading is allowed.
    Raises RuntimeError if something is off.
    """
    mt5.initialize()  # safe to call repeatedly
    term_info = mt5.terminal_info()
    if term_info is None:
        raise RuntimeError("MT5 terminal_info() is None (terminal not reachable?)")
    acct_info = mt5.account_info()
    if acct_info is None:
        raise RuntimeError("MT5 account_info() is None (not logged in?)")
    if not term_info.trade_allowed:
        raise RuntimeError("MT5 trade not allowed (check AutoTrading / permissions)")


def _get_positions_snapshot():
    """
    Return list(mt5.positions_get()) safely, never None.
    """
    poss = mt5.positions_get()
    if poss is None:
        return []
    return list(poss)


def _pip_size(symbol: str) -> float:
    """
    Naive pip size guesser.
    For majors like EURUSD, 1 pip = 0.0001.
    Upgrade later if you want per-symbol tick_size logic.
    """
    return 0.0001


def _get_spread_pips(symbol: str) -> float | None:
    """
    Return current spread in pips for symbol, or None if quote missing.
    """
    tick = mt5.symbol_info_tick(symbol)
    if tick is None:
        return None
    pip = _pip_size(symbol)
    spread_raw = tick.ask - tick.bid
    if spread_raw is None:
        return None
    return spread_raw / pip

# -------------------------------------------------
# global live/kill / allowlist / nonce safety
# -------------------------------------------------
def _live_switch_allows_trading() -> bool:
    """
    Global kill switch.
    Reads ai_lab/live_switch.json.
    Expected:
        { "allow_live": true }
    If file missing, malformed, or allow_live != True -> block.
    """
    try:
        with open(LIVE_SWITCH_PATH, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except FileNotFoundError:
        return False
    except Exception:
        return False
    return bool(data.get("allow_live") is True)


def _set_live_switch(allow: bool):
    """
    NEW:
    Circuit-breaker latch.
    We will force allow_live:false if we breach quality or risk.
    """
    os.makedirs("ai_lab", exist_ok=True)
    data = {"allow_live": bool(allow)}
    with open(LIVE_SWITCH_PATH, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
    print(f"[bridge_mt5] live_switch set to allow_live={allow}")


def _is_symbol_allowed(contract: dict) -> tuple[bool, str | None]:
    """
    Per-ticket guard.
    - symbol must be whitelisted
    - side must be allowed for that symbol
    - size must be <= max_lots for that symbol (and global MAX_LOTS)
    Returns (ok, reason_if_not_ok)
    """
    symbol = str(contract.get("symbol", "")).upper()
    side = str(contract.get("side", "")).upper()
    lots = float(contract.get("size", 0.0))

    spec = ALLOWED_SYMBOLS.get(symbol)
    if spec is None:
        return False, f"SYMBOL_NOT_ALLOWED:{symbol}"

    if side not in spec["sides"]:
        return False, f"SIDE_NOT_ALLOWED:{symbol}:{side}"

    max_lots_allowed = min(spec["max_lots"], MAX_LOTS)
    if lots > max_lots_allowed:
        return False, f"SIZE_TOO_BIG:{lots}>{max_lots_allowed}"

    return True, None


def _nonce_already_filled(nonce: str) -> bool:
    """
    Anti-replay:
    Return True if this ticket_nonce already appears in a FILL row
    in journal.ndjson.

    journal.ndjson can contain:
      • valid JSON dict rows
      • operator banners, blank lines, etc.  <-- ignore
    """
    if not os.path.exists(JOURNAL_PATH):
        return False
    with open(JOURNAL_PATH, "r", encoding="utf-8") as fh:
        for raw_line in fh:
            raw_line = raw_line.strip()
            if not raw_line:
                continue
            try:
                row = json.loads(raw_line)
            except Exception:
                continue
            if not isinstance(row, dict):
                continue
            if row.get("type") == "FILL":
                fill = row.get("fill", {})
                if isinstance(fill, dict):
                    if fill.get("ticket_nonce") == nonce:
                        return True
    return False

# -------------------------------------------------
# INTENT creation helper (manual stub for now)
# -------------------------------------------------
def make_execution_stub_intent():
    """
    Helper for manual testing without PowerShell.
    Writes artifacts/live/next_order.json and logs INTENT to journal.
    """
    now_iso = _now_utc_iso()
    contract = {
        "as_of": now_iso,
        "ticket_nonce": now_iso,
        "symbol": "EURUSD",
        "side": "BUY",
        "size": 0.35,
        "accept": True,
        "sl_pips": 15,
        "tp_pips": 30,
        "time_stop_bars": 90,
        "expected_value": 0.012,
        "reasons": ["manual_stub", "risk_ok"],
    }

    os.makedirs(ART_DIR, exist_ok=True)
    with open(NEXT_ORDER_PATH, "w", encoding="utf-8") as fh:
        json.dump(contract, fh, ensure_ascii=False, indent=2)

    intent_row = {
        "ts": contract["as_of"],
        "type": "INTENT",
        "contract": contract,
    }
    _append_ndjson(intent_row)
    return contract

# -------------------------------------------------
# Order send helpers
# -------------------------------------------------
def _calc_sltp_prices(
    symbol: str,
    side: str,
    entry_price: float,
    sl_pips: float,
    tp_pips: float,
):
    """
    Convert sl/tp distances in pips into absolute price levels
    based on the direction of the trade.
    """
    pip = _pip_size(symbol)
    if side.upper() == "BUY":
        sl_price = entry_price - sl_pips * pip
        tp_price = entry_price + tp_pips * pip
    else:  # SELL
        sl_price = entry_price + sl_pips * pip
        tp_price = entry_price - tp_pips * pip
    return sl_price, tp_price


def _send_market_order(contract: dict) -> dict:
    """
    Send a market order using MT5, attach SL/TP, return fill_info.
    """
    _ensure_mt5()

    symbol = contract["symbol"]
    side = contract["side"].upper()
    lots = float(contract["size"])

    if not mt5.symbol_select(symbol, True):
        raise RuntimeError(f"symbol_select failed for {symbol}")

    if side == "BUY":
        order_type = mt5.ORDER_TYPE_BUY
    elif side == "SELL":
        order_type = mt5.ORDER_TYPE_SELL
    else:
        raise RuntimeError(f"invalid side {side}")

    # snapshot before send
    tick_pre = mt5.symbol_info_tick(symbol)
    if tick_pre is None:
        raise RuntimeError(f"no tick for {symbol}")

    req_price = tick_pre.ask if side == "BUY" else tick_pre.bid
    pre_spread_pips = _get_spread_pips(symbol)

    req = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": lots,
        "type": order_type,
        "price": req_price,
        "deviation": 50,
        "type_filling": mt5.ORDER_FILLING_IOC,
        "comment": contract.get("ticket_nonce", "manual"),
    }

    t0 = time.time()
    result = mt5.order_send(req)
    t1 = time.time()

    if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
        # interpret common safe refusal
        comment = getattr(result, "comment", "")
        if "Market closed" in str(comment):
            # soft abort path: no position was opened
            raise RuntimeError("SOFT_ABORT_MARKET_CLOSED")
        raise RuntimeError(
            f"order_send failed ret={getattr(result,'retcode',None)} rsp={result}"
        )
    exec_ticket = result.order
    exec_price = result.price
    latency_s = t1 - t0

    # slippage calc (pips)
    pip = _pip_size(symbol)
    if side == "BUY":
        slip_pips = (exec_price - req_price) / pip
    else:
        slip_pips = (req_price - exec_price) / pip

    # attach SL/TP
    sl_pips = float(contract["sl_pips"])
    tp_pips = float(contract["tp_pips"])
    sl_price, tp_price = _calc_sltp_prices(symbol, side, exec_price, sl_pips, tp_pips)

    modify_req = {
        "action": mt5.TRADE_ACTION_SLTP,
        "position": exec_ticket,
        "sl": sl_price,
        "tp": tp_price,
        "comment": f"SET-SLTP-{exec_ticket}",
    }
    result2 = mt5.order_send(modify_req)
    sltp_ok = (result2 is not None and result2.retcode == mt5.TRADE_RETCODE_DONE)

    post_spread_pips = _get_spread_pips(symbol)

    fill_info = {
        "as_of": _now_utc_iso(),
        "symbol": symbol,
        "side": side,
        "size_exec": lots,
        "price_exec": exec_price,
        "ticket_id": exec_ticket,
        "ticket_nonce": contract.get("ticket_nonce"),
        "latency_sec": latency_s,
        "slippage_pips": slip_pips,
        "sl_price": sl_price,
        "tp_price": tp_price,
        "sltp_attached": sltp_ok,
        "spread_pips_pre": pre_spread_pips,
        "spread_pips_post": post_spread_pips,
    }

    print(
        "[bridge_mt5] FILL logged.",
        "nonce=", contract.get("ticket_nonce"),
        "ticket=", exec_ticket,
        "px=", exec_price,
        "lots=", lots,
        "spread_pre=", pre_spread_pips,
        "spread_post=", post_spread_pips,
        "slip_pips=", fill_info["slippage_pips"],
        "lat_s=", latency_s,
        "sltp_attached=", sltp_ok,
    )
    return fill_info

# -------------------------------------------------
# Breach / flatten helpers
# -------------------------------------------------
def _close_position_direct(pos):
    """
    Close a single hedge position by referencing its ticket.
    """
    symbol = pos.symbol
    lots = pos.volume
    is_buy = (pos.type == mt5.POSITION_TYPE_BUY)
    pos_side = "BUY" if is_buy else "SELL"

    req = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "position": pos.ticket,   # CRITICAL for hedge accounts
        "volume": lots,
        "type": mt5.ORDER_TYPE_SELL if is_buy else mt5.ORDER_TYPE_BUY,
        "deviation": 50,
        "type_filling": mt5.ORDER_FILLING_IOC,
        "comment": f"CLOSE-{pos.ticket}",
    }

    result = mt5.order_send(req)
    if result and result.retcode == mt5.TRADE_RETCODE_DONE:
        print(
            f"[bridge_mt5] CLOSED_DIRECT {pos_side} "
            f"ticket={pos.ticket} -> close_ticket={result.order} "
            f"vol={result.volume} px={result.price}"
        )
        return {
            "symbol": symbol,
            "side": f"CLOSE_{pos_side}",
            "size_exec": result.volume,
            "price_exec": result.price,
            "ticket_id": result.order,
            "ticket_nonce": f"CLOSE-{pos.ticket}",
            "latency_sec": None,
            "slippage_pips": None,
        }

    print(
        f"[bridge_mt5] CLOSE_DIRECT FAILED "
        f"ticket={pos.ticket} ({pos_side} {lots} {symbol}) "
        f"retcode={getattr(result,'retcode',None)}"
    )
    return None


def _pair_positions_by_symbol(positions):
    """
    Build {symbol: {"BUY":[pos,...], "SELL":[pos,...]}}
    """
    book = {}
    for p in positions:
        sym = p.symbol
        side = "BUY" if p.type == mt5.POSITION_TYPE_BUY else "SELL"
        book.setdefault(sym, {}).setdefault(side, []).append(p)
    return book


def _close_by_pairs(book):
    """
    For any symbol with at least one BUY and one SELL still open,
    attempt CLOSE_BY to nuke matched hedge pairs.
    Returns list of fill dicts.
    """
    closed = []
    for sym, sides in book.items():
        buys = sides.get("BUY", [])
        sells = sides.get("SELL", [])
        while buys and sells:
            bpos = buys.pop()
            spos = sells.pop()
            req = {
                "action": mt5.TRADE_ACTION_CLOSE_BY,
                "position": bpos.ticket,
                "position_by": spos.ticket,
                "comment": f"CLOSE_BY-{bpos.ticket}-{spos.ticket}",
            }
            result = mt5.order_send(req)
            if result and result.retcode == mt5.TRADE_RETCODE_DONE:
                print(
                    f"[bridge_mt5] CLOSED_BY BUY({bpos.ticket}) vs SELL({spos.ticket}) "
                    f"-> close_ticket={result.order} px={result.price}"
                )
                closed.append(
                    {
                        "symbol": sym,
                        "side": "CLOSE_BY",
                        "size_exec": None,
                        "price_exec": result.price,
                        "ticket_id": result.order,
                        "ticket_nonce": f"CLOSE_BY-{bpos.ticket}-{spos.ticket}",
                        "latency_sec": None,
                        "slippage_pips": None,
                    }
                )
            else:
                print(
                    f"[bridge_mt5] CLOSE_BY FAILED "
                    f"buy_ticket={bpos.ticket} sell_ticket={spos.ticket} "
                    f"retcode={getattr(result,'retcode',None)}"
                )
    return closed


def _close_all_positions_breach(breach_reason: str):
    """
    HARD KILL in hedge mode with 2 phases:
    1. CLOSE_DIRECT each open position.
    2. CLOSE_BY any remaining opposite-side pairs.
    """
    positions = _get_positions_snapshot()
    closed_fills = []
    for pos in positions:
        fill_info = _close_position_direct(pos)
        if fill_info:
            closed_fills.append(fill_info)

    leftovers = _get_positions_snapshot()
    if leftovers:
        book = _pair_positions_by_symbol(leftovers)
        closed_by_list = _close_by_pairs(book)
        closed_fills.extend(closed_by_list)

    breach_row = {
        "ts": _now_utc_iso(),
        "type": "BREACH",
        "breach": {
            "reason": breach_reason,
            "fills": closed_fills,
        },
    }
    return breach_row, len(closed_fills)


def _breach_and_flatten(breach_reason: str):
    """
    Immediately flatten everything, then log BREACH.
    Also latch kill switch OFF.
    """
    _ensure_mt5()
    breach_row, n_closed = _close_all_positions_breach(breach_reason)
    _append_ndjson(breach_row)
    print(
        f"[bridge_mt5] FLATTEN COMPLETE. closed positions: {n_closed} "
        f"(breach_reason={breach_reason})\n"
    )
    # kill further trading until operator intervenes
    _set_live_switch(False)

# -------------------------------------------------
# Public entrypoint
# -------------------------------------------------
def fire_next_order():
    """
    Load NEXT_ORDER_PATH, run safety gates, maybe send to MT5,
    and enforce execution quality. Auto-flatten on breach.
    NEW LAYERS ADDED:
    - session/time embargo check via _safe_session_ok_now()
    - risk governor check via _safe_risk_can_trade()
    - kill switch latch OFF if risk governor rejects or any breaker fires
    """
    # 1. global kill switch
    if not _live_switch_allows_trading():
        print("[bridge_mt5] ABORT: global kill switch (LIVE_SWITCH_BLOCKED)")
        return

    # 1.5 session / embargo window
    if not _safe_session_ok_now():
        print("[bridge_mt5] ABORT: session/time window not allowed (SESSION_BLOCK)")
        return

    # 1.6 risk governor (DD / exposure / etc.)
    rg_ok, rg_reason = _safe_risk_can_trade()
    if not rg_ok:
        print(f"[bridge_mt5] ABORT: risk governor block ({rg_reason}) -> RISK_BLOCK")
        # hard stop trading until operator resets
        _set_live_switch(False)
        return

    _ensure_mt5()

    # 2. staged ticket present?
    if not os.path.exists(NEXT_ORDER_PATH):
        raise RuntimeError(f"missing {NEXT_ORDER_PATH}, run LiveGuard first")

    with open(NEXT_ORDER_PATH, "r", encoding="utf-8") as fh:
        contract = json.load(fh)

    # 3. accept flag
    if not contract.get("accept", False):
        print("[bridge_mt5] ABORT: contract.accept == False (CONTRACT_NOT_ACCEPTED)")
        return

    # 4. anti-replay (nonce already fired?)
    nonce = str(contract.get("ticket_nonce", ""))
    if nonce and _nonce_already_filled(nonce):
        print(f"[bridge_mt5] ABORT: nonce {nonce} already filled (REPLAY_BLOCKED)")
        return

    # 5. per-ticket whitelist / sizing
    ok, reason = _is_symbol_allowed(contract)
    if not ok:
        print(f"[bridge_mt5] ABORT: {reason} -> flatten safeguard trip (NOT_ALLOWED)")
        _breach_and_flatten("NOT_ALLOWED")
        return

    symbol = contract["symbol"]

    # 6. Pre-trade spread safety
    spread_now = _get_spread_pips(symbol)
    if spread_now is None:
        print("[bridge_mt5] ABORT: cannot read spread, flattening (SPREAD_UNKNOWN)")
        _breach_and_flatten("SPREAD_UNKNOWN")
        return

    if spread_now > MAX_SPREAD_PIPS:
        print(
            f"[bridge_mt5] ABORT: spread {spread_now} pips > "
            f"{MAX_SPREAD_PIPS}, flattening (SPREAD_TOO_WIDE)"
        )
        _breach_and_flatten("SPREAD_TOO_WIDE")
        return

    # 7. Send order
    fill_info = _send_market_order(contract)

    # 8. Append FILL row
    fill_row = {
        "ts": fill_info["as_of"],
        "type": "FILL",
        "fill": fill_info,
    }
    _append_ndjson(fill_row)

    # 9. Post-fill quality enforcement
    if fill_info["latency_sec"] > MAX_LATENCY_SEC:
        print("[bridge_mt5] EXECUTION QUALITY BREACH: LATENCY_TOO_HIGH -> flatten")
        _breach_and_flatten("LATENCY_TOO_HIGH")
        return

    if abs(fill_info["slippage_pips"]) > MAX_SLIPPAGE_PIPS:
        print("[bridge_mt5] EXECUTION QUALITY BREACH: SLIPPAGE_TOO_HIGH -> flatten")
        _breach_and_flatten("SLIPPAGE_TOO_HIGH")
        return

    spread_post = fill_info.get("spread_pips_post")
    if (spread_post is not None) and (spread_post > MAX_SPREAD_PIPS):
        print("[bridge_mt5] EXECUTION QUALITY BREACH: SPREAD_TOO_WIDE_POST -> flatten")
        _breach_and_flatten("SPREAD_TOO_WIDE_POST")
        return

    # 10. If we got here, trade stays open with SL/TP.
    return fill_info


def emergency_flatten(breach_reason: str = "MANUAL_FLATTEN"):
    """
    Public 'panic button'. Closes all open positions and logs BREACH.
    Also kills future trading until operator explicitly re-enables.
    """
    _breach_and_flatten(breach_reason)
    # _breach_and_flatten already flips allow_live:false via _set_live_switch(False)