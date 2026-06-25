"""
core/charges.py
===============
Calculates all brokerage and statutory charges for every trade.
Based on AngelOne standard rates (verify monthly).
"""

from core.angelone import get_current_brokerage_rates


def calculate_charges(
    instrument: str,
    exchange: str,
    buy_value: float,
    sell_value: float,
    premium_turnover: float = 0.0,
) -> dict:
    """
    Calculate complete charge breakdown for one round trip.

    Args:
        instrument:       CASH / FUT / OPT
        exchange:         NSE / BSE / MCX
        buy_value:        Total buy side value (price × qty)
        sell_value:       Total sell side value (price × qty)
        premium_turnover: For OPT only — total premium value traded

    Returns dict with full breakdown and total.
    """
    r  = get_current_brokerage_rates()
    c  = {}
    instrument = instrument.upper()
    exchange   = exchange.upper()

    if instrument == "CASH":
        turnover           = buy_value + sell_value
        c["brokerage"]     = 0.0
        c["stt"]           = round((buy_value * r["CASH_STT_BUY"]) +
                                    (sell_value * r["CASH_STT_SELL"]), 2)
        c["exchange_charges"] = round(turnover * r["NSE_CASH_ETC"], 2)
        c["sebi_charges"]  = round(turnover / 10_000_000 * r["SEBI_PER_CRORE"], 2)
        c["gst"]           = round((c["brokerage"] + c["exchange_charges"]) * r["GST_RATE"], 2)
        c["stamp_duty"]    = round(buy_value * r["CASH_STAMP_DUTY_BUY"], 2)

    elif instrument == "FUT":
        turnover           = buy_value + sell_value
        c["brokerage"]     = r["FUT_BROKERAGE_PER_ORDER"] * 2   # entry + exit
        c["stt"]           = round(sell_value * r["FUT_STT_SELL"], 2)
        c["exchange_charges"] = round(turnover * r["NSE_FUT_ETC"], 2)
        c["sebi_charges"]  = round(turnover / 10_000_000 * r["SEBI_PER_CRORE"], 2)
        c["gst"]           = round((c["brokerage"] + c["exchange_charges"]) * r["GST_RATE"], 2)
        c["stamp_duty"]    = round(buy_value * r["FUT_STAMP_DUTY_BUY"], 2)

    elif instrument == "OPT":
        # For options, turnover = premium turnover
        pt                 = premium_turnover or (buy_value + sell_value)
        c["brokerage"]     = r["OPT_BROKERAGE_PER_ORDER"] * 2
        c["stt"]           = round(sell_value * r["OPT_STT_SELL"], 2)
        c["exchange_charges"] = round(pt * r["NSE_OPT_ETC"], 2)
        c["sebi_charges"]  = round(pt / 10_000_000 * r["SEBI_PER_CRORE"], 2)
        c["gst"]           = round((c["brokerage"] + c["exchange_charges"]) * r["GST_RATE"], 2)
        c["stamp_duty"]    = round(buy_value * r["OPT_STAMP_DUTY_BUY"], 2)

    elif exchange == "MCX":
        turnover           = buy_value + sell_value
        c["brokerage"]     = r["MCX_BROKERAGE_PER_ORDER"] * 2
        c["stt"]           = 0.0   # No STT on MCX
        c["exchange_charges"] = round(turnover * r["MCX_FUT_ETC"], 2)
        c["sebi_charges"]  = round(turnover / 10_000_000 * r["SEBI_PER_CRORE"], 2)
        c["gst"]           = round((c["brokerage"] + c["exchange_charges"]) * r["GST_RATE"], 2)
        c["stamp_duty"]    = round(buy_value * r["MCX_STAMP_DUTY_BUY"], 2)

    else:
        # Unknown instrument — zero charges (safe fallback)
        c = {k: 0.0 for k in
             ["brokerage","stt","exchange_charges","sebi_charges","gst","stamp_duty"]}

    c["total_charges"] = round(
        c["brokerage"] + c["stt"] + c["exchange_charges"] +
        c["sebi_charges"] + c["gst"] + c["stamp_duty"], 2
    )
    return c


def net_pnl(gross_pnl: float, charges: dict) -> float:
    """Net P&L after all charges."""
    return round(gross_pnl - charges.get("total_charges", 0), 2)


def roi_pct(net: float, capital: float) -> float:
    """ROI as a percentage of strategy capital."""
    if not capital or capital == 0:
        return 0.0
    return round((net / capital) * 100, 4)


def format_charges_breakdown(charges: dict) -> str:
    """Human-readable charge breakdown string."""
    lines = [
        f"Brokerage      : ₹{charges.get('brokerage', 0):,.2f}",
        f"STT            : ₹{charges.get('stt', 0):,.2f}",
        f"Exchange Chgs  : ₹{charges.get('exchange_charges', 0):,.2f}",
        f"SEBI Charges   : ₹{charges.get('sebi_charges', 0):,.2f}",
        f"GST            : ₹{charges.get('gst', 0):,.2f}",
        f"Stamp Duty     : ₹{charges.get('stamp_duty', 0):,.2f}",
        f"──────────────────────────────",
        f"Total Charges  : ₹{charges.get('total_charges', 0):,.2f}",
    ]
    return "\n".join(lines)
