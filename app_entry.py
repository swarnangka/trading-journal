"""
PARABOLIC DASHBOARD — Trade Entry
===================================
Private app for logging trades.
Dark premium design. No password needed (private URL).
"""

import streamlit as st
import pandas as pd
from datetime import datetime, date, time as dtime
import pytz
import uuid

from core.sheets import (
    get_strategy_list, get_fno_symbols, get_lot_size,
    read_trades, append_trade, soft_delete_trade, update_trade_field,
    now_ist, generate_trade_id, build_expiry_months,
    parse_fo_mktlots_csv, write_instruments_to_sheet,
    read_instruments,
)

# ── PAGE CONFIG ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Parabolic Dashboard · Entry",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── DESIGN TOKENS & CSS ────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

/* ── BASE ── */
html, body, [class*="css"] {
    font-family: 'Inter', sans-serif;
    background-color: #0a0a0f;
    color: #e2e8f0;
}
.stApp { background-color: #0a0a0f; }
.block-container { padding: 1.5rem 2rem 3rem 2rem; max-width: 1400px; }

/* ── HEADER ── */
.pb-header {
    display: flex;
    align-items: baseline;
    gap: 12px;
    padding: 0 0 1.5rem 0;
    border-bottom: 1px solid #1e1e2e;
    margin-bottom: 2rem;
}
.pb-logo {
    font-size: 1.1rem;
    font-weight: 700;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: #f97316;
}
.pb-sub {
    font-size: 0.75rem;
    color: #475569;
    letter-spacing: 0.08em;
    text-transform: uppercase;
}

/* ── PANEL ── */
.pb-panel {
    background: #0f0f1a;
    border: 1px solid #1e1e2e;
    border-radius: 8px;
    padding: 1.5rem;
}
.pb-panel-title {
    font-size: 0.65rem;
    font-weight: 600;
    letter-spacing: 0.14em;
    text-transform: uppercase;
    color: #475569;
    margin-bottom: 1.2rem;
    padding-bottom: 0.6rem;
    border-bottom: 1px solid #1e1e2e;
}

/* ── FORM INPUTS ── */
.stSelectbox label, .stNumberInput label, .stTextInput label,
.stDateInput label, .stTimeInput label, .stTextArea label {
    font-size: 0.7rem !important;
    font-weight: 500 !important;
    letter-spacing: 0.08em !important;
    text-transform: uppercase !important;
    color: #64748b !important;
    margin-bottom: 4px !important;
}
.stSelectbox > div > div,
.stTextInput > div > div > input,
.stNumberInput > div > div > input,
.stDateInput > div > div > input,
.stTimeInput > div > div > input {
    background-color: #141420 !important;
    border: 1px solid #252538 !important;
    border-radius: 6px !important;
    color: #e2e8f0 !important;
    font-family: 'Inter', sans-serif !important;
    font-size: 0.875rem !important;
}
.stSelectbox > div > div:focus-within,
.stTextInput > div > div:focus-within,
.stNumberInput > div > div:focus-within {
    border-color: #f97316 !important;
    box-shadow: 0 0 0 2px rgba(249,115,22,0.15) !important;
}
textarea {
    background-color: #141420 !important;
    border: 1px solid #252538 !important;
    border-radius: 6px !important;
    color: #e2e8f0 !important;
    font-size: 0.875rem !important;
}

/* ── BUTTONS ── */
.stButton > button {
    background: transparent;
    border: 1px solid #252538;
    border-radius: 6px;
    color: #94a3b8;
    font-size: 0.75rem;
    font-weight: 500;
    letter-spacing: 0.06em;
    padding: 0.4rem 0.9rem;
    transition: all 0.15s ease;
    cursor: pointer;
}
.stButton > button:hover {
    border-color: #f97316;
    color: #f97316;
    background: rgba(249,115,22,0.06);
}

/* Primary submit button */
.stForm [data-testid="stFormSubmitButton"] > button {
    background: #f97316;
    border: none;
    border-radius: 6px;
    color: #fff;
    font-size: 0.8rem;
    font-weight: 600;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    padding: 0.55rem 1.5rem;
    width: 100%;
    transition: all 0.15s ease;
}
.stForm [data-testid="stFormSubmitButton"] > button:hover {
    background: #ea6a0a;
}

/* ── QTY DISPLAY ── */
.qty-pill {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    background: rgba(249,115,22,0.1);
    border: 1px solid rgba(249,115,22,0.25);
    border-radius: 20px;
    padding: 4px 12px;
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.8rem;
    color: #f97316;
    margin: 6px 0 12px 0;
}
.qty-dot {
    width: 6px; height: 6px;
    background: #f97316;
    border-radius: 50%;
    display: inline-block;
}

/* ── ACTION BADGE ── */
.badge-buy {
    display: inline-block;
    background: rgba(34,197,94,0.12);
    border: 1px solid rgba(34,197,94,0.3);
    color: #22c55e;
    border-radius: 4px;
    padding: 2px 8px;
    font-size: 0.65rem;
    font-weight: 600;
    letter-spacing: 0.1em;
}
.badge-sell {
    display: inline-block;
    background: rgba(239,68,68,0.12);
    border: 1px solid rgba(239,68,68,0.3);
    color: #ef4444;
    border-radius: 4px;
    padding: 2px 8px;
    font-size: 0.65rem;
    font-weight: 600;
    letter-spacing: 0.1em;
}
.badge-new {
    display: inline-block;
    background: rgba(249,115,22,0.15);
    border: 1px solid rgba(249,115,22,0.35);
    color: #f97316;
    border-radius: 4px;
    padding: 1px 6px;
    font-size: 0.6rem;
    font-weight: 700;
    letter-spacing: 0.1em;
    margin-left: 4px;
}

/* ── TRADE ROW ── */
.trade-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 10px 14px;
    background: #0f0f1a;
    border: 1px solid #1e1e2e;
    border-radius: 7px;
    margin-bottom: 6px;
    transition: border-color 0.15s;
}
.trade-row:hover { border-color: #2e2e48; }
.trade-meta {
    font-size: 0.72rem;
    color: #475569;
    font-family: 'JetBrains Mono', monospace;
}
.trade-symbol {
    font-size: 0.9rem;
    font-weight: 600;
    color: #e2e8f0;
    margin-bottom: 2px;
}
.trade-price {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.85rem;
    color: #94a3b8;
}

/* ── EDIT PANEL ── */
.edit-panel {
    background: #0a0a14;
    border: 1px solid #2e2e48;
    border-radius: 8px;
    padding: 1rem 1.2rem;
    margin: 4px 0 10px 0;
}

/* ── WARN / INFO ── */
.warn-box {
    background: rgba(234,179,8,0.08);
    border-left: 3px solid #eab308;
    border-radius: 0 6px 6px 0;
    padding: 8px 12px;
    font-size: 0.78rem;
    color: #ca8a04;
    margin: 6px 0;
}
.info-box {
    background: rgba(59,130,246,0.08);
    border-left: 3px solid #3b82f6;
    border-radius: 0 6px 6px 0;
    padding: 8px 12px;
    font-size: 0.78rem;
    color: #60a5fa;
    margin: 6px 0;
}
.success-box {
    background: rgba(34,197,94,0.08);
    border-left: 3px solid #22c55e;
    border-radius: 0 6px 6px 0;
    padding: 8px 12px;
    font-size: 0.78rem;
    color: #22c55e;
    margin: 6px 0;
}

/* ── DIVIDER ── */
.pb-divider {
    border: none;
    border-top: 1px solid #1e1e2e;
    margin: 1rem 0;
}

/* ── INSTRUMENT TABS ── */
.stTabs [data-baseweb="tab-list"] {
    background: transparent;
    gap: 2px;
}
.stTabs [data-baseweb="tab"] {
    background: transparent;
    border: 1px solid #1e1e2e;
    border-radius: 6px;
    color: #64748b;
    font-size: 0.72rem;
    font-weight: 500;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    padding: 6px 14px;
}
.stTabs [aria-selected="true"] {
    background: rgba(249,115,22,0.1) !important;
    border-color: rgba(249,115,22,0.35) !important;
    color: #f97316 !important;
}

/* ── HIDE STREAMLIT CHROME ── */
#MainMenu, footer, header { visibility: hidden; }
.stDeployButton { display: none; }
</style>
""", unsafe_allow_html=True)


# ── HEADER ────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="pb-header">
    <span class="pb-logo">⚡ Parabolic</span>
    <span class="pb-sub">Trade Entry</span>
</div>
""", unsafe_allow_html=True)


# ── SESSION STATE ─────────────────────────────────────────────────────────────
if "edit_trade_id" not in st.session_state:
    st.session_state.edit_trade_id = None
if "show_instruments" not in st.session_state:
    st.session_state.show_instruments = False


# ── ANGELONE PRICE FETCH ───────────────────────────────────────────────────────
def fetch_ltp(symbol: str, exchange: str, instrument: str) -> float | None:
    """Fetch live LTP via AngelOne. Returns None on any failure."""
    try:
        from core.angelone import get_ltp
        return get_ltp(symbol, exchange, instrument)
    except Exception:
        return None


# ── HELPERS ───────────────────────────────────────────────────────────────────
def badge(action: str) -> str:
    cls = "badge-buy" if action == "BUY" else "badge-sell"
    return f'<span class="{cls}">{action}</span>'


def is_today(trade_date_str: str) -> bool:
    try:
        td = datetime.strptime(str(trade_date_str), "%Y-%m-%d").date()
        return td == now_ist().date()
    except Exception:
        return False


# ── INSTRUMENTS UPDATE SECTION ─────────────────────────────────────────────────
with st.expander("🔧 Update F&O Lot Sizes (paste NSE CSV)", expanded=st.session_state.show_instruments):
    st.markdown("""
    <div style='font-size:0.78rem; color:#64748b; margin-bottom:12px;'>
    Download <code>fo_mktlots.csv</code> from NSE quarterly → open in text editor →
    select all → copy → paste below → click Update.
    </div>
    """, unsafe_allow_html=True)

    csv_text = st.text_area(
        "Paste fo_mktlots.csv content here",
        height=120,
        placeholder="UNDERLYING,SYMBOL,JUN-26,JUL-26,...\nNIFTY 50,NIFTY,65,65,...",
        label_visibility="collapsed",
    )

    col_a, col_b = st.columns([1, 4])
    if col_a.button("Update Instruments", type="primary" if csv_text else "secondary"):
        if csv_text.strip():
            parsed = parse_fo_mktlots_csv(csv_text)
            if parsed:
                ok, msg = write_instruments_to_sheet(parsed)
                if ok:
                    st.markdown(f'<div class="success-box">{msg}</div>', unsafe_allow_html=True)
                else:
                    st.markdown(f'<div class="warn-box">{msg}</div>', unsafe_allow_html=True)
            else:
                st.markdown('<div class="warn-box">⚠️ Could not parse any symbols. Check the CSV format.</div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="warn-box">⚠️ Paste the CSV content first.</div>', unsafe_allow_html=True)

    # Show current instrument count
    df_inst = read_instruments()
    if not df_inst.empty:
        col_b.markdown(
            f'<div style="font-size:0.72rem; color:#475569; padding-top:0.6rem;">'
            f'{len(df_inst)} symbols loaded · Last update: '
            f'{df_inst["last_updated"].iloc[0] if "last_updated" in df_inst.columns else "unknown"}'
            f'</div>',
            unsafe_allow_html=True,
        )

st.markdown("<div class='pb-divider'></div>", unsafe_allow_html=True)


# ── MAIN LAYOUT: ENTRY FORM | OPEN TRADES ─────────────────────────────────────
col_form, col_trades = st.columns([1, 1.4], gap="large")


# ═══════════════════════════════════════════════════════
# LEFT: ENTRY FORM
# ═══════════════════════════════════════════════════════
with col_form:
    st.markdown('<div class="pb-panel-title">New Trade</div>', unsafe_allow_html=True)

    strategies = get_strategy_list()
    fno_symbols = get_fno_symbols()

    if not strategies:
        st.markdown('<div class="warn-box">No strategies found — check STRATEGIES tab in Google Sheet.</div>', unsafe_allow_html=True)
    else:
        with st.form("trade_entry_form", clear_on_submit=True):

            # ── Strategy ──
            strategy = st.selectbox("Strategy", strategies)

            # ── Exchange + Instrument ──
            c1, c2 = st.columns(2)
            exchange   = c1.selectbox("Exchange", ["NSE", "BSE", "MCX"])
            instrument = c2.selectbox("Instrument", ["FUT", "OPT", "CASH"])

            # ── Symbol ──
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
                        "Symbol",
                        placeholder="No F&O list — paste CSV above first, or type symbol"
                    ).upper().strip()

                c3, c4, c5 = st.columns(3)
                expiry = c3.selectbox("Expiry", build_expiry_months(6))
                if instrument == "OPT":
                    strike   = c4.number_input("Strike", min_value=0, step=50, value=0)
                    opt_type = c5.selectbox("CE / PE", ["CE", "PE"])
                else:
                    strike   = 0
                    opt_type = ""

            # ── Lot size & qty ──
            lot_size = 1
            if instrument != "CASH" and symbol:
                lot_size = get_lot_size(symbol)

            # ── Action + Lots / Qty ──
            c6, c7 = st.columns(2)
            action = c6.selectbox("Action", ["BUY", "SELL"])

            if instrument == "CASH":
                quantity  = c7.number_input("Quantity (shares)", min_value=1, step=1, value=1)
                lots      = 0
            else:
                lots     = c7.number_input("Lots", min_value=1, step=1, value=1)
                quantity = lots * lot_size

            # Show qty calculation pill
            if instrument != "CASH":
                if lot_size > 1:
                    st.markdown(
                        f'<div class="qty-pill"><span class="qty-dot"></span>'
                        f'{quantity:,} shares &nbsp;·&nbsp; {lots} lot{"s" if lots > 1 else ""} × {lot_size}</div>',
                        unsafe_allow_html=True
                    )
                else:
                    st.markdown(
                        f'<div class="warn-box">Lot size not found for <b>{symbol}</b>. '
                        f'Update instruments above or check symbol spelling.</div>',
                        unsafe_allow_html=True
                    )

            # ── Date / Time ──
            c8, c9 = st.columns(2)
            today_ist  = now_ist()
            trade_date = c8.date_input("Trade Date", value=today_ist.date())
            trade_time = c9.time_input("Trade Time", value=today_ist.time().replace(second=0, microsecond=0))

            is_backdated = (trade_date < today_ist.date())
            if is_backdated:
                st.markdown(
                    '<div class="info-box">↩ Backdated entry — price will not auto-fetch. Enter manually.</div>',
                    unsafe_allow_html=True
                )

            # ── Price ──
            c10, c11 = st.columns([1.2, 1])
            price_override = c11.checkbox("Manual price", value=is_backdated)
            
            if price_override or instrument == "CASH" or is_backdated:
                price        = c10.number_input("Price ₹", min_value=0.0, step=0.05, format="%.2f", value=0.0)
                price_source = "MANUAL"
            else:
                # Try AngelOne LTP
                fetched_price = fetch_ltp(symbol, exchange, instrument)
                if fetched_price:
                    price        = c10.number_input("Price ₹ (LTP)", min_value=0.0, step=0.05, format="%.2f", value=float(fetched_price))
                    price_source = "ANGELONE_LTP"
                else:
                    price        = c10.number_input("Price ₹", min_value=0.0, step=0.05, format="%.2f", value=0.0)
                    price_source = "MANUAL"
                    st.markdown(
                        '<div class="warn-box">AngelOne LTP unavailable. Enter price manually.</div>',
                        unsafe_allow_html=True
                    )

            # ── Notes ──
            notes = st.text_area("Notes (optional)", height=60, placeholder="Setup, reason, SL level...")

            # ── Submit ──
            submitted = st.form_submit_button("LOG TRADE →")

        if submitted:
            if not symbol:
                st.markdown('<div class="warn-box">⚠️ Symbol is required.</div>', unsafe_allow_html=True)
            elif price <= 0:
                st.markdown('<div class="warn-box">⚠️ Enter a valid price.</div>', unsafe_allow_html=True)
            else:
                trade_id = generate_trade_id()
                row = {
                    "trade_id":        trade_id,
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
                }
                ok = append_trade(row)
                if ok:
                    st.markdown(
                        f'<div class="success-box">✅ Trade logged — {action} {symbol} '
                        f'{"" + str(lots) + " lots" if instrument != "CASH" else str(int(quantity)) + " shares"} '
                        f'@ ₹{price:,.2f}</div>',
                        unsafe_allow_html=True
                    )


# ═══════════════════════════════════════════════════════
# RIGHT: OPEN TRADES
# ═══════════════════════════════════════════════════════
with col_trades:
    st.markdown('<div class="pb-panel-title">Open Trades</div>', unsafe_allow_html=True)

    # Refresh button
    rc1, rc2 = st.columns([1, 4])
    if rc1.button("↻ Refresh"):
        read_trades.clear()
        st.rerun()

    df = read_trades()

    if df.empty:
        st.markdown(
            '<div style="color:#475569; font-size:0.82rem; padding: 2rem 0; text-align:center;">'
            'No trades logged yet.</div>',
            unsafe_allow_html=True
        )
    else:
        # Filter to non-deleted trades only (already done in read_trades)
        # Sort newest first
        if "timestamp_entry" in df.columns:
            df = df.sort_values("timestamp_entry", ascending=False)

        today_str = now_ist().strftime("%Y-%m-%d")

        for _, row in df.iterrows():
            tid        = str(row.get("trade_id", ""))
            sym        = str(row.get("symbol", ""))
            act        = str(row.get("action", ""))
            instr      = str(row.get("instrument", ""))
            expiry_val = str(row.get("expiry", ""))
            strike_val = str(row.get("strike", ""))
            opt_val    = str(row.get("option_type", ""))
            lots_val   = str(row.get("lots_qty", ""))
            qty_val    = str(row.get("quantity", ""))
            price_val  = row.get("price", 0)
            strat_val  = str(row.get("strategy", ""))
            date_val   = str(row.get("trade_date", ""))

            # Build descriptor
            descriptor = sym
            if expiry_val:
                descriptor += f" {expiry_val}"
            if strike_val and strike_val not in ("", "0"):
                descriptor += f" {strike_val}{opt_val}"

            is_new_trade = (date_val == today_str)
            new_badge    = '<span class="badge-new">NEW</span>' if is_new_trade else ""

            try:
                price_fmt = f"₹{float(price_val):,.2f}"
            except Exception:
                price_fmt = str(price_val)

            qty_info = f"{lots_val} lots · {qty_val} shares" if instr != "CASH" else f"{qty_val} shares"

            is_editing = (st.session_state.edit_trade_id == tid)

            # ── Trade Row ──
            col_info, col_btns = st.columns([3, 1])

            with col_info:
                st.markdown(
                    f'<div class="trade-symbol">{badge(act)} &nbsp;{descriptor}{new_badge}</div>'
                    f'<div class="trade-meta">{strat_val} &nbsp;·&nbsp; {qty_info} &nbsp;·&nbsp; {price_fmt}</div>'
                    f'<div class="trade-meta">{date_val}</div>',
                    unsafe_allow_html=True
                )

            with col_btns:
                b1, b2 = st.columns(2)
                if b1.button("✏", key=f"edit_{tid}", help="Edit"):
                    if st.session_state.edit_trade_id == tid:
                        st.session_state.edit_trade_id = None
                    else:
                        st.session_state.edit_trade_id = tid
                    st.rerun()

                if b2.button("✕", key=f"del_{tid}", help="Delete"):
                    ok = soft_delete_trade(tid)
                    if ok:
                        st.session_state.edit_trade_id = None
                        st.rerun()

            # ── Edit Panel ──
            if is_editing:
                with st.container():
                    st.markdown('<div class="edit-panel">', unsafe_allow_html=True)
                    ec1, ec2, ec3 = st.columns(3)

                    new_date  = ec1.date_input(
                        "Trade Date", value=datetime.strptime(date_val, "%Y-%m-%d").date()
                        if date_val else now_ist().date(),
                        key=f"edate_{tid}"
                    )
                    try:
                        new_price = ec2.number_input(
                            "Price ₹", min_value=0.0, step=0.05, format="%.2f",
                            value=float(price_val), key=f"eprice_{tid}"
                        )
                    except Exception:
                        new_price = ec2.number_input(
                            "Price ₹", min_value=0.0, step=0.05, format="%.2f",
                            value=0.0, key=f"eprice_{tid}"
                        )

                    new_lots = ec3.number_input(
                        "Lots / Qty", min_value=1, step=1,
                        value=int(lots_val) if lots_val.isdigit() else 1,
                        key=f"elots_{tid}"
                    )

                    save_col, cancel_col = st.columns(2)
                    if save_col.button("Save", key=f"save_{tid}"):
                        update_trade_field(tid, "trade_date", str(new_date))
                        update_trade_field(tid, "price", new_price)
                        update_trade_field(tid, "lots_qty", new_lots)
                        st.session_state.edit_trade_id = None
                        st.rerun()
                    if cancel_col.button("Cancel", key=f"cancel_{tid}"):
                        st.session_state.edit_trade_id = None
                        st.rerun()

                    st.markdown('</div>', unsafe_allow_html=True)

            st.markdown("<div style='margin-bottom:2px'></div>", unsafe_allow_html=True)


if __name__ == "__main__":
    pass
