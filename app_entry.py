"""
app_entry.py
============
Trade Entry App — private, password protected.
For 2-3 authorised users to punch trades.

Deploy on Streamlit Cloud pointing to this file.
"""

import streamlit as st
import uuid
from datetime import datetime, date, time as dtime
import pytz
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from core.sheets      import (
    read_trades, append_trade, soft_delete_trade,
    update_trade_field, get_strategy_list, get_symbols_for,
    get_lot_size, read_instruments
)
from core.angelone    import (
    get_angel_obj, fetch_current_ltp, fetch_historical_price,
    get_symbol_token
)
from core.instruments import build_expiry_months

IST = pytz.timezone("Asia/Kolkata")

st.set_page_config(
    page_title = "Trade Entry — Trading Journal",
    page_icon  = "📋",
    layout     = "wide",
)

# ── THEME ─────────────────────────────────────────────────────
st.markdown("""
<style>
html, body, [class*="css"] {
    font-family: 'Inter', -apple-system, sans-serif;
    background-color: #0F1117;
    color: #E2E8F0;
}
.stApp { background-color: #0F1117; }
section[data-testid="stSidebar"] { background-color: #1C1F26; }

/* Cards */
.entry-card {
    background: #1C1F26;
    border: 1px solid #2D3748;
    border-radius: 12px;
    padding: 20px;
    margin-bottom: 12px;
}
.trade-row {
    background: #161B22;
    border: 1px solid #2D3748;
    border-left: 4px solid #2B6CB0;
    border-radius: 8px;
    padding: 12px 16px;
    margin: 6px 0;
    font-size: 0.9rem;
}
.trade-row-new {
    border-left-color: #00D4FF !important;
}

/* Buttons */
.stButton > button {
    background: linear-gradient(135deg, #2B6CB0, #1A4A8A);
    color: #E2E8F0;
    border: none;
    border-radius: 8px;
    padding: 10px 24px;
    font-weight: 600;
    width: 100%;
    transition: all 0.2s;
}
.stButton > button:hover {
    background: linear-gradient(135deg, #3182CE, #2B6CB0);
    transform: translateY(-1px);
    box-shadow: 0 4px 12px rgba(0,212,255,0.25);
}
.stButton > button[kind="secondary"] {
    background: #2D3748;
    color: #A0AEC0;
}

/* Inputs */
.stTextInput > div > div > input,
.stNumberInput > div > div > input,
.stDateInput > div > div > input,
.stTimeInput > div > div > input {
    background: #1C1F26 !important;
    border: 1px solid #2D3748 !important;
    color: #E2E8F0 !important;
    border-radius: 8px !important;
}
.stSelectbox > div > div {
    background: #1C1F26 !important;
    border: 1px solid #2D3748 !important;
    color: #E2E8F0 !important;
    border-radius: 8px !important;
}
label { color: #A0AEC0 !important; font-size: 0.85rem !important; }
.stMetric { background: #1C1F26; border-radius: 10px; padding: 12px; }
[data-testid="stMetricValue"] { color: #00D4FF; }

/* Section headers */
.section-header {
    color: #00D4FF;
    font-size: 1.1rem;
    font-weight: 700;
    letter-spacing: 0.05em;
    padding: 8px 0;
    border-bottom: 1px solid #2D3748;
    margin-bottom: 16px;
}
.qty-display {
    background: #0D2B1A;
    border: 1px solid #00FF88;
    border-radius: 8px;
    padding: 10px 16px;
    color: #00FF88;
    font-weight: 700;
    font-size: 1.1rem;
    text-align: center;
}
.price-display {
    background: #1A2B4A;
    border: 1px solid #00D4FF;
    border-radius: 8px;
    padding: 10px 16px;
    color: #00D4FF;
    font-weight: 700;
    text-align: center;
}
.warn-box {
    background: #2D1B00;
    border: 1px solid #F6C90E;
    border-radius: 8px;
    padding: 10px 16px;
    color: #F6C90E;
    margin: 8px 0;
}
</style>
""", unsafe_allow_html=True)


# ── PASSWORD GATE ─────────────────────────────────────────────
def check_entry_password():
    return True  # Password removed — open access


# ── HELPERS ───────────────────────────────────────────────────

def now_ist():
    return datetime.now(IST)


def get_exchange_for_strategy(strategy: str, instrument: str) -> str:
    """Determine exchange based on strategy and instrument."""
    if strategy == "COMMODITIES":
        return "MCX"
    return "NSE"


def format_contract(row) -> str:
    """Format a trade row into a readable contract string."""
    instr = str(row.get("instrument", "")).upper()
    sym   = str(row.get("symbol", ""))
    if instr == "FUT":
        return f"{sym} {row.get('expiry','')} FUT"
    elif instr == "OPT":
        return f"{sym} {row.get('expiry','')} {row.get('strike','')} {row.get('option_type','')}"
    return sym


# ── MAIN APP ──────────────────────────────────────────────────
def main():
    # No password required

    # Header
    st.markdown("""
    <div style='display:flex; align-items:center; gap:12px; margin-bottom:8px;'>
        <span style='font-size:1.8rem;'>📋</span>
        <div>
            <div style='font-size:1.4rem; font-weight:800; color:#00D4FF;'>
                TRADE ENTRY
            </div>
            <div style='color:#718096; font-size:0.8rem;'>
                Trading Journal — Entry Portal
            </div>
        </div>
        <div style='margin-left:auto;'>
    """, unsafe_allow_html=True)

    st.markdown("</div></div>", unsafe_allow_html=True)
    st.divider()

    # ── TWO COLUMNS: FORM | OPEN TRADES ──────────────────────
    col_form, col_trades = st.columns([1, 1.2], gap="large")

    with col_form:
        st.markdown("<div class='section-header'>📥 NEW TRADE</div>", unsafe_allow_html=True)
        render_entry_form()

    with col_trades:
        st.markdown("<div class='section-header'>📂 OPEN TRADES (Edit / Delete)</div>",
                    unsafe_allow_html=True)
        render_open_trades_panel()


def render_entry_form():
    """Render the trade entry form."""
    strategies = get_strategy_list()
    if not strategies:
        st.warning("No strategies found. Check STRATEGIES tab in Google Sheet.")
        return

    with st.form("trade_entry", clear_on_submit=True):

        # Row 1: Strategy + Instrument
        c1, c2 = st.columns(2)
        strategy   = c1.selectbox("Strategy", strategies)
        instrument = c2.selectbox("Instrument", ["FUT", "OPT", "CASH"])

        # Determine exchange
        exchange = get_exchange_for_strategy(strategy, instrument)

        # Row 2: Symbol
        if instrument == "CASH":
            symbol   = st.text_input("Symbol (NSE Code)", placeholder="e.g. RELIANCE").upper().strip()
            expiry   = ""
            strike   = ""
            opt_type = ""
        else:
            symbols = get_symbols_for(exchange, instrument)
            if not symbols:
                st.warning(f"No {exchange} {instrument} symbols found. Run refresh_instruments.py first.")
                symbols = []
            symbol = st.selectbox("Symbol", symbols if symbols else ["—"])

            c3, c4, c5 = st.columns(3)
            expiry = c3.selectbox("Expiry", build_expiry_months(6))

            if instrument == "OPT":
                strike   = c4.number_input("Strike", min_value=0, step=50)
                opt_type = c5.selectbox("Type", ["CE", "PE"])
            else:
                strike   = ""
                opt_type = ""

        # Row 3: Action + Lots/Qty
        c6, c7 = st.columns(2)
        action = c6.selectbox("Action", ["BUY", "SELL"])

        lot_size = 1
        if instrument != "CASH" and symbol and symbol != "—":
            lot_size = get_lot_size(symbol, exchange)

        if instrument == "CASH":
            qty_input = c7.number_input("Quantity (shares)", min_value=1, step=1, value=1)
            lots      = 0
            quantity  = qty_input
        else:
            lots_input = c7.number_input("Lots", min_value=1, step=1, value=1)
            lots       = lots_input
            quantity   = lots * lot_size

        # Show quantity calculation
        if instrument != "CASH" and lot_size > 0:
            st.markdown(
                f"<div class='qty-display'>Qty: {quantity:,} shares "
                f"({lots} lot{'s' if lots > 1 else ''} × {lot_size})</div>",
                unsafe_allow_html=True
            )

        st.divider()

        # Row 4: Date + Time
        c8, c9 = st.columns(2)
        today_ist = now_ist()
        trade_date = c8.date_input("Trade Date", value=today_ist.date())
        trade_time = c9.time_input("Trade Time", value=today_ist.time().replace(second=0, microsecond=0))

        is_backdated = (trade_date < today_ist.date())
        if is_backdated:
            st.markdown(
                "<div class='warn-box'>⚠️ Backdated trade — price will be fetched from historical candle data</div>",
                unsafe_allow_html=True
            )

        # Row 5: Price override
        override_price = st.checkbox("Override price (enter manually)")
        manual_price   = 0.0
        if override_price:
            manual_price = st.number_input("Price (₹)", min_value=0.0, step=0.05, format="%.2f")

        # Notes
        notes = st.text_input("Notes (optional)", placeholder="Any notes for this trade")

        st.divider()

        # Submit
        submitted = st.form_submit_button("✅ SUBMIT TRADE", use_container_width=True)

        if submitted:
            _handle_trade_submit(
                strategy    = strategy,
                instrument  = instrument,
                exchange    = exchange,
                symbol      = symbol,
                expiry      = str(expiry),
                strike      = str(strike) if strike else "",
                opt_type    = opt_type,
                action      = action,
                lots        = lots,
                quantity    = int(quantity),
                lot_size    = lot_size,
                trade_date  = trade_date,
                trade_time  = trade_time,
                override    = override_price,
                manual_price= manual_price,
                notes       = notes,
                is_backdated= is_backdated,
            )


def _handle_trade_submit(**kwargs):
    """Process and store a submitted trade."""
    symbol      = kwargs["symbol"]
    exchange    = kwargs["exchange"]
    instrument  = kwargs["instrument"]
    trade_date  = kwargs["trade_date"]
    trade_time  = kwargs["trade_time"]
    override    = kwargs["override"]
    manual_price= kwargs["manual_price"]
    is_backdated= kwargs["is_backdated"]

    if not symbol or symbol == "—":
        st.error("Please select a symbol")
        return

    # ── Fetch price ───────────────────────────────────────────
    price        = 0.0
    price_source = "MANUAL"

    if override and manual_price > 0:
        price        = manual_price
        price_source = "MANUAL"
    else:
        # Combine date and time
        trade_dt = datetime.combine(trade_date, trade_time)
        trade_dt = IST.localize(trade_dt)

        # Get AngelOne token for this symbol
        token = get_symbol_token(symbol, exchange, instrument)

        with st.spinner("Fetching price from AngelOne..."):
            if is_backdated or trade_dt < now_ist() - __import__("datetime").timedelta(minutes=5):
                price, price_source = fetch_historical_price(symbol, exchange, token, trade_dt)
            else:
                price, price_source = fetch_current_ltp(symbol, exchange, token)

        if not price:
            st.warning("Could not fetch price automatically. Please enter manually.")
            return

    # ── Build trade row ───────────────────────────────────────
    trade_id = str(uuid.uuid4())[:12].upper()
    now_str  = now_ist().strftime("%d/%m/%Y %H:%M:%S")

    row = {
        "trade_id":        trade_id,
        "timestamp_entry": now_str,
        "trade_date":      trade_date.strftime("%d/%m/%Y"),
        "trade_time":      trade_time.strftime("%H:%M"),
        "strategy":        kwargs["strategy"],
        "exchange":        exchange,
        "instrument":      instrument,
        "symbol":          symbol,
        "expiry":          kwargs["expiry"],
        "strike":          kwargs["strike"],
        "option_type":     kwargs["opt_type"],
        "action":          kwargs["action"],
        "lots_qty":        kwargs["lots"],
        "quantity":        kwargs["quantity"],
        "price":           round(price, 2),
        "price_source":    price_source,
        "lot_size":        kwargs["lot_size"],
        "notes":           kwargs["notes"],
        "is_deleted":      "FALSE",
        "punched_by":      "Entry User",
    }

    success = append_trade(row)
    if success:
        action  = kwargs["action"]
        qty_str = f"{kwargs['lots']} lots" if instrument != "CASH" else f"{kwargs['quantity']} shares"
        st.success(
            f"✅ Trade recorded: {action} {symbol} — {qty_str} @ ₹{price:,.2f} "
            f"({price_source})"
        )
    else:
        st.error("Failed to save trade. Please try again.")


def render_open_trades_panel():
    """Show all open trade rows with edit/delete options."""
    df = read_trades()

    if df.empty:
        st.info("No trades yet. Enter your first trade.")
        return

    # Filter non-deleted rows, sort by date descending
    df = df[df["is_deleted"].astype(str).str.upper() != "TRUE"].copy()
    if df.empty:
        st.info("No active trade rows.")
        return

    # Sort newest first
    if "trade_date" in df.columns:
        df["_sort_date"] = __import__("pandas").to_datetime(
            df["trade_date"], dayfirst=True, errors="coerce"
        )
        df = df.sort_values("_sort_date", ascending=False)

    today_str = now_ist().strftime("%d/%m/%Y")

    for _, row in df.iterrows():
        trade_id    = str(row.get("trade_id", ""))
        instrument  = str(row.get("instrument", "CASH")).upper()
        contract    = format_contract(row)
        action      = str(row.get("action", ""))
        direction_color = "#00FF88" if action == "BUY" else "#FF4757"
        is_today    = str(row.get("trade_date", "")) == today_str

        card_class = "trade-row trade-row-new" if is_today else "trade-row"

        st.markdown(f"""
        <div class='{card_class}'>
            <span style='color:{direction_color}; font-weight:700;'>{action}</span>
            <span style='color:#E2E8F0; margin-left:8px; font-weight:600;'>{contract}</span>
            <span style='color:#718096; margin-left:8px; font-size:0.8rem;'>
                {row.get('strategy','')} | {row.get('lots_qty','')} lots |
                ₹{row.get('price','')}&nbsp;
                {'🆕' if is_today else ''}
            </span>
        </div>
        """, unsafe_allow_html=True)

        # Edit / Delete buttons
        e1, e2, e3, e4 = st.columns([1.5, 1.5, 0.8, 0.8])
        new_date = e1.date_input(
            "Date", key=f"ed_{trade_id}",
            value=__import__("datetime").datetime.strptime(
                str(row.get("trade_date", today_str)), "%d/%m/%Y"
            ).date()
        )
        new_time_str = e2.text_input(
            "Time (HH:MM)", key=f"et_{trade_id}",
            value=str(row.get("trade_time", "09:15"))
        )

        if e3.button("💾 Save", key=f"save_{trade_id}"):
            update_trade_field(trade_id, "trade_date", new_date.strftime("%d/%m/%Y"))
            update_trade_field(trade_id, "trade_time", new_time_str)
            st.success("Updated")
            st.rerun()

        if e4.button("🗑️ Del", key=f"del_{trade_id}", type="secondary"):
            soft_delete_trade(trade_id)
            st.success("Deleted")
            st.rerun()

        st.markdown("<hr style='border-color:#1C1F26; margin:4px 0;'>", unsafe_allow_html=True)


if __name__ == "__main__":
    main()
