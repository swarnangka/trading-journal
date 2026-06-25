"""
core/angelone.py
================
AngelOne SmartAPI wrapper.
Handles: auto-login, LTP fetch, historical price, SPAN margin.
All calls minimised — only fetched when needed.
"""

import streamlit as st
import pyotp
from datetime import datetime, timedelta
import pytz
import time

IST = pytz.timezone("Asia/Kolkata")

# ── AUTO LOGIN ────────────────────────────────────────────────

@st.cache_resource(ttl=3600)
def get_angel_obj():
    """
    Login to AngelOne using secrets. Cached for 1 hour.
    Returns SmartConnect object or None on failure.
    """
    try:
        from SmartApi import SmartConnect
        cfg   = st.secrets["angelone"]
        totp  = pyotp.TOTP(cfg["totp_secret"]).now()
        obj   = SmartConnect(api_key=cfg["api_key"])
        resp  = obj.generateSession(cfg["client_id"], cfg["password"], totp)
        if resp and resp.get("status"):
            return obj
        st.warning("⚠️ AngelOne login failed — prices unavailable")
        return None
    except Exception as e:
        st.warning(f"⚠️ AngelOne connection error: {e}")
        return None


def _col_letter_to_num(letter: str) -> int:
    """Convert column letter to number. Not needed here but kept for reference."""
    result = 0
    for c in letter.upper():
        result = result * 26 + (ord(c) - ord('A') + 1)
    return result


# ── SYMBOL TOKEN LOOKUP ───────────────────────────────────────

@st.cache_data(ttl=86400)
def get_symbol_token(symbol: str, exchange: str, instrument: str) -> str:
    """
    Get AngelOne symbol token for a given symbol.
    Cached for 24 hours — tokens don't change daily.
    Returns token string or empty string if not found.
    """
    try:
        obj = get_angel_obj()
        if not obj:
            return ""
        # AngelOne searchScrip
        resp = obj.searchScrip(exchange, symbol)
        if resp and resp.get("status") and resp.get("data"):
            for item in resp["data"]:
                # Match by symbol name
                if item.get("tradingsymbol", "").upper().startswith(symbol.upper()):
                    return item.get("symboltoken", "")
        return ""
    except Exception:
        return ""


# ── LIVE LTP — BATCH ─────────────────────────────────────────

def fetch_ltp_batch(positions: list) -> dict:
    """
    Fetch LTP for multiple open positions in one API call.
    positions: list of dicts with keys: symbol, exchange, token
    Returns dict: {symbol_key: ltp_float}
    symbol_key = f"{symbol}_{exchange}"
    """
    obj = get_angel_obj()
    if not obj or not positions:
        return {}

    results = {}

    try:
        # Group by exchange for batch call
        exchange_groups = {}
        for pos in positions:
            exch = pos.get("exchange", "NSE").upper()
            if exch not in exchange_groups:
                exchange_groups[exch] = []
            token = pos.get("token", "")
            if token:
                exchange_groups[exch].append(token)

        for exch, tokens in exchange_groups.items():
            if not tokens:
                continue
            resp = obj.getMarketData("LTP", {exch: tokens})
            if resp and resp.get("status") and resp.get("data"):
                fetched = resp["data"].get("fetched", [])
                for item in fetched:
                    sym = item.get("tradingSymbol", "")
                    ltp = float(item.get("ltp", 0))
                    key = f"{sym}_{exch}"
                    results[key] = ltp

    except Exception as e:
        st.warning(f"LTP fetch error: {e}")

    return results


# ── HISTORICAL PRICE ──────────────────────────────────────────

def fetch_historical_price(
    symbol: str,
    exchange: str,
    token: str,
    trade_datetime: datetime,
) -> tuple:
    """
    Fetch historical price for a specific date and time.
    Returns (price, price_source) tuple.
    price_source: 'HISTORICAL' or 'MANUAL' if fetch fails.
    """
    obj = get_angel_obj()
    if not obj or not token:
        return None, "MANUAL"

    try:
        ist_dt   = trade_datetime.astimezone(IST)
        from_dt  = ist_dt - timedelta(minutes=1)
        to_dt    = ist_dt + timedelta(minutes=2)

        params = {
            "exchange":    exchange.upper(),
            "symboltoken": token,
            "interval":    "ONE_MINUTE",
            "fromdate":    from_dt.strftime("%Y-%m-%d %H:%M"),
            "todate":      to_dt.strftime("%Y-%m-%d %H:%M"),
        }
        resp = obj.getCandleData(params)

        if resp and resp.get("status") and resp.get("data"):
            # data format: [timestamp, open, high, low, close, volume]
            candle = resp["data"][0]
            open_  = float(candle[1])
            close_ = float(candle[4])
            price  = round((open_ + close_) / 2, 2)
            return price, "HISTORICAL"

    except Exception as e:
        pass

    return None, "MANUAL"


def fetch_current_ltp(symbol: str, exchange: str, token: str) -> tuple:
    """
    Fetch current LTP for a single symbol.
    Returns (price, 'LIVE') or (None, 'MANUAL').
    """
    obj = get_angel_obj()
    if not obj or not token:
        return None, "MANUAL"

    try:
        resp = obj.ltpData(exchange.upper(), symbol, token)
        if resp and resp.get("status") and resp.get("data"):
            ltp = float(resp["data"].get("ltp", 0))
            if ltp > 0:
                return ltp, "LIVE"
    except Exception:
        pass

    return None, "MANUAL"


# ── SPAN MARGIN ───────────────────────────────────────────────

def fetch_margin_for_positions(open_positions: list) -> dict:
    """
    Fetch SPAN margin for a list of open positions.
    open_positions: list of dicts with position details
    Returns dict: {position_key: margin_required}
    position_key = f"{symbol}_{strategy}"

    Uses AngelOne getMargin API.
    Called once per dashboard refresh.
    """
    obj = get_angel_obj()
    if not obj or not open_positions:
        return {}

    results  = {}
    requests = []

    for pos in open_positions:
        token = pos.get("token", "")
        if not token:
            continue

        instrument = pos.get("instrument", "CASH").upper()
        if instrument == "CASH":
            # For cash, margin = position value (full amount)
            key = f"{pos.get('symbol')}_{pos.get('strategy')}"
            price = pos.get("avg_entry_price", 0) or 0
            qty   = pos.get("quantity", 0) or 0
            results[key] = round(float(price) * float(qty), 2)
            continue

        requests.append({
            "exchange":    pos.get("exchange", "NSE").upper(),
            "tradingsymbol": pos.get("trading_symbol", pos.get("symbol")),
            "symboltoken": token,
            "producttype": "CARRYFORWARD",
            "transactiontype": "BUY",
            "quantity":    str(int(pos.get("quantity", 0))),
            "price":       str(pos.get("avg_entry_price", 0)),
            "tradedsquareoff": "0",
        })

    if requests:
        try:
            resp = obj.getMargin({"orders": requests})
            if resp and resp.get("status") and resp.get("data"):
                data = resp["data"]
                total_margin = float(data.get("charges", {}).get("total", 0))
                # Distribute proportionally if batch
                # For simplicity store total; individual breakdown done in positions.py
                results["_total_required"] = total_margin
        except Exception as e:
            pass

    return results


# ── BROKERAGE RATE CHECK ──────────────────────────────────────

def get_current_brokerage_rates() -> dict:
    """
    Returns current AngelOne brokerage rates.
    Update this monthly if rates change.
    Last verified: Jun 2025
    Source: angelone.in/charges
    """
    return {
        "CASH_DELIVERY_BROKERAGE":  0.00,       # Free delivery
        "FUT_BROKERAGE_PER_ORDER":  20.00,       # ₹20 flat
        "OPT_BROKERAGE_PER_ORDER":  20.00,       # ₹20 flat
        "MCX_BROKERAGE_PER_ORDER":  20.00,       # ₹20 flat

        # STT rates
        "CASH_STT_BUY":             0.001,       # 0.1% delivery
        "CASH_STT_SELL":            0.001,       # 0.1% delivery
        "FUT_STT_SELL":             0.0002,      # 0.02% sell side only
        "OPT_STT_SELL":             0.001,       # 0.1% on premium sell side

        # Exchange transaction charges (NSE)
        "NSE_CASH_ETC":             0.0000345,   # 0.00345%
        "NSE_FUT_ETC":              0.000019,    # 0.0019%
        "NSE_OPT_ETC":              0.000495,    # 0.0495% on premium
        "MCX_FUT_ETC":              0.000026,    # 0.0026%

        # Other charges
        "SEBI_PER_CRORE":           10.00,       # ₹10 per crore
        "GST_RATE":                 0.18,        # 18% on brokerage + ETC
        "CASH_STAMP_DUTY_BUY":      0.00015,     # 0.015% on buy
        "FUT_STAMP_DUTY_BUY":       0.00002,     # 0.002% on buy
        "OPT_STAMP_DUTY_BUY":       0.00003,     # 0.003% on buy
        "MCX_STAMP_DUTY_BUY":       0.00002,     # 0.002% on buy

        "last_verified": "Jun-2025",
    }
