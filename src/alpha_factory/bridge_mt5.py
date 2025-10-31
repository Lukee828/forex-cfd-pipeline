import os
import time
import json
from datetime import datetime, timezone

import MetaTrader5 as mt5

ART_DIR = os.path.join("artifacts", "live")
NEXT_ORDER_PATH = os.path.join(ART_DIR, "next_order.json")
JOURNAL_PATH = os.path.join(ART_DIR, "journal.ndjson")


# -------------------------------------------------
# low-level utils
# -------------------------------------------------

def _now_utc_iso():
    # always Zulu for clarity
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
    import MetaTrader5 as mt5  # local import just in case

    # initialize() returns False if it's already initialized.
    mt5.initialize()

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


# -------------------------------------------------
# INTENT creation helper (ExecutionStub equivalent)
# -------------------------------------------------

def make_execution_stub_intent():
    """
    This is basically what LiveGuard.ps1 was simulating:
    decide on a dummy contract to trade and log it.
    We keep it extremely dumb here (manual_stub BUY EURUSD 0.35).
    """
    now_iso = _now_utc_iso()
    contract = {
        "as_of": now_iso,
        "ticket_nonce": now_iso,     # unique per ticket
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

    # log INTENT row into journal
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

def _calc_sltp_prices(symbol: str, side: str, entry_price: float,
                      sl_pips: float, tp_pips: float):
    """
    Convert sl/tp distances in pips into absolute price levels
    based on the direction of the trade.
    We'll assume pip = 0.0001 for FX majors like EURUSD.
    If you need per-symbol pip size, upgrade this later.
    """
    pip = 0.0001
    if side.upper() == "BUY":
        sl_price = entry_price - sl_pips * pip
        tp_price = entry_price + tp_pips * pip
    else:  # SELL
        sl_price = entry_price + sl_pips * pip
        tp_price = entry_price - tp_pips * pip
    return sl_price, tp_price


def _send_market_order(contract: dict):
    """
    Send a market order using MT5.
    contract keys:
      symbol, side ("BUY"/"SELL"), size, sl_pips, tp_pips
    1) request deal
    2) attach SL/TP
    3) return fill_info dict for logging
    """
    _ensure_mt5()

    symbol = contract["symbol"]
    side = contract["side"].upper()
    lots = float(contract["size"])

    # ensure symbol is selected
    if not mt5.symbol_select(symbol, True):
        raise RuntimeError(f"symbol_select failed for {symbol}")

    # figure out order type
    if side == "BUY":
        order_type = mt5.ORDER_TYPE_BUY
    elif side == "SELL":
        order_type = mt5.ORDER_TYPE_SELL
    else:
        raise RuntimeError(f"invalid side {side}")

    # current price
    tick = mt5.symbol_info_tick(symbol)
    if tick is None:
        raise RuntimeError(f"no tick for {symbol}")

    price = tick.ask if side == "BUY" else tick.bid

    req = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": lots,
        "type": order_type,
        "price": price,
        "deviation": 50,
        "type_filling": mt5.ORDER_FILLING_IOC,
        "comment": contract.get("ticket_nonce", "manual"),
    }

    t0 = time.time()
    result = mt5.order_send(req)
    t1 = time.time()

    if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
        raise RuntimeError(f"order_send failed ret={getattr(result,'retcode',None)} rsp={result}")

    exec_ticket = result.order
    exec_price = result.price
    latency_s = t1 - t0

    # Attach SL/TP if requested
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

    # build the row we log
    fill_info = {
        "as_of": _now_utc_iso(),
        "symbol": symbol,
        "side": side,
        "size_exec": lots,
        "price_exec": exec_price,
        "ticket_id": exec_ticket,
        "ticket_nonce": contract.get("ticket_nonce"),
        "latency_sec": latency_s,
        "slippage_pips": 0.0,  # TODO: compute from requested vs filled
        "sl_price": sl_price,
        "tp_price": tp_price,
        "sltp_attached": sltp_ok,
    }

    print(
        "[bridge_mt5] FILL logged. nonce=", contract.get("ticket_nonce"),
        "ticket=", exec_ticket,
        "px=", exec_price,
        "lots=", lots,
        "slip_pips=", fill_info["slippage_pips"],
        "lat_s=", latency_s,
        "sltp_attached=", sltp_ok,
    )

    return fill_info


def fire_next_order():
    """
    Load NEXT_ORDER_PATH, actually send it to MT5,
    log FILL row to journal.ndjson.
    """
    _ensure_mt5()

    if not os.path.exists(NEXT_ORDER_PATH):
        raise RuntimeError(f"missing {NEXT_ORDER_PATH}, run LiveGuard first")

    with open(NEXT_ORDER_PATH, "r", encoding="utf-8") as fh:
        contract = json.load(fh)

    # sanity
    if not contract.get("accept", False):
        raise RuntimeError("contract.accept is False, refusing to trade")

    fill_info = _send_market_order(contract)

    # append FILL row
    fill_row = {
        "ts": fill_info["as_of"],
        "type": "FILL",
        "fill": fill_info,
    }
    _append_ndjson(fill_row)

    # done
    return fill_info


# -------------------------------------------------
# Hedge-safe flatten logic
# -------------------------------------------------

def _close_position_direct(pos):
    """
    Attempt direct close of a single hedge position by referencing its ticket.
    Returns dict(fill_info) on success, or None if failed.
    """
    symbol = pos.symbol
    lots = pos.volume
    is_buy = (pos.type == mt5.POSITION_TYPE_BUY)
    pos_side = "BUY" if is_buy else "SELL"

    req = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "position": pos.ticket,  # <-- CRITICAL for hedge accounts
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


def _close_all_positions_breach():
    """
    HARD KILL in hedge mode with 2 phases:
    1. Try direct close for every open ticket (position field).
    2. Re-snapshot; if BUY/SELL leftovers for same symbol, use CLOSE_BY pairs.
    """
    # phase 1: direct close
    positions = _get_positions_snapshot()
    closed_fills = []
    for pos in positions:
        fill_info = _close_position_direct(pos)
        if fill_info:
            closed_fills.append(fill_info)

    # phase 2: close_by for any leftovers
    leftovers = _get_positions_snapshot()
    if leftovers:
        book = _pair_positions_by_symbol(leftovers)
        closed_by_list = _close_by_pairs(book)
        closed_fills.extend(closed_by_list)

    breach_row = {
        "ts": _now_utc_iso(),
        "type": "BREACH",
        "breach": {
            "reason": "MANUAL_FLATTEN",
            "fills": closed_fills,
        },
    }
    return breach_row, len(closed_fills)


def emergency_flatten():
    """
    Public entry point used by Flatten-All.ps1.
    After this there should be 0 positions in MT5.
    Logs BREACH row (all closes).
    """
    _ensure_mt5()
    breach_row, n_closed = _close_all_positions_breach()
    _append_ndjson(breach_row)
    print(f"[bridge_mt5] FLATTEN COMPLETE. closed positions: {n_closed}\n")