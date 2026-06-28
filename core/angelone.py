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
@st.cache_resource(ttl=3600)
def get_angel_obj():
    """
    Login to AngelOne via direct REST call (avoids SmartConnect getProfile timeout).
    Returns a simple namespace with jwt_token and api_key. Cached 1 hour.
    """
    try:
        cfg     = st.secrets["angelone"]
        api_key = "".join(c for c in str(cfg["api_key"]).strip() if c.isprintable() and c > " ")
        client  = str(cfg["client_id"]).strip()
        pwd     = str(cfg["password"]).strip()
        totp    = pyotp.TOTP(str(cfg["totp_secret"]).strip()).now()

        headers = {
            "Content-Type":    "application/json",
            "Accept":          "application/json",
            "X-UserType":      "USER",
            "X-SourceID":      "WEB",
            "X-ClientLocalIP": "127.0.0.1",
            "X-ClientPublicIP":"106.193.147.98",
            "X-MACAddress":    "AA:BB:CC:DD:EE:FF",
            "X-PrivateKey":    api_key,
        }
        body = {"clientcode": client, "password": pwd, "totp": totp}
        resp = requests.post(
            "https://apiconnect.angelone.in/rest/auth/angelbroking/user/v1/loginByPassword",
            json=body, headers=headers, timeout=15
        )
        data = resp.json()
        if data.get("status") and data.get("data"):
            jwt = data["data"].get("jwtToken","")
            if jwt:
                # Return simple object with what we need
                class _AO:
                    def __init__(self, jwt, key):
                        self.jwt = jwt
                        self.api_key = key
                return _AO(jwt, api_key)
        return None
    except Exception:
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


def find_token(symbol: str, exchange: str, instrument: str, expiry: str = "", strike: float = 0, opt_type: str = "") -> tuple:
    """
    Find AngelOne token + tradingsymbol for a given symbol.
    Returns (token, tradingsymbol) or ("", "").
    Handles CASH/equity stocks via NSE equity segment.
    """
    try:
        # ── CASH / EQUITY / ETF stocks ──
        if instrument.upper() in ("CASH", "ETF"):
            ao = get_angel_obj()
            if not ao: return "", ""
            # Try symbol + -EQ suffix first (NSE equity format)
            for ts_try in [f"{symbol.upper()}-EQ", symbol.upper()]:
                headers = {
                    "Content-Type":    "application/json",
                    "Accept":          "application/json",
                    "X-UserType":      "USER",
                    "X-SourceID":      "WEB",
                    "X-ClientLocalIP": "127.0.0.1",
                    "X-ClientPublicIP":"106.193.147.98",
                    "X-MACAddress":    "AA:BB:CC:DD:EE:FF",
                    "X-PrivateKey":    ao.api_key,
                    "Authorization":   f"Bearer {ao.jwt}",
                }
                try:
                    resp = requests.post(
                        "https://apiconnect.angelone.in/rest/secure/angelbroking/order/v1/searchScrip",
                        json={"exchange": "NSE", "searchscrip": ts_try},
                        headers=headers, timeout=8
                    )
                    data = resp.json()
                    if data.get("status") and data.get("data"):
                        for item in data["data"]:
                            ts = item.get("tradingsymbol","")
                            if ts.upper() in (f"{symbol.upper()}-EQ", symbol.upper()):
                                return str(item.get("symboltoken","")), ts
                except Exception:
                    pass
            return "", ""

        df = get_instrument_master()
        if df.empty: return "", ""

        # Filter by base symbol name
        mask = df["name"].str.upper() == symbol.upper()
        sub  = df[mask]
        if sub.empty:
            mask = df["symbol"].str.upper().str.startswith(symbol.upper())
            sub  = df[mask]
        if sub.empty: return "", ""

        # Filter by instrument type
        if instrument.upper() == "FUT":
            sub2 = sub[sub["instrumenttype"].str.upper().isin(["FUTSTK","FUTIDX"])]
            if not sub2.empty: sub = sub2
        elif instrument.upper() == "OPT":
            sub2 = sub[sub["instrumenttype"].str.upper().isin(["OPTSTK","OPTIDX"])]
            if not sub2.empty: sub = sub2
            if opt_type:
                sub3 = sub[sub["symbol"].str.upper().str.endswith(opt_type.upper())]
                if not sub3.empty: sub = sub3
            if strike > 0:
                sub3 = sub[sub["strike"] == strike * 100]
                if not sub3.empty: sub = sub3

        if sub.empty: return "", ""

        # Match expiry
        if expiry:
            try:
                exp_dt = datetime.strptime(expiry, "%b-%y")
                sub2 = sub[
                    sub["expiry"].str.contains(str(exp_dt.year), na=False) &
                    sub["expiry"].str.upper().str.contains(exp_dt.strftime("%b").upper(), na=False)
                ]
                if not sub2.empty: sub = sub2
            except Exception:
                pass

        row = sub.iloc[0]
        return str(row["token"]), str(row.get("symbol",""))

    except Exception:
        return "", ""


# ── LTP ────────────────────────────────────────────────────────────────────────

def fetch_current_ltp(symbol: str, exchange: str, token: str, instrument_hint: str = "FUT") -> tuple:
    """Fetch LTP via direct REST. Returns (price, 'LIVE') or (None, 'MANUAL')."""
    ao = get_angel_obj()
    if not ao or not token: return None, "MANUAL"
    try:
        # CASH/ETF stocks use NSE segment, F&O uses NFO
        if instrument_hint.upper() in ("CASH", "ETF"):
            seg = "NSE"
        elif exchange.upper() in ("NSE","NFO"):
            seg = "NFO"
        else:
            seg = exchange.upper()
        headers = {
            "Content-Type":    "application/json",
            "Accept":          "application/json",
            "X-UserType":      "USER",
            "X-SourceID":      "WEB",
            "X-ClientLocalIP": "127.0.0.1",
            "X-ClientPublicIP":"106.193.147.98",
            "X-MACAddress":    "AA:BB:CC:DD:EE:FF",
            "X-PrivateKey":    ao.api_key,
            "Authorization":   f"Bearer {ao.jwt}",
        }
        resp = requests.post(
            "https://apiconnect.angelone.in/rest/secure/angelbroking/market/v1/quote/",
            json={"mode":"LTP","exchangeTokens":{seg:[token]}},
            headers=headers, timeout=10
        )
        data = resp.json()
        if data.get("status") and data.get("data"):
            fetched = data["data"].get("fetched",[])
            if fetched:
                ltp = float(fetched[0].get("ltp",0))
                if ltp > 0: return ltp, "LIVE"
    except Exception:
        pass
    return None, "MANUAL"


def get_symbol_token(symbol: str, exchange: str, instrument: str,
                     expiry: str = "", strike: float = 0, opt_type: str = "") -> str:
    """Public wrapper — returns just the token string."""
    token, _ = find_token(symbol, exchange, instrument, expiry, strike, opt_type)
    return token

def get_symbol_token_and_ts(symbol: str, exchange: str, instrument: str,
                             expiry: str = "", strike: float = 0, opt_type: str = "") -> tuple:
    """Returns (token, tradingsymbol) tuple."""
    return find_token(symbol, exchange, instrument, expiry, strike, opt_type)


# ── MARGIN ────────────────────────────────────────────────────────────────────

def fetch_margin_for_positions(positions: list) -> dict:
    """Fetch SPAN margin via direct REST. Returns dict with _total_required."""
    ao = get_angel_obj()
    if not ao or not positions: return {}
    try:
        orders = []
        for pos in positions:
            token = pos.get("token","")
            instr = pos.get("instrument","FUT").upper()
            if instr == "CASH": continue
            # If no token, try to fetch it now
            if not token:
                token, ts = find_token(
                    pos.get("symbol",""),
                    pos.get("exchange","NSE"),
                    instr,
                    pos.get("expiry",""),
                )
            else:
                _, ts = find_token(
                    pos.get("symbol",""),
                    pos.get("exchange","NSE"),
                    instr,
                    pos.get("expiry",""),
                )
            if not token: continue
            # Use actual trading symbol from master, fall back to base symbol
            trading_sym = ts if ts else pos.get("symbol","")
            exch = "NFO" if pos.get("exchange","NSE").upper() in ("NSE","NFO") else pos.get("exchange","NSE").upper()
            orders.append({
                "exchange":        exch,
                "tradingsymbol":   trading_sym,
                "symboltoken":     token,
                "producttype":     "CARRYFORWARD",
                "transactiontype": "BUY",
                "quantity":        str(max(1, int(pos.get("quantity",1)))),
                "price":           str(pos.get("avg_entry_price",0)),
                "tradedsquareoff": "0",
            })
        if not orders: return {}
        headers = {
            "Content-Type":    "application/json",
            "Accept":          "application/json",
            "X-UserType":      "USER",
            "X-SourceID":      "WEB",
            "X-ClientLocalIP": "127.0.0.1",
            "X-ClientPublicIP":"106.193.147.98",
            "X-MACAddress":    "AA:BB:CC:DD:EE:FF",
            "X-PrivateKey":    ao.api_key,
            "Authorization":   f"Bearer {ao.jwt}",
        }
        resp = requests.post(
            "https://apiconnect.angelone.in/rest/secure/angelbroking/order/v1/getMargin",
            json={"orders": orders}, headers=headers, timeout=10
        )
        data = resp.json()
        if data.get("status") and data.get("data"):
            total = float(data["data"].get("charges",{}).get("total",0))
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
