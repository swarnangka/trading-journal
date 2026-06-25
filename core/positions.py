"""
core/positions.py
=================
Core position calculation engine.

Reads raw TRADES rows and produces:
  - Open positions (net long/short with avg price)
  - Closed positions (auto-detected, written to CLOSED_TRADES)

Key rule:
  Position key = strategy + symbol + instrument + expiry + strike + option_type
  Net qty = sum(BUY qty) - sum(SELL qty)
  Net = 0 → closed. Net > 0 → long. Net < 0 → short.
"""

import pandas as pd
import numpy as np
from datetime import datetime, date
import uuid
import pytz

from core.charges import calculate_charges, net_pnl, roi_pct
from core.sheets  import (
    read_trades, read_closed_trades, append_closed_trade,
    closed_trade_exists, get_strategy_capital
)

IST = pytz.timezone("Asia/Kolkata")


def _position_key(row) -> str:
    """Unique key per position group."""
    parts = [
        str(row.get("strategy",    "")),
        str(row.get("symbol",      "")),
        str(row.get("instrument",  "")),
        str(row.get("expiry",      "")),
        str(row.get("strike",      "")),
        str(row.get("option_type", "")),
    ]
    return "|".join(parts)


def _safe_float(val, default=0.0) -> float:
    try:
        return float(str(val).replace(",", "")) if val != "" else default
    except (ValueError, TypeError):
        return default


def _safe_int(val, default=0) -> int:
    try:
        return int(float(str(val).replace(",", ""))) if val != "" else default
    except (ValueError, TypeError):
        return default


def compute_positions() -> tuple:
    """
    Main function. Reads all trades, computes open and closed positions.

    Returns:
        (open_positions, newly_closed) where:
        open_positions: list of dicts (one per open position group)
        newly_closed:   list of dicts (positions just detected as closed,
                        written to CLOSED_TRADES tab)
    """
    df = read_trades()
    if df.empty:
        return [], []

    # Ensure numeric columns are clean
    for col in ["lots_qty", "quantity", "price", "lot_size"]:
        if col in df.columns:
            df[col] = df[col].apply(_safe_float)

    # Parse trade date
    if "trade_date" in df.columns:
        df["trade_date_parsed"] = pd.to_datetime(
            df["trade_date"], dayfirst=True, errors="coerce"
        )

    # Get existing closed trade keys to avoid re-processing
    closed_df    = read_closed_trades()
    existing_ids = set()
    if not closed_df.empty and "linked_trade_ids" in closed_df.columns:
        for ids_str in closed_df["linked_trade_ids"].dropna():
            for tid in str(ids_str).split(","):
                existing_ids.add(tid.strip())

    open_positions  = []
    newly_closed    = []
    capital_map     = get_strategy_capital()

    # Group by position key
    df["_pos_key"] = df.apply(_position_key, axis=1)

    for pos_key, group in df.groupby("_pos_key"):
        group = group.sort_values("trade_date_parsed", na_position="last")

        # Separate BUY and SELL rows
        buys  = group[group["action"].str.upper() == "BUY"]
        sells = group[group["action"].str.upper() == "SELL"]

        total_buy_qty  = buys["quantity"].sum()
        total_sell_qty = sells["quantity"].sum()
        net_qty        = total_buy_qty - total_sell_qty

        # Base metadata from first row in group
        first = group.iloc[0]
        meta  = {
            "strategy":    str(first.get("strategy",    "")),
            "symbol":      str(first.get("symbol",      "")),
            "exchange":    str(first.get("exchange",    "NSE")),
            "instrument":  str(first.get("instrument",  "CASH")),
            "expiry":      str(first.get("expiry",      "")),
            "strike":      str(first.get("strike",      "")),
            "option_type": str(first.get("option_type", "")),
            "lot_size":    _safe_int(first.get("lot_size", 1)),
        }

        # ── POSITION IS CLOSED ─────────────────────────────
        if abs(net_qty) < 0.001:
            trade_ids = ",".join(group["trade_id"].astype(str).tolist())

            # Skip if already written to CLOSED_TRADES
            # Check by seeing if all trade IDs are already accounted for
            all_ids = set(group["trade_id"].astype(str).tolist())
            if all_ids.issubset(existing_ids):
                continue

            # Calculate weighted average entry and exit prices
            avg_entry = _weighted_avg_price(buys)
            avg_exit  = _weighted_avg_price(sells)

            instrument = meta["instrument"].upper()
            buy_val    = avg_entry * total_buy_qty
            sell_val   = avg_exit  * total_sell_qty
            gross      = round((avg_exit - avg_entry) * total_buy_qty, 2)

            # For SELL-first (short) positions
            if total_sell_qty > total_buy_qty:
                gross = round((avg_entry - avg_exit) * total_sell_qty, 2)

            # Charges
            premium_to = 0.0
            if instrument == "OPT":
                premium_to = buy_val + sell_val

            charges = calculate_charges(
                instrument = instrument,
                exchange   = meta["exchange"],
                buy_value  = buy_val,
                sell_value = sell_val,
                premium_turnover = premium_to,
            )
            net    = net_pnl(gross, charges)
            cap    = capital_map.get(meta["strategy"], 0)
            roi    = roi_pct(net, cap)

            # Dates
            open_dt  = group["trade_date_parsed"].min()
            close_dt = group["trade_date_parsed"].max()
            hold     = (close_dt - open_dt).days if pd.notna(open_dt) and pd.notna(close_dt) else 0

            direction = "LONG" if total_buy_qty >= total_sell_qty else "SHORT"
            lots      = _safe_int(group["lots_qty"].sum() / 2)  # total lots each side / 2

            close_row = {
                "close_id":          str(uuid.uuid4())[:8].upper(),
                "strategy":          meta["strategy"],
                "symbol":            meta["symbol"],
                "exchange":          meta["exchange"],
                "instrument":        meta["instrument"],
                "expiry":            meta["expiry"],
                "strike":            meta["strike"],
                "option_type":       meta["option_type"],
                "direction":         direction,
                "open_date":         open_dt.strftime("%d/%m/%Y") if pd.notna(open_dt) else "",
                "close_date":        close_dt.strftime("%d/%m/%Y") if pd.notna(close_dt) else "",
                "hold_days":         hold,
                "quantity":          int(total_buy_qty),
                "lots":              lots,
                "avg_entry_price":   round(avg_entry, 2),
                "avg_exit_price":    round(avg_exit, 2),
                "gross_pnl":         gross,
                "brokerage":         charges["brokerage"],
                "stt":               charges["stt"],
                "exchange_charges":  charges["exchange_charges"],
                "sebi_charges":      charges["sebi_charges"],
                "gst":               charges["gst"],
                "stamp_duty":        charges["stamp_duty"],
                "total_charges":     charges["total_charges"],
                "net_pnl":           net,
                "roi_pct":           roi,
                "close_type":        "FULL",
                "linked_trade_ids":  trade_ids,
            }
            newly_closed.append(close_row)
            append_closed_trade(close_row)
            continue

        # ── POSITION IS OPEN ───────────────────────────────
        # Net qty > 0 means net long (more buys than sells)
        # Net qty < 0 means net short (more sells than buys)

        direction = "LONG" if net_qty > 0 else "SHORT"

        # Avg entry price — weighted, accounting for partial exits
        # For LONG: avg of BUY rows weighted by qty, adjusted for sells already matched
        avg_entry = _weighted_avg_price(buys)

        # Open trade dates
        open_date = group["trade_date_parsed"].min()
        today     = datetime.now(IST).date()
        days_open = (today - open_date.date()).days if pd.notna(open_date) else 0

        # Most recent trade date (for "new trade" badge)
        latest_trade_date = group["trade_date_parsed"].max()
        is_new_today      = (
            pd.notna(latest_trade_date) and
            latest_trade_date.date() == today
        )

        open_positions.append({
            "pos_key":          pos_key,
            "strategy":         meta["strategy"],
            "symbol":           meta["symbol"],
            "exchange":         meta["exchange"],
            "instrument":       meta["instrument"],
            "expiry":           meta["expiry"],
            "strike":           meta["strike"],
            "option_type":      meta["option_type"],
            "direction":        direction,
            "net_qty":          abs(net_qty),
            "lot_size":         meta["lot_size"],
            "lots":             int(abs(net_qty) / meta["lot_size"]) if meta["lot_size"] > 0 else 0,
            "avg_entry_price":  round(avg_entry, 2),
            "days_open":        days_open,
            "open_date":        open_date.strftime("%d/%m/%Y") if pd.notna(open_date) else "",
            "is_new_today":     is_new_today,
            "latest_trade_date": latest_trade_date.strftime("%d/%m/%Y") if pd.notna(latest_trade_date) else "",
            "trade_ids":        ",".join(group["trade_id"].astype(str).tolist()),
            # These filled later by dashboard with live data
            "ltp":              0.0,
            "unrealised_pnl":  0.0,
            "margin_required":  0.0,
            "token":            "",
        })

    return open_positions, newly_closed


def _weighted_avg_price(rows: pd.DataFrame) -> float:
    """Weighted average price from a set of trade rows."""
    if rows.empty:
        return 0.0
    total_value = (rows["price"] * rows["quantity"]).sum()
    total_qty   = rows["quantity"].sum()
    if total_qty == 0:
        return 0.0
    return total_value / total_qty


def calculate_unrealised_pnl(position: dict) -> float:
    """
    Calculate unrealised P&L for an open position.
    position must have: direction, net_qty, avg_entry_price, ltp
    """
    ltp        = _safe_float(position.get("ltp", 0))
    avg_entry  = _safe_float(position.get("avg_entry_price", 0))
    qty        = _safe_float(position.get("net_qty", 0))
    direction  = str(position.get("direction", "LONG")).upper()

    if direction == "LONG":
        return round((ltp - avg_entry) * qty, 2)
    else:
        return round((avg_entry - ltp) * qty, 2)


def get_strategy_summary(closed_df: pd.DataFrame, capital_map: dict,
                          from_date=None, to_date=None) -> list:
    """
    Build strategy performance summary from closed trades.

    Args:
        closed_df:   DataFrame of closed trades
        capital_map: {strategy_name: capital}
        from_date:   Optional date filter start
        to_date:     Optional date filter end

    Returns list of dicts — one per strategy.
    """
    if closed_df.empty:
        return []

    df = closed_df.copy()

    # Parse close_date
    df["close_date_parsed"] = pd.to_datetime(
        df["close_date"], dayfirst=True, errors="coerce"
    )

    # Apply date filters
    if from_date:
        df = df[df["close_date_parsed"] >= pd.Timestamp(from_date)]
    if to_date:
        df = df[df["close_date_parsed"] <= pd.Timestamp(to_date)]

    if df.empty:
        return []

    # Numeric cols
    for col in ["net_pnl", "gross_pnl", "total_charges", "roi_pct"]:
        if col in df.columns:
            df[col] = df[col].apply(_safe_float)

    results = []
    for strategy, grp in df.groupby("strategy"):
        capital     = capital_map.get(strategy, 0)
        total_net   = grp["net_pnl"].sum()
        total_gross = grp["gross_pnl"].sum()
        total_chg   = grp["total_charges"].sum()
        n_trades    = len(grp)
        n_winners   = (grp["net_pnl"] > 0).sum()
        n_losers    = (grp["net_pnl"] < 0).sum()
        win_rate    = (n_winners / n_trades * 100) if n_trades > 0 else 0
        avg_pnl     = grp["net_pnl"].mean()
        best_trade  = grp["net_pnl"].max()
        worst_trade = grp["net_pnl"].min()
        roi         = roi_pct(total_net, capital) if capital > 0 else 0

        # Expectancy
        avg_win  = grp[grp["net_pnl"] > 0]["net_pnl"].mean() if n_winners > 0 else 0
        avg_loss = grp[grp["net_pnl"] < 0]["net_pnl"].mean() if n_losers  > 0 else 0
        wr       = win_rate / 100
        lr       = 1 - wr
        expectancy = round((avg_win * wr) - (abs(avg_loss) * lr), 2) if n_trades > 0 else 0

        # Top 5 best trades
        top_trades = (
            grp.nlargest(5, "net_pnl")
            [["symbol","instrument","open_date","close_date","net_pnl","roi_pct"]]
            .to_dict("records")
        )

        # Equity curve — cumulative P&L sorted by close date
        equity_curve = (
            grp.sort_values("close_date_parsed")[["close_date_parsed", "net_pnl"]]
            .assign(cumulative_pnl=lambda x: x["net_pnl"].cumsum())
            .rename(columns={"close_date_parsed": "date"})
            .to_dict("records")
        )

        results.append({
            "strategy":    strategy,
            "capital":     capital,
            "total_net":   round(total_net, 2),
            "total_gross": round(total_gross, 2),
            "total_chg":   round(total_chg, 2),
            "roi":         round(roi, 2),
            "n_trades":    n_trades,
            "n_winners":   int(n_winners),
            "n_losers":    int(n_losers),
            "win_rate":    round(win_rate, 1),
            "avg_pnl":     round(avg_pnl, 2),
            "best_trade":  round(best_trade, 2),
            "worst_trade": round(worst_trade, 2),
            "expectancy":  expectancy,
            "top_trades":  top_trades,
            "equity_curve": equity_curve,
        })

    return sorted(results, key=lambda x: x["total_net"], reverse=True)
