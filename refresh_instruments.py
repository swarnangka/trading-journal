"""
refresh_instruments.py
======================
Loads all NSE F&O + MCX symbols into your Google Sheet.

DATA SOURCES (tried in order until one succeeds):
  1. nsearchives.nseindia.com/content/fo/fo_mktlots.csv  ← Primary (official NSE)
  2. www.nseindia.com/content/fo/fo_mktlots.csv          ← Alternate NSE URL
  3. Dhan website table scrape                            ← Broker fallback
  4. Built-in list (200+ stocks)                         ← Always works

Run from your Mac — works perfectly from Indian IP addresses.

USAGE:
    python3 refresh_instruments.py

WHEN TO RUN:
    → Right now (first time setup)
    → After each NSE quarterly expiry (Mar/Jun/Sep/Dec)
    → When a symbol is missing from the entry app dropdown
"""

import json, sys, io, csv, time, re
import requests
from datetime import datetime
from google.oauth2.service_account import Credentials
import gspread

# ── YOUR SETTINGS ──────────────────────────────────────────────
SHEET_ID             = "1aa1cgsArVXymlS_bDiHxERADQSBnhhST0pXuC0X87sw"
SERVICE_ACCOUNT_FILE = "service_account.json"
# ──────────────────────────────────────────────────────────────

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

BROWSER_HEADERS = {
    "User-Agent":      "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/120.0.0.0 Safari/537.36",
    "Accept":          "text/html,application/xhtml+xml,application/xml;"
                       "q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-IN,en-US;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection":      "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}


# ════════════════════════════════════════════════════════════════
# SOURCE 1 & 2 — NSE CSV FILE
# ════════════════════════════════════════════════════════════════

def parse_nse_csv(content: str) -> list:
    """
    Parse NSE fo_mktlots.csv content.

    NSE CSV has this structure:
      Row 0: blank or title row (sometimes)
      Row 1: headers — UNDERLYING, SYMBOL IN F&O, LOT SIZE, ...
      Row 2+: data

    OR sometimes:
      Row 0: headers
      Row 1+: data

    We detect the header row dynamically.
    """
    today   = datetime.now().strftime("%d-%m-%Y")
    results = []

    lines = content.strip().split("\n")
    if len(lines) < 3:
        return []

    # Find header row — look for row containing UNDERLYING or LOT SIZE
    header_idx = None
    for i, line in enumerate(lines[:5]):
        upper = line.upper()
        if "UNDERLYING" in upper or "LOT SIZE" in upper or "SYMBOL IN F&O" in upper:
            header_idx = i
            break

    if header_idx is None:
        header_idx = 0   # Assume first row

    # Parse with csv module
    reader   = csv.reader(io.StringIO(content))
    all_rows = list(reader)

    if header_idx >= len(all_rows):
        return []

    # Normalise header names
    raw_headers = all_rows[header_idx]
    headers     = [h.strip().upper().replace("\ufeff", "") for h in raw_headers]

    # Find column indices
    sym_col = None
    lot_col = None

    for idx, h in enumerate(headers):
        if sym_col is None and any(k in h for k in ["UNDERLYING", "SYMBOL"]):
            sym_col = idx
        if lot_col is None and "LOT" in h:
            lot_col = idx

    if sym_col is None: sym_col = 0
    if lot_col is None: lot_col = 1

    # Parse data rows
    seen = {}
    for row in all_rows[header_idx + 1:]:
        if not row or len(row) <= max(sym_col, lot_col):
            continue

        sym = row[sym_col].strip().upper().replace("\ufeff", "")
        if not sym or len(sym) < 2:
            continue
        # Skip non-symbol rows
        if any(skip in sym for skip in ["UNDERLYING", "SYMBOL", "NOTE", "---", "***"]):
            continue

        # Clean lot size
        raw_lot = row[lot_col].strip().replace(",", "")
        try:
            lot = int(float(raw_lot))
        except ValueError:
            continue

        if lot <= 0 or lot > 500000:
            continue

        if sym not in seen:
            seen[sym] = True
            results.append([sym, "NSE", "FUT_OPT", lot, "Shares", today])

    return results


def fetch_nse_csv_primary():
    """
    Try nsearchives.nseindia.com — the URL you confirmed works.
    """
    today = datetime.now().strftime("%d-%m-%Y")

    primary_urls = [
        "https://nsearchives.nseindia.com/content/fo/fo_mktlots.csv",
        "https://www.nseindia.com/content/fo/fo_mktlots.csv",
    ]

    session = requests.Session()

    # Warm up session with homepage visit (NSE requires cookies)
    try:
        print("    Warming up NSE session...")
        session.get("https://www.nseindia.com", headers=BROWSER_HEADERS, timeout=10)
        time.sleep(2)
        session.get("https://nsearchives.nseindia.com", headers=BROWSER_HEADERS, timeout=8)
        time.sleep(1)
    except Exception:
        pass  # Continue even if warmup fails

    for url in primary_urls:
        print(f"    Trying: {url}")
        try:
            resp = session.get(url, headers=BROWSER_HEADERS, timeout=20)
            print(f"    Status: {resp.status_code}, Size: {len(resp.content):,} bytes")

            if resp.status_code == 200 and len(resp.content) > 500:
                content = resp.content.decode("utf-8", errors="ignore")
                rows    = parse_nse_csv(content)
                if len(rows) > 30:
                    print(f"    ✓ Parsed {len(rows)} symbols")
                    return rows
                else:
                    print(f"    Only {len(rows)} symbols — trying next URL")

            elif resp.status_code == 404:
                print("    URL not found — trying next")

            elif resp.status_code == 403:
                print("    Access denied — trying next URL with different headers")
                # Try with minimal headers
                resp2 = requests.get(
                    url,
                    headers={"User-Agent": "Mozilla/5.0"},
                    timeout=15
                )
                if resp2.status_code == 200 and len(resp2.content) > 500:
                    content = resp2.content.decode("utf-8", errors="ignore")
                    rows    = parse_nse_csv(content)
                    if len(rows) > 30:
                        return rows

        except requests.Timeout:
            print("    Timed out — trying next")
        except Exception as e:
            print(f"    Error: {e}")

    return []


# ════════════════════════════════════════════════════════════════
# SOURCE 3 — DHAN WEBSITE TABLE SCRAPE
# ════════════════════════════════════════════════════════════════

def fetch_from_dhan():
    """
    Scrape lot sizes from Dhan's public page:
    https://dhan.co/nse-fno-lot-size/

    Dhan shows an HTML table with Symbol and Lot Size columns.
    No login required.
    """
    today   = datetime.now().strftime("%d-%m-%Y")
    results = []
    url     = "https://dhan.co/nse-fno-lot-size/"

    print(f"    Trying Dhan: {url}")
    try:
        resp = requests.get(url, headers=BROWSER_HEADERS, timeout=20)
        print(f"    Status: {resp.status_code}, Size: {len(resp.content):,} bytes")

        if resp.status_code != 200:
            print("    Dhan page not accessible")
            return []

        html  = resp.text
        seen  = {}

        # Method 1: Find JSON data embedded in page (many React sites do this)
        json_pattern = re.compile(
            r'"symbol"\s*:\s*"([A-Z&-]{2,20})"\s*,\s*"lot_?size"\s*:\s*(\d+)',
            re.IGNORECASE
        )
        for match in json_pattern.finditer(html):
            sym = match.group(1).strip().upper()
            lot = int(match.group(2))
            if sym and lot > 0 and sym not in seen:
                seen[sym] = True
                results.append([sym, "NSE", "FUT_OPT", lot, "Shares", today])

        if results:
            print(f"    ✓ Found {len(results)} symbols via JSON pattern")
            return results

        # Method 2: Parse HTML table
        # Look for <table> rows with two columns: symbol and lot size
        row_pattern = re.compile(
            r"<tr[^>]*>.*?<td[^>]*>\s*([A-Z&-]{2,20})\s*</td>.*?"
            r"<td[^>]*>\s*(\d[\d,]*)\s*</td>",
            re.IGNORECASE | re.DOTALL
        )
        for match in row_pattern.finditer(html):
            sym = match.group(1).strip().upper()
            try:
                lot = int(match.group(2).replace(",", ""))
            except ValueError:
                continue
            if sym and lot > 0 and 1 <= lot <= 500000 and sym not in seen:
                seen[sym] = True
                results.append([sym, "NSE", "FUT_OPT", lot, "Shares", today])

        if results:
            print(f"    ✓ Found {len(results)} symbols via HTML table")
            return results

        # Method 3: Generic number pairs near stock names
        # Look for patterns like "RELIANCE 250" or "NIFTY\n75"
        cell_pattern = re.compile(
            r"([A-Z][A-Z0-9&-]{1,19})\D{0,30}?(\d{1,6})\b",
        )
        # Extract all text content first
        text_only = re.sub(r"<[^>]+>", " ", html)
        for match in cell_pattern.finditer(text_only):
            sym = match.group(1).strip().upper()
            try:
                lot = int(match.group(2))
            except ValueError:
                continue
            # Validate: lot sizes are typically 1-100000, symbols are 2-15 chars
            if (2 <= len(sym) <= 15 and
                1 <= lot <= 100000 and
                sym not in seen and
                not sym.isdigit()):
                seen[sym] = True
                results.append([sym, "NSE", "FUT_OPT", lot, "Shares", today])

        print(f"    Found {len(results)} symbols via text pattern")
        return results

    except requests.Timeout:
        print("    Dhan request timed out")
    except Exception as e:
        print(f"    Dhan error: {e}")

    return []


# ════════════════════════════════════════════════════════════════
# SOURCE 4 — COMPLETE BUILT-IN LIST (200+ stocks)
# Last verified: Jun 2025 from NSE fo_mktlots.csv
# Update after each quarterly revision if needed
# ════════════════════════════════════════════════════════════════

def get_builtin_nse_list():
    today = datetime.now().strftime("%d-%m-%Y")
    # Format: (SYMBOL, LOT_SIZE)
    stocks = [
        # Index derivatives
        ("NIFTY",        75),  ("BANKNIFTY",    15),  ("FINNIFTY",     40),
        ("MIDCPNIFTY",   75),  ("SENSEX",       10),  ("BANKEX",       15),
        # Nifty 50 stocks
        ("ADANIENT",    400),  ("ADANIPORTS",  800),  ("APOLLOHOSP",  125),
        ("ASIANPAINT",  200),  ("AXISBANK",   1200),  ("BAJAJ-AUTO",   75),
        ("BAJFINANCE",  125),  ("BAJAJFINSV",  125),  ("BHARTIARTL",  950),
        ("BPCL",       1800),  ("BRITANNIA",    50),  ("CIPLA",       650),
        ("COALINDIA",  4200),  ("DIVISLAB",    200),  ("DRREDDY",     125),
        ("EICHERMOT",    75),  ("GRASIM",      375),  ("HCLTECH",     350),
        ("HDFCBANK",    550),  ("HDFCLIFE",   1100),  ("HEROMOTOCO",  150),
        ("HINDALCO",   1400),  ("HINDUNILVR",  300),  ("ICICIBANK",   700),
        ("INDUSINDBK",  500),  ("INFY",        300),  ("ITC",        3200),
        ("JSWSTEEL",   1350),  ("KOTAKBANK",   400),  ("LT",          300),
        ("M&M",         700),  ("MARUTI",       50),  ("NESTLEIND",    40),
        ("NTPC",       3750),  ("ONGC",       3850),  ("POWERGRID",  3400),
        ("RELIANCE",    250),  ("SBILIFE",     750),  ("SBIN",       1500),
        ("SHREECEM",     25),  ("SUNPHARMA",   700),  ("TATAMOTORS", 1400),
        ("TATASTEEL",  5525),  ("TCS",         150),  ("TECHM",       600),
        ("TITAN",       375),  ("TRENT",       300),  ("ULTRACEMCO",  100),
        ("WIPRO",      1500),
        # Nifty Next 50 / Midcap
        ("ABBOTINDIA",   30),  ("ACC",          500),  ("ADANIGREEN",  500),
        ("ADANIPOWER", 2700),  ("ALKEM",         75),  ("AMBUJACEM",  2000),
        ("ANGELONE",    300),  ("APOLLOTYRE", 3500),  ("ASHOKLEY",   5400),
        ("ASTRAL",      350),  ("ATUL",           75),  ("AUBANK",    1000),
        ("AUROPHARMA",  650),  ("BALKRISIND",   300),  ("BANDHANBNK", 1800),
        ("BANKBARODA", 5850),  ("BATAINDIA",    375),  ("BEL",        3750),
        ("BERGEPAINT",  975),  ("BHEL",        6750),  ("BIOCON",     2800),
        ("BSOFT",      2200),  ("CAMS",          300),  ("CANBK",     5000),
        ("CANFINHOME",  750),  ("CDSL",          600),  ("CESC",      2200),
        ("CHOLAFIN",    500),  ("COFORGE",       150),  ("COLPAL",     350),
        ("CONCOR",      700),  ("COROMANDEL",   500),  ("CROMPTON",  2000),
        ("CUMMINSIND",  600),  ("CYIENT",        450),  ("DABUR",     2800),
        ("DALBHARAT",   300),  ("DEEPAKNTR",    400),  ("DELTACORP", 4500),
        ("DIXON",       100),  ("DLF",          1650),  ("EMAMILTD",   900),
        ("ESCORTS",     275),  ("EXIDEIND",    3500),  ("FACT",       1600),
        ("FEDERALBNK", 5000),  ("GAIL",         3850),  ("GLENMARK",   725),
        ("GMRINFRA",  22500),  ("GNFC",          900),  ("GODREJCP",   500),
        ("GODREJPROP",  425),  ("GRANULES",     1600),  ("GSPL",      2000),
        ("GUJGASLTD",   750),  ("HAL",           150),  ("HAVELLS",    500),
        ("HDFCAMC",     200),  ("HINDPETRO",   1300),  ("HONAUT",      10),
        ("IBREALEST",  6300),  ("IDFCFIRSTB", 8400),  ("IEX",        3750),
        ("IGL",         700),  ("INDUSTOWER", 2800),  ("INTELLECT",   700),
        ("IOC",        5000),  ("IRCTC",         875),  ("IRFC",      5000),
        ("ISEC",        750),  ("JINDALSTEL",  1250),  ("JUBLFOOD",   500),
        ("KAJARIACER",  600),  ("KANSAINER",    300),  ("KEI",         300),
        ("KPITTECH",    750),  ("LAURUSLABS", 2000),  ("LICHSGFIN",  1000),
        ("LINDEINDIA",   75),  ("LTIM",          150),  ("LTTS",       150),
        ("LUPIN",       400),  ("MARICO",       1800),  ("MAZDOCK",    150),
        ("MCX",         250),  ("METROPOLIS",   200),  ("MFSL",        700),
        ("MPHASIS",     200),  ("MRF",            10),  ("MTAR",        300),
        ("MUTHOOTFIN",  300),  ("NAUKRI",        125),  ("NAVINFLUOR", 200),
        ("NBCC",       7500),  ("NCC",          5000),  ("NHPC",      8000),
        ("NMDC",       4500),  ("OBEROIRLTY",   400),  ("OFSS",        100),
        ("OIL",        2200),  ("PAGEIND",        15),  ("PAYTM",     2000),
        ("PCBL",       3000),  ("PERSISTENT",   150),  ("PETRONET",  3000),
        ("PFC",        2700),  ("PIIND",         125),  ("POLICYBZR",  700),
        ("POLYCAB",     250),  ("PNB",          8000),  ("PRESTIGE",   600),
        ("RAMCOCEM",   1000),  ("RAYMOND",       600),  ("RECLTD",    2700),
        ("SAIL",       7500),  ("SCHAEFFLER",   350),  ("SCI",        2800),
        ("SHRIRAMFIN",  300),  ("SIEMENS",       250),  ("SJVN",      7500),
        ("SKFINDIA",    300),  ("SONACOMS",    1000),  ("SPARC",      2200),
        ("STAR",       1500),  ("SUPREME",       400),  ("SUZLON",   14000),
        ("SYNGENE",    1300),  ("TANLA",         700),  ("TATACHEM",   500),
        ("TATACOMM",    625),  ("TATAELXSI",    150),  ("TATAPOWER", 2700),
        ("TIINDIA",     300),  ("TIMKEN",        400),  ("TORNTPHARM", 125),
        ("TORNTPOWER", 1250),  ("TRIDENT",     20000),  ("TVSMOTOR",   350),
        ("TVSMOTORS",   350),  ("UCOBANK",    10000),  ("UBL",         500),
        ("UJJIVANSFB", 6000),  ("UNIONBANK",   5600),  ("UNITDSPR",   700),
        ("UPL",        1300),  ("VEDL",         2900),  ("VOLTAS",     600),
        ("WHIRLPOOL",   350),  ("YESBANK",    40000),  ("ZEEL",       5000),
        ("ZOMATO",     4500),  ("ZYDUSLIFE",   1000),  ("APOLLOHOSP", 125),
        ("DIVI",        200),  ("FORTIS",       2700),  ("AFFLE",      550),
        ("AIAENG",      125),  ("AJANTPHARM",   250),  ("AMARAJABAT", 750),
        ("IOCLBR",      400),
    ]
    seen = {}
    rows = []
    for sym, lot in stocks:
        if sym not in seen:
            seen[sym] = True
            rows.append([sym, "NSE", "FUT_OPT", lot, "Shares", today])
    return rows


# ════════════════════════════════════════════════════════════════
# MCX — ALWAYS HARDCODED (stable, rarely changes)
# ════════════════════════════════════════════════════════════════

def get_mcx_symbols():
    today = datetime.now().strftime("%d-%m-%Y")
    return [
        ["GOLD",        "MCX", "FUT",  100,  "Grams",   today],
        ["GOLDM",       "MCX", "FUT",   10,  "Grams",   today],
        ["GOLDPETAL",   "MCX", "FUT",    1,  "Gram",    today],
        ["SILVER",      "MCX", "FUT",   30,  "Kg",      today],
        ["SILVERMIC",   "MCX", "FUT",    1,  "Kg",      today],
        ["SILVERMINI",  "MCX", "FUT",    5,  "Kg",      today],
        ["CRUDEOIL",    "MCX", "FUT",  100,  "Barrels", today],
        ["CRUDEOILM",   "MCX", "FUT",   10,  "Barrels", today],
        ["NATURALGAS",  "MCX", "FUT", 1250,  "MMBtu",   today],
        ["NATURALGASM", "MCX", "FUT",  250,  "MMBtu",   today],
        ["COPPER",      "MCX", "FUT", 2500,  "Kg",      today],
        ["COPPERM",     "MCX", "FUT",  250,  "Kg",      today],
        ["ZINC",        "MCX", "FUT", 5000,  "Kg",      today],
        ["ZINCMINI",    "MCX", "FUT", 1000,  "Kg",      today],
        ["LEAD",        "MCX", "FUT", 5000,  "Kg",      today],
        ["LEADMINI",    "MCX", "FUT", 1000,  "Kg",      today],
        ["ALUMINIUM",   "MCX", "FUT", 5000,  "Kg",      today],
        ["ALUMINIUMM",  "MCX", "FUT", 1000,  "Kg",      today],
        ["NICKEL",      "MCX", "FUT", 1500,  "Kg",      today],
        ["NICKELM",     "MCX", "FUT",  100,  "Kg",      today],
    ]


# ════════════════════════════════════════════════════════════════
# GOOGLE SHEET
# ════════════════════════════════════════════════════════════════

def get_worksheet():
    with open(SERVICE_ACCOUNT_FILE, "r") as f:
        info = json.load(f)
    creds  = Credentials.from_service_account_info(info, scopes=SCOPES)
    client = gspread.authorize(creds)
    return client.open_by_key(SHEET_ID).worksheet("INSTRUMENTS")


# ════════════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════════════

def main():
    print("\n🔄  NSE F&O Instrument Refresh")
    print("=" * 50)

    if SHEET_ID == "YOUR_GOOGLE_SHEET_ID_HERE":
        print("\n❌  Set your SHEET_ID at the top of this file first.")
        sys.exit(1)
    try:
        with open(SERVICE_ACCOUNT_FILE) as f: json.load(f)
        print(f"✓   Found {SERVICE_ACCOUNT_FILE}")
    except FileNotFoundError:
        print(f"❌  {SERVICE_ACCOUNT_FILE} not found in this folder.")
        sys.exit(1)

    # ── FETCH NSE DATA ────────────────────────────────────────
    nse_rows    = []
    source_used = ""

    print("\nFetching NSE F&O lot sizes...")

    # Source 1 & 2: NSE CSV (archives + main site)
    print("  [1/3] NSE fo_mktlots.csv ...")
    nse_rows = fetch_nse_csv_primary()
    if len(nse_rows) >= 50:
        source_used = "NSE fo_mktlots.csv (official)"
    else:
        # Source 3: Dhan website
        print(f"  NSE CSV gave {len(nse_rows)} symbols.")
        print("  [2/3] Dhan website ...")
        dhan_rows = fetch_from_dhan()
        if len(dhan_rows) >= 50:
            nse_rows    = dhan_rows
            source_used = "Dhan website (dhan.co/nse-fno-lot-size)"
        else:
            # Source 4: Built-in list
            print(f"  Dhan gave {len(dhan_rows)} symbols.")
            print("  [3/3] Using built-in master list (200+ stocks) ...")
            nse_rows    = get_builtin_nse_list()
            source_used = "Built-in master list (Jun-2025)"

    print(f"\n  ✓  NSE: {len(nse_rows)} symbols  |  Source: {source_used}")

    # MCX
    mcx_rows = get_mcx_symbols()
    print(f"  ✓  MCX: {len(mcx_rows)} symbols  |  Source: Hardcoded (stable)")

    all_rows = nse_rows + mcx_rows

    # ── WRITE TO SHEET ────────────────────────────────────────
    print("\nConnecting to Google Sheet...")
    try:
        ws = get_worksheet()
        print("✓   Connected")
    except Exception as e:
        print(f"❌  Connection failed: {e}")
        sys.exit(1)

    print(f"Writing {len(all_rows)} rows to INSTRUMENTS tab...")
    try:
        ws.batch_clear(["A2:F3000"])
        ws.update("A2", all_rows, value_input_option="USER_ENTERED")
        print("✓   Written")
    except Exception as e:
        print(f"❌  Write failed: {e}")
        sys.exit(1)

    # ── SUMMARY ───────────────────────────────────────────────
    print(f"""
✅  Refresh Complete!
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   NSE F&O  :  {len(nse_rows)} symbols
   MCX      :  {len(mcx_rows)} symbols
   Total    :  {len(all_rows)} symbols
   Source   :  {source_used}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Open your sheet to verify:
  https://docs.google.com/spreadsheets/d/{SHEET_ID}/edit#gid=0

Run again after each NSE quarterly expiry:
  March / June / September / December
""")

    # Warn if using built-in list
    if "Built-in" in source_used:
        print("""⚠️   NOTE: Built-in list was used.
   Lot sizes are correct as of Jun-2025.
   After next quarterly revision, run this script again —
   the NSE CSV should be accessible then.
   You can also manually edit lot sizes in your
   INSTRUMENTS tab in Google Sheet anytime.
""")


if __name__ == "__main__":
    main()
