"""
PARABOLIC DASHBOARD — Trade Entry (fully self-contained)
"""

import streamlit as st
import pandas as pd
import gspread
import csv
import io
import pytz
from datetime import datetime
from google.oauth2.service_account import Credentials

st.set_page_config(page_title="ParabolicTrends · Entry", page_icon="⚡", layout="wide", initial_sidebar_state="collapsed")

IST    = pytz.timezone("Asia/Kolkata")
SCOPES = ["https://www.googleapis.com/auth/spreadsheets","https://www.googleapis.com/auth/drive"]
TAB_TRADES      = "TRADES"
TAB_INSTRUMENTS = "INSTRUMENTS"
TAB_STRATEGIES  = "STRATEGIES"

# ── CSS ──────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');
html,body,[class*="css"]{font-family:'Inter',sans-serif;background:#0a0a0f;color:#e2e8f0;}
.stApp{background:#0a0a0f;}
.block-container{padding:1.5rem 2rem 3rem 2rem;max-width:1400px;}
.pb-header{display:flex;align-items:baseline;gap:12px;padding:0 0 1.2rem 0;border-bottom:1px solid #1e1e2e;margin-bottom:1.5rem;}
.pb-logo{font-size:1.1rem;font-weight:700;letter-spacing:0.12em;text-transform:uppercase;color:#f97316;}
.pb-sub{font-size:0.75rem;color:#475569;letter-spacing:0.08em;text-transform:uppercase;}
.pb-panel-title{font-size:0.65rem;font-weight:600;letter-spacing:0.14em;text-transform:uppercase;color:#475569;margin-bottom:1rem;padding-bottom:0.5rem;border-bottom:1px solid #1e1e2e;}
/* inputs */
.stSelectbox label,.stNumberInput label,.stTextInput label,.stDateInput label,.stTimeInput label,.stTextArea label{font-size:0.68rem!important;font-weight:500!important;letter-spacing:0.08em!important;text-transform:uppercase!important;color:#64748b!important;margin-bottom:3px!important;}
.stSelectbox>div>div,.stTextInput>div>div>input,.stNumberInput>div>div>input,.stDateInput>div>div>input{background:#141420!important;border:1px solid #252538!important;border-radius:6px!important;color:#e2e8f0!important;font-size:0.875rem!important;}
textarea{background:#141420!important;border:1px solid #252538!important;border-radius:6px!important;color:#e2e8f0!important;font-size:0.875rem!important;}
/* buttons */
.stButton>button{background:transparent;border:1px solid #252538;border-radius:6px;color:#94a3b8;font-size:0.75rem;font-weight:500;padding:0.4rem 0.9rem;transition:all 0.15s;}
.stButton>button:hover{border-color:#f97316;color:#f97316;background:rgba(249,115,22,0.06);}
.stForm [data-testid="stFormSubmitButton"]>button{background:#f97316;border:none;border-radius:6px;color:#fff;font-size:0.8rem;font-weight:600;letter-spacing:0.08em;text-transform:uppercase;padding:0.55rem 1.5rem;width:100%;}
.stForm [data-testid="stFormSubmitButton"]>button:hover{background:#ea6a0a;}
/* badges */
.badge-buy{background:rgba(34,197,94,0.12);border:1px solid rgba(34,197,94,0.3);color:#22c55e;border-radius:4px;padding:2px 8px;font-size:0.65rem;font-weight:600;}
.badge-sell{background:rgba(239,68,68,0.12);border:1px solid rgba(239,68,68,0.3);color:#ef4444;border-radius:4px;padding:2px 8px;font-size:0.65rem;font-weight:600;}
.badge-new{background:rgba(249,115,22,0.15);border:1px solid rgba(249,115,22,0.35);color:#f97316;border-radius:4px;padding:1px 6px;font-size:0.6rem;font-weight:700;margin-left:4px;}
/* stat box */
.stat-box{background:#0f0f1a;border:1px solid #1e1e2e;border-radius:7px;padding:10px 14px;}
.stat-label{font-size:0.6rem;color:#475569;letter-spacing:0.1em;text-transform:uppercase;margin-bottom:4px;}
.stat-value{font-size:1.15rem;font-weight:700;font-family:'JetBrains Mono',monospace;}
.stat-sub{font-size:0.65rem;color:#475569;margin-top:2px;}
/* qty box */
.qty-box{background:#0f0f1a;border:1px solid #252538;border-radius:6px;padding:10px 14px;margin:8px 0;}
.qty-label{font-size:0.65rem;color:#64748b;text-transform:uppercase;letter-spacing:0.08em;margin-bottom:4px;}
.qty-value{font-size:1rem;font-weight:600;font-family:'JetBrains Mono',monospace;}
/* trade row */
.trade-row{padding:10px 14px;background:#0f0f1a;border:1px solid #1e1e2e;border-radius:7px;margin-bottom:6px;}
.trade-row:hover{border-color:#2e2e48;}
.trade-symbol{font-size:0.9rem;font-weight:600;color:#e2e8f0;margin-bottom:2px;}
.trade-meta{font-size:0.72rem;color:#475569;font-family:'JetBrains Mono',monospace;}
.edit-panel{background:#0a0a14;border:1px solid #2e2e48;border-radius:8px;padding:1rem 1.2rem;margin:4px 0 10px 0;}
/* alerts */
.warn-box{background:rgba(234,179,8,0.08);border-left:3px solid #eab308;border-radius:0 6px 6px 0;padding:8px 12px;font-size:0.78rem;color:#ca8a04;margin:6px 0;}
.info-box{background:rgba(59,130,246,0.08);border-left:3px solid #3b82f6;border-radius:0 6px 6px 0;padding:8px 12px;font-size:0.78rem;color:#60a5fa;margin:6px 0;}
.success-box{background:rgba(34,197,94,0.08);border-left:3px solid #22c55e;border-radius:0 6px 6px 0;padding:8px 12px;font-size:0.78rem;color:#22c55e;margin:6px 0;}
.divider{border:none;border-top:1px solid #1e1e2e;margin:1rem 0;}
#MainMenu,footer,header{visibility:hidden;}
.stDeployButton{display:none;}
</style>
""", unsafe_allow_html=True)


# ── GOOGLE SHEETS ─────────────────────────────────────────────────────────────

@st.cache_resource(ttl=3600)
def get_client():
    raw = dict(st.secrets["gcp_service_account"])
    pk  = str(raw.get("private_key","")).replace("\\n","\n")
    if not pk.endswith("\n"): pk += "\n"
    raw["private_key"] = pk
    return gspread.authorize(Credentials.from_service_account_info(raw, scopes=SCOPES))

def get_ws(tab):
    return get_client().open_by_key(st.secrets["app"]["sheet_id"]).worksheet(tab)


# ── DATA READS (cached) ───────────────────────────────────────────────────────

@st.cache_data(ttl=30)
def read_trades():
    data = get_ws(TAB_TRADES).get_all_records()
    if not data: return pd.DataFrame()
    df = pd.DataFrame(data)
    if "is_deleted" in df.columns:
        df = df[df["is_deleted"].astype(str).str.upper() != "TRUE"]
    return df

def read_instruments():
    """Always read fresh — sheet is small (216 rows), stale cache breaks lot size lookup."""
    try:
        data = get_ws(TAB_INSTRUMENTS).get_all_records()
        return pd.DataFrame(data) if data else pd.DataFrame()
    except Exception:
        return pd.DataFrame()

@st.cache_data(ttl=300)
def read_strategies():
    data = get_ws(TAB_STRATEGIES).get_all_records()
    return pd.DataFrame(data) if data else pd.DataFrame()

def get_strategy_list():
    df = read_strategies()
    if df.empty or "strategy_name" not in df.columns: return []
    if "active" in df.columns:
        df = df[df["active"].astype(str).str.upper() == "Y"]
    return df["strategy_name"].tolist()

def get_fno_symbols():
    df = read_instruments()
    if df.empty or "symbol" not in df.columns: return []
    return sorted(df["symbol"].str.strip().tolist())

def get_lot_size(symbol: str) -> int:
    if not symbol: return 1
    df = read_instruments()
    if df.empty or "symbol" not in df.columns or "lot_size" not in df.columns: return 1
    match = df[df["symbol"].str.upper().str.strip() == symbol.upper().strip()]
    if match.empty: return 1
    try:
        v = int(str(match.iloc[0]["lot_size"]).strip())
        return v if v > 0 else 1
    except: return 1


# ── WRITES ────────────────────────────────────────────────────────────────────

def append_trade(row_data):
    try:
        ws      = get_ws(TAB_TRADES)
        headers = ws.row_values(1)
        ws.append_row([str(row_data.get(h,"")) for h in headers], value_input_option="USER_ENTERED")
        read_trades.clear()
        return True
    except Exception as e:
        st.error(f"Write error: {e}"); return False

def soft_delete_trade(trade_id):
    try:
        ws = get_ws(TAB_TRADES)
        headers = ws.row_values(1)
        ti = headers.index("trade_id")+1
        di = headers.index("is_deleted")+1
        for i,v in enumerate(ws.col_values(ti)):
            if v == str(trade_id):
                ws.update_cell(i+1, di, "TRUE")
                read_trades.clear(); return True
        return False
    except Exception as e:
        st.error(f"Delete error: {e}"); return False

def update_trade_field(trade_id, field, value):
    try:
        ws = get_ws(TAB_TRADES)
        headers = ws.row_values(1)
        ti = headers.index("trade_id")+1
        fi = headers.index(field)+1
        for i,v in enumerate(ws.col_values(ti)):
            if v == str(trade_id):
                ws.update_cell(i+1, fi, str(value))
                read_trades.clear(); return True
        return False
    except Exception as e:
        st.error(f"Update error: {e}"); return False


# ── CSV PARSER ────────────────────────────────────────────────────────────────

def parse_fo_csv(text: str) -> list:
    """Parse NSE fo_mktlots.csv — handles comma, tab, and space-separated formats."""
    rows = []
    for line in text.splitlines():
        line = line.strip()
        if not line: continue
        if "," in line:
            parts = [p.strip() for p in line.split(",")]
        elif "\t" in line:
            parts = [p.strip() for p in line.split("\t")]
        else:
            tokens = line.split()
            lot_idx = next((i for i,t in enumerate(tokens) if t.isdigit()), None)
            if lot_idx is None or lot_idx < 2: continue
            parts = [" ".join(tokens[:lot_idx-1]), tokens[lot_idx-1], tokens[lot_idx]]
        if len(parts) < 3: continue
        underlying, symbol, lot_str = parts[0].strip(), parts[1].strip(), parts[2].strip()
        if not symbol or symbol.lower() in ("symbol","underlying",""): continue
        if not lot_str or not lot_str.isdigit(): continue
        if underlying.lower().startswith("derivatives on individual"): continue
        rows.append({
            "symbol": symbol, "underlying": underlying,
            "lot_size": int(lot_str), "exchange": "NSE",
            "instrument_type": "FUT_OPT",
            "last_updated": now_ist().strftime("%d-%m-%Y %H:%M"),
        })
    return rows

def write_instruments(parsed_rows: list) -> tuple:
    try:
        ws = get_ws(TAB_INSTRUMENTS)
        all_vals = ws.get_all_values()
        if len(all_vals) > 1:
            ws.batch_clear([f"A2:Z{len(all_vals)}"])
        data = [[r["symbol"],r["underlying"],r["lot_size"],
                 r["exchange"],r["instrument_type"],r["last_updated"]]
                for r in parsed_rows]
        ws.append_rows(data, value_input_option="USER_ENTERED")
        return True, f"✅ {len(data)} F&O symbols loaded — {now_ist().strftime('%d-%m-%Y %H:%M')}"
    except Exception as e:
        return False, f"❌ {e}"


# ── UTILS ─────────────────────────────────────────────────────────────────────

def now_ist():
    return datetime.now(IST)

def generate_trade_id():
    return now_ist().strftime("TRD-%Y%m%d-%H%M%S")

def build_expiry_months(n=6):
    months = []
    base = now_ist()
    for i in range(n):
        month = (base.month-1+i)%12+1
        year  = base.year+(base.month-1+i)//12
        months.append(datetime(year,month,1).strftime("%b-%y").upper())
    return months

def badge(action):
    cls = "badge-buy" if action=="BUY" else "badge-sell"
    return f'<span class="{cls}">{action}</span>'

def fmt_price(v):
    try: return f"₹{float(v):,.2f}"
    except: return str(v)


# ── SESSION STATE ─────────────────────────────────────────────────────────────
if "edit_id" not in st.session_state:  st.session_state.edit_id = None
if "inst_done" not in st.session_state: st.session_state.inst_done = False


# ══════════════════════════════════════════════════════════════════════════════
# HEADER
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("""
<div class="pb-header">
    <span class="pb-logo">⚡ ParabolicTrends</span>
    <span class="pb-sub">Trade Entry</span>
</div>""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# INSTRUMENTS PANEL
# ══════════════════════════════════════════════════════════════════════════════
df_inst    = read_instruments()
inst_count = len(df_inst) if not df_inst.empty else 0
inst_last  = df_inst["last_updated"].iloc[0] if (not df_inst.empty and "last_updated" in df_inst.columns) else ""

# Always show status line
status_color = "#f97316" if inst_count > 0 else "#ef4444"
status_text  = f"{inst_count} F&O symbols loaded · {inst_last}" if inst_count > 0 else "No F&O symbols — upload fo_mktlots.csv below"
st.markdown(
    f'<div style="font-size:0.72rem;color:{status_color};margin-bottom:6px;">'
    f'📋 {status_text}</div>',
    unsafe_allow_html=True
)

# Expander — open by default if no symbols loaded, collapsed otherwise
with st.expander("🔧 Update F&O Lot Sizes", expanded=(inst_count == 0)):
    st.markdown(
        '<div style="font-size:0.78rem;color:#64748b;margin-bottom:10px;">'
        'Download <b>fo_mktlots.csv</b> from NSE → select the file below → click Update Instruments.</div>',
        unsafe_allow_html=True
    )
    uploaded = st.file_uploader("fo_mktlots.csv", type=["csv"], label_visibility="collapsed")

    if st.button("⬆ Update Instruments", type="primary" if uploaded else "secondary"):
        if uploaded:
            raw = uploaded.read().decode("utf-8", errors="replace")
            parsed = parse_fo_csv(raw)
            if parsed:
                ok, msg = write_instruments(parsed)
                if ok:
                    st.markdown(f'<div class="success-box">{msg}</div>', unsafe_allow_html=True)
                    st.rerun()
                else:
                    st.markdown(f'<div class="warn-box">{msg}</div>', unsafe_allow_html=True)
            else:
                st.markdown('<div class="warn-box">⚠️ Could not parse file — check it is the NSE fo_mktlots.csv</div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="warn-box">⚠️ Select fo_mktlots.csv first</div>', unsafe_allow_html=True)

st.markdown("<div class='divider'></div>", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# MAIN COLUMNS
# ══════════════════════════════════════════════════════════════════════════════
col_form, col_trades = st.columns([1, 1.4], gap="large")


# ══════════════════════════════════════════════════════
# LEFT — ENTRY FORM
# ══════════════════════════════════════════════════════
with col_form:
    st.markdown('<div class="pb-panel-title">New Trade</div>', unsafe_allow_html=True)

    strategies  = get_strategy_list()
    fno_symbols = get_fno_symbols()

    if not strategies:
        st.markdown('<div class="warn-box">No strategies found — check STRATEGIES tab in Google Sheet.</div>', unsafe_allow_html=True)
    else:
        with st.form("entry_form", clear_on_submit=True):

            # Strategy
            strategy = st.selectbox("Strategy", strategies)

            # Exchange + Instrument
            c1, c2 = st.columns(2)
            exchange   = c1.selectbox("Exchange", ["NSE","BSE","MCX"])
            instrument = c2.selectbox("Instrument", ["FUT","OPT","CASH"])

            # Symbol
            if instrument == "CASH":
                symbol   = st.text_input("Symbol", placeholder="e.g. RELIANCE").upper().strip()
                expiry   = ""
                strike   = 0
                opt_type = ""
            else:
                if fno_symbols:
                    symbol = st.selectbox(
                        "Symbol",
                        fno_symbols,
                        key=f"sym_{instrument}_{exchange}"
                    )
                else:
                    symbol = st.text_input(
                        "Symbol (upload F&O list above first)",
                        placeholder="e.g. NIFTY"
                    ).upper().strip()

                c3, c4, c5 = st.columns(3)
                expiry = c3.selectbox("Expiry", build_expiry_months(6))
                if instrument == "OPT":
                    strike   = c4.number_input("Strike", min_value=0, step=50, value=0)
                    opt_type = c5.selectbox("CE / PE", ["CE","PE"])
                else:
                    strike   = 0
                    opt_type = ""

            # Lot size — always fresh, no cache on read_instruments
            lot_size = 1
            if instrument != "CASH" and symbol and symbol != "—":
                lot_size = get_lot_size(symbol)

            # Action + Lots
            c6, c7 = st.columns(2)
            action = c6.selectbox("Action", ["BUY","SELL"])

            if instrument == "CASH":
                quantity = c7.number_input("Quantity (shares)", min_value=1, step=1, value=1)
                lots     = 0
            else:
                lots     = c7.number_input("Lots", min_value=1, step=1, value=1)
                quantity = lots * lot_size

            # ── QTY BREAKDOWN — always visible for F&O ──
            if instrument != "CASH":
                qa, qb, qc = st.columns(3)
                # Lot Size
                ls_color = "#f97316" if lot_size > 1 else "#ef4444"
                ls_val   = str(lot_size) if lot_size > 1 else "NOT FOUND"
                qa.markdown(
                    f'<div class="qty-box">'
                    f'<div class="qty-label">Lot Size</div>'
                    f'<div class="qty-value" style="color:{ls_color};">{ls_val}</div>'
                    f'</div>', unsafe_allow_html=True
                )
                # Lots × Size
                qb.markdown(
                    f'<div class="qty-box">'
                    f'<div class="qty-label">Lots × Size</div>'
                    f'<div class="qty-value" style="color:#94a3b8;">{lots} × {lot_size}</div>'
                    f'</div>', unsafe_allow_html=True
                )
                # Total Qty
                qty_color = "#22c55e" if lot_size > 1 else "#ef4444"
                qc.markdown(
                    f'<div class="qty-box">'
                    f'<div class="qty-label">Total Quantity</div>'
                    f'<div class="qty-value" style="color:{qty_color};">{quantity:,} shares</div>'
                    f'</div>', unsafe_allow_html=True
                )
                if lot_size == 1 and symbol:
                    total_inst = len(read_instruments())
                    st.markdown(
                        f'<div class="warn-box">⚠️ <b>{symbol}</b> lot size not found. '
                        f'({total_inst} symbols in sheet) — '
                        f'{"Try scrolling the Symbol dropdown to re-select" if total_inst > 0 else "Upload fo_mktlots.csv first"}.</div>',
                        unsafe_allow_html=True
                    )

            # Date + Time
            c8, c9 = st.columns(2)
            now        = now_ist()
            trade_date = c8.date_input("Trade Date", value=now.date())
            trade_time = c9.time_input("Trade Time", value=now.time().replace(second=0, microsecond=0))

            is_back = trade_date < now.date()
            if is_back:
                st.markdown('<div class="info-box">↩ Backdated entry — enter price manually.</div>', unsafe_allow_html=True)

            # Price
            c10, c11 = st.columns([1.5, 1])
            manual = c11.checkbox("Manual price", value=True)
            price  = c10.number_input("Price ₹", min_value=0.0, step=0.05, format="%.2f", value=0.0)
            price_source = "MANUAL"

            if not manual and not is_back and instrument != "CASH":
                try:
                    from core.angelone import get_ltp
                    ltp = get_ltp(symbol, exchange, instrument)
                    if ltp and ltp > 0:
                        price        = ltp
                        price_source = "ANGELONE_LTP"
                        st.markdown(f'<div class="success-box">LTP: ₹{ltp:,.2f}</div>', unsafe_allow_html=True)
                    else:
                        st.markdown('<div class="warn-box">AngelOne returned no price — enter manually.</div>', unsafe_allow_html=True)
                except Exception as ex:
                    st.markdown(f'<div class="warn-box">AngelOne unavailable ({ex}) — enter manually.</div>', unsafe_allow_html=True)

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
                    qty_desc = f"{lots} lots ({quantity:,} shares)" if instrument != "CASH" else f"{int(quantity):,} shares"
                    st.markdown(
                        f'<div class="success-box">✅ {action} {symbol} — {qty_desc} @ {fmt_price(price)}</div>',
                        unsafe_allow_html=True
                    )


# ══════════════════════════════════════════════════════
# RIGHT — OPEN TRADES
# ══════════════════════════════════════════════════════
with col_trades:
    st.markdown('<div class="pb-panel-title">Open Trades</div>', unsafe_allow_html=True)

    rb1, rb2 = st.columns([1, 5])
    if rb1.button("↻ Refresh"):
        read_trades.clear()
        st.rerun()

    df = read_trades()
    today_str = now_ist().strftime("%Y-%m-%d")

    # ── METRICS ROW ──
    if not df.empty:
        total  = len(df)
        buys   = len(df[df["action"].astype(str).str.upper()=="BUY"]) if "action" in df.columns else 0
        sells  = total - buys
        todays = len(df[df["trade_date"].astype(str)==today_str]) if "trade_date" in df.columns else 0

        # Try AngelOne LTP
        ltp_map = {}
        try:
            from core.angelone import get_ltp
            for _, row in df.iterrows():
                sym = str(row.get("symbol",""))
                if sym and sym not in ltp_map:
                    ltp = get_ltp(sym, str(row.get("exchange","NSE")), str(row.get("instrument","FUT")))
                    if ltp and ltp > 0:
                        ltp_map[sym] = ltp
        except Exception:
            pass

        # MTM
        mtm = 0.0
        for _, row in df.iterrows():
            sym = str(row.get("symbol",""))
            if sym in ltp_map:
                ep  = float(row.get("price",0) or 0)
                qty = float(row.get("quantity",0) or 0)
                act = str(row.get("action","BUY")).upper()
                ltp = ltp_map[sym]
                mtm += ((ltp-ep)*qty) if act=="BUY" else ((ep-ltp)*qty)

        mtm_col  = "#22c55e" if mtm >= 0 else "#ef4444"
        mtm_sign = "+" if mtm >= 0 else ""
        mtm_str  = f"{mtm_sign}₹{abs(mtm):,.0f}" if ltp_map else "—"
        mtm_sub  = f"{len(ltp_map)} LTPs live" if ltp_map else "Add AngelOne credentials"

        m1, m2, m3, m4 = st.columns(4)
        m1.markdown(f'<div class="stat-box"><div class="stat-label">Positions</div><div class="stat-value" style="color:#e2e8f0">{total}</div><div class="stat-sub">{buys}L · {sells}S</div></div>', unsafe_allow_html=True)
        m2.markdown(f'<div class="stat-box"><div class="stat-label">MTM P&L</div><div class="stat-value" style="color:{mtm_col}">{mtm_str}</div><div class="stat-sub">{mtm_sub}</div></div>', unsafe_allow_html=True)
        m3.markdown(f'<div class="stat-box"><div class="stat-label">Margin Used</div><div class="stat-value" style="color:#e2e8f0">—</div><div class="stat-sub">SPAN via AngelOne</div></div>', unsafe_allow_html=True)
        m4.markdown(f'<div class="stat-box"><div class="stat-label">Today</div><div class="stat-value" style="color:#f97316">{todays}</div><div class="stat-sub">trades today</div></div>', unsafe_allow_html=True)

        # LTP chips
        if ltp_map:
            chips = "".join(
                f'<span style="font-size:0.7rem;font-family:JetBrains Mono,monospace;'
                f'background:#0f0f1a;border:1px solid #1e1e2e;border-radius:4px;'
                f'padding:3px 8px;margin:2px 3px 2px 0;display:inline-block;">'
                f'<span style="color:#64748b">{s}</span> '
                f'<span style="color:#e2e8f0">₹{v:,.2f}</span></span>'
                for s,v in ltp_map.items()
            )
            st.markdown(f'<div style="margin:8px 0 12px 0;">{chips}</div>', unsafe_allow_html=True)

        st.markdown("<div class='divider'></div>", unsafe_allow_html=True)

    if df.empty:
        st.markdown('<div style="color:#475569;font-size:0.82rem;padding:2rem 0;text-align:center;">No trades logged yet.</div>', unsafe_allow_html=True)
    else:
        if "timestamp_entry" in df.columns:
            df = df.sort_values("timestamp_entry", ascending=False)

        for _, row in df.iterrows():
            tid    = str(row.get("trade_id",""))
            sym    = str(row.get("symbol",""))
            act    = str(row.get("action",""))
            instr  = str(row.get("instrument",""))
            exp_v  = str(row.get("expiry",""))
            stk_v  = str(row.get("strike",""))
            opt_v  = str(row.get("option_type",""))
            lots_v = str(row.get("lots_qty",""))
            qty_v  = str(row.get("quantity",""))
            px_v   = row.get("price",0)
            strat  = str(row.get("strategy",""))
            dt_v   = str(row.get("trade_date",""))
            ls_v   = str(row.get("lot_size",""))

            # descriptor
            desc = sym
            if exp_v: desc += f" {exp_v}"
            if stk_v and stk_v not in ("","0"): desc += f" {stk_v}{opt_v}"
            new_b = '<span class="badge-new">NEW</span>' if dt_v == today_str else ""

            # qty info with lot size
            if instr != "CASH":
                # Use current lot size from instruments sheet, fall back to stored
                current_ls = get_lot_size(sym)
                display_ls = current_ls if current_ls > 1 else (int(ls_v) if str(ls_v).isdigit() and int(ls_v) > 1 else "?")
                current_qty = int(lots_v) * current_ls if (str(lots_v).isdigit() and current_ls > 1) else qty_v
                qty_info = f"{lots_v} lots × {display_ls} = {current_qty} sh"
            else:
                qty_info = f"{qty_v} shares"

            # LTP chip for this symbol
            ltp_chip = ""
            if sym in ltp_map:
                lv = ltp_map[sym]
                try:
                    ep   = float(px_v)
                    qty  = float(qty_v)
                    pnl  = (lv-ep)*qty if act.upper()=="BUY" else (ep-lv)*qty
                    pc   = "#22c55e" if pnl>=0 else "#ef4444"
                    sign = "+" if pnl>=0 else ""
                    ltp_chip = (f'<span style="font-family:JetBrains Mono,monospace;font-size:0.7rem;color:#94a3b8;"> '
                                f'LTP ₹{lv:,.2f} · '
                                f'<span style="color:{pc}">{sign}₹{abs(pnl):,.0f}</span></span>')
                except Exception:
                    ltp_chip = f'<span style="font-size:0.7rem;color:#94a3b8;"> LTP ₹{lv:,.2f}</span>'

            is_editing = (st.session_state.edit_id == tid)

            ci, cb2 = st.columns([3,1])
            with ci:
                st.markdown(
                    f'<div class="trade-symbol">{badge(act)} &nbsp;{desc}{new_b}</div>'
                    f'<div class="trade-meta">{strat} · {qty_info}{ltp_chip}</div>'
                    f'<div class="trade-meta">{dt_v} · {fmt_price(px_v)}</div>',
                    unsafe_allow_html=True
                )
            with cb2:
                b1, b2 = st.columns(2)
                if b1.button("✏", key=f"e_{tid}", help="Edit"):
                    st.session_state.edit_id = None if is_editing else tid
                    st.rerun()
                if b2.button("✕", key=f"d_{tid}", help="Delete"):
                    soft_delete_trade(tid)
                    st.session_state.edit_id = None
                    st.rerun()

            if is_editing:
                st.markdown('<div class="edit-panel">', unsafe_allow_html=True)
                ea, eb, ec = st.columns(3)
                try:    dv = datetime.strptime(dt_v, "%Y-%m-%d").date()
                except: dv = now_ist().date()
                new_date  = ea.date_input("Date",     value=dv,                  key=f"ed_{tid}")
                new_price = eb.number_input("Price ₹", min_value=0.0, step=0.05,
                                            format="%.2f",
                                            value=float(px_v) if px_v else 0.0,  key=f"ep_{tid}")
                new_lots  = ec.number_input("Lots",    min_value=1, step=1,
                                            value=int(lots_v) if str(lots_v).isdigit() else 1,
                                            key=f"el_{tid}")
                s1, s2 = st.columns(2)
                if s1.button("Save", key=f"sv_{tid}"):
                    update_trade_field(tid,"trade_date",str(new_date))
                    update_trade_field(tid,"price",new_price)
                    update_trade_field(tid,"lots_qty",new_lots)
                    # recalculate quantity
                    ls = get_lot_size(sym)
                    update_trade_field(tid,"quantity", new_lots * ls if instr!="CASH" else new_lots)
                    st.session_state.edit_id = None
                    st.rerun()
                if s2.button("Cancel", key=f"cx_{tid}"):
                    st.session_state.edit_id = None
                    st.rerun()
                st.markdown('</div>', unsafe_allow_html=True)

            st.markdown("<div style='margin-bottom:4px'></div>", unsafe_allow_html=True)
