"""
TRADING JOURNAL — GOOGLE SHEET SETUP
=====================================
Run this ONCE on your laptop to create the Google Sheet structure.

Usage:
    python3 setup_sheet.py

Requirements:
    pip3 install gspread google-auth
"""

import json
import sys
import gspread
from google.oauth2.service_account import Credentials

# ── YOUR SETTINGS — FILL THESE IN ─────────────────────────────
SHEET_ID             = "1aa1cgsArVXymlS_bDiHxERADQSBnhhST0pXuC0X87sw"
SERVICE_ACCOUNT_FILE = "service_account.json"
# ──────────────────────────────────────────────────────────────

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

# ── TAB DEFINITIONS ───────────────────────────────────────────

TRADES_HEADERS = [
    "trade_id", "timestamp_entry", "trade_date", "trade_time",
    "strategy", "exchange", "instrument", "symbol",
    "expiry", "strike", "option_type",
    "action", "lots_qty", "quantity", "price", "price_source",
    "lot_size", "notes", "is_deleted", "punched_by",
]

CLOSED_TRADES_HEADERS = [
    "close_id", "strategy", "symbol", "exchange", "instrument",
    "expiry", "strike", "option_type", "direction",
    "open_date", "close_date", "hold_days",
    "quantity", "lots", "avg_entry_price", "avg_exit_price",
    "gross_pnl", "brokerage", "stt", "exchange_charges",
    "sebi_charges", "gst", "stamp_duty", "total_charges",
    "net_pnl", "roi_pct", "close_type", "linked_trade_ids",
]

INSTRUMENTS_HEADERS = [
    "symbol", "exchange", "instrument_type",
    "lot_size", "contract_unit", "last_updated",
]

STRATEGIES_HEADERS = [
    "strategy_name", "allocated_capital",
    "instruments_allowed", "active",
]

INSTRUMENTS_STARTER = [
    ["NIFTY",       "NSE", "FUT_OPT", 75,   "Index Units", ""],
    ["BANKNIFTY",   "NSE", "FUT_OPT", 15,   "Index Units", ""],
    ["FINNIFTY",    "NSE", "FUT_OPT", 40,   "Index Units", ""],
    ["MIDCPNIFTY",  "NSE", "FUT_OPT", 75,   "Index Units", ""],
    ["SENSEX",      "BSE", "FUT_OPT", 10,   "Index Units", ""],
    ["GOLD",        "MCX", "FUT",    100,   "Grams",       ""],
    ["GOLDM",       "MCX", "FUT",     10,   "Grams",       ""],
    ["GOLDPETAL",   "MCX", "FUT",      1,   "Gram",        ""],
    ["SILVER",      "MCX", "FUT",     30,   "Kg",          ""],
    ["SILVERMIC",   "MCX", "FUT",      1,   "Kg",          ""],
    ["SILVERMINI",  "MCX", "FUT",      5,   "Kg",          ""],
    ["CRUDEOIL",    "MCX", "FUT",    100,   "Barrels",     ""],
    ["CRUDEOILM",   "MCX", "FUT",     10,   "Barrels",     ""],
    ["NATURALGAS",  "MCX", "FUT",   1250,   "MMBtu",       ""],
    ["NATURALGASM", "MCX", "FUT",    250,   "MMBtu",       ""],
    ["COPPER",      "MCX", "FUT",   2500,   "Kg",          ""],
    ["COPPERM",     "MCX", "FUT",    250,   "Kg",          ""],
    ["ZINC",        "MCX", "FUT",   5000,   "Kg",          ""],
    ["LEAD",        "MCX", "FUT",   5000,   "Kg",          ""],
    ["ALUMINIUM",   "MCX", "FUT",   5000,   "Kg",          ""],
    ["NICKEL",      "MCX", "FUT",   1500,   "Kg",          ""],
    ["NICKELM",     "MCX", "FUT",    100,   "Kg",          ""],
]

STRATEGIES_STARTER = [
    ["TREND",       2500000, "FUT,OPT",      "Y"],
    ["MOMENTUM",     700000, "CASH,FUT,OPT", "Y"],
    ["50K",         1000000, "FUT,OPT",      "Y"],
    ["COMMODITIES", 2500000, "MCX",          "Y"],
    ["MIDCAP",      5000000, "CASH",         "Y"],
    ["CASH",         500000, "CASH",         "Y"],
    ["ETF",         1000000, "CASH",         "Y"],
]


def get_client():
    """
    Connect to Google Sheets using service account JSON file.
    Compatible with all gspread versions.
    """
    # Read the JSON file manually
    with open(SERVICE_ACCOUNT_FILE, "r") as f:
        service_account_info = json.load(f)

    # Create credentials from the dict
    creds = Credentials.from_service_account_info(
        service_account_info,
        scopes=SCOPES,
    )

    # Authorize gspread
    return gspread.authorize(creds)


def setup_tab(ss, tab_name, headers, starter_data=None):
    """Create or clear a tab and write headers and optional data."""
    print(f"  Setting up {tab_name}...")

    # Get existing or create new worksheet
    try:
        ws = ss.worksheet(tab_name)
        ws.clear()
        print(f"    Cleared existing {tab_name}")
    except gspread.WorksheetNotFound:
        ws = ss.add_worksheet(
            title=tab_name,
            rows=2000,
            cols=len(headers) + 2,
        )
        print(f"    Created {tab_name}")

    # Write headers in row 1
    ws.update("A1", [headers])

    # Bold and colour the header row via format API
    header_range = f"A1:{col_letter(len(headers))}1"
    ws.format(header_range, {
        "textFormat": {
            "bold": True,
            "foregroundColor": {
                "red": 1.0, "green": 1.0, "blue": 1.0
            },
            "fontSize": 10,
        },
        "backgroundColor": {
            "red":   0.11,
            "green": 0.23,
            "blue":  0.42,
        },
        "horizontalAlignment": "CENTER",
    })

    # Freeze header row
    ws.freeze(rows=1)

    # Write starter data if provided
    if starter_data:
        ws.update("A2", starter_data)
        print(f"    Written {len(starter_data)} starter rows")

    print(f"    {tab_name} done — {len(headers)} columns")
    return ws


def col_letter(n):
    """Convert column number to letter. 1=A, 26=Z, 27=AA etc."""
    result = ""
    while n > 0:
        n, remainder = divmod(n - 1, 26)
        result = chr(65 + remainder) + result
    return result


def set_column_widths(ss, tab_name, widths_map):
    """
    Set column widths.
    widths_map: {col_index_0based: pixel_width}
    """
    try:
        ws = ss.worksheet(tab_name)
        requests = []
        for col_idx, width in widths_map.items():
            requests.append({
                "updateDimensionProperties": {
                    "range": {
                        "sheetId":    ws.id,
                        "dimension":  "COLUMNS",
                        "startIndex": col_idx,
                        "endIndex":   col_idx + 1,
                    },
                    "properties": {"pixelSize": width},
                    "fields": "pixelSize",
                }
            })
        if requests:
            ss.batch_update({"requests": requests})
    except Exception as e:
        print(f"    Column width setting skipped: {e}")


def main():
    print("\n🚀 Trading Journal — Google Sheet Setup")
    print("=" * 45)

    # Check Sheet ID was filled in
    if SHEET_ID == "YOUR_GOOGLE_SHEET_ID_HERE":
        print("\n❌  ERROR: You need to set your SHEET_ID first.")
        print("   Open setup_sheet.py in TextEdit")
        print('   Change: SHEET_ID = "YOUR_GOOGLE_SHEET_ID_HERE"')
        print("   To your actual Sheet ID from the Google Sheet URL")
        sys.exit(1)

    # Check JSON file exists
    try:
        with open(SERVICE_ACCOUNT_FILE, "r") as f:
            json.load(f)
        print(f"\n✓  Found {SERVICE_ACCOUNT_FILE}")
    except FileNotFoundError:
        print(f"\n❌  ERROR: {SERVICE_ACCOUNT_FILE} not found.")
        print("   Make sure service_account.json is in the same folder as this script")
        sys.exit(1)
    except json.JSONDecodeError:
        print(f"\n❌  ERROR: {SERVICE_ACCOUNT_FILE} is not valid JSON.")
        print("   Download the file again from Google Cloud Console")
        sys.exit(1)

    # Connect
    print("\nConnecting to Google Sheets...")
    try:
        client = get_client()
        ss     = client.open_by_key(SHEET_ID)
        print(f"✓  Connected to: {ss.title}")
    except gspread.exceptions.APIError as e:
        print(f"\n❌  API Error: {e}")
        print("\nMost likely cause: Sheet not shared with service account.")
        print("Fix:")
        print("  1. Open service_account.json in TextEdit")
        print('  2. Find the "client_email" line')
        print("  3. Copy that email address")
        print("  4. Open your Google Sheet → Share → paste email → Editor → Share")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌  Connection failed: {e}")
        sys.exit(1)

    # Build tabs
    print("\nCreating tabs...")
    setup_tab(ss, "TRADES",        TRADES_HEADERS,        None)
    setup_tab(ss, "CLOSED_TRADES", CLOSED_TRADES_HEADERS, None)
    setup_tab(ss, "INSTRUMENTS",   INSTRUMENTS_HEADERS,   INSTRUMENTS_STARTER)
    setup_tab(ss, "STRATEGIES",    STRATEGIES_HEADERS,    STRATEGIES_STARTER)

    # Remove any default sheets left over
    keep = {"TRADES", "CLOSED_TRADES", "INSTRUMENTS", "STRATEGIES"}
    for tab in ss.worksheets():
        if tab.title not in keep:
            try:
                ss.del_worksheet(tab)
                print(f"  Removed default tab: {tab.title}")
            except Exception:
                pass

    # Set column widths for TRADES
    print("\nSetting column widths...")
    set_column_widths(ss, "TRADES", {
        0:  120, 1:  145, 2:  100, 3:   80,
        4:  110, 5:   80, 6:   90, 7:  120,
        8:   85, 9:   75, 10:  90, 11:  75,
        12:  80, 13:  80, 14: 100, 15: 110,
        16:  80, 17: 180, 18:  85, 19: 100,
    })
    set_column_widths(ss, "CLOSED_TRADES", {
        0:  120, 1:  110, 2:  120, 3:   80,
        4:   90, 5:   85, 6:   75, 7:   90,
        8:   85, 9:  100, 10: 100, 11:  85,
        12:  85, 13:  60, 14: 130, 15: 120,
        16: 125, 17: 100, 18:  80, 19: 130,
        20: 110, 21:  80, 22: 100, 23: 120,
        24: 100, 25:  80, 26:  90, 27: 180,
    })
    set_column_widths(ss, "INSTRUMENTS", {
        0: 140, 1: 90, 2: 110, 3: 90, 4: 140, 5: 120,
    })
    set_column_widths(ss, "STRATEGIES", {
        0: 150, 1: 160, 2: 180, 3: 80,
    })

    print("\n✅  Google Sheet setup complete!")
    print(f"\nOpen your sheet and verify 4 tabs are created:")
    print(f"  https://docs.google.com/spreadsheets/d/{SHEET_ID}/edit")
    print("\nNext step:")
    print("  Run: python3 refresh_instruments.py")
    print("  This loads all NSE F&O stocks into the INSTRUMENTS tab")


if __name__ == "__main__":
    main()
