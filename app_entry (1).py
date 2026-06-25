"""
PARABOLIC DASHBOARD — Trade Entry (self-contained, no core imports)
"""

import streamlit as st
import pandas as pd
import gspread
import csv
import io
import pytz
from datetime import datetime
from google.oauth2.service_account import Credentials

# ── PAGE CONFIG ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Parabolic Dashboard · Entry",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── CONSTANTS ──────────────────────────────────────────────────────────────────
IST    = pytz.timezone("Asia/Kolkata")
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]
TAB_TRADES      = "TRADES"
TAB_INSTRUMENTS = "INSTRUMENTS"
TAB_STRATEGIES  = "STRATEGIES"

# ── CSS ────────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');
html, body, [class*="css"] { font-family: 'Inter', sans-serif; background:#0a0a0f; color:#e2e8f0; }
.stApp { background:#0a0a0f; }
.block-container { padding:1.5rem 2rem 3rem 2rem; max-width:1400px; }
.pb-header { display:flex; align-items:baseline; gap:12px; padding:0 0 1.5rem 0; border-bottom:1px solid #1e1e2e; margin-bottom:2rem; }
.pb-logo { font-size:1.1rem; font-weight:700; letter-spacing:0.12em; text-transform:uppercase; color:#f97316; }
.pb-sub  { font-size:0.75rem; color:#475569; letter-spacing:0.08em; text-transform:uppercase; }
.pb-panel-title { font-size:0.65rem; font-weight:600; letter-spacing:0.14em; text-transform:uppercase; color:#475569; margin-bottom:1.2rem; padding-bottom:0.6rem; border-bottom:1px solid #1e1e2e; }
.stSelectbox label, .stNumberInput label, .stTextInput label, .stDateInput label, .stTimeInput label, .stTextArea label {
    font-size:0.7rem !important; font-weight:500 !important; letter-spacing:0.08em !important;
    text-transform:uppercase !important; color:#64748b !important; margin-bottom:4px !important;
}
.stSelectbox > div > div, .stTextInput > div > div > input,
.stNumberInput > div > div > input, .stDateInput > div > div > input {
    background-color:#141420 !important; border:1px solid #252538 !important;
    border-radius:6px !important; color:#e2e8f0 !important; font-size:0.875rem !important;
}
textarea { background-color:#141420 !important; border:1px solid #252538 !important; border-radius:6px !important; color:#e2e8f0 !important; font-size:0.875rem !important; }
.stButton > button { background:transparent; border:1px solid #252538; border-radius:6px; color:#94a3b8; font-size:0.75rem; font-weight:500; padding:0.4rem 0.9rem; transition:all 0.15s; }
.stButton > button:hover { border-color:#f97316; color:#f97316; background:rgba(249,115,22,0.06); }
.stForm [data-testid="stFormSubmitButton"] > button { background:#f97316; border:none; border-radius:6px; color:#fff; font-size:0.8rem; font-weight:600; letter-spacing:0.08em; text-transform:uppercase; padding:0.55rem 1.5rem; width:100%; }
.stForm [data-testid="stFormSubmitButton"] > button:hover { background:#ea6a0a; }
.qty-pill { display:inline-flex; align-items:center; gap:6px; background:rgba(249,115,22,0.1); border:1px solid rgba(249,115,22,0.25); border-radius:20px; padding:4px 12px; font-family:'JetBrains Mono',monospace; font-size:0.8rem; color:#f97316; margin:6px 0 12px 0; }
.badge-buy  { background:rgba(34,197,94,0.12); border:1px solid rgba(34,197,94,0.3); color:#22c55e; border-radius:4px; padding:2px 8px; font-size:0.65rem; font-weight:600; }
.badge-sell { background:rgba(239,68,68,0.12); border:1px solid rgba(239,68,68,0.3); color:#ef4444; border-radius:4px; padding:2px 8px; font-size:0.65rem; font-weight:600; }
.badge-new  { background:rgba(249,115,22,0.15); border:1px solid rgba(249,115,22,0.35); color:#f97316; border-radius:4px; padding:1px 6px; font-size:0.6rem; font-weight:700; margin-left:4px; }
.trade-symbol { font-size:0.9rem; font-weight:600; color:#e2e8f0; margin-bottom:2px; }
.trade-meta   { font-size:0.72rem; color:#475569; font-family:'JetBrains Mono',monospace; }
.edit-panel   { background:#0a0a14; border:1px solid #2e2e48; border-radius:8px; padding:1rem 1.2rem; margin:4px 0 10px 0; }
.warn-box    { background:rgba(234,179,8,0.08); border-left:3px solid #eab308; border-radius:0 6px 6px 0; padding:8px 12px; font-size:0.78rem; color:#ca8a04; margin:6px 0; }
.info-box    { background:rgba(59,130,246,0.08); border-left:3px solid #3b82f6; border-radius:0 6px 6px 0; padding:8px 12px; font-size:0.78rem; color:#60a5fa; margin:6px 0; }
.success-box { background:rgba(34,197,94,0.08); border-left:3px solid #22c55e; border-radius:0 6px 6px 0; padding:8px 12px; font-size:0.78rem; color:#22c55e; margin:6px 0; }
.pb-divider  { border:none; border-top:1px solid #1e1e2e; margin:1rem 0; }
.stTabs [data-baseweb="tab-list"] { background:transparent; gap:2px; }
.stTabs [data-baseweb="tab"] { background:transparent; border:1px solid #1e1e2e; border-radius:6px; color:#64748b; font-size:0.72rem; font-weight:500; letter-spacing:0.08em; text-transform:uppercase; padding:6px 14px; }
.stTabs [aria-selected="true"] { background:rgba(249,115,22,0.1) !important; border-color:rgba(249,115,22,0.35) !important; color:#f97316 !important; }
#MainMenu, footer, header { visibility:hidden; }
.stDeployButton { display:none; }
</style>
""", unsafe_allow_html=True)


# ── GOOGLE SHEETS AUTH ─────────────────────────────────────────────────────────

@st.cache_resource(ttl=3600)
def get_client():
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

def get_ws(tab):
    return get_sheet().worksheet(tab)


# ── READ HELPERS ───────────────────────────────────────────────────────────────

@st.cache_data(ttl=60)
def read_trades():
    data = get_ws(TAB_TRADES).get_all_records()
    if not data:
        return pd.DataFrame()
    df = pd.DataFrame(data)
    if "is_deleted" in df.columns:
        df = df[df["is_deleted"].astype(str).str.upper() != "TRUE"]
    return df

@st.cache_data(ttl=60)
def read_instruments():
    data = get_ws(TAB_INSTRUMENTS).get_all_records()
    return pd.DataFrame(data) if data else pd.DataFrame()

@st.cache_data(ttl=300)
def read_strategies():
    data = get_ws(TAB_STRATEGIES).get_all_records()
    return pd.DataFrame(data) if data else pd.DataFrame()

def get_strategy_list():
    df = read_strategies()
    if df.empty or "strategy_name" not in df.columns:
        return []
    if "active" in df.columns:
        df = df[df["active"].astype(str).str.upper() == "Y"]
    return df["strategy_name"].tolist()

def get_fno_symbols():
    # No separate cache — reads from read_instruments() which has 60s TTL
    df = read_instruments()
    if df.empty or "symbol" not in df.columns:
        return []
    return sorted(df["symbol"].str.strip().tolist())

def get_lot_size(symbol):
    """Fetch lot size from INSTRUMENTS tab. Reads from cached read_instruments (60s TTL)."""
    if not symbol:
        return 1
    df = read_instruments()
    if df.empty:
        return 1
    if "symbol" not in df.columns or "lot_size" not in df.columns:
        return 1
    sym_upper = symbol.upper().strip()
    match = df[df["symbol"].str.upper().str.strip() == sym_upper]
    if match.empty:
        return 1
    try:
        val = int(str(match.iloc[0]["lot_size"]).strip())
        return val if val > 0 else 1
    except Exception:
        return 1
def append_trade(row_data):
    try:
        ws      = get_ws(TAB_TRADES)
        headers = ws.row_values(1)
        row     = [str(row_data.get(h, "")) for h in headers]
        ws.append_row(row, value_input_option="USER_ENTERED")
        read_trades.clear()
        return True
    except Exception as e:
        st.error(f"Write error: {e}")
        return False

def soft_delete_trade(trade_id):
    try:
        ws      = get_ws(TAB_TRADES)
        headers = ws.row_values(1)
        tid_col     = headers.index("trade_id") + 1
        deleted_col = headers.index("is_deleted") + 1
        for i, val in enumerate(ws.col_values(tid_col)):
            if val == str(trade_id):
                ws.update_cell(i + 1, deleted_col, "TRUE")
                read_trades.clear()
                return True
        return False
    except Exception as e:
        st.error(f"Delete error: {e}")
        return False

def update_trade_field(trade_id, field, value):
    try:
        ws      = get_ws(TAB_TRADES)
        headers = ws.row_values(1)
        tid_col   = headers.index("trade_id") + 1
        field_col = headers.index(field) + 1
        for i, val in enumerate(ws.col_values(tid_col)):
            if val == str(trade_id):
                ws.update_cell(i + 1, field_col, str(value))
                read_trades.clear()
                return True
        return False
    except Exception as e:
        st.error(f"Update error: {e}")
        return False


# ── INSTRUMENTS CSV PARSER ─────────────────────────────────────────────────────

def parse_fo_csv(csv_text):
    """
    Parse NSE fo_mktlots.csv pasted as text.
    Handles:
      - Comma-separated (direct copy from .csv file in text editor)
      - Tab-separated   (copy from Excel/Numbers)
      - Space-separated (copy from some viewers)
    Logic: col[0]=UNDERLYING, col[1]=SYMBOL, col[2]=nearest lot size
    """
    rows = []
    for line in csv_text.splitlines():
        line = line.strip()
        if not line:
            continue

        # Detect delimiter
        if ',' in line:
            parts = [p.strip() for p in line.split(',')]
        elif '\t' in line:
            parts = [p.strip() for p in line.split('\t')]
        else:
            # Space-separated: underlying name may have spaces
            # SYMBOL is always a single uppercase word, lot is a number
            # Strategy: find first numeric token — that's lot size
            # token before it is SYMBOL, everything before that is UNDERLYING
            tokens = line.split()
            # Find first digit-only token
            lot_idx = None
            for i, t in enumerate(tokens):
                if t.isdigit():
                    lot_idx = i
                    break
            if lot_idx is None or lot_idx < 2:
                continue
            # SYMBOL is the token just before lot size
            sym_idx = lot_idx - 1
            parts = [
                " ".join(tokens[:sym_idx]),   # UNDERLYING
                tokens[sym_idx],               # SYMBOL
                tokens[lot_idx],               # LOT SIZE
            ]

        if len(parts) < 3:
            continue

        underlying = parts[0].strip()
        symbol     = parts[1].strip()
        lot_str    = parts[2].strip()

        if not symbol or symbol.lower() in ("symbol", "underlying", ""):
            continue
        if not lot_str or not lot_str.isdigit():
            continue
        if underlying.lower().startswith("derivatives on individual"):
            continue

        rows.append({
            "symbol":          symbol,
            "underlying":      underlying,
            "lot_size":        int(lot_str),
            "exchange":        "NSE",
            "instrument_type": "FUT_OPT",
            "last_updated":    now_ist().strftime("%Y-%m-%d %H:%M"),
        })
    return rows

def write_instruments(parsed_rows):
    try:
        ws = get_ws(TAB_INSTRUMENTS)
        # Clear all data rows safely (never touches row 1 header)
        all_values = ws.get_all_values()
        if len(all_values) > 1:
            # Clear from row 2 to last row
            last_row = len(all_values)
            ws.batch_clear([f"A2:Z{last_row}"])
        # Write new data
        data = [[r["symbol"], r["underlying"], r["lot_size"],
                 r["exchange"], r["instrument_type"], r["last_updated"]]
                for r in parsed_rows]
        ws.append_rows(data, value_input_option="USER_ENTERED")
        read_instruments.clear()
        get_fno_symbols.cache_clear() if hasattr(get_fno_symbols, 'cache_clear') else None
        return True, f"✅ {len(data)} symbols written to INSTRUMENTS tab. Reload the page to see updated dropdown."
    except Exception as e:
        return False, f"❌ {e}"


# ── UTILS ──────────────────────────────────────────────────────────────────────

def now_ist():
    return datetime.now(IST)

def generate_trade_id():
    return now_ist().strftime("TRD-%Y%m%d-%H%M%S")

def build_expiry_months(n=6):
    months = []
    base = now_ist()
    for i in range(n):
        month = (base.month - 1 + i) % 12 + 1
        year  = base.year + (base.month - 1 + i) // 12
        months.append(datetime(year, month, 1).strftime("%b-%y").upper())
    return months

def badge(action):
    cls = "badge-buy" if action == "BUY" else "badge-sell"
    return f'<span class="{cls}">{action}</span>'


# ── SESSION STATE ──────────────────────────────────────────────────────────────
if "edit_trade_id" not in st.session_state:
    st.session_state.edit_trade_id = None


# ══════════════════════════════════════════════════════════════════════════════
# PAGE
# ══════════════════════════════════════════════════════════════════════════════

st.markdown("""
<div class="pb-header">
    <span class="pb-logo">⚡ ParabolicTrends</span>
    <span class="pb-sub">Trade Entry</span>
</div>
""", unsafe_allow_html=True)


# ── INSTRUMENTS UPDATER ────────────────────────────────────────────────────────
# Instruments panel — auto-collapse after successful upload
if "inst_expanded" not in st.session_state:
    st.session_state.inst_expanded = True

df_inst = read_instruments()
inst_count = len(df_inst) if not df_inst.empty else 0
inst_last  = df_inst["last_updated"].iloc[0] if (not df_inst.empty and "last_updated" in df_inst.columns) else None

# Show compact status bar when collapsed
if inst_count > 0:
    st.markdown(
        f'<div style="font-size:0.72rem;color:#475569;margin-bottom:6px;">'
        f'F&O Instruments: <span style="color:#f97316">{inst_count} symbols</span>'
        f'{" · updated " + inst_last if inst_last else ""}'
        f' &nbsp;·&nbsp; <span style="color:#3b82f6;cursor:pointer;" '
        f'onclick="">click below to update</span></div>',
        unsafe_allow_html=True
    )

with st.expander("🔧 Update F&O Lot Sizes", expanded=st.session_state.inst_expanded and inst_count == 0):
    st.markdown(
        '<div style="font-size:0.78rem;color:#64748b;margin-bottom:10px;">'
        'Download <code>fo_mktlots.csv</code> from NSE quarterly → '
        'upload the file directly below → click Update.</div>',
        unsafe_allow_html=True
    )

    uploaded_file = st.file_uploader(
        "Select fo_mktlots.csv", type=["csv"],
        label_visibility="collapsed"
    )

    ca, cb = st.columns([1, 4])
    if ca.button("⬆ Update Instruments"):
        if uploaded_file is not None:
            raw_text = uploaded_file.read().decode("utf-8", errors="replace")
            parsed = parse_fo_csv(raw_text)
            if parsed:
                ok, msg = write_instruments(parsed)
                st.markdown(
                    f'<div class="{"success-box" if ok else "warn-box"}">{msg}</div>',
                    unsafe_allow_html=True
                )
                if ok:
                    st.session_state.inst_expanded = False
                    st.rerun()
            else:
                st.markdown('<div class="warn-box">⚠️ No valid rows found in file.</div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="warn-box">⚠️ Select the fo_mktlots.csv file first.</div>', unsafe_allow_html=True)

    if inst_count > 0:
        cb.markdown(
            f'<div style="font-size:0.72rem;color:#475569;padding-top:0.6rem;">' +
            f'{inst_count} symbols loaded · {inst_last}</div>',
            unsafe_allow_html=True
        )
st.markdown("<div class='pb-divider'></div>", unsafe_allow_html=True)


# ── MAIN COLUMNS ──────────────────────────────────────────────────────────────
col_form, col_trades = st.columns([1, 1.4], gap="large")


# ══════════════════════════════════════════════════════
# LEFT — ENTRY FORM
# ══════════════════════════════════════════════════════
with col_form:
    st.markdown('<div class="pb-panel-title">New Trade</div>', unsafe_allow_html=True)

    strategies  = get_strategy_list()
    fno_symbols = get_fno_symbols()

    if not strategies:
        st.markdown('<div class="warn-box">No strategies — check STRATEGIES tab in Google Sheet.</div>', unsafe_allow_html=True)
    else:
        with st.form("entry_form", clear_on_submit=True):

            strategy = st.selectbox("Strategy", strategies)

            c1, c2 = st.columns(2)
            exchange   = c1.selectbox("Exchange", ["NSE", "BSE", "MCX"])
            instrument = c2.selectbox("Instrument", ["FUT", "OPT", "CASH"])

            # Symbol
            if instrument == "CASH":
                symbol   = st.text_input("Symbol", placeholder="e.g. RELIANCE").upper().strip()
                expiry   = ""
                strike   = 0
                opt_type = ""
            else:
                if fno_symbols:
                    symbol = st.selectbox("Symbol", fno_symbols)
                else:
                    symbol = st.text_input(
                        "Symbol (no F&O list yet — paste CSV above)",
                        placeholder="e.g. NIFTY"
                    ).upper().strip()

                c3, c4, c5 = st.columns(3)
                expiry = c3.selectbox("Expiry", build_expiry_months(6))
                if instrument == "OPT":
                    strike   = c4.number_input("Strike", min_value=0, step=50, value=0)
                    opt_type = c5.selectbox("CE / PE", ["CE", "PE"])
                else:
                    strike   = 0
                    opt_type = ""

            # Lot size — always fetch fresh (cache TTL=60s)
            lot_size = 1
            if instrument != "CASH" and symbol:
                lot_size = get_lot_size(symbol)

            # Action row
            c6, c7 = st.columns(2)
            action = c6.selectbox("Action", ["BUY", "SELL"])

            # Lots / Quantity
            if instrument == "CASH":
                quantity = c7.number_input("Quantity (shares)", min_value=1, step=1, value=1)
                lots     = 0
            else:
                lots     = c7.number_input("Lots", min_value=1, step=1, value=1)
                quantity = lots * lot_size

            # Quantity display row — always visible
            if instrument != "CASH":
                cq1, cq2, cq3 = st.columns(3)
                cq1.markdown(
                    f'<div style="font-size:0.65rem;color:#64748b;text-transform:uppercase;'
                    f'letter-spacing:0.08em;margin-bottom:4px;">Lot Size</div>'
                    f'<div style="font-size:1rem;font-weight:600;color:'
                    f'{"#f97316" if lot_size > 1 else "#ef4444"};font-family:JetBrains Mono,monospace;">'
                    f'{lot_size if lot_size > 1 else "NOT FOUND"}</div>',
                    unsafe_allow_html=True
                )
                cq2.markdown(
                    f'<div style="font-size:0.65rem;color:#64748b;text-transform:uppercase;'
                    f'letter-spacing:0.08em;margin-bottom:4px;">Total Qty</div>'
                    f'<div style="font-size:1rem;font-weight:600;color:#e2e8f0;font-family:JetBrains Mono,monospace;">'
                    f'{quantity:,} shares</div>',
                    unsafe_allow_html=True
                )
                cq3.markdown(
                    f'<div style="font-size:0.65rem;color:#64748b;text-transform:uppercase;'
                    f'letter-spacing:0.08em;margin-bottom:4px;">= Lots × Size</div>'
                    f'<div style="font-size:1rem;font-weight:600;color:#64748b;font-family:JetBrains Mono,monospace;">'
                    f'{lots} × {lot_size}</div>',
                    unsafe_allow_html=True
                )
                if lot_size == 1 and symbol:
                    st.markdown(
                        f'<div class="warn-box">⚠️ <b>{symbol}</b> lot size not found. '
                        f'Upload fo_mktlots.csv → click Update Instruments → then re-select symbol.</div>',
                        unsafe_allow_html=True
                    )

            # Date / Time
            c8, c9 = st.columns(2)
            now       = now_ist()
            trade_date = c8.date_input("Trade Date", value=now.date())
            trade_time = c9.time_input("Trade Time", value=now.time().replace(second=0, microsecond=0))

            is_backdated = trade_date < now.date()
            if is_backdated:
                st.markdown(
                    '<div class="info-box">↩ Backdated entry — enter price manually.</div>',
                    unsafe_allow_html=True
                )

            # Price
            c10, c11 = st.columns([1.2, 1])
            manual = c11.checkbox("Manual price", value=True)
            price  = c10.number_input("Price ₹", min_value=0.0, step=0.05, format="%.2f", value=0.0)
            price_source = "MANUAL"

            if not manual and not is_backdated and instrument != "CASH":
                # Try AngelOne LTP
                try:
                    from core.angelone import get_ltp
                    ltp = get_ltp(symbol, exchange, instrument)
                    if ltp:
                        price        = ltp
                        price_source = "ANGELONE_LTP"
                        st.markdown(
                            f'<div class="success-box">LTP fetched: ₹{ltp:,.2f}</div>',
                            unsafe_allow_html=True
                        )
                except Exception:
                    st.markdown(
                        '<div class="warn-box">AngelOne unavailable — enter price manually.</div>',
                        unsafe_allow_html=True
                    )

            notes = st.text_area("Notes", height=56, placeholder="Setup, SL, reason...")

            submitted = st.form_submit_button("LOG TRADE →")

        if submitted:
            if not symbol:
                st.markdown('<div class="warn-box">⚠️ Symbol required.</div>', unsafe_allow_html=True)
            elif price <= 0:
                st.markdown('<div class="warn-box">⚠️ Enter a valid price.</div>', unsafe_allow_html=True)
            else:
                ok = append_trade({
                    "trade_id":        generate_trade_id(),
                    "timestamp_entry": now_ist().strftime("%Y-%m-%d %H:%M:%S"),
                    "trade_date":      str(trade_date),
                    "trade_time":      str(trade_time),
                    "strategy":        strategy,
                    "exchange":        exchange,
                    "instrument":      instrument,
                    "symbol":          symbol,
                    "expiry":          expiry,
                    "strike":          strike if strike else "",
                    "option_type":     opt_type,
                    "action":          action,
                    "lots_qty":        lots if instrument != "CASH" else quantity,
                    "quantity":        int(quantity),
                    "price":           price,
                    "price_source":    price_source,
                    "lot_size":        lot_size,
                    "notes":           notes,
                    "is_deleted":      "FALSE",
                    "punched_by":      "SELF",
                })
                if ok:
                    st.markdown(
                        f'<div class="success-box">✅ Logged — {action} {symbol} '
                        f'{"@ " + str(lots) + " lots" if instrument != "CASH" else str(int(quantity)) + " shares"} '
                        f'@ ₹{price:,.2f}</div>',
                        unsafe_allow_html=True
                    )


# ══════════════════════════════════════════════════════
# RIGHT — OPEN TRADES
# ══════════════════════════════════════════════════════
with col_trades:
    st.markdown('<div class="pb-panel-title">Open Trades</div>', unsafe_allow_html=True)

    r1, r2, r3 = st.columns([1, 1, 4])
    if r1.button("↻ Refresh"):
        read_trades.clear()
        st.rerun()
    if r2.button("⟳ Clear Cache"):
        read_trades.clear()
        read_instruments.clear()
        read_strategies.clear()
        st.rerun()

    df = read_trades()
    today_str = now_ist().strftime("%Y-%m-%d")

    # ── POSITION METRICS ──
    if not df.empty:
        # Aggregate stats from what we have (LTP from AngelOne if available)
        total_trades  = len(df)
        buy_trades    = len(df[df["action"].astype(str).str.upper() == "BUY"]) if "action" in df.columns else 0
        sell_trades   = total_trades - buy_trades

        # Try fetch LTP for each open position via AngelOne
        ltp_map = {}
        try:
            from core.angelone import get_ltp
            for _, row in df.iterrows():
                sym   = str(row.get("symbol",""))
                exch  = str(row.get("exchange","NSE"))
                instr = str(row.get("instrument","FUT"))
                if sym and sym not in ltp_map:
                    ltp = get_ltp(sym, exch, instr)
                    if ltp:
                        ltp_map[sym] = ltp
        except Exception:
            pass

        # Calculate MTM where LTP available
        mtm_total = 0.0
        for _, row in df.iterrows():
            sym      = str(row.get("symbol",""))
            entry_px = float(row.get("price", 0) or 0)
            qty      = float(row.get("quantity", 0) or 0)
            action   = str(row.get("action","BUY")).upper()
            if sym in ltp_map and qty > 0 and entry_px > 0:
                ltp = ltp_map[sym]
                pnl = (ltp - entry_px) * qty if action == "BUY" else (entry_px - ltp) * qty
                mtm_total += pnl

        mtm_color = "#22c55e" if mtm_total >= 0 else "#ef4444"
        mtm_sign  = "+" if mtm_total >= 0 else ""
        ltp_avail = len(ltp_map)

        st.markdown(f"""
        <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin-bottom:1rem;">
            <div style="background:#0f0f1a;border:1px solid #1e1e2e;border-radius:7px;padding:10px 12px;">
                <div style="font-size:0.6rem;color:#475569;letter-spacing:0.1em;text-transform:uppercase;margin-bottom:4px;">Open Positions</div>
                <div style="font-size:1.2rem;font-weight:700;color:#e2e8f0;font-family:'JetBrains Mono',monospace;">{total_trades}</div>
                <div style="font-size:0.65rem;color:#475569;">{buy_trades}L · {sell_trades}S</div>
            </div>
            <div style="background:#0f0f1a;border:1px solid #1e1e2e;border-radius:7px;padding:10px 12px;">
                <div style="font-size:0.6rem;color:#475569;letter-spacing:0.1em;text-transform:uppercase;margin-bottom:4px;">MTM P&L</div>
                <div style="font-size:1.2rem;font-weight:700;color:{mtm_color};font-family:'JetBrains Mono',monospace;">
                    {"—" if ltp_avail == 0 else f"{mtm_sign}₹{abs(mtm_total):,.0f}"}
                </div>
                <div style="font-size:0.65rem;color:#475569;">{"LTP not available — add AngelOne" if ltp_avail == 0 else f"{ltp_avail} LTPs fetched"}</div>
            </div>
            <div style="background:#0f0f1a;border:1px solid #1e1e2e;border-radius:7px;padding:10px 12px;">
                <div style="font-size:0.6rem;color:#475569;letter-spacing:0.1em;text-transform:uppercase;margin-bottom:4px;">Margin Used</div>
                <div style="font-size:1.2rem;font-weight:700;color:#e2e8f0;font-family:'JetBrains Mono',monospace;">—</div>
                <div style="font-size:0.65rem;color:#475569;">SPAN via AngelOne</div>
            </div>
            <div style="background:#0f0f1a;border:1px solid #1e1e2e;border-radius:7px;padding:10px 12px;">
                <div style="font-size:0.6rem;color:#475569;letter-spacing:0.1em;text-transform:uppercase;margin-bottom:4px;">Today's Trades</div>
                <div style="font-size:1.2rem;font-weight:700;color:#f97316;font-family:'JetBrains Mono',monospace;">
                    {len(df[df["trade_date"].astype(str) == today_str]) if "trade_date" in df.columns else 0}
                </div>
                <div style="font-size:0.65rem;color:#475569;">entries today</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # Per-trade LTP row
        if ltp_map:
            ltp_html = ""
            for sym, ltp in ltp_map.items():
                ltp_html += (
                    f'<span style="font-size:0.7rem;font-family:JetBrains Mono,monospace;' +
                    f'background:#0f0f1a;border:1px solid #1e1e2e;border-radius:4px;' +
                    f'padding:3px 8px;margin:2px;display:inline-block;">' +
                    f'<span style="color:#64748b">{sym}</span> ' +
                    f'<span style="color:#e2e8f0">₹{ltp:,.2f}</span></span>'
                )
            st.markdown(
                f'<div style="margin-bottom:10px;">{ltp_html}</div>',
                unsafe_allow_html=True
            )

    if df.empty:
        st.markdown(
            '<div style="color:#475569;font-size:0.82rem;padding:2rem 0;text-align:center;">'
            'No trades logged yet.</div>',
            unsafe_allow_html=True
        )
    else:
        if "timestamp_entry" in df.columns:
            df = df.sort_values("timestamp_entry", ascending=False)

        for _, row in df.iterrows():
            tid       = str(row.get("trade_id", ""))
            sym       = str(row.get("symbol", ""))
            act       = str(row.get("action", ""))
            instr     = str(row.get("instrument", ""))
            expiry_v  = str(row.get("expiry", ""))
            strike_v  = str(row.get("strike", ""))
            opt_v     = str(row.get("option_type", ""))
            lots_v    = str(row.get("lots_qty", ""))
            qty_v     = str(row.get("quantity", ""))
            price_v   = row.get("price", 0)
            strat_v   = str(row.get("strategy", ""))
            date_v    = str(row.get("trade_date", ""))

            desc = sym
            if expiry_v: desc += f" {expiry_v}"
            if strike_v and strike_v not in ("", "0"): desc += f" {strike_v}{opt_v}"

            new_badge = '<span class="badge-new">NEW</span>' if date_v == today_str else ""
            try:
                pf = f"₹{float(price_v):,.2f}"
            except Exception:
                pf = str(price_v)

            qty_info = f"{lots_v} lots · {qty_v} sh" if instr != "CASH" else f"{qty_v} shares"
            is_editing = (st.session_state.edit_trade_id == tid)

            ci, cb2 = st.columns([3, 1])
            with ci:
                st.markdown(
                    f'<div class="trade-symbol">{badge(act)} &nbsp;{desc}{new_badge}</div>'
                    f'<div class="trade-meta">{strat_v} · {qty_info} · {pf}</div>'
                    f'<div class="trade-meta">{date_v}</div>',
                    unsafe_allow_html=True
                )
            with cb2:
                b1, b2 = st.columns(2)
                if b1.button("✏", key=f"e_{tid}", help="Edit"):
                    st.session_state.edit_trade_id = None if is_editing else tid
                    st.rerun()
                if b2.button("✕", key=f"d_{tid}", help="Delete"):
                    soft_delete_trade(tid)
                    st.session_state.edit_trade_id = None
                    st.rerun()

            if is_editing:
                with st.container():
                    st.markdown('<div class="edit-panel">', unsafe_allow_html=True)
                    ec1, ec2, ec3 = st.columns(3)
                    try:
                        dv = datetime.strptime(date_v, "%Y-%m-%d").date()
                    except Exception:
                        dv = now_ist().date()
                    new_date  = ec1.date_input("Date",     value=dv,             key=f"ed_{tid}")
                    new_price = ec2.number_input("Price ₹", min_value=0.0, step=0.05,
                                                 format="%.2f", value=float(price_v) if price_v else 0.0,
                                                 key=f"ep_{tid}")
                    new_lots  = ec3.number_input("Lots/Qty", min_value=1, step=1,
                                                 value=int(lots_v) if str(lots_v).isdigit() else 1,
                                                 key=f"el_{tid}")
                    s1, s2 = st.columns(2)
                    if s1.button("Save", key=f"sv_{tid}"):
                        update_trade_field(tid, "trade_date", str(new_date))
                        update_trade_field(tid, "price", new_price)
                        update_trade_field(tid, "lots_qty", new_lots)
                        st.session_state.edit_trade_id = None
                        st.rerun()
                    if s2.button("Cancel", key=f"cx_{tid}"):
                        st.session_state.edit_trade_id = None
                        st.rerun()
                    st.markdown('</div>', unsafe_allow_html=True)

            st.markdown("<div style='margin-bottom:4px'></div>", unsafe_allow_html=True)
