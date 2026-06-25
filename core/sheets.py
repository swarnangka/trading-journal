"""
PARABOLIC DASHBOARD — Google Sheets Layer
==========================================
All Sheet reads and writes go through here.
Private key fix: Streamlit TOML stores \n as literal text — we convert back.
"""

import streamlit as st
import gspread
import pandas as pd
from google.oauth2.service_account import Credentials
from datetime import datetime
import pytz
import csv
import io

IST = pytz.timezone("Asia/Kolkata")

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

TAB_TRADES      = "TRADES"
TAB_CLOSED      = "CLOSED_TRADES"
TAB_INSTRUMENTS = "INSTRUMENTS"
TAB_STRATEGIES  = "STRATEGIES"


# ── AUTH ──────────────────────────────────────────────────────────────────────

@st.cache_resource(ttl=3600)
def get_client():
    """Return authenticated gspread client. Cached 1 hour."""
    raw = dict(st.secrets["gcp_service_account"])
    pk  = str(raw.get("private_key", ""))
    pk  = pk.replace("\\n", "\n")
    if not pk.endswith("\n"):
        pk += "\n"
    raw["private_key"] = pk
    creds = Credentials.from_service_account_info(raw, scopes=SCOPES)
    return gspread.authorize(creds)


def get_sheet():
    return get_client().open_by_key(st.secrets["app"]["sheet_id"])


def get_worksheet(tab_name: str):
    return get_sheet().worksheet(tab_name)


# ── READ FUNCTIONS ─────────────────────────────────────────────────────────────

@st.cache_data(ttl=60)
def read_trades() -> pd.DataFrame:
    ws   = get_worksheet(TAB_TRADES)
    data = ws.get_all_records()
    if not data:
        return pd.DataFrame()
    df = pd.DataFrame(data)
    if "is_deleted" in df.columns:
        df = df[df["is_deleted"].astype(str).str.upper() != "TRUE"]
    return df


@st.cache_data(ttl=120)
def read_closed_trades() -> pd.DataFrame:
    ws   = get_worksheet(TAB_CLOSED)
    data = ws.get_all_records()
    return pd.DataFrame(data) if data else pd.DataFrame()


@st.cache_data(ttl=3600)
def read_instruments() -> pd.DataFrame:
    ws   = get_worksheet(TAB_INSTRUMENTS)
    data = ws.get_all_records()
    return pd.DataFrame(data) if data else pd.DataFrame()


@st.cache_data(ttl=300)
def read_strategies() -> pd.DataFrame:
    ws   = get_worksheet(TAB_STRATEGIES)
    data = ws.get_all_records()
    return pd.DataFrame(data) if data else pd.DataFrame()


# ── INSTRUMENTS — CSV PASTE PARSER ─────────────────────────────────────────────

def parse_fo_mktlots_csv(csv_text: str) -> list[dict]:
    """
    Parse the NSE fo_mktlots.csv content (pasted as text).
    Returns list of dicts: {symbol, underlying, lot_size, exchange, instrument_type}
    
    CSV format:
      Col 0: UNDERLYING (full name)
      Col 1: SYMBOL     (tradeable code)
      Col 2: nearest month lot size
      ...more months...
    
    Skips rows where:
      - SYMBOL is empty or "Symbol" (header repeats)
      - lot size col is empty or non-numeric
    """
    rows = []
    reader = csv.reader(io.StringIO(csv_text))
    for row in reader:
        if len(row) < 3:
            continue
        underlying = row[0].strip()
        symbol     = row[1].strip()
        lot_str    = row[2].strip()

        # Skip header / section divider rows
        if not symbol or symbol.lower() in ("symbol", "underlying", ""):
            continue
        if not lot_str or not lot_str.isdigit():
            continue
        # Skip the index section header
        if underlying.lower().startswith("derivatives on individual"):
            continue

        lot_size = int(lot_str)

        # Determine exchange and instrument type
        # Indices (NIFTY, BANKNIFTY etc) trade on NSE as FUT+OPT
        # Individual stocks trade on NSE as FUT+OPT
        # MCX commodities not in this file — handled separately
        exchange        = "NSE"
        instrument_type = "FUT_OPT"

        rows.append({
            "symbol":          symbol,
            "underlying":      underlying,
            "lot_size":        lot_size,
            "exchange":        exchange,
            "instrument_type": instrument_type,
        })

    return rows


def write_instruments_to_sheet(parsed_rows: list[dict]) -> tuple[bool, str]:
    """
    Overwrites the INSTRUMENTS tab with parsed F&O lot size data.
    Keeps the header row intact, replaces all data rows.
    Returns (success, message).
    """
    try:
        ws = get_worksheet(TAB_INSTRUMENTS)

        # Build rows in sheet column order: symbol, underlying, lot_size, exchange, instrument_type, last_updated
        now_str = now_ist().strftime("%Y-%m-%d %H:%M")
        data_rows = []
        for r in parsed_rows:
            data_rows.append([
                r["symbol"],
                r["underlying"],
                r["lot_size"],
                r["exchange"],
                r["instrument_type"],
                now_str,
            ])

        # Clear everything below header (row 1)
        ws.resize(rows=1)  # shrink to just header
        # Append all rows at once
        ws.append_rows(data_rows, value_input_option="USER_ENTERED")

        # Clear cache
        read_instruments.clear()
        return True, f"✅ {len(data_rows)} symbols written to INSTRUMENTS tab."

    except Exception as e:
        return False, f"❌ Error writing instruments: {e}"


# ── SYMBOL / LOT HELPERS ───────────────────────────────────────────────────────

def get_fno_symbols() -> list:
    df = read_instruments()
    if df.empty or "symbol" not in df.columns:
        return []
    return sorted(df["symbol"].str.strip().tolist())


def get_lot_size(symbol: str) -> int:
    df = read_instruments()
    if df.empty:
        return 1
    match = df[df["symbol"].str.upper().str.strip() == symbol.upper().strip()]
    if match.empty:
        return 1
    try:
        return int(match.iloc[0]["lot_size"])
    except Exception:
        return 1


def get_strategy_list() -> list:
    df = read_strategies()
    if df.empty or "strategy_name" not in df.columns:
        return []
    if "active" in df.columns:
        df = df[df["active"].astype(str).str.upper() == "Y"]
    return df["strategy_name"].tolist()


# ── WRITE FUNCTIONS ────────────────────────────────────────────────────────────

def append_trade(row_data: dict) -> bool:
    try:
        ws      = get_worksheet(TAB_TRADES)
        headers = ws.row_values(1)
        row     = [str(row_data.get(h, "")) for h in headers]
        ws.append_row(row, value_input_option="USER_ENTERED")
        read_trades.clear()
        return True
    except Exception as e:
        st.error(f"Write error: {e}")
        return False


def soft_delete_trade(trade_id: str) -> bool:
    try:
        ws      = get_worksheet(TAB_TRADES)
        headers = ws.row_values(1)
        if "is_deleted" not in headers or "trade_id" not in headers:
            return False
        tid_col     = headers.index("trade_id") + 1
        deleted_col = headers.index("is_deleted") + 1
        col_vals    = ws.col_values(tid_col)
        for i, val in enumerate(col_vals):
            if val == str(trade_id):
                ws.update_cell(i + 1, deleted_col, "TRUE")
                read_trades.clear()
                return True
        return False
    except Exception as e:
        st.error(f"Delete error: {e}")
        return False


def update_trade_field(trade_id: str, field: str, value) -> bool:
    try:
        ws      = get_worksheet(TAB_TRADES)
        headers = ws.row_values(1)
        if field not in headers or "trade_id" not in headers:
            return False
        tid_col   = headers.index("trade_id") + 1
        field_col = headers.index(field) + 1
        col_vals  = ws.col_values(tid_col)
        for i, val in enumerate(col_vals):
            if val == str(trade_id):
                ws.update_cell(i + 1, field_col, str(value))
                read_trades.clear()
                return True
        return False
    except Exception as e:
        st.error(f"Update error: {e}")
        return False


# ── UTILITY ────────────────────────────────────────────────────────────────────

def now_ist() -> datetime:
    return datetime.now(IST)


def generate_trade_id() -> str:
    return now_ist().strftime("TRD-%Y%m%d-%H%M%S")


def build_expiry_months(n: int = 6) -> list:
    months = []
    base   = now_ist()
    for i in range(n):
        month = (base.month - 1 + i) % 12 + 1
        year  = base.year + (base.month - 1 + i) // 12
        months.append(datetime(year, month, 1).strftime("%b-%y").upper())
    return months
