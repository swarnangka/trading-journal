"""
core/sheets.py
==============
All Google Sheet read and write operations.
Single source of truth for sheet access.
Uses service account credentials from Streamlit secrets.
"""

import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
from datetime import datetime
import pytz

IST = pytz.timezone("Asia/Kolkata")

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

TAB_TRADES        = "TRADES"
TAB_CLOSED        = "CLOSED_TRADES"
TAB_INSTRUMENTS   = "INSTRUMENTS"
TAB_STRATEGIES    = "STRATEGIES"


# ── CONNECTION ────────────────────────────────────────────────

@st.cache_resource(ttl=3600)
def get_client():
    """Return authenticated gspread client. Cached for 1 hour."""
    creds_dict = dict(st.secrets["gcp_service_account"])
    creds      = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
    return gspread.authorize(creds)


def get_sheet():
    """Return the spreadsheet object."""
    client   = get_client()
    sheet_id = st.secrets["app"]["sheet_id"]
    return client.open_by_key(sheet_id)


def get_worksheet(tab_name: str):
    """Return a specific worksheet by name."""
    return get_sheet().worksheet(tab_name)


# ── READ FUNCTIONS ────────────────────────────────────────────

@st.cache_data(ttl=30)
def read_trades() -> pd.DataFrame:
    """
    Read all rows from TRADES tab.
    Excludes deleted rows.
    Returns DataFrame.
    """
    ws   = get_worksheet(TAB_TRADES)
    data = ws.get_all_records()
    if not data:
        return pd.DataFrame()
    df = pd.DataFrame(data)
    # Exclude deleted rows
    if "is_deleted" in df.columns:
        df = df[df["is_deleted"].astype(str).str.upper() != "TRUE"]
    return df


@st.cache_data(ttl=30)
def read_closed_trades() -> pd.DataFrame:
    """Read all closed trades."""
    ws   = get_worksheet(TAB_CLOSED)
    data = ws.get_all_records()
    return pd.DataFrame(data) if data else pd.DataFrame()


@st.cache_data(ttl=300)
def read_instruments() -> pd.DataFrame:
    """Read F&O symbol master. Cached 5 min."""
    ws   = get_worksheet(TAB_INSTRUMENTS)
    data = ws.get_all_records()
    return pd.DataFrame(data) if data else pd.DataFrame()


@st.cache_data(ttl=300)
def read_strategies() -> pd.DataFrame:
    """Read strategy config. Cached 5 min."""
    ws   = get_worksheet(TAB_STRATEGIES)
    data = ws.get_all_records()
    if not data:
        return pd.DataFrame()
    df = pd.DataFrame(data)
    if "active" in df.columns:
        df = df[df["active"].astype(str).str.upper() == "Y"]
    return df


# ── WRITE FUNCTIONS ───────────────────────────────────────────

def append_trade(row: dict) -> bool:
    """
    Append one trade row to TRADES tab.
    row keys must match TRADES_HEADERS exactly.
    Returns True on success.
    """
    try:
        ws = get_worksheet(TAB_TRADES)
        headers = ws.row_values(1)
        new_row = [str(row.get(h, "")) for h in headers]
        ws.append_row(new_row, value_input_option="USER_ENTERED")
        # Clear cache so next read sees this row
        read_trades.clear()
        return True
    except Exception as e:
        st.error(f"Failed to write trade: {e}")
        return False


def update_trade_field(trade_id: str, field: str, value) -> bool:
    """
    Update a single field in a trade row by trade_id.
    Used for editing date/time of open trades.
    """
    try:
        ws      = get_worksheet(TAB_TRADES)
        headers = ws.row_values(1)
        if field not in headers:
            st.error(f"Field '{field}' not found in TRADES tab")
            return False

        col_idx  = headers.index(field) + 1   # 1-indexed
        id_col   = headers.index("trade_id") + 1
        all_ids  = ws.col_values(id_col)

        for row_num, cell_val in enumerate(all_ids, start=1):
            if cell_val == trade_id:
                ws.update_cell(row_num, col_idx, str(value))
                read_trades.clear()
                return True

        st.error(f"Trade ID {trade_id} not found")
        return False
    except Exception as e:
        st.error(f"Failed to update trade: {e}")
        return False


def soft_delete_trade(trade_id: str) -> bool:
    """
    Mark a trade as deleted (is_deleted = TRUE).
    Never hard-deletes rows — audit trail preserved.
    """
    return update_trade_field(trade_id, "is_deleted", "TRUE")


def append_closed_trade(row: dict) -> bool:
    """Append one closed trade to CLOSED_TRADES tab."""
    try:
        ws      = get_worksheet(TAB_CLOSED)
        headers = ws.row_values(1)
        new_row = [str(row.get(h, "")) for h in headers]
        ws.append_row(new_row, value_input_option="USER_ENTERED")
        read_closed_trades.clear()
        return True
    except Exception as e:
        st.error(f"Failed to write closed trade: {e}")
        return False


def closed_trade_exists(close_id: str) -> bool:
    """Check if a close_id already exists in CLOSED_TRADES."""
    df = read_closed_trades()
    if df.empty or "close_id" not in df.columns:
        return False
    return close_id in df["close_id"].values


def write_instruments(rows: list) -> bool:
    """
    Overwrite entire INSTRUMENTS tab data (not headers).
    Used by refresh_instruments.py.
    rows: list of lists matching INSTRUMENTS_HEADERS.
    """
    try:
        ws = get_worksheet(TAB_INSTRUMENTS)
        # Clear from row 2 downward
        ws.batch_clear(["A2:Z5000"])
        if rows:
            ws.update("A2", rows, value_input_option="USER_ENTERED")
        read_instruments.clear()
        return True
    except Exception as e:
        print(f"Failed to write instruments: {e}")
        return False


# ── HELPER: Get strategy capital map ─────────────────────────

def get_strategy_capital() -> dict:
    """Returns {strategy_name: allocated_capital} dict."""
    df = read_strategies()
    if df.empty:
        return {}
    result = {}
    for _, row in df.iterrows():
        try:
            result[str(row["strategy_name"])] = float(str(row["allocated_capital"]).replace(",", ""))
        except (ValueError, KeyError):
            pass
    return result


def get_strategy_list() -> list:
    """Returns list of active strategy names."""
    df = read_strategies()
    if df.empty:
        return []
    return df["strategy_name"].tolist()


# ── HELPER: Get instruments for dropdowns ────────────────────

def get_symbols_for(exchange: str, instrument_type: str) -> list:
    """
    Returns sorted list of symbols for given exchange and instrument type.
    instrument_type: 'FUT', 'OPT', or 'FUT_OPT'
    """
    df = read_instruments()
    if df.empty:
        return []

    df["exchange"]        = df["exchange"].astype(str).str.upper()
    df["instrument_type"] = df["instrument_type"].astype(str).str.upper()

    exchange = exchange.upper()
    mask     = df["exchange"] == exchange

    if instrument_type.upper() == "FUT":
        mask &= df["instrument_type"].isin(["FUT", "FUT_OPT"])
    elif instrument_type.upper() == "OPT":
        mask &= df["instrument_type"].isin(["OPT", "FUT_OPT"])

    symbols = df[mask]["symbol"].dropna().unique().tolist()
    return sorted(symbols)


def get_lot_size(symbol: str, exchange: str) -> int:
    """Return lot size for a symbol. Returns 1 if not found."""
    df = read_instruments()
    if df.empty:
        return 1
    df["symbol"]   = df["symbol"].astype(str).str.upper()
    df["exchange"]  = df["exchange"].astype(str).str.upper()
    match = df[(df["symbol"] == symbol.upper()) & (df["exchange"] == exchange.upper())]
    if match.empty:
        return 1
    try:
        return int(float(str(match.iloc[0]["lot_size"])))
    except (ValueError, TypeError):
        return 1
