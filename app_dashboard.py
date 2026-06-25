"""
app_dashboard.py
================
Audience Dashboard — read-only, password protected.
Shows open positions and strategy performance.

Deploy on Streamlit Cloud pointing to this file.
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, date, timedelta
import pytz
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from core.sheets      import read_closed_trades, get_strategy_capital, get_strategy_list
from core.positions   import compute_positions, calculate_unrealised_pnl, get_strategy_summary
from core.angelone    import fetch_ltp_batch, fetch_margin_for_positions, get_symbol_token
from core.nse_events  import fetch_corporate_events, get_event_badge

IST = pytz.timezone("Asia/Kolkata")

st.set_page_config(
    page_title = "Trading Journal — Dashboard",
    page_icon  = "📈",
    layout     = "wide",
    initial_sidebar_state = "collapsed",
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
section[data-testid="stSidebar"] { background-color: #1C1F26; border-right: 1px solid #2D3748; }

/* Metric cards */
[data-testid="metric-container"] {
    background: #1C1F26;
    border: 1px solid #2D3748;
    border-radius: 12px;
    padding: 16px !important;
}
[data-testid="stMetricValue"] { color: #00D4FF; font-size: 1.4rem !important; }
[data-testid="stMetricLabel"] { color: #718096; font-size: 0.8rem !important; }

/* Tabs */
.stTabs [data-baseweb="tab-list"] {
    background: #1C1F26; border-radius: 10px; padding: 4px; gap: 4px;
}
.stTabs [data-baseweb="tab"] {
    background: transparent; color: #718096;
    border-radius: 8px; font-weight: 600; padding: 8px 20px;
}
.stTabs [aria-selected="true"] {
    background: #2D3748 !important; color: #00D4FF !important;
}

/* Position cards */
.pos-card {
    background: #1C1F26;
    border: 1px solid #2D3748;
    border-radius: 12px;
    padding: 16px 20px;
    margin: 8px 0;
    position: relative;
}
.pos-card-new { border-left: 4px solid #00D4FF !important; }
.pos-card-long  { border-left: 4px solid #00FF88; }
.pos-card-short { border-left: 4px solid #FF4757; }

/* Strategy header */
.strat-header {
    border-radius: 10px;
    padding: 10px 18px;
    margin: 18px 0 8px 0;
    font-size: 1rem;
    font-weight: 700;
    letter-spacing: 0.04em;
}

/* Margin bar */
.margin-bar-wrap {
    background: #1C1F26;
    border: 1px solid #2D3748;
    border-radius: 10px;
    padding: 16px 20px;
    margin-bottom: 16px;
}

/* Event badges */
.event-badge {
    display: inline-block;
    padding: 3px 10px;
    border-radius: 20px;
    font-size: 0.75rem;
    font-weight: 600;
    margin-left: 8px;
}

/* Scorecard cards */
.score-card {
    background: #1C1F26;
    border: 1px solid #2D3748;
    border-radius: 12px;
    padding: 16px;
    margin-bottom: 12px;
}
.score-positive { color: #00FF88; font-weight: 700; }
.score-negative { color: #FF4757; font-weight: 700; }

label { color: #A0AEC0 !important; font-size: 0.85rem !important; }
.stButton > button {
    background: linear-gradient(135deg, #2B6CB0, #1A4A8A);
    color: #E2E8F0; border: none; border-radius: 8px;
    padding: 8px 20px; font-weight: 600;
}
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: #1C1F26; }
::-webkit-scrollbar-thumb { background: #2D3748; border-radius: 3px; }
</style>
""", unsafe_allow_html=True)

STRATEGY_COLORS = {
    "TREND":       "#F6C90E",
    "MOMENTUM":    "#00D4FF",
    "50K":         "#00FF88",
    "COMMODITIES": "#FF8C00",
    "MIDCAP":      "#9B59B6",
    "CASH":        "#1ABC9C",
    "ETF":         "#FF6B6B",
}


# ── PASSWORD GATE ─────────────────────────────────────────────
def check_viewer_password():
    if st.session_state.get("viewer_auth"):
        return True
    col1, col2, col3 = st.columns([1, 1.2, 1])
    with col2:
        st.markdown("<br><br>", unsafe_allow_html=True)
        st.markdown("""
        <div style='text-align:center; margin-bottom:28px;'>
            <div style='font-size:3rem;'>📈</div>
            <div style='font-size:1.8rem; font-weight:800; color:#00D4FF; letter-spacing:0.05em;'>
                TRADING JOURNAL
            </div>
            <div style='color:#718096; font-size:0.9rem; margin-top:4px;'>
                Live Portfolio Dashboard
            </div>
        </div>
        """, unsafe_allow_html=True)
        pwd = st.text_input("Password", type="password", placeholder="Enter viewer password")
        if st.button("🔓 View Dashboard", use_container_width=True):
            if pwd == st.secrets.get("app", {}).get("viewer_password", ""):
                st.session_state["viewer_auth"] = True
                st.rerun()
            else:
                st.error("Incorrect password")
    return False


# ── MAIN ──────────────────────────────────────────────────────
def main():
    if not check_viewer_password():
        return

    # Header bar
    h1, h2 = st.columns([4, 1])
    with h1:
        st.markdown("""
        <div style='display:flex; align-items:center; gap:12px;'>
            <span style='font-size:2rem;'>📈</span>
            <div>
                <div style='font-size:1.5rem; font-weight:800; color:#00D4FF; letter-spacing:0.05em;'>
                    TRADING JOURNAL
                </div>
                <div style='color:#718096; font-size:0.8rem;'>Live Portfolio Dashboard — NSE & MCX</div>
            </div>
        </div>
        """, unsafe_allow_html=True)
    with h2:
        now_str = datetime.now(IST).strftime("%d %b %Y  %H:%M IST")
        st.markdown(f"<div style='text-align:right; color:#718096; font-size:0.8rem; padding-top:12px;'>{now_str}</div>",
                    unsafe_allow_html=True)
        if st.button("🔄 Refresh"):
            st.cache_data.clear()
            st.rerun()

    st.divider()

    # Tabs
    tab1, tab2 = st.tabs(["📊  Open Positions", "🏆  Strategy Performance"])

    with tab1:
        render_open_positions()

    with tab2:
        render_strategy_performance()


# ── TAB 1: OPEN POSITIONS ─────────────────────────────────────
def render_open_positions():
    with st.spinner("Computing positions..."):
        open_positions, _ = compute_positions()

    if not open_positions:
        st.info("No open positions at the moment.")
        return

    capital_map = get_strategy_capital()

    # Fetch tokens + LTP for all open positions
    with st.spinner("Fetching live prices..."):
        for pos in open_positions:
            pos["token"] = get_symbol_token(
                pos["symbol"], pos["exchange"], pos["instrument"]
            )

        ltp_data = fetch_ltp_batch(open_positions)

        for pos in open_positions:
            sym_key  = f"{pos['symbol']}_{pos['exchange']}"
            ltp      = ltp_data.get(sym_key, 0)
            pos["ltp"] = ltp
            pos["unrealised_pnl"] = calculate_unrealised_pnl(pos) if ltp else 0

    # Fetch margin
    with st.spinner("Fetching margin data..."):
        margin_data = fetch_margin_for_positions(open_positions)

    # Attach margin per position (approximate distribution)
    total_margin_required = margin_data.get("_total_required", 0)

    # Fetch events for all open symbols
    symbols_tuple = tuple(set(p["symbol"] for p in open_positions if p["exchange"] == "NSE"))
    with st.spinner("Fetching events..."):
        events_map = fetch_corporate_events(symbols_tuple)

    # ── MARGIN SUMMARY BAR ────────────────────────────────────
    total_capital  = sum(capital_map.get(p["strategy"], 0) for p in open_positions)
    total_deployed = total_margin_required or sum(
        p["avg_entry_price"] * p["net_qty"] for p in open_positions
        if p["instrument"] == "CASH"
    )
    total_pnl      = sum(p["unrealised_pnl"] for p in open_positions)
    remaining      = max(0, total_capital - total_deployed)
    remaining_pct  = (remaining / total_capital * 100) if total_capital > 0 else 100

    bar_color = "#00FF88" if remaining_pct > 50 else ("#F6C90E" if remaining_pct > 20 else "#FF4757")
    bg_color  = "#0D2B1A" if remaining_pct > 50 else ("#2B1F00" if remaining_pct > 20 else "#2B0000")

    st.markdown(f"""
    <div class='margin-bar-wrap' style='background:{bg_color}; border-color:{bar_color}33;'>
        <div style='display:flex; justify-content:space-between; align-items:center; margin-bottom:10px;'>
            <span style='color:#A0AEC0; font-size:0.85rem; font-weight:600;'>MARGIN UTILISATION</span>
            <span style='color:{bar_color}; font-weight:700; font-size:1rem;'>
                {remaining_pct:.0f}% Available
            </span>
        </div>
        <div style='background:#2D3748; border-radius:6px; height:10px; overflow:hidden;'>
            <div style='background:{bar_color}; width:{min(100-remaining_pct,100):.0f}%;
                        height:100%; border-radius:6px; transition:width 0.5s;'></div>
        </div>
        <div style='display:flex; justify-content:space-between; margin-top:8px; font-size:0.8rem;'>
            <span style='color:#718096;'>Deployed: <span style='color:#E2E8F0; font-weight:600;'>
                ₹{total_deployed:,.0f}</span></span>
            <span style='color:#718096;'>Available: <span style='color:{bar_color}; font-weight:600;'>
                ₹{remaining:,.0f}</span></span>
            <span style='color:#718096;'>Total M2M: <span style='
                color:{"#00FF88" if total_pnl >= 0 else "#FF4757"}; font-weight:700;'>
                {"▲" if total_pnl >= 0 else "▼"} ₹{abs(total_pnl):,.0f}</span></span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Summary metrics
    mc1, mc2, mc3, mc4 = st.columns(4)
    mc1.metric("Open Positions", len(open_positions))
    mc2.metric("Total M2M",
               f"{'▲' if total_pnl >= 0 else '▼'} ₹{abs(total_pnl):,.0f}",
               delta=f"{total_pnl:+,.0f}")
    mc3.metric("Capital Deployed", f"₹{total_deployed:,.0f}")
    mc4.metric("Margin Available", f"₹{remaining:,.0f}")

    st.divider()

    # ── POSITIONS GROUPED BY STRATEGY ─────────────────────────
    # Sort: new trades today first, then by strategy
    open_positions.sort(key=lambda x: (not x["is_new_today"], x["strategy"]))

    current_strat = None
    for pos in open_positions:
        strat  = pos["strategy"]
        color  = STRATEGY_COLORS.get(strat, "#718096")
        cap    = capital_map.get(strat, 0)

        # Strategy header
        if strat != current_strat:
            current_strat = strat
            strat_pnl = sum(p["unrealised_pnl"] for p in open_positions if p["strategy"] == strat)
            pnl_color = "#00FF88" if strat_pnl >= 0 else "#FF4757"

            st.markdown(f"""
            <div class='strat-header'
                 style='background:linear-gradient(135deg,{color}22,{color}11);
                        border-left:4px solid {color};'>
                <span style='color:{color};'>⬡ {strat}</span>
                <span style='float:right; font-size:0.85rem; font-weight:400; color:#718096;'>
                    Capital: ₹{cap:,.0f} &nbsp;|&nbsp;
                    M2M: <span style='color:{pnl_color}; font-weight:700;'>
                        {"▲" if strat_pnl >= 0 else "▼"} ₹{abs(strat_pnl):,.0f}
                    </span>
                </span>
            </div>
            """, unsafe_allow_html=True)

        render_position_card(pos, color, events_map)


def render_position_card(pos, color, events_map):
    """Render a single open position card."""
    ltp        = pos.get("ltp", 0)
    pnl        = pos.get("unrealised_pnl", 0)
    entry      = pos.get("avg_entry_price", 0)
    direction  = pos.get("direction", "LONG")
    is_new     = pos.get("is_new_today", False)

    pnl_color  = "#00FF88" if pnl >= 0 else "#FF4757"
    dir_color  = "#00FF88" if direction == "LONG" else "#FF4757"
    dir_emoji  = "▲" if direction == "LONG" else "▼"
    pnl_pct    = ((ltp - entry) / entry * 100) if entry and ltp else 0
    if direction == "SHORT":
        pnl_pct = -pnl_pct

    instrument = pos.get("instrument", "CASH").upper()
    symbol     = pos.get("symbol", "")
    expiry     = pos.get("expiry", "")
    strike     = pos.get("strike", "")
    opt_type   = pos.get("option_type", "")

    # Contract display
    if instrument == "FUT":
        contract = f"{symbol} {expiry} FUT"
    elif instrument == "OPT":
        contract = f"{symbol} {expiry} {strike} {opt_type}"
    else:
        contract = symbol

    qty_label = f"{pos.get('lots', 0)} lots" if instrument != "CASH" else f"{int(pos.get('net_qty',0))} shares"
    ltp_str   = f"₹{ltp:,.2f}" if ltp else "Fetching..."
    margin    = pos.get("margin_required", 0)

    # Event badge
    sym_events = events_map.get(symbol.upper(), [])
    badge      = get_event_badge(sym_events)

    badge_html = ""
    if badge:
        badge_html = f"""
        <span class='event-badge' style='background:{badge["color"]}22;
              color:{badge["color"]}; border:1px solid {badge["color"]}55;'>
            {badge["label"]}
        </span>"""

    new_badge  = "🆕 <span style='color:#00D4FF; font-size:0.75rem;'>NEW TODAY</span>&nbsp;" if is_new else ""
    card_extra = "pos-card-new" if is_new else (
        "pos-card-long" if direction == "LONG" else "pos-card-short"
    )

    st.markdown(f"""
    <div class='pos-card {card_extra}' style='border-left-color:{color};'>
        <div style='display:flex; justify-content:space-between; align-items:flex-start;'>
            <div>
                {new_badge}
                <span style='font-size:1rem; font-weight:700; color:#E2E8F0;'>{contract}</span>
                <span style='margin-left:10px; color:{dir_color}; font-weight:600;'>
                    {dir_emoji} {direction}
                </span>
                <span style='margin-left:8px; color:#718096; font-size:0.85rem;'>
                    {qty_label}
                </span>
                {badge_html}
            </div>
            <div style='text-align:right;'>
                <div style='font-size:1.1rem; font-weight:700; color:{pnl_color};'>
                    {"▲" if pnl >= 0 else "▼"} ₹{abs(pnl):,.0f}
                </div>
                <div style='font-size:0.8rem; color:{pnl_color};'>{pnl_pct:+.2f}%</div>
            </div>
        </div>
        <div style='display:flex; gap:24px; margin-top:12px; font-size:0.82rem; color:#718096;'>
            <div>
                <div>Entry</div>
                <div style='color:#E2E8F0; font-weight:600;'>₹{entry:,.2f}</div>
            </div>
            <div>
                <div>LTP</div>
                <div style='color:#00D4FF; font-weight:600;'>{ltp_str}</div>
            </div>
            <div>
                <div>Days Open</div>
                <div style='color:#E2E8F0;'>{pos.get("days_open", 0)}</div>
            </div>
            <div>
                <div>Exchange</div>
                <div style='color:#E2E8F0;'>{pos.get("exchange","NSE")}</div>
            </div>
            {f'<div><div>Margin</div><div style="color:#E2E8F0;">₹{margin:,.0f}</div></div>' if margin else ""}
        </div>
    </div>
    """, unsafe_allow_html=True)


# ── TAB 2: STRATEGY PERFORMANCE ───────────────────────────────
def render_strategy_performance():
    closed_df   = read_closed_trades()
    capital_map = get_strategy_capital()

    if closed_df.empty:
        st.info("No closed trades yet. Performance will appear after first trade is exited.")
        return

    # Date filters
    st.markdown("<div style='margin-bottom:12px;'>", unsafe_allow_html=True)
    dc1, dc2, dc3 = st.columns([1, 1, 2])
    min_date = date(2024, 1, 1)
    max_date = date.today()
    from_date = dc1.date_input("From", value=date(date.today().year, 1, 1),
                                min_value=min_date, max_value=max_date)
    to_date   = dc2.date_input("To",   value=date.today(),
                                min_value=min_date, max_value=max_date)
    st.markdown("</div>", unsafe_allow_html=True)

    # Compute strategy summaries
    summaries = get_strategy_summary(
        closed_df, capital_map,
        from_date=from_date, to_date=to_date
    )

    if not summaries:
        st.info("No closed trades in this date range.")
        return

    # ── SUMMARY METRICS ROW ───────────────────────────────────
    total_net = sum(s["total_net"] for s in summaries)
    total_chg = sum(s["total_chg"] for s in summaries)
    total_trades = sum(s["n_trades"] for s in summaries)
    total_winners = sum(s["n_winners"] for s in summaries)
    overall_wr = (total_winners / total_trades * 100) if total_trades > 0 else 0

    m1, m2, m3, m4 = st.columns(4)
    pnl_color = "#00FF88" if total_net >= 0 else "#FF4757"
    m1.metric("Total Net P&L", f"₹{total_net:,.0f}")
    m2.metric("Total Trades",  total_trades)
    m3.metric("Overall Win Rate", f"{overall_wr:.1f}%")
    m4.metric("Total Charges", f"₹{total_chg:,.0f}")

    st.divider()

    # ── STRATEGY CARDS ────────────────────────────────────────
    cols = st.columns(min(len(summaries), 3))
    for i, s in enumerate(summaries):
        color     = STRATEGY_COLORS.get(s["strategy"], "#718096")
        pnl_c     = "#00FF88" if s["total_net"] >= 0 else "#FF4757"
        roi_c     = "#00FF88" if s["roi"] >= 0 else "#FF4757"

        with cols[i % 3]:
            st.markdown(f"""
            <div class='score-card' style='border-top:3px solid {color};'>
                <div style='color:{color}; font-weight:800; font-size:1rem;
                            letter-spacing:0.05em; margin-bottom:12px;'>
                    {s["strategy"]}
                </div>
                <div style='display:grid; grid-template-columns:1fr 1fr; gap:8px; font-size:0.88rem;'>
                    <div>
                        <div style='color:#718096; font-size:0.75rem;'>Net P&L</div>
                        <div class='{"score-positive" if s["total_net"]>=0 else "score-negative"}'>
                            ₹{s["total_net"]:,.0f}
                        </div>
                    </div>
                    <div>
                        <div style='color:#718096; font-size:0.75rem;'>ROI</div>
                        <div class='{"score-positive" if s["roi"]>=0 else "score-negative"}'>
                            {s["roi"]:+.2f}%
                        </div>
                    </div>
                    <div>
                        <div style='color:#718096; font-size:0.75rem;'>Win Rate</div>
                        <div style='color:#E2E8F0;'>{s["win_rate"]:.1f}%</div>
                    </div>
                    <div>
                        <div style='color:#718096; font-size:0.75rem;'>Trades</div>
                        <div style='color:#E2E8F0;'>{s["n_trades"]}
                            <span style='color:#00FF88; font-size:0.75rem;'>W:{s["n_winners"]}</span>
                            <span style='color:#FF4757; font-size:0.75rem;'> L:{s["n_losers"]}</span>
                        </div>
                    </div>
                    <div>
                        <div style='color:#718096; font-size:0.75rem;'>Best Trade</div>
                        <div style='color:#00FF88;'>₹{s["best_trade"]:,.0f}</div>
                    </div>
                    <div>
                        <div style='color:#718096; font-size:0.75rem;'>Worst Trade</div>
                        <div style='color:#FF4757;'>₹{s["worst_trade"]:,.0f}</div>
                    </div>
                    <div style='grid-column:span 2;'>
                        <div style='color:#718096; font-size:0.75rem;'>Expectancy</div>
                        <div class='{"score-positive" if s["expectancy"]>=0 else "score-negative"}'>
                            ₹{s["expectancy"]:,.0f} per trade
                        </div>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)

    st.divider()

    # ── EQUITY CURVES ──────────────────────────────────────────
    st.markdown("<div style='color:#00D4FF; font-weight:700; font-size:1.1rem; margin-bottom:12px;'>📈 Equity Curves</div>",
                unsafe_allow_html=True)

    fig = go.Figure()
    for s in summaries:
        if not s["equity_curve"]:
            continue
        color  = STRATEGY_COLORS.get(s["strategy"], "#718096")
        dates  = [pt["date"] for pt in s["equity_curve"]]
        cumulative = [pt["cumulative_pnl"] for pt in s["equity_curve"]]

        fig.add_trace(go.Scatter(
            x=dates, y=cumulative,
            name=s["strategy"],
            line=dict(color=color, width=2),
            mode="lines+markers",
            marker=dict(size=5),
            hovertemplate=(
                "<b>" + s["strategy"] + "</b><br>"
                "Date: %{x}<br>"
                "Cumulative P&L: ₹%{y:,.0f}<extra></extra>"
            )
        ))

    fig.update_layout(
        paper_bgcolor="#0F1117",
        plot_bgcolor="#1C1F26",
        font=dict(color="#E2E8F0", family="Inter"),
        legend=dict(
            bgcolor="#1C1F26", bordercolor="#2D3748",
            borderwidth=1, font=dict(size=11),
        ),
        xaxis=dict(gridcolor="#2D3748", showgrid=True, title="Date"),
        yaxis=dict(gridcolor="#2D3748", showgrid=True, title="Cumulative P&L (₹)",
                   tickprefix="₹"),
        hovermode="x unified",
        height=400,
        margin=dict(l=20, r=20, t=20, b=20),
    )
    fig.add_hline(y=0, line_dash="dash", line_color="#4A5568", line_width=1)
    st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # ── TOP TRADES PER STRATEGY ───────────────────────────────
    st.markdown("<div style='color:#00D4FF; font-weight:700; font-size:1.1rem; margin-bottom:12px;'>🏆 Top Trades</div>",
                unsafe_allow_html=True)

    for s in summaries:
        if not s["top_trades"]:
            continue
        color = STRATEGY_COLORS.get(s["strategy"], "#718096")
        with st.expander(f"⬡ {s['strategy']} — Top Trades", expanded=False):
            for rank, trade in enumerate(s["top_trades"], 1):
                pnl_val = float(str(trade.get("net_pnl", 0)).replace(",", ""))
                st.markdown(f"""
                <div style='display:flex; justify-content:space-between;
                            padding:8px 12px; margin:4px 0;
                            background:#161B22; border-radius:8px;
                            border-left:3px solid {color};'>
                    <span style='color:#718096; min-width:24px;'>#{rank}</span>
                    <span style='color:#E2E8F0; flex:1;'>
                        {trade.get("symbol","")} {trade.get("instrument","")}
                    </span>
                    <span style='color:#718096; font-size:0.8rem;'>
                        {trade.get("close_date","")}
                    </span>
                    <span style='color:#00FF88; font-weight:700; min-width:100px; text-align:right;'>
                        ₹{pnl_val:,.0f}
                    </span>
                </div>
                """, unsafe_allow_html=True)


if __name__ == "__main__":
    main()
