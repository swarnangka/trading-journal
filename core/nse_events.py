"""
core/nse_events.py
==================
Fetches corporate events (results, dividends, bonus)
from NSE website for open position symbols.
Free, no API key needed.
Cached per session to minimise calls.
"""

import requests
import streamlit as st
from datetime import datetime, timedelta
import pytz

IST = pytz.timezone("Asia/Kolkata")

NSE_HEADERS = {
    "User-Agent":       "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept":           "application/json, text/plain, */*",
    "Accept-Language":  "en-US,en;q=0.9",
    "Referer":          "https://www.nseindia.com/",
    "Connection":       "keep-alive",
}


@st.cache_data(ttl=3600)   # Cache for 1 hour
def fetch_corporate_events(symbols: tuple) -> dict:
    """
    Fetch upcoming corporate events for given symbols.

    Args:
        symbols: tuple of symbol strings (tuple for hashability with cache)

    Returns:
        dict: {symbol: list of event dicts}
        event dict: {event_type, event_date, description}
    """
    if not symbols:
        return {}

    events_map = {}
    for sym in symbols:
        events_map[sym] = []

    # ── NSE Corporate Announcements ───────────────────────────
    try:
        today    = datetime.now(IST)
        from_dt  = today.strftime("%d-%m-%Y")
        to_dt    = (today + timedelta(days=30)).strftime("%d-%m-%Y")

        url = (
            f"https://www.nseindia.com/api/corporate-announcements"
            f"?index=equities&from_date={from_dt}&to_date={to_dt}&symbol="
        )
        resp = requests.get(url, headers=NSE_HEADERS, timeout=8)

        if resp.status_code == 200:
            data = resp.json()
            for item in data:
                sym  = item.get("symbol", "").upper()
                if sym not in events_map:
                    continue
                subject = item.get("subject", "").lower()
                dt_str  = item.get("bm_date") or item.get("date", "")

                event_type = _classify_event(subject)
                if event_type:
                    events_map[sym].append({
                        "event_type":  event_type,
                        "event_date":  dt_str,
                        "description": item.get("subject", ""),
                    })
    except Exception as e:
        pass   # Silently fail — events are informational only

    # ── NSE Board Meetings / Results ──────────────────────────
    try:
        url2 = "https://www.nseindia.com/api/corporates-corporateActions?index=equities"
        resp2 = requests.get(url2, headers=NSE_HEADERS, timeout=8)

        if resp2.status_code == 200:
            data2 = resp2.json()
            today_ts = datetime.now(IST)

            for item in data2:
                sym = item.get("symbol", "").upper()
                if sym not in events_map:
                    continue
                purpose = item.get("purpose", "").lower()
                dt_str  = item.get("exDate") or item.get("recordDate", "")

                # Parse date and check if within 30 days
                try:
                    ev_date = datetime.strptime(dt_str, "%d-%b-%Y")
                    days_away = (ev_date - today_ts.replace(tzinfo=None)).days
                    if days_away < 0 or days_away > 30:
                        continue
                except Exception:
                    pass

                event_type = _classify_event(purpose)
                if event_type:
                    events_map[sym].append({
                        "event_type":  event_type,
                        "event_date":  dt_str,
                        "description": item.get("purpose", ""),
                        "days_away":   days_away if "days_away" in dir() else 0,
                    })
    except Exception:
        pass

    return events_map


def _classify_event(text: str) -> str:
    """
    Classify an event description into a type.
    Returns event type string or empty string if not relevant.
    """
    text = text.lower()

    if any(kw in text for kw in ["board meeting", "financial results", "quarterly results",
                                   "results", "earnings"]):
        return "RESULTS"
    if any(kw in text for kw in ["dividend", "interim dividend", "final dividend"]):
        return "DIVIDEND"
    if any(kw in text for kw in ["bonus", "bonus shares"]):
        return "BONUS"
    if any(kw in text for kw in ["split", "stock split", "face value"]):
        return "SPLIT"
    if any(kw in text for kw in ["agm", "annual general"]):
        return "AGM"
    return ""


def get_event_badge(events: list) -> dict:
    """
    Returns badge info for display.
    Prioritises RESULTS > DIVIDEND > BONUS > SPLIT.

    Returns dict: {label, color, days_away} or None
    """
    if not events:
        return None

    priority = {"RESULTS": 0, "DIVIDEND": 1, "BONUS": 2, "SPLIT": 3, "AGM": 4}
    sorted_ev = sorted(events, key=lambda e: priority.get(e["event_type"], 9))

    ev = sorted_ev[0]
    ev_type = ev.get("event_type", "")
    days    = ev.get("days_away", 99)

    colors = {
        "RESULTS":  "#FF4757" if days <= 7 else "#F6C90E",
        "DIVIDEND": "#00D4FF",
        "BONUS":    "#00FF88",
        "SPLIT":    "#9B59B6",
        "AGM":      "#718096",
    }

    labels = {
        "RESULTS":  f"📊 Results {ev.get('event_date', '')}",
        "DIVIDEND": f"💰 Dividend {ev.get('event_date', '')}",
        "BONUS":    f"🎁 Bonus {ev.get('event_date', '')}",
        "SPLIT":    f"✂️ Split {ev.get('event_date', '')}",
        "AGM":      f"🏛️ AGM {ev.get('event_date', '')}",
    }

    return {
        "label":     labels.get(ev_type, ev_type),
        "color":     colors.get(ev_type, "#718096"),
        "days_away": days,
        "event_type": ev_type,
    }
