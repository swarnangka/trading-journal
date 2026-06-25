"""PARABOLIC DASHBOARD — Trade Entry"""

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

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');
html,body,[class*="css"]{font-family:'Inter',sans-serif;background:#0a0a0f;color:#e2e8f0;}
.stApp{background:#0a0a0f;}
.block-container{padding:1.5rem 2rem 3rem 2rem;max-width:1400px;}
.pb-header{display:flex;align-items:baseline;gap:12px;padding:0 0 1.2rem 0;border-bottom:1px solid #1e1e2e;margin-bottom:1.5rem;}
.pb-logo{font-size:1.1rem;font-weight:700;letter-spacing:0.12em;text-transform:uppercase;color:#f97316;}
.pb-sub{font-size:0.75rem;color:#475569;letter-spacing:0.08em;text-transform:uppercase;}
.section-title{font-size:0.65rem;font-weight:600;letter-spacing:0.14em;text-transform:uppercase;color:#475569;margin-bottom:1rem;padding-bottom:0.5rem;border-bottom:1px solid #1e1e2e;}
.stSelectbox label,.stNumberInput label,.stTextInput label,.stDateInput label,.stTimeInput label,.stTextArea label,.stCheckbox label{font-size:0.68rem!important;font-weight:500!important;letter-spacing:0.08em!important;text-transform:uppercase!important;color:#64748b!important;}
.stSelectbox>div>div,.stTextInput>div>div>input,.stNumberInput>div>div>input,.stDateInput>div>div>input{background:#141420!important;border:1px solid #252538!important;border-radius:6px!important;color:#e2e8f0!important;font-size:0.875rem!important;}
textarea{background:#141420!important;border:1px solid #252538!important;border-radius:6px!important;color:#e2e8f0!important;}
.stButton>button{background:transparent;border:1px solid #252538;border-radius:6px;color:#94a3b8;font-size:0.75rem;padding:0.4rem 0.9rem;transition:all 0.15s;}
.stButton>button:hover{border-color:#f97316;color:#f97316;background:rgba(249,115,22,0.06);}
.stForm [data-testid="stFormSubmitButton"]>button{background:#f97316;border:none;border-radius:6px;color:#fff;font-size:0.8rem;font-weight:600;letter-spacing:0.08em;text-transform:uppercase;padding:0.55rem 1.5rem;width:100%;}
.badge-buy{background:rgba(34,197,94,0.12);border:1px solid rgba(34,197,94,0.3);color:#22c55e;border-radius:4px;padding:2px 8px;font-size:0.65rem;font-weight:600;}
.badge-sell{background:rgba(239,68,68,0.12);border:1px solid rgba(239,68,68,0.3);color:#ef4444;border-radius:4px;padding:2px 8px;font-size:0.65rem;font-weight:600;}
.badge-new{background:rgba(249,115,22,0.15);border:1px solid rgba(249,115,22,0.35);color:#f97316;border-radius:4px;padding:1px 6px;font-size:0.6rem;font-weight:700;margin-left:4px;}
.qty-box{background:#0f0f1a;border:1px solid #1e1e2e;border-radius:6px;padding:10px 14px;margin-top:8px;}
.qty-label{font-size:0.6rem;color:#64748b;text-transform:uppercase;letter-spacing:0.08em;margin-bottom:4px;}
.qty-value{font-size:1rem;font-weight:700;font-family:'JetBrains Mono',monospace;}
.stat-box{background:#0f0f1a;border:1px solid #1e1e2e;border-radius:7px;padding:10px 14px;}
.stat-label{font-size:0.6rem;color:#475569;letter-spacing:0.1em;text-transform:uppercase;margin-bottom:4px;}
.stat-value{font-size:1.15rem;font-weight:700;font-family:'JetBrains Mono',monospace;}
.stat-sub{font-size:0.65rem;color:#475569;margin-top:2px;}
.trade-symbol{font-size:0.9rem;font-weight:600;color:#e2e8f0;margin-bottom:2px;}
.trade-meta{font-size:0.72rem;color:#475569;font-family:'JetBrains Mono',monospace;}
.edit-panel{background:#0a0a14;border:1px solid #2e2e48;border-radius:8px;padding:1rem 1.2rem;margin:4px 0 10px 0;}
.warn-box{background:rgba(234,179,8,0.08);border-left:3px solid #eab308;border-radius:0 6px 6px 0;padding:8px 12px;font-size:0.78rem;color:#ca8a04;margin:6px 0;}
.info-box{background:rgba(59,130,246,0.08);border-left:3px solid #3b82f6;border-radius:0 6px 6px 0;padding:8px 12px;font-size:0.78rem;color:#60a5fa;margin:6px 0;}
.success-box{background:rgba(34,197,94,0.08);border-left:3px solid #22c55e;border-radius:0 6px 6px 0;padding:8px 12px;font-size:0.78rem;color:#22c55e;margin:6px 0;}
.divider{border:none;border-top:1px solid #1e1e2e;margin:1rem 0;}
#MainMenu,footer,header{visibility:hidden;}
.stDeployButton{display:none;}
</style>
""", unsafe_allow_html=True)


# ── SHEETS AUTH ───────────────────────────────────────────────────────────────
@st.cache_resource(ttl=3600)
def get_client():
    raw = dict(st.secrets["gcp_service_account"])
    pk  = str(raw.get("private_key","")).replace("\\n","\n")
    if not pk.endswith("\n"): pk += "\n"
    raw["private_key"] = pk
    return gspread.authorize(Credentials.from_service_account_info(raw, scopes=SCOPES))

def get_ws(tab):
    return get_client().open_by_key(st.secrets["app"]["sheet_id"]).worksheet(tab)


# ── DATA READS ────────────────────────────────────────────────────────────────
# KEY: instruments cached in session_state (not st.cache_data) so it persists
# across reruns but can be manually invalidated after CSV upload.
# This avoids hitting Google API quota on every widget interaction.

def load_instruments_to_session():
    """Read instruments from sheet once and store in session_state."""
    try:
        data = get_ws(TAB_INSTRUMENTS).get_all_records()
        st.session_state["_instruments_df"] = pd.DataFrame(data) if data else pd.DataFrame()
        st.session_state["_instruments_loaded"] = True
    except Exception as e:
        st.session_state["_instruments_df"] = pd.DataFrame()
        st.session_state["_instruments_loaded"] = False
        st.session_state["_instruments_error"] = str(e)

def get_instruments() -> pd.DataFrame:
    """Return instruments DataFrame from session cache."""
    if "_instruments_df" not in st.session_state:
        load_instruments_to_session()
    return st.session_state.get("_instruments_df", pd.DataFrame())

@st.cache_data(ttl=30)
def read_trades():
    try:
        data = get_ws(TAB_TRADES).get_all_records()
        if not data: return pd.DataFrame()
        df = pd.DataFrame(data)
        if "is_deleted" in df.columns:
            df = df[df["is_deleted"].astype(str).str.upper() != "TRUE"]
        return df
    except: return pd.DataFrame()

@st.cache_data(ttl=300)
def read_strategies():
    try:
        data = get_ws(TAB_STRATEGIES).get_all_records()
        return pd.DataFrame(data) if data else pd.DataFrame()
    except: return pd.DataFrame()


# ── HELPERS ───────────────────────────────────────────────────────────────────
def get_strategy_list():
    df = read_strategies()
    if df.empty or "strategy_name" not in df.columns: return []
    if "active" in df.columns:
        df = df[df["active"].astype(str).str.upper() == "Y"]
    return df["strategy_name"].tolist()

def get_fno_symbols():
    df = get_instruments()
    if df.empty or "symbol" not in df.columns: return []
    return sorted(df["symbol"].str.strip().tolist())

def get_lot_size(symbol: str) -> int:
    """Look up lot size from session-cached instruments DataFrame."""
    if not symbol: return 1
    df = get_instruments()
    if df.empty or "symbol" not in df.columns or "lot_size" not in df.columns: return 1
    m = df[df["symbol"].str.upper().str.strip() == symbol.upper().strip()]
    if m.empty: return 1
    try:
        v = int(str(m.iloc[0]["lot_size"]).strip())
        return v if v > 0 else 1
    except: return 1

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

def badge(a):
    c = "badge-buy" if a=="BUY" else "badge-sell"
    return f'<span class="{c}">{a}</span>'

def fmt_px(v):
    try: return f"₹{float(v):,.2f}"
    except: return str(v)


# ── WRITES ────────────────────────────────────────────────────────────────────
def append_trade(row_data):
    try:
        ws = get_ws(TAB_TRADES)
        headers = ws.row_values(1)
        ws.append_row([str(row_data.get(h,"")) for h in headers], value_input_option="USER_ENTERED")
        read_trades.clear()
        return True
    except Exception as e:
        st.error(f"Write error: {e}"); return False

def soft_delete(trade_id):
    try:
        ws = get_ws(TAB_TRADES)
        h  = ws.row_values(1)
        ti,di = h.index("trade_id")+1, h.index("is_deleted")+1
        for i,v in enumerate(ws.col_values(ti)):
            if v==str(trade_id):
                ws.update_cell(i+1,di,"TRUE"); read_trades.clear(); return True
        return False
    except Exception as e:
        st.error(f"Delete error: {e}"); return False

def update_field(trade_id, field, value):
    try:
        ws = get_ws(TAB_TRADES)
        h  = ws.row_values(1)
        ti,fi = h.index("trade_id")+1, h.index(field)+1
        for i,v in enumerate(ws.col_values(ti)):
            if v==str(trade_id):
                ws.update_cell(i+1,fi,str(value)); read_trades.clear(); return True
        return False
    except Exception as e:
        st.error(f"Update error: {e}"); return False

def parse_fo_csv(text):
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
            li = next((i for i,t in enumerate(tokens) if t.isdigit()), None)
            if li is None or li < 2: continue
            parts = [" ".join(tokens[:li-1]), tokens[li-1], tokens[li]]
        if len(parts) < 3: continue
        u,s,l = parts[0].strip(), parts[1].strip(), parts[2].strip()
        if not s or s.lower() in ("symbol","underlying",""): continue
        if not l or not l.isdigit(): continue
        if u.lower().startswith("derivatives on individual"): continue
        rows.append({"symbol":s,"underlying":u,"lot_size":int(l),
                     "exchange":"NSE","instrument_type":"FUT_OPT",
                     "last_updated":now_ist().strftime("%d-%m-%Y %H:%M")})
    return rows

def write_instruments(rows):
    try:
        ws = get_ws(TAB_INSTRUMENTS)
        av = ws.get_all_values()
        if len(av) > 1:
            ws.batch_clear([f"A2:Z{len(av)}"])
        data = [[r["symbol"],r["underlying"],r["lot_size"],
                 r["exchange"],r["instrument_type"],r["last_updated"]] for r in rows]
        ws.append_rows(data, value_input_option="USER_ENTERED")
        # Immediately update session cache — no extra API call needed
        st.session_state["_instruments_df"] = pd.DataFrame(rows)
        st.session_state["_instruments_loaded"] = True
        return True, f"✅ {len(data)} symbols loaded — {now_ist().strftime('%d-%m-%Y %H:%M')}"
    except Exception as e:
        return False, f"❌ {e}"


# ── SESSION STATE INIT ────────────────────────────────────────────────────────
if "edit_id" not in st.session_state: st.session_state.edit_id = None

# Load instruments into session on first load (one API call total)
if "_instruments_loaded" not in st.session_state:
    load_instruments_to_session()

df_inst    = get_instruments()
inst_count = len(df_inst) if not df_inst.empty else 0
inst_last  = df_inst["last_updated"].iloc[0] if (not df_inst.empty and "last_updated" in df_inst.columns) else ""


# ══════════════════════════════════════════════════════════════════════════════
# HEADER
# ══════════════════════════════════════════════════════════════════════════════
st.markdown(
    '<div class="pb-header">'
    '<span style="font-size:1.3rem;font-weight:700;letter-spacing:0.02em;">'
    '<span style="color:#ffffff;">Parabolic</span>'
    '<span style="color:#7c6fcd;">Trends</span>'
    '</span>'
    '<span class="pb-sub" style="margin-left:16px;">Trade Entry</span>'
    '</div>',
    unsafe_allow_html=True
)


# ══════════════════════════════════════════════════════════════════════════════
# INSTRUMENTS PANEL
# ══════════════════════════════════════════════════════════════════════════════
col_status = "#f97316" if inst_count > 0 else "#ef4444"
st.markdown(
    f'<div style="font-size:0.72rem;color:{col_status};margin-bottom:6px;">'
    f'📋 {inst_count} F&O symbols loaded{" · " + inst_last if inst_last else " — upload fo_mktlots.csv below"}</div>',
    unsafe_allow_html=True
)

with st.expander("🔧 Update F&O Lot Sizes", expanded=(inst_count == 0)):
    st.markdown('<div style="font-size:0.78rem;color:#64748b;margin-bottom:8px;">Select <b>fo_mktlots.csv</b> → click Update.</div>', unsafe_allow_html=True)
    uploaded = st.file_uploader("fo_mktlots.csv", type=["csv"], label_visibility="collapsed")
    if st.button("⬆ Update Instruments"):
        if uploaded:
            parsed = parse_fo_csv(uploaded.read().decode("utf-8", errors="replace"))
            if parsed:
                ok, msg = write_instruments(parsed)
                st.markdown(f'<div class="{"success-box" if ok else "warn-box"}">{msg}</div>', unsafe_allow_html=True)
                if ok: st.rerun()
            else:
                st.markdown('<div class="warn-box">⚠️ Could not parse — check file is NSE fo_mktlots.csv</div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="warn-box">⚠️ Select file first</div>', unsafe_allow_html=True)

st.markdown("<div class='divider'></div>", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# MAIN LAYOUT
# ══════════════════════════════════════════════════════════════════════════════
col_form, col_trades = st.columns([1, 1.4], gap="large")


# ══════════════════════════════════════════════════════
# LEFT — ENTRY
# Selectors are OUTSIDE the form so every symbol change
# triggers an immediate rerun and lot size updates live.
# ══════════════════════════════════════════════════════
with col_form:
    st.markdown('<div class="section-title">New Trade</div>', unsafe_allow_html=True)

    strategies  = get_strategy_list()
    fno_symbols = get_fno_symbols()

    if not strategies:
        st.markdown('<div class="warn-box">No strategies — check STRATEGIES tab in Google Sheet.</div>', unsafe_allow_html=True)
    else:
        # ── ALL SELECTORS OUTSIDE FORM ──
        strategy = st.selectbox("Strategy", strategies, key="sel_strategy")

        sc1, sc2 = st.columns(2)
        exchange   = sc1.selectbox("Exchange",   ["NSE","BSE","MCX"], key="sel_exchange")
        instrument = sc2.selectbox("Instrument", ["FUT","OPT","CASH"], key="sel_instrument")

        if instrument == "CASH":
            symbol   = st.text_input("Symbol", placeholder="e.g. RELIANCE", key="sel_symbol_text").upper().strip()
            expiry, strike, opt_type = "", 0, ""
        else:
            if fno_symbols:
                symbol = st.selectbox("Symbol", fno_symbols, key="sel_symbol_fno")
            else:
                symbol = st.text_input("Symbol (upload F&O list above)", key="sel_symbol_manual").upper().strip()

            ec1, ec2, ec3 = st.columns(3)
            expiry = ec1.selectbox("Expiry", build_expiry_months(6), key="sel_expiry")
            if instrument == "OPT":
                strike   = ec2.number_input("Strike", min_value=0, step=50, value=0, key="sel_strike")
                opt_type = ec3.selectbox("CE / PE", ["CE","PE"], key="sel_opttype")
            else:
                strike, opt_type = 0, ""

        # ── LOT SIZE from session cache — zero API calls ──
        lot_size = 1
        if instrument != "CASH" and symbol:
            lot_size = get_lot_size(symbol)

        ac1, ac2 = st.columns(2)
        action = ac1.selectbox("Action", ["BUY","SELL"], key="sel_action")

        if instrument == "CASH":
            quantity = ac2.number_input("Quantity (shares)", min_value=1, step=1, value=1, key="sel_qty")
            lots     = 0
        else:
            lots     = ac2.number_input("Lots", min_value=1, step=1, value=1, key="sel_lots")
            quantity = lots * lot_size

        # ── QTY DISPLAY ──
        if instrument != "CASH":
            qc1, qc2, qc3 = st.columns(3)
            ls_color = "#f97316" if lot_size > 1 else "#ef4444"
            ls_disp  = str(lot_size) if lot_size > 1 else "NOT FOUND"
            qc1.markdown(f'<div class="qty-box"><div class="qty-label">Lot Size</div><div class="qty-value" style="color:{ls_color};">{ls_disp}</div></div>', unsafe_allow_html=True)
            qc2.markdown(f'<div class="qty-box"><div class="qty-label">Lots × Size</div><div class="qty-value" style="color:#94a3b8;">{lots} × {lot_size}</div></div>', unsafe_allow_html=True)
            qt_color = "#22c55e" if lot_size > 1 else "#ef4444"
            qc3.markdown(f'<div class="qty-box"><div class="qty-label">Total Qty</div><div class="qty-value" style="color:{qt_color};">{quantity:,} shares</div></div>', unsafe_allow_html=True)
            if lot_size == 1 and symbol:
                st.markdown(f'<div class="warn-box">⚠️ <b>{symbol}</b> not found in {inst_count} loaded symbols. Upload fo_mktlots.csv above.</div>', unsafe_allow_html=True)

        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

        # ── FORM — date/price/notes/submit only ──
        with st.form("entry_form", clear_on_submit=True):
            now = now_ist()
            fc1, fc2   = st.columns(2)
            trade_date = fc1.date_input("Trade Date", value=now.date())
            trade_time = fc2.time_input("Trade Time", value=now.time().replace(second=0,microsecond=0))

            is_back = trade_date < now.date()
            if is_back:
                st.markdown('<div class="info-box">↩ Backdated entry — enter price manually.</div>', unsafe_allow_html=True)

            fp1, fp2 = st.columns([1.5,1])
            manual   = fp2.checkbox("Manual price", value=True)
            price    = fp1.number_input("Price ₹", min_value=0.0, step=0.05, format="%.2f", value=0.0)
            price_source = "MANUAL"

            if not manual and not is_back and instrument != "CASH":
                try:
                    from core.angelone import get_angel_obj, get_symbol_token, fetch_current_ltp
                    obj = get_angel_obj()
                    if obj:
                        token = get_symbol_token(symbol, exchange, instrument)
                        if token:
                            ltp, _ = fetch_current_ltp(symbol, exchange, token)
                            if ltp and ltp > 0:
                                price = ltp; price_source = "ANGELONE_LTP"
                                st.markdown(f'<div class="success-box">LTP fetched: {fmt_px(ltp)}</div>', unsafe_allow_html=True)
                            else:
                                st.markdown('<div class="warn-box">No price returned — enter manually.</div>', unsafe_allow_html=True)
                        else:
                            st.markdown(f'<div class="warn-box">Symbol token not found for {symbol}.</div>', unsafe_allow_html=True)
                    else:
                        st.markdown('<div class="warn-box">AngelOne login failed — enter manually.</div>', unsafe_allow_html=True)
                except Exception as ex:
                    st.markdown(f'<div class="warn-box">AngelOne error: {ex}</div>', unsafe_allow_html=True)

            notes     = st.text_area("Notes", height=56, placeholder="Setup, SL, reason...")
            submitted = st.form_submit_button("LOG TRADE →")

        if submitted:
            if not symbol:
                st.markdown('<div class="warn-box">⚠️ Symbol required.</div>', unsafe_allow_html=True)
            elif price <= 0:
                st.markdown('<div class="warn-box">⚠️ Enter a valid price > 0.</div>', unsafe_allow_html=True)
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
                    qty_desc = f"{lots} lots ({quantity:,} sh)" if instrument!="CASH" else f"{int(quantity):,} shares"
                    st.markdown(f'<div class="success-box">✅ {action} {symbol} — {qty_desc} @ {fmt_px(price)}</div>', unsafe_allow_html=True)


# ══════════════════════════════════════════════════════
# RIGHT — OPEN TRADES (grouped by strategy)
# ══════════════════════════════════════════════════════
with col_trades:
    st.markdown('<div class="section-title">Open Trades</div>', unsafe_allow_html=True)

    if st.button("↻ Refresh"):
        read_trades.clear()
        st.rerun()

    df        = read_trades()
    today_str = now_ist().strftime("%Y-%m-%d")

    if df.empty:
        st.markdown('<div style="color:#475569;font-size:0.82rem;padding:2rem 0;text-align:center;">No trades logged yet.</div>', unsafe_allow_html=True)
    else:
        if "timestamp_entry" in df.columns:
            df = df.sort_values("timestamp_entry", ascending=False)

        # ── FETCH LTP + MARGIN FOR ALL POSITIONS (one batch) ──
        ltp_map           = {}
        total_margin_used = 0.0

        try:
            from core.angelone import get_angel_obj, get_symbol_token, fetch_current_ltp, fetch_margin_for_positions
            obj = get_angel_obj()
            if obj:
                positions_for_margin = []
                for _, row in df.iterrows():
                    sym   = str(row.get("symbol",""))
                    exch  = str(row.get("exchange","NSE"))
                    instr = str(row.get("instrument","FUT"))
                    exp_v = str(row.get("expiry",""))
                    stk_v = float(row.get("strike",0) or 0)
                    opt_v = str(row.get("option_type",""))
                    qty   = float(row.get("quantity",0) or 0)
                    px    = float(row.get("price",0) or 0)
                    if sym and sym not in ltp_map:
                        token = get_symbol_token(sym, exch, instr, exp_v, stk_v, opt_v)
                        ltp, _ = fetch_current_ltp(sym, exch, token)
                        if ltp and ltp > 0:
                            ltp_map[sym] = ltp
                        positions_for_margin.append({
                            "symbol": sym, "exchange": exch, "instrument": instr,
                            "token": token, "quantity": qty, "avg_entry_price": px,
                            "strategy": str(row.get("strategy","")),
                        })
                if positions_for_margin:
                    mdata = fetch_margin_for_positions(positions_for_margin)
                    total_margin_used = float(mdata.get("_total_required", 0))
        except Exception:
            pass

        # ── TOTAL ALLOCATED CAPITAL ──
        total_capital = 0
        try:
            df_strat = read_strategies()
            if not df_strat.empty and "allocated_capital" in df_strat.columns:
                for _, sr in df_strat.iterrows():
                    try:
                        cap = str(sr["allocated_capital"]).replace("L","").replace("l","").strip()
                        cv  = float(cap)
                        if cv < 10000: cv *= 100000
                        total_capital += cv
                    except: pass
        except: pass

        # ── TOTAL MTM ──
        total_mtm = 0.0
        for _, row in df.iterrows():
            sym = str(row.get("symbol",""))
            if sym in ltp_map:
                ep  = float(row.get("price",0) or 0)
                qty = float(row.get("quantity",0) or 0)
                act = str(row.get("action","BUY")).upper()
                total_mtm += ((ltp_map[sym]-ep)*qty) if act=="BUY" else ((ep-ltp_map[sym])*qty)

        # ── SUMMARY METRICS ROW ──
        tm_c = "#22c55e" if total_mtm>=0 else "#ef4444"
        tm_s = ("+" if total_mtm>=0 else "")+f"₹{abs(total_mtm):,.0f}" if ltp_map else "—"
        mg_s = f"₹{total_margin_used/100000:.1f}L" if total_margin_used > 0 else "—"
        mg_p = f"{total_margin_used/total_capital*100:.1f}%" if (total_capital>0 and total_margin_used>0) else ""
        mg_c = "#22c55e" if (total_margin_used/total_capital < 0.5 if total_capital>0 and total_margin_used>0 else True) else "#eab308"
        cr_s = f"₹{(total_capital-total_margin_used)/100000:.1f}L" if (total_capital>0 and total_margin_used>0) else "—"

        m1,m2,m3,m4 = st.columns(4)
        m1.markdown(f'<div class="stat-box"><div class="stat-label">Positions</div><div class="stat-value" style="color:#e2e8f0">{len(df)}</div><div class="stat-sub">{len(df[df["action"].str.upper()=="BUY"])}L · {len(df[df["action"].str.upper()=="SELL"])}S</div></div>', unsafe_allow_html=True)
        m2.markdown(f'<div class="stat-box"><div class="stat-label">Total MTM</div><div class="stat-value" style="color:{tm_c}">{tm_s}</div><div class="stat-sub">{"live" if ltp_map else "needs AngelOne"}</div></div>', unsafe_allow_html=True)
        m3.markdown(f'<div class="stat-box"><div class="stat-label">Margin Used</div><div class="stat-value" style="color:{mg_c}">{mg_s} {mg_p}</div><div class="stat-sub">{"of ₹"+str(int(total_capital//100000))+"L capital" if total_capital>0 else "SPAN via AngelOne"}</div></div>', unsafe_allow_html=True)
        m4.markdown(f'<div class="stat-box"><div class="stat-label">Capital Free</div><div class="stat-value" style="color:#e2e8f0">{cr_s}</div><div class="stat-sub">{"remaining" if cr_s != "—" else "add AngelOne"}</div></div>', unsafe_allow_html=True)

        st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)

        # ── GROUP BY STRATEGY — fixed order ──
        STRATEGY_ORDER = ["TREND", "COMMODITIES", "MOMENTUM"]
        all_strats = df["strategy"].unique().tolist() if "strategy" in df.columns else []
        # Put known strategies first in order, then any others alphabetically
        ordered = [s for s in STRATEGY_ORDER if s in all_strats]
        others  = sorted([s for s in all_strats if s not in STRATEGY_ORDER])
        strategies_in_trades = ordered + others

        for strategy_name in strategies_in_trades:
            strategy_df = df[df["strategy"] == strategy_name].copy()

            # Strategy MTM
            strat_mtm = 0.0
            for _, row in strategy_df.iterrows():
                sym = str(row.get("symbol",""))
                if sym in ltp_map:
                    ep  = float(row.get("price",0) or 0)
                    qty = float(row.get("quantity",0) or 0)
                    act = str(row.get("action","BUY")).upper()
                    strat_mtm += ((ltp_map[sym]-ep)*qty) if act=="BUY" else ((ep-ltp_map[sym])*qty)

            strat_mtm_c = "#22c55e" if strat_mtm>=0 else "#ef4444"
            strat_mtm_s = ("+" if strat_mtm>=0 else "")+f"₹{abs(strat_mtm):,.0f}" if ltp_map else "—"
            strat_today = len(strategy_df[strategy_df["trade_date"].astype(str)==today_str]) if "trade_date" in strategy_df.columns else 0

            # Strategy header row
            sc1, sc2, sc3, sc4, sc5 = st.columns([2,1,1,1,1])
            sc1.markdown(
                f'<div style="background:rgba(249,115,22,0.12);border:1px solid rgba(249,115,22,0.3);'
                f'border-radius:5px;padding:5px 12px;display:inline-block;font-size:0.75rem;'
                f'font-weight:700;letter-spacing:0.1em;color:#f97316;text-transform:uppercase;">{strategy_name}</div>',
                unsafe_allow_html=True
            )
            sc2.markdown(f'<div style="font-size:0.65rem;color:#475569;text-transform:uppercase;letter-spacing:0.08em;margin-top:2px;">Positions</div><div style="font-size:0.9rem;font-weight:600;color:#e2e8f0;">{len(strategy_df)}</div>', unsafe_allow_html=True)
            sc3.markdown(f'<div style="font-size:0.65rem;color:#475569;text-transform:uppercase;letter-spacing:0.08em;margin-top:2px;">MTM P&L</div><div style="font-size:0.9rem;font-weight:600;color:{strat_mtm_c};">{strat_mtm_s}</div>', unsafe_allow_html=True)
            sc4.markdown(f'<div style="font-size:0.65rem;color:#475569;text-transform:uppercase;letter-spacing:0.08em;margin-top:2px;">Margin</div><div style="font-size:0.9rem;font-weight:600;color:#e2e8f0;">—</div>', unsafe_allow_html=True)
            sc5.markdown(f'<div style="font-size:0.65rem;color:#475569;text-transform:uppercase;letter-spacing:0.08em;margin-top:2px;">Today</div><div style="font-size:0.9rem;font-weight:600;color:#f97316;">{strat_today}</div>', unsafe_allow_html=True)

            st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)

            # Trade rows under this strategy
            for _, row in strategy_df.iterrows():
                tid   = str(row.get("trade_id",""))
                sym   = str(row.get("symbol",""))
                act   = str(row.get("action",""))
                instr = str(row.get("instrument",""))
                exp_v = str(row.get("expiry",""))
                stk_v = str(row.get("strike",""))
                opt_v = str(row.get("option_type",""))
                lv    = str(row.get("lots_qty",""))
                qv    = str(row.get("quantity",""))
                pv    = row.get("price",0)
                dt_v  = str(row.get("trade_date",""))

                # Descriptor
                desc  = sym
                if exp_v: desc += f" {exp_v}"
                if stk_v and stk_v not in ("","0"): desc += f" {stk_v}{opt_v}"
                new_b = '<span class="badge-new">NEW</span>' if dt_v==today_str else ""

                # Days open
                try:
                    days_open = (now_ist().date() - datetime.strptime(dt_v,"%Y-%m-%d").date()).days
                    days_str  = "today" if days_open==0 else f"{days_open}d"
                except: days_str = "—"

                # Qty
                cur_ls  = get_lot_size(sym)
                cur_qty = int(lv)*cur_ls if (str(lv).isdigit() and cur_ls>1) else qv
                qty_info = f"{lv}L×{cur_ls}={cur_qty}sh" if instr!="CASH" else f"{qv}sh"

                # LTP + MTM per trade
                ltp_str = ""
                mtm_str = ""
                if sym in ltp_map:
                    lp = ltp_map[sym]
                    ltp_str = fmt_px(lp)
                    try:
                        ep  = float(pv)
                        qty = float(qv)
                        pnl = (lp-ep)*qty if act.upper()=="BUY" else (ep-lp)*qty
                        pc  = "#22c55e" if pnl>=0 else "#ef4444"
                        mtm_str = f'<span style="color:{pc};font-weight:600">{"+" if pnl>=0 else ""}₹{abs(pnl):,.0f}</span>'
                    except: mtm_str = ""

                is_editing = (st.session_state.edit_id == tid)
                ci, cb2   = st.columns([3,1])

                with ci:
                    st.markdown(
                        f'<div style="background:#0f0f1a;border:1px solid #1e1e2e;border-radius:6px;padding:8px 12px;margin-bottom:4px;">'
                        f'<div class="trade-symbol">{badge(act)} &nbsp;{desc}{new_b}</div>'
                        f'<div class="trade-meta">{qty_info} · {fmt_px(pv)} entry'
                        f'{"  ·  LTP " + ltp_str if ltp_str else ""}'
                        f'{"  " + mtm_str if mtm_str else ""}'
                        f'</div>'
                        f'<div class="trade-meta">{dt_v} · {days_str} open</div>'
                        f'</div>',
                        unsafe_allow_html=True
                    )

                with cb2:
                    b1,b2 = st.columns(2)
                    if b1.button("✏", key=f"e_{tid}"):
                        st.session_state.edit_id = None if is_editing else tid
                        st.rerun()
                    if b2.button("✕", key=f"d_{tid}"):
                        soft_delete(tid); st.session_state.edit_id=None; st.rerun()

                if is_editing:
                    st.markdown('<div class="edit-panel">', unsafe_allow_html=True)
                    ea,eb,ec = st.columns(3)
                    try:    dv = datetime.strptime(dt_v,"%Y-%m-%d").date()
                    except: dv = now_ist().date()
                    nd = ea.date_input("Date",    value=dv,              key=f"ed_{tid}")
                    np = eb.number_input("Price ₹", min_value=0.0, step=0.05,
                                         format="%.2f", value=float(pv) if pv else 0.0, key=f"ep_{tid}")
                    nl = ec.number_input("Lots",    min_value=1, step=1,
                                         value=int(lv) if str(lv).isdigit() else 1, key=f"el_{tid}")
                    s1,s2 = st.columns(2)
                    if s1.button("Save", key=f"sv_{tid}"):
                        update_field(tid,"trade_date",str(nd))
                        update_field(tid,"price",np)
                        update_field(tid,"lots_qty",nl)
                        ls = get_lot_size(sym)
                        update_field(tid,"quantity", nl*ls if instr!="CASH" else nl)
                        st.session_state.edit_id=None; st.rerun()
                    if s2.button("Cancel", key=f"cx_{tid}"):
                        st.session_state.edit_id=None; st.rerun()
                    st.markdown('</div>', unsafe_allow_html=True)

            # Spacing between strategy groups
            st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
