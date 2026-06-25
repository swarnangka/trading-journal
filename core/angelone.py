"""
core/angelone.py — AngelOne SmartAPI wrapper
Handles: login, LTP fetch, SPAN margin.
Token lookup uses instrument master CSV (downloaded once per session).
"""

import streamlit as st
import pyotp
import requests
import pandas as pd
import io
from datetime import datetime
import pytz

IST = pytz.timezone("Asia/Kolkata")

# ── LOGIN ──────────────────────────────────────────────────────────────────────

@st.cache_resource(ttl=3600)
def get_angel_obj():
    """Login to AngelOne. Cached 1 hour. Returns SmartConnect or None."""
    try:
        from SmartApi import SmartConnect
        cfg     = st.secrets["angelone"]
        # Strip all whitespace and non-printable chars from api_key
        api_key = str(cfg["api_key"]).strip().replace("\xa0","").replace("\u00a0","")
        api_key = "".join(c for c in api_key if c.isprintable() and c != " ")
        totp    = pyotp.TOTP(str(cfg["totp_secret"]).strip()).now()
        obj     = SmartConnect(api_key=api_key)
        resp    = obj.generateSession(
            str(cfg["client_id"]).strip(),
            str(cfg["password"]).strip(),
            totp
        )
        if resp and resp.get("status"):
            return obj
        return None
    except Exception as e:
        return None


# ── INSTRUMENT MASTER ──────────────────────────────────────────────────────────

@st.cache_data(ttl=86400)
def get_instrument_master() -> pd.DataFrame:
    """
    Download NSE F&O instrument master from AngelOne.
    Returns DataFrame with columns: token, symbol, name, expiry, strike, lotsize, instrumenttype, exch_seg
    Cached 24 hours.
    """
    try:
        url  = "https://margincalculator.angelbroking.com/OpenAPI_File/files/OpenAPIScripMaster.json"
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            df   = pd.DataFrame(data)
            # Keep only NSE F&O
            df   = df[df["exch_seg"].isin(["NFO","MCX"])].copy()
            df["token"]  = df["token"].astype(str)
            df["strike"] = pd.to_numeric(df["strike"], errors="coerce").fillna(0)
            return df
    except Exception:
        pass
    return pd.DataFrame()


def find_token(symbol: str, exchange: str, instrument: str, expiry: str = "", strike: float = 0, opt_type: str = "") -> str:
    """
    Find AngelOne token for a given symbol.
    Uses instrument master — no API call per symbol.
    
    For FUT: match symbol + expiry + "FUT" in tradingsymbol
    For OPT: match symbol + expiry + strike + CE/PE
    For CASH: direct NSE equity lookup
    """
    try:
        if instrument == "CASH":
            # For cash equity — simple approach
            obj  = get_angel_obj()
            if not obj: return ""
            resp = obj.searchScrip("NSE", symbol)
            if resp and resp.get("data"):
                for item in resp["data"]:
                    ts = item.get("tradingsymbol","")
                    if ts.upper() == symbol.upper() + "-EQ" or ts.upper() == symbol.upper():
                        return str(item.get("symboltoken",""))
            return ""

        df = get_instrument_master()
        if df.empty: return ""

        # Filter by base symbol
        mask = df["name"].str.upper() == symbol.upper()
        sub  = df[mask]
        if sub.empty:
            # Try symbol column
            mask = df["symbol"].str.upper().str.startswith(symbol.upper())
            sub  = df[mask]
        if sub.empty: return ""

        # Filter by instrument type
        if instrument == "FUT":
            sub = sub[sub["instrumenttype"].str.upper() == "FUTSTK"]
            if sub.empty:
                sub = df[mask][df[mask]["instrumenttype"].str.upper() == "FUTIDX"]
        elif instrument == "OPT":
            sub = sub[sub["instrumenttype"].str.upper().isin(["OPTSTK","OPTIDX"])]
            if opt_type:
                sub = sub[sub["symbol"].str.upper().str.endswith(opt_type.upper())]
            if strike > 0:
                sub = sub[sub["strike"] == strike * 100]  # AngelOne stores strike * 100

        if sub.empty: return ""

        # Match expiry if provided
        if expiry:
            # expiry format from our app: "JUN-26" — AngelOne format: "25JUN2026" or "2026-06-26"
            try:
                exp_dt = datetime.strptime(expiry, "%b-%y")
                exp_month = exp_dt.month
                exp_year  = exp_dt.year
                sub2 = sub[
                    sub["expiry"].str.contains(str(exp_year), na=False) &
                    sub["expiry"].str.upper().str.contains(exp_dt.strftime("%b").upper(), na=False)
                ]
                if not sub2.empty:
                    sub = sub2
            except Exception:
                pass

        # Return token of first match
        return str(sub.iloc[0]["token"])

    except Exception:
        return ""


# ── LTP ────────────────────────────────────────────────────────────────────────

def fetch_current_ltp(symbol: str, exchange: str, token: str) -> tuple:
    """
    Fetch LTP for a single symbol using token.
    Returns (price, "LIVE") or (None, "MANUAL").
    """
    obj = get_angel_obj()
    if not obj: return None, "MANUAL"
    if not token: return None, "MANUAL"
    try:
        # Map exchange to AngelOne segment
        exch_map = {"NSE": "NSE", "BSE": "BSE", "MCX": "MCX", "NFO": "NFO"}
        seg = "NFO" if exchange.upper() in ("NSE","NFO") else exchange.upper()
        resp = obj.ltpData(seg, symbol, token)
        if resp and resp.get("status") and resp.get("data"):
            ltp = float(resp["data"].get("ltp", 0))
            if ltp > 0: return ltp, "LIVE"
    except Exception:
        pass
    return None, "MANUAL"


def get_symbol_token(symbol: str, exchange: str, instrument: str,
                     expiry: str = "", strike: float = 0, opt_type: str = "") -> str:
    """Public wrapper — find token from instrument master."""
    return find_token(symbol, exchange, instrument, expiry, strike, opt_type)


# ── MARGIN ────────────────────────────────────────────────────────────────────

def fetch_margin_for_positions(positions: list) -> dict:
    """
    Fetch SPAN margin for open positions.
    Returns dict with "_total_required" key.
    """
    obj = get_angel_obj()
    if not obj or not positions: return {}
    try:
        orders = []
        for pos in positions:
            token = pos.get("token","")
            instr = pos.get("instrument","FUT").upper()
            if not token or instr == "CASH": continue
            orders.append({
                "exchange":        "NFO" if pos.get("exchange","NSE").upper()=="NSE" else pos.get("exchange","NSE").upper(),
                "tradingsymbol":   pos.get("symbol",""),
                "symboltoken":     token,
                "producttype":     "CARRYFORWARD",
                "transactiontype": "BUY",
                "quantity":        str(int(pos.get("quantity",0))),
                "price":           str(pos.get("avg_entry_price",0)),
                "tradedsquareoff": "0",
            })
        if not orders: return {}
        resp = obj.getMargin({"orders": orders})
        if resp and resp.get("status") and resp.get("data"):
            total = float(resp["data"].get("charges",{}).get("total",0))
            return {"_total_required": total}
    except Exception:
        pass
    return {}


def get_current_brokerage_rates() -> dict:
    return {
        "FUT_BROKERAGE_PER_ORDER": 20.0,
        "OPT_BROKERAGE_PER_ORDER": 20.0,
        "last_verified": "Jun-2025",
    }
