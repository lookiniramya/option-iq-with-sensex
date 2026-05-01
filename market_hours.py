"""
market_hours.py - Indian Market Hours Detection (no external deps)
NSE Trading Hours: Mon-Fri 09:15 to 15:30 IST
Uses Python stdlib only - IST = UTC+5:30
"""

import datetime
from typing import Any, Dict

# IST = UTC + 5:30
IST_OFFSET = datetime.timezone(datetime.timedelta(hours=5, minutes=30))

MARKET_OPEN_H, MARKET_OPEN_M = 9, 15
MARKET_CLOSE_H, MARKET_CLOSE_M = 15, 30
PREOPEN_H, PREOPEN_M = 9, 0

NSE_HOLIDAYS = {
    # 2025
    datetime.date(2025, 1, 26),
    datetime.date(2025, 2, 26),
    datetime.date(2025, 3, 14),
    datetime.date(2025, 3, 31),
    datetime.date(2025, 4, 10),
    datetime.date(2025, 4, 14),
    datetime.date(2025, 4, 18),
    datetime.date(2025, 5, 1),
    datetime.date(2025, 8, 15),
    datetime.date(2025, 8, 27),
    datetime.date(2025, 10, 2),
    datetime.date(2025, 10, 21),
    datetime.date(2025, 10, 22),
    datetime.date(2025, 11, 5),
    datetime.date(2025, 12, 25),
    # 2026
    datetime.date(2026, 1, 26),
    datetime.date(2026, 3, 3),
    datetime.date(2026, 3, 20),
    datetime.date(2026, 4, 2),
    datetime.date(2026, 4, 3),
    datetime.date(2026, 4, 14),
    datetime.date(2026, 5, 1),
    datetime.date(2026, 8, 15),
    datetime.date(2026, 10, 2),
    datetime.date(2026, 12, 25),
}


def _now_ist() -> datetime.datetime:
    return datetime.datetime.now(IST_OFFSET)


def get_market_status() -> Dict[str, Any]:
    now = _now_ist()
    today = now.date()
    weekday = now.weekday()  # 0=Mon ... 6=Sun

    t_open = now.replace(hour=MARKET_OPEN_H, minute=MARKET_OPEN_M, second=0, microsecond=0)
    t_close = now.replace(hour=MARKET_CLOSE_H, minute=MARKET_CLOSE_M, second=0, microsecond=0)
    t_preopen = now.replace(hour=PREOPEN_H, minute=PREOPEN_M, second=0, microsecond=0)

    is_weekend = weekday >= 5
    is_holiday = today in NSE_HOLIDAYS

    if is_weekend:
        status = "WEEKEND"
        is_open = False
    elif is_holiday:
        status = "HOLIDAY"
        is_open = False
    elif now < t_preopen:
        status = "PRE-MARKET"
        is_open = False
    elif t_preopen <= now < t_open:
        status = "PRE-OPEN"
        is_open = False
    elif t_open <= now <= t_close:
        status = "OPEN"
        is_open = True
    else:
        status = "CLOSED"
        is_open = False

    minutes_to_open = max(0, int((t_open - now).total_seconds() // 60))
    minutes_to_close = max(0, int((t_close - now).total_seconds() // 60)) if is_open else 0
    elapsed_since_open = max(0, int((now - t_open).total_seconds() // 60)) if is_open else 0

    if is_open:
        detail = f"Closes in {_fmt_td(t_close - now)}"
    elif status == "PRE-OPEN":
        detail = f"Opens in {_fmt_td(t_open - now)}"
    else:
        nxt = _next_open(now)
        detail = f"Next open in {_fmt_td(nxt - now)}"

    last_td = _last_trading_day(today)

    hour = now.hour
    if is_open:
        session = "MORNING" if hour < 12 else "AFTERNOON"
    elif status == "PRE-OPEN":
        session = "PRE-OPEN"
    else:
        session = "POST-CLOSE" if hour >= 15 else "PRE-MARKET"

    if is_open:
        if minutes_to_close <= 15:
            session_phase = "CLOSING_BELL"
        elif minutes_to_close <= 45:
            session_phase = "LATE_SESSION"
        elif elapsed_since_open <= 30:
            session_phase = "OPENING_DRIVE"
        elif hour < 12:
            session_phase = "MORNING_TREND"
        else:
            session_phase = "MIDDAY_OR_AFTERNOON"
    else:
        session_phase = status

    return {
        "is_open": is_open,
        "status": status,
        "status_detail": detail,
        "current_ist": now.strftime("%d %b %Y, %I:%M:%S %p IST"),
        "current_time": now.strftime("%H:%M:%S"),
        "current_date": now.strftime("%d-%b-%Y"),
        "weekday": now.strftime("%A"),
        "session": session,
        "session_phase": session_phase,
        "last_trading_day": last_td.strftime("%d-%b-%Y"),
        "last_td_date": last_td,
        "is_holiday": is_holiday,
        "is_weekend": is_weekend,
        "minutes_to_open": minutes_to_open if not is_open else 0,
        "minutes_to_close": minutes_to_close,
        "elapsed_since_open_minutes": elapsed_since_open,
        "is_near_close": bool(is_open and minutes_to_close <= 45),
        "avoid_new_option_buys": bool(is_open and minutes_to_close <= 15),
        "market_open_time": "09:15 IST",
        "market_close_time": "15:30 IST",
        "data_note": (
            ""
            if is_open
            else f"Warning: market is {status.lower()}. Data shown is from last trading session ({last_td.strftime('%d-%b-%Y')})."
        ),
    }


def get_trade_timing_context(info: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """Compact timing data for AI prompts and realistic trade planning."""
    info = info or get_market_status()
    minutes_to_close = int(info.get("minutes_to_close", 0) or 0)

    if info.get("is_open"):
        if minutes_to_close <= 15:
            suggested_max_holding = max(5, minutes_to_close - 2)
        elif minutes_to_close <= 45:
            suggested_max_holding = max(10, minutes_to_close - 5)
        else:
            suggested_max_holding = min(60, max(15, minutes_to_close - 10))
    else:
        suggested_max_holding = 0

    return {
        "request_time_ist": info.get("current_ist", ""),
        "market_status": info.get("status", "UNKNOWN"),
        "session": info.get("session", ""),
        "session_phase": info.get("session_phase", ""),
        "is_open": bool(info.get("is_open")),
        "minutes_to_close": minutes_to_close,
        "minutes_to_open": int(info.get("minutes_to_open", 0) or 0),
        "market_close_time": info.get("market_close_time", "15:30 IST"),
        "market_open_time": info.get("market_open_time", "09:15 IST"),
        "avoid_new_option_buys": bool(info.get("avoid_new_option_buys")),
        "is_near_close": bool(info.get("is_near_close")),
        "suggested_max_holding_minutes": int(suggested_max_holding),
        "status_detail": info.get("status_detail", ""),
    }


def _fmt_td(td: datetime.timedelta) -> str:
    total_seconds = int(td.total_seconds())
    if total_seconds <= 0:
        return "now"
    hours, rem = divmod(total_seconds, 3600)
    minutes, seconds = divmod(rem, 60)
    if hours:
        return f"{hours}h {minutes}m"
    if minutes:
        return f"{minutes}m {seconds}s"
    return f"{seconds}s"


def _next_open(now: datetime.datetime) -> datetime.datetime:
    check = now.date()
    for _ in range(10):
        check += datetime.timedelta(days=1)
        if check.weekday() < 5 and check not in NSE_HOLIDAYS:
            return datetime.datetime(
                check.year,
                check.month,
                check.day,
                MARKET_OPEN_H,
                MARKET_OPEN_M,
                0,
                tzinfo=IST_OFFSET,
            )
    return now


def _last_trading_day(today: datetime.date) -> datetime.date:
    check = today
    for _ in range(10):
        if check.weekday() < 5 and check not in NSE_HOLIDAYS:
            return check
        check -= datetime.timedelta(days=1)
    return today


def market_status_banner(info: Dict[str, Any]) -> str:
    """Return HTML banner string for embedding in Streamlit."""
    status = info["status"]
    detail = info["status_detail"]
    current_ts = info["current_ist"]
    note = info.get("data_note", "")

    cfg = {
        "OPEN": ("#e8f5e9", "#2e7d32", "MARKET OPEN", "pulse 1.5s infinite"),
        "PRE-OPEN": ("#fff8e1", "#f57f17", "PRE-OPEN SESSION", "pulse 2s infinite"),
        "PRE-MARKET": ("#e8eaf6", "#3949ab", "PRE-MARKET", ""),
        "WEEKEND": ("#e8eaf6", "#3949ab", f"WEEKEND - {info['weekday']}", ""),
        "HOLIDAY": ("#fff3e0", "#e65100", "MARKET HOLIDAY", ""),
        "CLOSED": ("#fce8e8", "#c62828", "MARKET CLOSED", ""),
    }.get(status, ("#f0f2f6", "#546e7a", status, ""))

    bg, border, label, anim = cfg
    text_color = "#1b5e20" if "OPEN" in label else "#c62828" if "CLOSED" in label else "#1a237e"
    sub_color = "#2e7d32" if "OPEN" in label else "#c62828" if "CLOSED" in label else "#3949ab"
    dot_anim = f"animation:{anim};" if anim else ""

    note_html = (
        f'<div style="font-size:0.72rem;color:#e65100;margin-top:4px">{note}</div>'
        if note
        else ""
    )

    return f"""
<style>
@keyframes pulse {{
  0%,100%{{opacity:1;transform:scale(1)}} 50%{{opacity:.5;transform:scale(1.4)}}
}}
</style>
<div style="background:{bg};border:1px solid {border}88;border-radius:10px;
            padding:10px 16px;margin-bottom:8px;display:flex;
            align-items:center;justify-content:space-between;flex-wrap:wrap;gap:8px">
  <div style="display:flex;align-items:center;gap:8px">
    <div style="width:10px;height:10px;border-radius:50%;
                background:{border};{dot_anim}flex-shrink:0"></div>
    <span style="font-weight:700;color:{text_color};font-size:0.9rem">{label}</span>
    <span style="color:{sub_color};font-size:0.8rem">- {detail}</span>
  </div>
  <span style="font-size:0.72rem;color:{sub_color}">{current_ts}</span>
  {note_html}
</div>"""
