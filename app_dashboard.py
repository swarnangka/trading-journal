"""PARABOLIC DASHBOARD — Audience View (read-only)"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import gspread
import pytz
from datetime import datetime, date, timedelta
from google.oauth2.service_account import Credentials
import requests

st.set_page_config(page_title="ParabolicTrends · Dashboard", page_icon="📊", layout="wide", initial_sidebar_state="collapsed")

# ── PASSWORD GATE ────────────────────────────────────────────────────────────
QUOTES = [
    ("The trend is your friend until the end when it bends.", "Ed Seykota"),
    ("I just wait until there is money lying in the corner, and all I have to do is go over there and pick it up.", "Jim Rogers"),
    ("The game of speculation is the most uniformly fascinating game in the world. But it is not a game for the stupid, the mentally lazy, the person of inferior emotional balance.", "Jesse Livermore"),
    ("Cut losses. Let profits run.", "Ed Seykota"),
    ("There is only one side of the market and it is not the bull side or the bear side, but the right side.", "Jesse Livermore"),
    ("Everybody gets what they want from the markets.", "Ed Seykota"),
    ("The markets are never wrong — opinions often are.", "Jesse Livermore"),
    ("Win or lose, everybody gets what they want out of the market. Some people seem to like to lose, so they win by losing money.", "Ed Seykota"),
    ("It takes patience, discipline and courage to follow the trend.", "Dennis Ritchards"),
    ("I keep a close eye on the big picture — the trend. You have to know what you want before you can get it.", "Dennis Ritchards"),
    ("Trade with the trend. It's the path of least resistance.", "Dennis Ritchards"),
    ("The elements of good trading are: cutting losses, cutting losses, and cutting losses.", "Ed Seykota"),
    ("Markets are never wrong — only opinions are.", "Jesse Livermore"),
    ("I don't think about losing. I think about making money.", "Paul Tudor Jones"),
    ("The most important thing is to have a method for staying with your winners and getting rid of your losers.", "Gary Bielfeldt"),
    ("At the end of the day, the most important thing is how good are you at risk control.", "Paul Tudor Jones"),
    ("Where you want to be is always in control, never wishing, always trading, and always, first and foremost protecting your butt.", "Paul Tudor Jones"),
    ("Losers average losers.", "Paul Tudor Jones"),
    ("The key to trading success is emotional discipline. If intelligence were the key, there would be a lot more people making money trading.", "Victor Sperandeo"),
    ("The trend is your friend, follow it to the end.", "Michael Covel"),
    ("I have two basic rules about winning in trading as well as in life: If you don't bet, you can't win. If you lose all your chips, you can't bet.", "Larry Hite"),
    ("Risk no more than you can afford to lose, and also risk enough so that a win is meaningful.", "Ed Seykota"),
    ("The biggest risk is not taking a risk.", "Michael Covel"),
    ("Markets trend only 15 to 20 percent of the time; the rest of the time they move sideways.", "Richard Donchian"),
    ("Follow the trend lines, not the headlines.", "Bill Miller"),
    ("In this business if you're good, you're right six times out of ten.", "Peter Lynch"),
    ("Know what you own, and know why you own it.", "Peter Lynch"),
    ("The stock market is filled with individuals who know the price of everything, but the value of nothing.", "Philip Fisher"),
    ("Be fearful when others are greedy, and greedy when others are fearful.", "Warren Buffett"),
    ("Price is what you pay, value is what you get.", "Warren Buffett"),
    ("The individual investor should act consistently as an investor and not as a speculator.", "Benjamin Graham"),
    ("The four most dangerous words in investing are: this time it's different.", "Sir John Templeton"),
    ("Successful investing is about managing risk, not avoiding it.", "Benjamin Graham"),
    ("Good investing is boring.", "George Soros"),
    ("It's not whether you're right or wrong, but how much money you make when you're right and how much you lose when you're wrong.", "George Soros"),
    ("Trade the trend, not your opinion.", "Anonymous"),
    ("He who lives by the crystal ball soon learns to eat ground glass.", "Edgar Fiedler"),
    ("The secret to being successful from a trading perspective is to have an indefatigable and an undying and unquenchable thirst for information and knowledge.", "Paul Tudor Jones"),
    ("Compound interest is the eighth wonder of the world.", "Albert Einstein"),
    ("October. This is one of the peculiarly dangerous months to speculate in stocks. The others are July, January, September, April, November, May, March, June, December, August, and February.", "Mark Twain"),
]

def check_password():
    """Returns True if correct password entered, shows motivational screen if not."""
    if st.session_state.get("_auth_ok"):
        return True

    # Build scrolling ticker text — quotes joined by separator
    ticker_items = "".join(
        f'<span class="qt-item">'
        f'<span class="qt-text">"{q}"</span>'
        f'<span class="qt-attr">— {a}</span>'
        f'</span>'
        f'<span class="qt-sep">✦</span>'
        for q, a in QUOTES
    )
    # Duplicate for seamless loop
    ticker_html = ticker_items * 2

    st.markdown(f"""
    <style>
    html, body, [class*="css"], .stApp {{
        background: #05050d !important;
        color: #e2e8f0;
        font-family: 'Inter', sans-serif;
    }}
    .block-container {{ padding: 0 !important; max-width: 100% !important; }}

    /* ── Full screen layout ── */
    .login-screen {{
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        min-height: 100vh;
        background: #05050d;
        position: relative;
        overflow: hidden;
    }}

    /* ── Background grid ── */
    .login-screen::before {{
        content: '';
        position: absolute;
        inset: 0;
        background-image:
            linear-gradient(rgba(124,111,205,0.04) 1px, transparent 1px),
            linear-gradient(90deg, rgba(124,111,205,0.04) 1px, transparent 1px);
        background-size: 60px 60px;
        pointer-events: none;
    }}

    /* ── Logo ── */
    .login-logo {{
        font-size: 2.6rem;
        font-weight: 800;
        letter-spacing: 0.04em;
        margin-bottom: 0.3rem;
        z-index: 2;
    }}
    .login-tagline {{
        font-size: 0.72rem;
        color: #334155;
        letter-spacing: 0.22em;
        text-transform: uppercase;
        margin-bottom: 3.5rem;
        z-index: 2;
    }}

    /* ── Ticker tape wrapper ── */
    .ticker-outer {{
        width: 100%;
        overflow: hidden;
        background: linear-gradient(135deg, #0d0d1f 0%, #0a0a18 100%);
        border-top: 1px solid rgba(124,111,205,0.2);
        border-bottom: 1px solid rgba(124,111,205,0.2);
        padding: 28px 0;
        margin-bottom: 4rem;
        position: relative;
        z-index: 2;
    }}
    .ticker-outer::before,
    .ticker-outer::after {{
        content: '';
        position: absolute;
        top: 0; bottom: 0;
        width: 120px;
        z-index: 3;
    }}
    .ticker-outer::before {{
        left: 0;
        background: linear-gradient(90deg, #05050d, transparent);
    }}
    .ticker-outer::after {{
        right: 0;
        background: linear-gradient(-90deg, #05050d, transparent);
    }}
    .ticker-track {{
        display: flex;
        align-items: center;
        white-space: nowrap;
        animation: scroll-left 220s linear infinite;
        will-change: transform;
    }}
    @keyframes scroll-left {{
        0%   {{ transform: translateX(0); }}
        100% {{ transform: translateX(-50%); }}
    }}
    .qt-item {{
        display: inline-flex;
        align-items: baseline;
        gap: 14px;
        margin-right: 0;
    }}
    .qt-text {{
        font-size: 1.25rem;
        font-weight: 600;
        color: #c8c0f0;
        font-style: italic;
        letter-spacing: 0.01em;
    }}
    .qt-attr {{
        font-size: 0.78rem;
        font-weight: 700;
        color: #f97316;
        letter-spacing: 0.1em;
        text-transform: uppercase;
        white-space: nowrap;
    }}
    .qt-sep {{
        font-size: 1.2rem;
        color: rgba(124,111,205,0.4);
        margin: 0 48px;
    }}

    /* ── Password box ── */
    .pw-wrap {{
        z-index: 2;
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 12px;
        width: 320px;
    }}
    .pw-label {{
        font-size: 0.65rem;
        color: #334155;
        letter-spacing: 0.2em;
        text-transform: uppercase;
        margin-bottom: -4px;
    }}

    /* Streamlit widget overrides for dark inputs */
    .stTextInput > div > div > input {{
        background: #0f0f1a !important;
        border: 1px solid #252538 !important;
        border-radius: 6px !important;
        color: #e2e8f0 !important;
        font-size: 0.9rem !important;
        text-align: center !important;
        letter-spacing: 0.2em !important;
        padding: 10px 16px !important;
    }}
    .stTextInput > div > div > input:focus {{
        border-color: #7c6fcd !important;
        box-shadow: 0 0 0 2px rgba(124,111,205,0.15) !important;
    }}
    .stButton > button {{
        background: linear-gradient(135deg, #7c6fcd, #6357b8) !important;
        color: #ffffff !important;
        border: none !important;
        border-radius: 6px !important;
        font-size: 0.8rem !important;
        font-weight: 600 !important;
        letter-spacing: 0.12em !important;
        padding: 10px 32px !important;
        width: 100% !important;
        cursor: pointer !important;
        transition: opacity 0.15s !important;
    }}
    .stButton > button:hover {{
        opacity: 0.88 !important;
    }}
    </style>

    <div class="login-screen">
      <div class="login-logo">
        <span style="color:#ffffff;">Parabolic</span><span style="color:#7c6fcd;">Trends</span>
      </div>
      <div class="login-tagline">Trend · Follow · Profit</div>

      <div class="ticker-outer">
        <div class="ticker-track">{ticker_html}</div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    # Centered password form
    _, mid, _ = st.columns([1, 1, 1])
    with mid:
        st.markdown('<div class="pw-label">Enter Access Password</div>', unsafe_allow_html=True)
        pwd = st.text_input("pw", type="password", placeholder="••••••••",
                            label_visibility="collapsed", key="pw_input")
        if st.button("ENTER DASHBOARD →", use_container_width=True):
            correct = str(st.secrets.get("dashboard", {}).get("password", ""))
            if pwd and pwd == correct:
                st.session_state["_auth_ok"] = True
                st.rerun()
            else:
                st.markdown(
                    '<div style="color:#ef4444;font-size:0.75rem;text-align:center;'
                    'margin-top:6px;letter-spacing:0.05em;">Incorrect password</div>',
                    unsafe_allow_html=True
                )
    return False

if not check_password():
    st.stop()

# ─────────────────────────────────────────────────────────────────────────────
IST    = pytz.timezone("Asia/Kolkata")
SCOPES = ["https://www.googleapis.com/auth/spreadsheets","https://www.googleapis.com/auth/drive"]
TAB_TRADES   = "TRADES"
TAB_CLOSED   = "CLOSED_TRADES"
TAB_STRATEGIES = "STRATEGIES"

# ── CSS (identical to entry app) ──────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');
html,body,[class*="css"]{font-family:'Inter',sans-serif;background:#0a0a0f;color:#e2e8f0;}
.stApp{background:#0a0a0f;}
.block-container{padding:1.5rem 2rem 3rem 2rem;max-width:1400px;}
.pb-header{display:flex;align-items:baseline;gap:12px;padding:0 0 1.2rem 0;border-bottom:1px solid #1e1e2e;margin-bottom:1.5rem;}
.pb-logo{font-size:1.1rem;font-weight:700;letter-spacing:0.12em;text-transform:uppercase;}
.pb-sub{font-size:0.75rem;color:#475569;letter-spacing:0.08em;text-transform:uppercase;}
.section-title{font-size:0.7rem;font-weight:700;letter-spacing:0.16em;text-transform:uppercase;color:#94a3b8;margin-bottom:1rem;padding-bottom:0.6rem;border-bottom:1px solid #1e1e2e;}
.badge-buy{background:rgba(34,197,94,0.12);border:1px solid rgba(34,197,94,0.3);color:#22c55e;border-radius:4px;padding:2px 8px;font-size:0.65rem;font-weight:600;}
.badge-sell{background:rgba(239,68,68,0.12);border:1px solid rgba(239,68,68,0.3);color:#ef4444;border-radius:4px;padding:2px 8px;font-size:0.65rem;font-weight:600;}
.badge-new{background:rgba(249,115,22,0.15);border:1px solid rgba(249,115,22,0.35);color:#f97316;border-radius:4px;padding:1px 6px;font-size:0.6rem;font-weight:700;margin-left:4px;}
.stat-box{background:#0f0f1a;border:1px solid #1e1e2e;border-radius:7px;padding:14px 16px;height:90px;display:flex;flex-direction:column;justify-content:space-between;}
.stat-label{font-size:0.58rem;color:#475569;letter-spacing:0.12em;text-transform:uppercase;margin-bottom:0;}
.stat-value{font-size:1.1rem;font-weight:700;font-family:'JetBrains Mono',monospace;line-height:1.2;margin:0;}
.stat-sub{font-size:0.6rem;color:#475569;margin-top:0;}
.trade-symbol{font-size:0.88rem;font-weight:600;color:#e2e8f0;margin-bottom:3px;line-height:1.3;}
.trade-meta{font-size:0.71rem;color:#475569;font-family:'JetBrains Mono',monospace;line-height:1.5;}
.card{background:#0f0f1a;border:1px solid #1e1e2e;border-radius:10px;padding:1.4rem 1.6rem;margin-bottom:1.2rem;}
.card-header{display:flex;align-items:center;gap:12px;margin-bottom:1rem;padding-bottom:0.8rem;border-bottom:1px solid #1e1e2e;}
.strat-badge{background:rgba(249,115,22,0.12);border:1px solid rgba(249,115,22,0.3);border-radius:5px;padding:5px 14px;font-size:0.75rem;font-weight:700;letter-spacing:0.1em;color:#f97316;text-transform:uppercase;white-space:nowrap;}
.metric-row{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-bottom:1rem;}
.metric-item{background:#141420;border:1px solid #1e1e2e;border-radius:6px;padding:10px 12px;}
.metric-label{font-size:0.58rem;color:#475569;letter-spacing:0.1em;text-transform:uppercase;margin-bottom:3px;}
.metric-value{font-size:0.9rem;font-weight:700;font-family:'JetBrains Mono',monospace;}
.top-trade-row{display:flex;align-items:center;justify-content:space-between;padding:7px 0;border-bottom:1px solid #1e1e2e;}
.top-trade-rank{font-size:0.65rem;color:#475569;font-weight:600;min-width:16px;}
.top-trade-sym{font-size:0.8rem;font-weight:600;color:#e2e8f0;}
.top-trade-detail{font-size:0.7rem;color:#475569;font-family:'JetBrains Mono',monospace;}
.divider{border:none;border-top:1px solid #1e1e2e;margin:0.8rem 0;}
#MainMenu,footer,header{visibility:hidden;}
.stDeployButton{display:none;}
</style>
""", unsafe_allow_html=True)


# ── SHEETS ────────────────────────────────────────────────────────────────────
@st.cache_resource(ttl=3600)
def get_client():
    raw = dict(st.secrets["gcp_service_account"])
    pk  = str(raw.get("private_key","")).replace("\\n","\n")
    if not pk.endswith("\n"): pk += "\n"
    raw["private_key"] = pk
    return gspread.authorize(Credentials.from_service_account_info(raw, scopes=SCOPES))

@st.cache_resource(ttl=3600)
def get_spreadsheet():
    return get_client().open_by_key(st.secrets["app"]["sheet_id"])

@st.cache_resource(ttl=3600)
def get_ws_cached(tab):
    return get_spreadsheet().worksheet(tab)

def get_ws(tab):
    return get_ws_cached(tab)


# ── DATA ──────────────────────────────────────────────────────────────────────
@st.cache_data(ttl=60)
def read_open_trades():
    try:
        data = get_ws(TAB_TRADES).get_all_records()
        if not data: return pd.DataFrame()
        df = pd.DataFrame(data)
        if "is_deleted" in df.columns:
            df = df[df["is_deleted"].astype(str).str.upper() != "TRUE"]
        return df
    except: return pd.DataFrame()

@st.cache_data(ttl=60)
def read_closed_trades():
    try:
        data = get_ws(TAB_CLOSED).get_all_records()
        return pd.DataFrame(data) if data else pd.DataFrame()
    except: return pd.DataFrame()

@st.cache_data(ttl=300)
def read_strategies():
    try:
        data = get_ws(TAB_STRATEGIES).get_all_records()
        return pd.DataFrame(data) if data else pd.DataFrame()
    except: return pd.DataFrame()

@st.cache_data(ttl=3600)
def read_instruments():
    try:
        data = get_ws("INSTRUMENTS").get_all_records()
        return pd.DataFrame(data) if data else pd.DataFrame()
    except: return pd.DataFrame()

def get_lot_size(symbol):
    if not symbol: return 1
    df = read_instruments()
    if df.empty or "symbol" not in df.columns or "lot_size" not in df.columns: return 1
    m = df[df["symbol"].str.upper().str.strip() == symbol.upper().strip()]
    if m.empty: return 1
    try:
        v = int(str(m.iloc[0]["lot_size"]).strip())
        return v if v > 0 else 1
    except: return 1

def get_strategy_capital(strategy_name):
    df = read_strategies()
    if df.empty or "strategy_name" not in df.columns: return 0
    m = df[df["strategy_name"] == strategy_name]
    if m.empty: return 0
    try:
        cap = str(m.iloc[0].get("allocated_capital","0")).replace("L","").replace("l","").strip()
        v = float(cap)
        return v * 100000 if v < 10000 else v
    except: return 0


# ── ANGELONE LTP ──────────────────────────────────────────────────────────────
@st.cache_resource(ttl=3600)
def get_angel_obj():
    try:
        import pyotp
        cfg     = st.secrets["angelone"]
        api_key = "".join(c for c in str(cfg["api_key"]).strip() if c.isprintable() and c > " ")
        totp    = pyotp.TOTP(str(cfg["totp_secret"]).strip()).now()
        headers = {
            "Content-Type":"application/json","Accept":"application/json",
            "X-UserType":"USER","X-SourceID":"WEB",
            "X-ClientLocalIP":"127.0.0.1","X-ClientPublicIP":"106.193.147.98",
            "X-MACAddress":"AA:BB:CC:DD:EE:FF","X-PrivateKey":api_key,
        }
        resp = requests.post(
            "https://apiconnect.angelone.in/rest/auth/angelbroking/user/v1/loginByPassword",
            json={"clientcode":str(cfg["client_id"]).strip(),"password":str(cfg["password"]).strip(),"totp":totp},
            headers=headers, timeout=15
        )
        data = resp.json()
        if data.get("status") and data.get("data"):
            jwt = data["data"].get("jwtToken","")
            if jwt:
                class _AO:
                    def __init__(self,j,k): self.jwt=j; self.api_key=k
                return _AO(jwt, api_key)
    except: pass
    return None

def fetch_ltp_batch(positions):
    """Fetch LTP for multiple symbols. Returns {symbol: ltp}."""
    ao = get_angel_obj()
    if not ao: return {}
    ltp_map = {}
    try:
        from core.angelone import get_symbol_token, fetch_current_ltp
        for pos in positions:
            sym   = pos.get("symbol","")
            exch  = pos.get("exchange","NSE")
            instr = pos.get("instrument","FUT")
            exp   = pos.get("expiry","")
            if sym and sym not in ltp_map:
                token = get_symbol_token(sym, exch, instr, exp)
                ltp, _ = fetch_current_ltp(sym, exch, token, instr)
                if ltp and ltp > 0:
                    ltp_map[sym] = ltp
    except: pass
    return ltp_map


# ── UTILS ──────────────────────────────────────────────────────────────────────
def now_ist():
    return datetime.now(IST)

def badge(action):
    c = "badge-buy" if action=="BUY" else "badge-sell"
    return f'<span class="{c}">{action}</span>'

def fmt_px(v):
    try: return f"₹{float(v):,.2f}"
    except: return str(v)

def fmt_cr(v):
    try:
        fv = float(v)
        sign = "+" if fv >= 0 else ""
        return f"{sign}₹{abs(fv):,.0f}"
    except: return str(v)

def pnl_color(v):
    try: return "#22c55e" if float(v) >= 0 else "#ef4444"
    except: return "#e2e8f0"


# ══════════════════════════════════════════════════════════════════════════════
# HEADER
# ══════════════════════════════════════════════════════════════════════════════
st.markdown(
    '<div class="pb-header">'
    '<span class="pb-logo"><span style="color:#ffffff;">Parabolic</span>'
    '<span style="color:#7c6fcd;">Trends</span></span>'
    '<span class="pb-sub" style="margin-left:16px;">Dashboard</span>'
    '</div>',
    unsafe_allow_html=True
)

# Refresh button
if st.button("↻ Refresh"):
    read_open_trades.clear()
    read_closed_trades.clear()
    st.rerun()

st.markdown("<div class='divider'></div>", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 1 — OPEN POSITIONS
# ══════════════════════════════════════════════════════════════════════════════
st.markdown('<div class="section-title">✦ Open Positions</div>', unsafe_allow_html=True)

df_open   = read_open_trades()
today_str = now_ist().strftime("%Y-%m-%d")

if df_open.empty:
    st.markdown('<div style="color:#475569;font-size:0.82rem;padding:1rem 0;">No open positions.</div>', unsafe_allow_html=True)
else:
    if "timestamp_entry" in df_open.columns:
        df_open = df_open.sort_values("timestamp_entry", ascending=False)

    # Fetch LTP for all open positions
    positions_list = [
        {"symbol": str(r.get("symbol","")), "exchange": str(r.get("exchange","NSE")),
         "instrument": str(r.get("instrument","FUT")), "expiry": str(r.get("expiry",""))}
        for _, r in df_open.iterrows()
    ]
    ltp_map = fetch_ltp_batch(positions_list)

    # Build margin map
    margin_map = {}
    for _, row in df_open.iterrows():
        sym   = str(row.get("symbol",""))
        instr = str(row.get("instrument","FUT"))
        tid   = str(row.get("trade_id",""))
        if sym in ltp_map:
            ltp = ltp_map[sym]
            if instr.upper() == "CASH":
                qty = float(row.get("quantity",0) or 0)
                margin_map[tid] = ltp * qty * 0.20
            else:
                ls  = get_lot_size(sym)
                lts = float(row.get("lots_qty",0) or 0)
                qty = lts * ls if ls > 1 else float(row.get("quantity",0) or 0)
                pct = 0.12 if instr.upper()=="OPT" else 0.15
                margin_map[tid] = ltp * qty * pct

    # Summary metrics
    total_capital = 0
    try:
        df_st = read_strategies()
        if not df_st.empty and "allocated_capital" in df_st.columns:
            for _, sr in df_st.iterrows():
                try:
                    cv = float(str(sr["allocated_capital"]).replace("L","").replace("l","").strip())
                    total_capital += cv * 100000 if cv < 10000 else cv
                except: pass
    except: pass

    total_mtm     = 0.0
    total_margin  = sum(margin_map.values())
    for _, row in df_open.iterrows():
        sym = str(row.get("symbol",""))
        if sym in ltp_map:
            ep  = float(row.get("price",0) or 0)
            qty = float(row.get("quantity",0) or 0)
            act = str(row.get("action","BUY")).upper()
            total_mtm += ((ltp_map[sym]-ep)*qty) if act=="BUY" else ((ep-ltp_map[sym])*qty)

    mtm_c  = "#22c55e" if total_mtm>=0 else "#ef4444"
    mtm_s  = ("+" if total_mtm>=0 else "")+f"₹{abs(total_mtm):,.0f}" if ltp_map else "—"
    mg_s   = f"₹{total_margin/100000:.1f}L" if total_margin>0 else "—"
    mg_p   = f"{total_margin/total_capital*100:.1f}%" if total_capital>0 and total_margin>0 else ""
    mg_c   = "#22c55e" if (total_margin/total_capital<0.5 if total_capital>0 and total_margin>0 else True) else "#eab308"
    cr_s   = f"₹{(total_capital-total_margin)/100000:.1f}L" if total_capital>0 and total_margin>0 else "—"
    n_pos  = len(df_open)
    n_buy  = len(df_open[df_open["action"].str.upper()=="BUY"]) if "action" in df_open.columns else 0

    m1, m2, m3, m4 = st.columns(4)
    m1.markdown(f'<div class="stat-box"><div class="stat-label">Positions</div><div class="stat-value" style="color:#e2e8f0">{n_pos}</div><div class="stat-sub">{n_buy}L · {n_pos-n_buy}S</div></div>', unsafe_allow_html=True)
    m2.markdown(f'<div class="stat-box"><div class="stat-label">Total MTM</div><div class="stat-value" style="color:{mtm_c}">{mtm_s}</div><div class="stat-sub">{"live" if ltp_map else "needs AngelOne"}</div></div>', unsafe_allow_html=True)
    m3.markdown(f'<div class="stat-box"><div class="stat-label">Margin Utilised</div><div style="display:flex;align-items:baseline;gap:8px;"><span style="font-size:1.1rem;font-weight:700;font-family:JetBrains Mono,monospace;color:{mg_c};">{mg_s}</span><span style="font-size:0.82rem;font-weight:600;color:{mg_c};">{mg_p}</span></div><div class="stat-sub">{"of ₹"+str(int(total_capital//100000))+"L capital" if total_capital>0 else "SPAN estimated"}</div></div>', unsafe_allow_html=True)
    m4.markdown(f'<div class="stat-box"><div class="stat-label">Margin Remaining</div><div class="stat-value" style="color:#e2e8f0">{cr_s}</div><div class="stat-sub">{"of ₹"+str(int(total_capital//100000))+"L total" if cr_s!="—" else "add AngelOne"}</div></div>', unsafe_allow_html=True)

    st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)

    # Strategy grouped positions
    STRATEGY_ORDER = ["TREND","COMMODITIES","MOMENTUM"]
    all_strats = df_open["strategy"].unique().tolist() if "strategy" in df_open.columns else []
    ordered    = [s for s in STRATEGY_ORDER if s in all_strats]
    others     = sorted([s for s in all_strats if s not in STRATEGY_ORDER])

    for strategy_name in ordered + others:
        strat_df = df_open[df_open["strategy"]==strategy_name].copy()

        # Strategy MTM + margin
        strat_mtm = 0.0
        for _, row in strat_df.iterrows():
            sym = str(row.get("symbol",""))
            if sym in ltp_map:
                ep  = float(row.get("price",0) or 0)
                qty = float(row.get("quantity",0) or 0)
                act = str(row.get("action","BUY")).upper()
                strat_mtm += ((ltp_map[sym]-ep)*qty) if act=="BUY" else ((ep-ltp_map[sym])*qty)

        strat_margin  = sum(margin_map.get(str(r.get("trade_id","")),0) for _,r in strat_df.iterrows())
        strat_capital = get_strategy_capital(strategy_name)
        strat_rem     = strat_capital - strat_margin if strat_capital>0 and strat_margin>0 else None
        strat_mtm_c   = "#22c55e" if strat_mtm>=0 else "#ef4444"
        strat_mtm_s   = ("+" if strat_mtm>=0 else "")+f"₹{abs(strat_mtm):,.0f}" if ltp_map else "—"
        strat_mg_s    = f"₹{strat_margin/100000:.1f}L" if strat_margin>0 else "—"
        strat_rem_s   = f"₹{strat_rem/100000:.1f}L free" if strat_rem else ""
        strat_mg_c    = "#22c55e" if strat_rem and strat_rem>0 else "#475569"
        strat_today   = len(strat_df[strat_df["trade_date"].astype(str)==today_str]) if "trade_date" in strat_df.columns else 0

        sc1,sc2,sc3,sc4,sc5 = st.columns([1.2,0.8,1.2,1.8,0.8])
        sc1.markdown(f'<div class="strat-badge">{strategy_name}</div>', unsafe_allow_html=True)
        sc2.markdown(f'<div class="stat-label">Positions</div><div style="font-size:0.95rem;font-weight:700;color:#e2e8f0;">{len(strat_df)}</div>', unsafe_allow_html=True)
        sc3.markdown(f'<div class="stat-label">MTM P&L</div><div style="font-size:0.95rem;font-weight:700;color:{strat_mtm_c};">{strat_mtm_s}</div>', unsafe_allow_html=True)
        _rem_html = f'  ·  <span style="color:#22c55e">{strat_rem_s}</span>' if strat_rem_s else ""
        sc4.markdown(f'<div class="stat-label">Utilised · Remaining</div>'
            f'<div style="font-size:0.85rem;font-weight:600;color:{strat_mg_c};">{strat_mg_s}{_rem_html}</div>',
            unsafe_allow_html=True)
        sc5.markdown(f'<div class="stat-label">Today</div><div style="font-size:0.95rem;font-weight:700;color:#f97316;">{strat_today}</div>', unsafe_allow_html=True)

        st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)

        # Aggregate positions
        grp_cols  = ["symbol","instrument","expiry","strike","option_type","action"]
        avail_gc  = [c for c in grp_cols if c in strat_df.columns]
        agg_rows  = []
        for grp_key, grp in strat_df.groupby(avail_gc, dropna=False, sort=False):
            base = grp.sort_values("timestamp_entry").iloc[0].copy() if "timestamp_entry" in grp.columns else grp.iloc[0].copy()
            total_lots, total_qty, wprice_sum = 0.0, 0.0, 0.0
            earliest = None
            for _, r in grp.iterrows():
                lots_r = float(r.get("lots_qty", r.get("quantity",0)) or 0)
                px_r   = float(r.get("price",0) or 0)
                ls_r   = get_lot_size(str(r.get("symbol","")))
                qty_r  = lots_r * ls_r if ls_r > 1 else float(r.get("quantity",0) or 0)
                total_lots += lots_r; total_qty += qty_r; wprice_sum += px_r * qty_r
                dt_r = str(r.get("trade_date",""))
                if dt_r and (earliest is None or dt_r < earliest): earliest = dt_r
            avg_px = wprice_sum / total_qty if total_qty > 0 else 0
            base["lots_qty"]   = total_lots
            base["quantity"]   = int(total_qty)
            base["price"]      = round(avg_px, 2)
            base["trade_date"] = earliest or str(base.get("trade_date",""))
            base["_agg_count"] = len(grp)
            agg_rows.append(base)

        render_df = pd.DataFrame(agg_rows) if agg_rows else strat_df

        for _ri, (_, row) in enumerate(render_df.iterrows()):
            tid   = str(row.get("trade_id","")).strip()
            sym   = str(row.get("symbol","")).strip()
            act   = str(row.get("action","")).strip()
            instr = str(row.get("instrument","")).strip()
            exp_v = str(row.get("expiry","")).strip()
            stk_v = str(row.get("strike","")).strip()
            opt_v = str(row.get("option_type","")).strip()
            lv    = str(row.get("lots_qty","")).strip()
            qv    = str(row.get("quantity","")).strip()
            pv    = row.get("price",0)
            dt_v  = str(row.get("trade_date","")).strip()
            if not tid or not sym or not act: continue

            desc  = sym
            if exp_v: desc += f" {exp_v}"
            if stk_v and stk_v not in ("","0"): desc += f" {stk_v}{opt_v}"
            new_b = '<span class="badge-new">NEW</span>' if dt_v==today_str else ""
            agg_c = int(row.get("_agg_count",1))
            agg_b = f'<span style="font-size:0.6rem;color:#7c6fcd;margin-left:4px;">[{agg_c} trades]</span>' if agg_c>1 else ""

            # Days open
            try:
                days_open = (now_ist().date()-datetime.strptime(dt_v,"%Y-%m-%d").date()).days
                days_str  = "today" if days_open==0 else f"{days_open}d"
            except: days_str = "—"

            # Qty info
            cur_ls  = get_lot_size(sym)
            cur_qty = int(float(lv))*cur_ls if (lv.replace(".","").isdigit() and cur_ls>1) else qv
            qty_info = f"{lv}L×{cur_ls}={cur_qty}sh" if instr!="CASH" else f"{qv}sh"

            # LTP + MTM
            ltp_line = ""
            if sym in ltp_map:
                lp = ltp_map[sym]
                try:
                    ep   = float(pv); qty = float(qv)
                    pnl  = (lp-ep)*qty if act.upper()=="BUY" else (ep-lp)*qty
                    pc   = "#22c55e" if pnl>=0 else "#ef4444"
                    sign = "+" if pnl>=0 else ""
                    ltp_line = (f' &nbsp;·&nbsp; <span style="color:#94a3b8">LTP {fmt_px(lp)}</span>'
                                f' <span style="color:{pc};font-weight:600">{sign}₹{abs(pnl):,.0f}</span>')
                except: ltp_line = f' &nbsp;·&nbsp; <span style="color:#94a3b8">LTP {fmt_px(ltp_map[sym])}</span>'

            pos_margin    = margin_map.get(tid,0)
            pos_margin_s  = f"Mrgn ₹{pos_margin/100000:.2f}L" if pos_margin>0 else ""

            st.markdown(
                f'<div style="background:#0f0f1a;border:1px solid #1e1e2e;border-radius:6px;padding:10px 14px;margin-bottom:5px;">'
                f'<div class="trade-symbol">{badge(act)} &nbsp;{desc}{new_b}{agg_b}</div>'
                f'<div class="trade-meta">{qty_info} · {fmt_px(pv)} entry{ltp_line}</div>'
                f'<div class="trade-meta">{dt_v} · {days_str} open'
                f'{"  ·  <span style=\\'color:#7c6fcd;\\'>" + pos_margin_s + "</span>" if pos_margin_s else ""}'
                f'</div></div>',
                unsafe_allow_html=True
            )

        st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 2 — STRATEGY PERFORMANCE
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("<div class='divider'></div>", unsafe_allow_html=True)
st.markdown('<div class="section-title">✦ Strategy Performance</div>', unsafe_allow_html=True)

df_closed = read_closed_trades()

# ── FILTERS: strategy dropdown + date range ───────────────────────────────────
# Get available strategies from closed trades for dropdown
_avail_strats = []
if not df_closed.empty and "strategy" in df_closed.columns:
    _s_ordered = [s for s in STRATEGY_ORDER if s in df_closed["strategy"].unique()]
    _s_others  = sorted([s for s in df_closed["strategy"].unique() if s not in STRATEGY_ORDER])
    _avail_strats = _s_ordered + _s_others

fc1, fc2, fc3 = st.columns([1.2, 1, 1])
# Strategy dropdown — default TREND if available
_default_idx = 0
if _avail_strats and "TREND" in _avail_strats:
    _default_idx = _avail_strats.index("TREND")

selected_strategy = fc1.selectbox(
    "Strategy",
    options=_avail_strats if _avail_strats else ["No data yet"],
    index=_default_idx,
    key="perf_strategy"
)
date_from = fc2.date_input("From", value=date(2024,1,1), label_visibility="visible")
date_to   = fc3.date_input("To",   value=now_ist().date(), label_visibility="visible")

if df_closed.empty:
    st.markdown('<div style="color:#475569;font-size:0.82rem;padding:1rem 0;">No closed trades yet. Close positions to see performance.</div>', unsafe_allow_html=True)
else:
    # Normalise closed trades columns
    df_c = df_closed.copy()

    # Map column name variants
    col_map = {}
    for col in df_c.columns:
        cu = col.strip().lower()
        if cu in ("exit_date","close_date"):        col_map[col] = "exit_date"
        elif cu in ("entry_date","open_date"):      col_map[col] = "entry_date"
        elif cu in ("gross_pnl","gross_p&l"):       col_map[col] = "gross_pnl"
        elif cu in ("net_pnl","net_p&l"):           col_map[col] = "net_pnl"
        elif cu in ("avg_entry_price","entry_price"):col_map[col]= "avg_entry_price"
        elif cu in ("avg_exit_price","exit_price"): col_map[col] = "avg_exit_price"
        elif cu in ("lots_qty","lots"):              col_map[col] = "lots_qty"
        elif cu in ("roi_pct","roi"):                col_map[col] = "roi_pct"
    df_c = df_c.rename(columns=col_map)

    # Ensure numeric columns
    for nc in ["gross_pnl","net_pnl","roi_pct","quantity","avg_entry_price","avg_exit_price"]:
        if nc in df_c.columns:
            df_c[nc] = pd.to_numeric(df_c[nc], errors="coerce").fillna(0)

    # Apply date filter
    if "exit_date" in df_c.columns:
        df_c["exit_date"] = pd.to_datetime(df_c["exit_date"], errors="coerce")
        mask = (df_c["exit_date"].dt.date >= date_from) & (df_c["exit_date"].dt.date <= date_to)
        df_filtered = df_c[mask].copy()
    else:
        df_filtered = df_c.copy()

    if df_filtered.empty:
        st.markdown('<div style="color:#475569;font-size:0.82rem;">No trades in selected date range.</div>', unsafe_allow_html=True)
    else:
        # Only show selected strategy
        strategies_to_show = [selected_strategy] if selected_strategy and selected_strategy != "No data yet" else []

        for strategy_name in strategies_to_show:
            strat_c = df_filtered[df_filtered["strategy"]==strategy_name].copy()
            if strat_c.empty:
                st.markdown(
                    f'<div style="color:#475569;font-size:0.82rem;padding:1.5rem 0;">' 
                    f'No closed trades for <b>{strategy_name}</b> in selected date range.</div>',
                    unsafe_allow_html=True
                )
                continue

            # ── STATS ──────────────────────────────────────────────────────
            n_trades   = len(strat_c)
            gross_pnl  = strat_c["gross_pnl"].sum() if "gross_pnl" in strat_c.columns else 0
            net_pnl    = strat_c["net_pnl"].sum() if "net_pnl" in strat_c.columns else gross_pnl
            winners    = strat_c[strat_c["gross_pnl"]>0] if "gross_pnl" in strat_c.columns else pd.DataFrame()
            losers     = strat_c[strat_c["gross_pnl"]<=0] if "gross_pnl" in strat_c.columns else pd.DataFrame()
            win_rate   = len(winners)/n_trades*100 if n_trades>0 else 0
            strat_cap  = get_strategy_capital(strategy_name)

            # Hold days
            avg_hold = 0
            if "hold_days" in strat_c.columns:
                hd = pd.to_numeric(strat_c["hold_days"], errors="coerce").dropna()
                avg_hold = hd.mean() if len(hd)>0 else 0
            elif "entry_date" in strat_c.columns and "exit_date" in strat_c.columns:
                strat_c["_hold"] = (strat_c["exit_date"] - pd.to_datetime(strat_c["entry_date"],errors="coerce")).dt.days
                avg_hold = strat_c["_hold"].mean() or 0

            # ROI on deployed capital (gross_pnl / total entry value)
            roi_pct = 0.0
            if "avg_entry_price" in strat_c.columns and "quantity" in strat_c.columns:
                total_deployed = (strat_c["avg_entry_price"] * strat_c["quantity"]).sum()
                roi_pct = (gross_pnl / total_deployed * 100) if total_deployed > 0 else 0
            elif "roi_pct" in strat_c.columns:
                roi_pct = strat_c["roi_pct"].mean()

            gross_c    = pnl_color(gross_pnl)
            net_c      = pnl_color(net_pnl)
            roi_c      = "#22c55e" if roi_pct>=0 else "#ef4444"
            roi_sign   = "+" if roi_pct>=0 else ""

            # ── EQUITY CURVE ───────────────────────────────────────────────
            eq_df = strat_c.copy()
            if "exit_date" in eq_df.columns and "gross_pnl" in eq_df.columns:
                eq_df = eq_df.sort_values("exit_date")
                eq_df["cumulative_pnl"] = eq_df["gross_pnl"].cumsum()
                eq_df["exit_date_str"]  = eq_df["exit_date"].dt.strftime("%d %b")

            # ── TOP 3 TRADES BY ROI ──────────────────────────────────────
            top3 = pd.DataFrame()
            if "roi_pct" in strat_c.columns and n_trades>0:
                top3 = strat_c.nlargest(3,"roi_pct")[["symbol","expiry","gross_pnl","roi_pct","exit_date"]].copy()
            elif "gross_pnl" in strat_c.columns and n_trades>0:
                top3 = strat_c.nlargest(3,"gross_pnl")[["symbol","expiry","gross_pnl","exit_date"]].copy()
                if "avg_entry_price" in strat_c.columns and "quantity" in strat_c.columns:
                    strat_c["_dep"] = strat_c["avg_entry_price"] * strat_c["quantity"]
                    strat_c["_roi"] = strat_c.apply(lambda r: (r["gross_pnl"]/r["_dep"]*100) if r["_dep"]>0 else 0, axis=1)
                    top3 = strat_c.nlargest(3,"_roi")[["symbol","expiry","gross_pnl","_roi","exit_date"]].copy()
                    top3 = top3.rename(columns={"_roi":"roi_pct"})

            # ── RENDER CARD ────────────────────────────────────────────────
            st.markdown(f'<div class="card">', unsafe_allow_html=True)

            # Card header
            st.markdown(
                f'<div class="card-header">'
                f'<span class="strat-badge">{strategy_name}</span>'
                f'<span style="font-size:0.75rem;color:#475569;">'
                f'{n_trades} trades &nbsp;·&nbsp; '
                f'Win {win_rate:.0f}% &nbsp;·&nbsp; '
                f'Avg hold {avg_hold:.1f}d &nbsp;·&nbsp; '
                f'Capital ₹{strat_cap/100000:.0f}L'
                f'</span>'
                f'</div>',
                unsafe_allow_html=True
            )

            # Metrics row
            st.markdown(
                f'<div class="metric-row">'
                f'<div class="metric-item"><div class="metric-label">Gross P&L</div>'
                f'<div class="metric-value" style="color:{gross_c};">{fmt_cr(gross_pnl)}</div></div>'
                f'<div class="metric-item"><div class="metric-label">Net P&L</div>'
                f'<div class="metric-value" style="color:{net_c};">{fmt_cr(net_pnl)}</div></div>'
                f'<div class="metric-item"><div class="metric-label">ROI (deployed)</div>'
                f'<div class="metric-value" style="color:{roi_c};">{roi_sign}{roi_pct:.2f}%</div></div>'
                f'<div class="metric-item"><div class="metric-label">Trades W/L</div>'
                f'<div class="metric-value">'
                f'<span style="color:#22c55e">{len(winners)}W</span>'
                f' / <span style="color:#ef4444">{len(losers)}L</span>'
                f'</div></div>'
                f'</div>',
                unsafe_allow_html=True
            )

            # Two columns: equity curve + top 3
            ec_col, t3_col = st.columns([2.5, 1])

            with ec_col:
                if "exit_date" in eq_df.columns and len(eq_df) > 0:
                    cum_vals  = eq_df["cumulative_pnl"].tolist()
                    line_col  = "#22c55e" if cum_vals[-1]>=0 else "#ef4444"
                    fill_col  = "rgba(34,197,94,0.08)" if cum_vals[-1]>=0 else "rgba(239,68,68,0.08)"

                    fig = go.Figure()
                    fig.add_trace(go.Scatter(
                        x=eq_df["exit_date"].tolist(),
                        y=cum_vals,
                        mode="lines",
                        line=dict(color=line_col, width=2),
                        fill="tozeroy",
                        fillcolor=fill_col,
                        hovertemplate="<b>%{x|%d %b %Y}</b><br>P&L: ₹%{y:,.0f}<extra></extra>",
                    ))
                    fig.add_hline(y=0, line_dash="dot", line_color="#2e2e48", line_width=1)
                    fig.update_layout(
                        height=220, margin=dict(l=0,r=0,t=8,b=0),
                        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                        font=dict(family="JetBrains Mono", size=10, color="#475569"),
                        xaxis=dict(showgrid=False, zeroline=False, showline=False,
                                   tickformat="%d %b", tickfont=dict(size=9,color="#475569")),
                        yaxis=dict(showgrid=True, gridcolor="#1e1e2e", zeroline=False,
                                   tickprefix="₹", tickformat=",.0f",
                                   tickfont=dict(size=9,color="#475569")),
                        showlegend=False,
                    )
                    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar":False})
                else:
                    st.markdown('<div style="color:#475569;font-size:0.78rem;padding:2rem 0;">Equity curve available after first closure.</div>', unsafe_allow_html=True)

            with t3_col:
                st.markdown(
                    '<div style="font-size:0.6rem;color:#475569;letter-spacing:0.1em;'
                    'text-transform:uppercase;margin-bottom:8px;">Top 3 Trades by ROI</div>',
                    unsafe_allow_html=True
                )
                if not top3.empty:
                    for rank, (_, tr) in enumerate(top3.iterrows(), 1):
                        sym_t  = str(tr.get("symbol",""))
                        exp_t  = str(tr.get("expiry",""))
                        pnl_t  = float(tr.get("gross_pnl",0))
                        roi_t  = float(tr.get("roi_pct",0)) if "roi_pct" in tr.index else 0
                        pc_t   = "#22c55e" if pnl_t>=0 else "#ef4444"
                        sign_t = "+" if pnl_t>=0 else ""
                        st.markdown(
                            f'<div class="top-trade-row">'
                            f'<span class="top-trade-rank">#{rank}</span>'
                            f'<div style="flex:1;margin-left:8px;">'
                            f'<div class="top-trade-sym">{sym_t} <span style="font-size:0.65rem;color:#475569;">{exp_t}</span></div>'
                            f'<div class="top-trade-detail" style="color:{pc_t};">'
                            f'{sign_t}₹{abs(pnl_t):,.0f}'
                            f'{" · "+sign_t+str(round(roi_t,1))+"%" if roi_t else ""}'
                            f'</div>'
                            f'</div>'
                            f'</div>',
                            unsafe_allow_html=True
                        )
                else:
                    st.markdown('<div style="color:#475569;font-size:0.75rem;">No closed trades yet.</div>', unsafe_allow_html=True)

            st.markdown('</div>', unsafe_allow_html=True)  # end card
