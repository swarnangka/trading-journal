"""
core/instruments.py
====================
Handles F&O symbol list and lot size management.
Fetches from NSE API and writes to INSTRUMENTS tab.
Run refresh_instruments.py to update.
"""

import requests
import pandas as pd
from datetime import datetime
import pytz
import time

IST = pytz.timezone("Asia/Kolkata")

NSE_HEADERS = {
    "User-Agent":       "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept":           "application/json, text/plain, */*",
    "Accept-Language":  "en-US,en;q=0.9",
    "Referer":          "https://www.nseindia.com/",
    "Connection":       "keep-alive",
}

MCX_HEADERS = {
    "User-Agent":      "Mozilla/5.0",
    "Accept":          "application/json",
    "Referer":         "https://www.mcxindia.com/",
}


def fetch_nse_fo_symbols() -> list:
    """
    Fetch all NSE F&O equity symbols with lot sizes.
    Returns list of dicts: {symbol, exchange, instrument_type, lot_size, contract_unit}
    """
    results = []
    today   = datetime.now(IST).strftime("%d-%m-%Y")

    # ── Endpoint 1: Securities in F&O ────────────────────────
    try:
        # First hit the main page to get cookies
        session = requests.Session()
        session.get("https://www.nseindia.com", headers=NSE_HEADERS, timeout=10)
        time.sleep(1)

        resp = session.get(
            "https://www.nseindia.com/api/equity-stockIndices?index=SECURITIES%20IN%20F%26O",
            headers=NSE_HEADERS, timeout=15
        )
        if resp.status_code == 200:
            data = resp.json().get("data", [])
            for item in data:
                sym     = str(item.get("symbol", "")).strip().upper()
                lot     = item.get("lotSize") or item.get("lot_size") or 0
                if sym and int(float(str(lot).replace(",", ""))) > 0:
                    results.append({
                        "symbol":          sym,
                        "exchange":        "NSE",
                        "instrument_type": "FUT_OPT",
                        "lot_size":        int(float(str(lot).replace(",", ""))),
                        "contract_unit":   "Shares",
                        "last_updated":    today,
                    })

        if results:
            print(f"  NSE Endpoint 1: {len(results)} symbols")
            return results
    except Exception as e:
        print(f"  NSE Endpoint 1 failed: {e}")

    # ── Endpoint 2: Derivatives market data ──────────────────
    try:
        session2 = requests.Session()
        session2.get("https://www.nseindia.com", headers=NSE_HEADERS, timeout=10)
        time.sleep(1)

        resp2 = session2.get(
            "https://www.nseindia.com/api/master-quote",
            headers=NSE_HEADERS, timeout=15
        )
        if resp2.status_code == 200:
            text = resp2.text
            seen = {}
            for line in text.split("\n"):
                parts = line.split(",")
                if len(parts) >= 6 and parts[0].strip() == "NSE":
                    sym     = parts[1].strip().upper()
                    try:
                        lot = int(float(parts[5].strip()))
                    except Exception:
                        continue
                    if sym and lot > 0 and sym not in seen:
                        seen[sym] = True
                        results.append({
                            "symbol":          sym,
                            "exchange":        "NSE",
                            "instrument_type": "FUT_OPT",
                            "lot_size":        lot,
                            "contract_unit":   "Shares",
                            "last_updated":    today,
                        })

        if results:
            print(f"  NSE Endpoint 2: {len(results)} symbols")
            return results
    except Exception as e:
        print(f"  NSE Endpoint 2 failed: {e}")

    print("  ⚠️ Both NSE endpoints failed — returning empty list")
    return results


def get_mcx_symbols() -> list:
    """
    Returns hardcoded MCX commodity symbols with lot sizes.
    MCX lot sizes rarely change. Verify against MCX website periodically.
    Last verified: Jun 2025
    """
    today = datetime.now(IST).strftime("%d-%m-%Y")
    return [
        # Gold
        {"symbol": "GOLD",       "exchange": "MCX", "instrument_type": "FUT", "lot_size": 100,  "contract_unit": "Grams",   "last_updated": today},
        {"symbol": "GOLDM",      "exchange": "MCX", "instrument_type": "FUT", "lot_size": 10,   "contract_unit": "Grams",   "last_updated": today},
        {"symbol": "GOLDPETAL",  "exchange": "MCX", "instrument_type": "FUT", "lot_size": 1,    "contract_unit": "Gram",    "last_updated": today},
        # Silver
        {"symbol": "SILVER",     "exchange": "MCX", "instrument_type": "FUT", "lot_size": 30,   "contract_unit": "Kg",      "last_updated": today},
        {"symbol": "SILVERMIC",  "exchange": "MCX", "instrument_type": "FUT", "lot_size": 1,    "contract_unit": "Kg",      "last_updated": today},
        {"symbol": "SILVERMINI", "exchange": "MCX", "instrument_type": "FUT", "lot_size": 5,    "contract_unit": "Kg",      "last_updated": today},
        # Crude Oil
        {"symbol": "CRUDEOIL",   "exchange": "MCX", "instrument_type": "FUT", "lot_size": 100,  "contract_unit": "Barrels", "last_updated": today},
        {"symbol": "CRUDEOILM",  "exchange": "MCX", "instrument_type": "FUT", "lot_size": 10,   "contract_unit": "Barrels", "last_updated": today},
        # Natural Gas
        {"symbol": "NATURALGAS", "exchange": "MCX", "instrument_type": "FUT", "lot_size": 1250, "contract_unit": "MMBtu",   "last_updated": today},
        {"symbol": "NATURALGASM","exchange": "MCX", "instrument_type": "FUT", "lot_size": 250,  "contract_unit": "MMBtu",   "last_updated": today},
        # Base Metals
        {"symbol": "COPPER",     "exchange": "MCX", "instrument_type": "FUT", "lot_size": 2500, "contract_unit": "Kg",      "last_updated": today},
        {"symbol": "COPPERM",    "exchange": "MCX", "instrument_type": "FUT", "lot_size": 250,  "contract_unit": "Kg",      "last_updated": today},
        {"symbol": "ZINC",       "exchange": "MCX", "instrument_type": "FUT", "lot_size": 5000, "contract_unit": "Kg",      "last_updated": today},
        {"symbol": "ZINCMINI",   "exchange": "MCX", "instrument_type": "FUT", "lot_size": 1000, "contract_unit": "Kg",      "last_updated": today},
        {"symbol": "LEAD",       "exchange": "MCX", "instrument_type": "FUT", "lot_size": 5000, "contract_unit": "Kg",      "last_updated": today},
        {"symbol": "LEADMINI",   "exchange": "MCX", "instrument_type": "FUT", "lot_size": 1000, "contract_unit": "Kg",      "last_updated": today},
        {"symbol": "ALUMINIUM",  "exchange": "MCX", "instrument_type": "FUT", "lot_size": 5000, "contract_unit": "Kg",      "last_updated": today},
        {"symbol": "ALUMINIUMM", "exchange": "MCX", "instrument_type": "FUT", "lot_size": 1000, "contract_unit": "Kg",      "last_updated": today},
        {"symbol": "NICKEL",     "exchange": "MCX", "instrument_type": "FUT", "lot_size": 1500, "contract_unit": "Kg",      "last_updated": today},
        {"symbol": "NICKELM",    "exchange": "MCX", "instrument_type": "FUT", "lot_size": 100,  "contract_unit": "Kg",      "last_updated": today},
    ]


def build_full_instruments_list() -> list:
    """
    Combines NSE F&O + MCX symbols into one list.
    Returns list of lists matching INSTRUMENTS tab columns.
    Columns: symbol, exchange, instrument_type, lot_size, contract_unit, last_updated
    """
    nse_symbols = fetch_nse_fo_symbols()
    mcx_symbols = get_mcx_symbols()
    all_symbols = nse_symbols + mcx_symbols

    # Convert to list of lists for sheet write
    rows = []
    for item in all_symbols:
        rows.append([
            item["symbol"],
            item["exchange"],
            item["instrument_type"],
            item["lot_size"],
            item["contract_unit"],
            item["last_updated"],
        ])

    return rows


def build_expiry_months(count: int = 6) -> list:
    """Generate list of expiry month options for dropdowns."""
    from datetime import date
    import calendar
    months     = []
    month_names = ["Jan","Feb","Mar","Apr","May","Jun",
                   "Jul","Aug","Sep","Oct","Nov","Dec"]
    today      = date.today()
    year       = today.year
    month      = today.month

    for _ in range(count):
        months.append(f"{month_names[month-1]}-{str(year)[2:]}")
        month += 1
        if month > 12:
            month = 1
            year += 1

    return months
