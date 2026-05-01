"""
features.py Ã¢â‚¬â€ Advanced features for OptionsIQ
Provides 5 new high-value modules:
  1. Entry Timing Score Ã¢â‚¬â€ real-time "enter now or wait" signal
  2. Live Trade Tracker Ã¢â‚¬â€ P&L, SL/target alerts, exit timer
  3. OI Change Velocity Ã¢â‚¬â€ detect fresh writing vs covering
  4. AI Trade History Ã¢â‚¬â€ log & win rate tracker (persisted via localStorage bridge)
  5. Multi-expiry PCR + BankNifty divergence
"""

import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
import json
import os
from analytics import get_strike_gap, get_lot_size


def _clean_text(value: Any) -> str:
    """Normalize mojibake-prone UI text before rendering in Streamlit."""
    text = str(value or "")
    replacements = {
        "Ã¢â‚¬â€": "-",
        "Ã¢â‚¬â€œ": "-",
        "Ã¢â€šÂ¹": "Rs. ",
        "Ã‚Â·": "|",
        "Â·": "|",
        "Ã¢Å¡Â Ã¯Â¸Â": "Warning:",
        "Ã¢Å¡ÂÃ¯Â¸Â": "Warning:",
        "Ã¢Å“â€¦": "OK:",
        "Ã¢ÂÅ’": "No:",
        "Ã¢Å“â€œ": "OK",
        "Ã¢Å“â€”": "X",
        "Ã¢Å¡Â¡": "",
        "Ã¢ÂÂ¸": "",
        "Ã¢ÂÂ³": "Waiting:",
        "Ã°Å¸â€™Â¡": "Tip:",
        "Ã°Å¸â€œÂ": "Note:",
        "Ã¢â€“Â²": "UP",
        "Ã¢â€“Â¼": "DOWN",
        "Ã¢â€ â€”": "RISING",
        "Ã¢â€ Ëœ": "FALLING",
        "Ã¢â€ â€™": "FLAT",
        "Ã°Å¸Å¸Â¢": "COVER",
        "Ã¢Å¡â€“Ã¯Â¸Â": "Neutral:",
        "ðŸ“Š": "",
        "ðŸ“Œ": "",
        "ðŸ¤–": "AI",
        "ðŸ”’": "Hidden:",
        "â€”": "-",
        "₹": "Rs. ",
        "✓": "OK",
        "✗": "X",
    }
    for bad, good in replacements.items():
        text = text.replace(bad, good)
    return " ".join(text.split())


# Ã¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢Â
# 1. ENTRY TIMING SCORE
# Ã¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢Â

def compute_entry_timing_score(
    live_price: Dict, df_calls: pd.DataFrame, df_puts: pd.DataFrame,
    candles_1m: pd.DataFrame, sentiment: Dict, action: str = "BUY CALL"
) -> Dict[str, Any]:
    """
    Score 0-100 for how good the current moment is to enter.
    Combines momentum, spread, volume, and candle confirmation.
    """
    score = 50  # neutral base
    signals = []
    is_call = action == "BUY CALL"

    spot = float(live_price.get("ltp", 0) or 0)
    if spot <= 0:
        return {"score": 0, "grade": "F", "signals": ["No price data"], "wait": True}

    # Ã¢â€â‚¬Ã¢â€â‚¬ Momentum: candle direction Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
    if candles_1m is not None and len(candles_1m) >= 3:
        last3 = candles_1m.tail(3)
        bullish_count = (last3["dir"] == "Bullish").sum()
        if is_call:
            if bullish_count == 3:  score += 15; signals.append("Ã¢Å“â€¦ 3 consecutive green candles")
            elif bullish_count == 2: score += 7;  signals.append("Ã¢Å“â€¦ 2 of 3 candles green")
            elif bullish_count == 0: score -= 15; signals.append("Ã¢ÂÅ’ 3 consecutive red candles")
            else:                    score -= 5;  signals.append("Ã¢Å¡Â Ã¯Â¸Â Mixed candle direction")
        else:
            if bullish_count == 0:  score += 15; signals.append("Ã¢Å“â€¦ 3 consecutive red candles")
            elif bullish_count == 1: score += 7;  signals.append("Ã¢Å“â€¦ 2 of 3 candles red")
            elif bullish_count == 3: score -= 15; signals.append("Ã¢ÂÅ’ 3 consecutive green candles")
            else:                    score -= 5;  signals.append("Ã¢Å¡Â Ã¯Â¸Â Mixed candle direction")

        # Candle body size vs range (larger body = stronger momentum)
        last = candles_1m.iloc[-1]
        body = abs(last["close"] - last["open"])
        rng  = last["high"] - last["low"]
        if rng > 0 and body / rng > 0.6:
            score += 8; signals.append("Ã¢Å“â€¦ Strong candle body (momentum)")
        elif rng > 0 and body / rng < 0.3:
            score -= 5; signals.append("Ã¢Å¡Â Ã¯Â¸Â Weak doji candle (indecision)")

    # Ã¢â€â‚¬Ã¢â€â‚¬ Volume spike on last candle Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
    if candles_1m is not None and len(candles_1m) >= 5:
        avg_vol = candles_1m["display_volume"].iloc[:-1].mean()
        last_vol = candles_1m["display_volume"].iloc[-1]
        if avg_vol > 0:
            ratio = last_vol / avg_vol
            if ratio > 2.0:   score += 10; signals.append(f"Ã¢Å“â€¦ Volume spike {ratio:.1f}x avg")
            elif ratio > 1.3: score += 4;  signals.append(f"Ã¢Å“â€¦ Above-avg volume {ratio:.1f}x")
            elif ratio < 0.5: score -= 8;  signals.append(f"Ã¢Å¡Â Ã¯Â¸Â Low volume {ratio:.1f}x avg")

    # Ã¢â€â‚¬Ã¢â€â‚¬ Option spread tightness (proxy: ATM option price > 0) Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
    sym = live_price.get('symbol', 'NIFTY') if isinstance(live_price, dict) else 'NIFTY'
    atm = round(spot / get_strike_gap(sym)) * get_strike_gap(sym)
    chain_df = df_calls if is_call else df_puts
    if not chain_df.empty:
        atm_row = chain_df[chain_df["strike_price"].astype(float).sub(atm).abs() < 30]
        if not atm_row.empty:
            ltp = float(atm_row.iloc[0].get("price", 0) or 0)
            oi  = float(atm_row.iloc[0].get("oi", 0) or 0)
            vol = float(atm_row.iloc[0].get("volume", 0) or 0)
            if ltp > 0:
                score += 5; signals.append(f"Ã¢Å“â€¦ ATM LTP Ã¢â€šÂ¹{ltp:.0f} (liquid)")
            if oi > 100000:
                score += 5; signals.append(f"Ã¢Å“â€¦ High OI {oi/100000:.1f}L (easy exit)")
            if vol > 50000:
                score += 5; signals.append(f"Ã¢Å“â€¦ High volume {vol/1000:.0f}K (active)")

    # Ã¢â€â‚¬Ã¢â€â‚¬ Sentiment alignment Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
    sent_score = sentiment.get("score", 0) if sentiment else 0
    if is_call and sent_score > 20:
        score += 8; signals.append(f"Ã¢Å“â€¦ Bullish sentiment {sent_score:+d}")
    elif is_call and sent_score < -20:
        score -= 10; signals.append(f"Ã¢ÂÅ’ Bearish sentiment {sent_score:+d}")
    elif not is_call and sent_score < -20:
        score += 8; signals.append(f"Ã¢Å“â€¦ Bearish sentiment {sent_score:+d}")
    elif not is_call and sent_score > 20:
        score -= 10; signals.append(f"Ã¢ÂÅ’ Bullish sentiment {sent_score:+d}")

    # Ã¢â€â‚¬Ã¢â€â‚¬ Time of day penalty Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
    now_h = datetime.now().hour
    now_m = datetime.now().minute
    time_val = now_h + now_m / 60
    if 9.25 <= time_val <= 9.75:
        score -= 10; signals.append("Ã¢Å¡Â Ã¯Â¸Â Opening 30min Ã¢â‚¬â€ volatile, avoid")
    elif time_val >= 14.75:
        score -= 12; signals.append("Ã¢Å¡Â Ã¯Â¸Â After 2:45 PM Ã¢â‚¬â€ theta decay accelerating")
    elif 11.0 <= time_val <= 13.0:
        score -= 5;  signals.append("Ã¢Å¡Â Ã¯Â¸Â Midday lull Ã¢â‚¬â€ lower momentum")
    else:
        score += 5;  signals.append("Ã¢Å“â€¦ Good trading window")

    score = max(0, min(100, score))
    if score >= 75:   grade, wait = "A", False
    elif score >= 60: grade, wait = "B", False
    elif score >= 45: grade, wait = "C", True
    elif score >= 30: grade, wait = "D", True
    else:             grade, wait = "F", True

    return {"score": score, "grade": grade, "signals": signals, "wait": wait,
            "action": action}


def render_entry_timing(timing: Dict):
    """Render entry timing score widget."""
    score = timing["score"]
    grade = timing["grade"]
    wait  = timing["wait"]
    color = ("#2e7d32" if grade in ["A","B"] else
             "#ffcc00" if grade == "C" else "#c62828")
    label = "ENTER NOW" if not wait else ("WAIT" if grade in ["C","D"] else "SKIP")

    st.markdown(f"""
    <div style="background:#ffffff;border:1px solid {color}44;border-left:4px solid {color};
                border-radius:8px;padding:0.8rem 1rem;margin-bottom:0.6rem">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:0.5rem">
            <div>
                <span style="font-size:0.65rem;color:#78909c;text-transform:uppercase">
                    Entry Timing Score</span>
                <span style="font-size:2rem;font-weight:700;color:{color};
                             font-family:monospace;margin-left:0.8rem">{score}</span>
                <span style="font-size:1rem;color:{color};margin-left:0.3rem">/ 100</span>
            </div>
            <div style="background:{color}22;border:1px solid {color};border-radius:6px;
                        padding:0.3rem 0.8rem;font-weight:700;color:{color};font-size:0.9rem">
                {grade} - {label}
            </div>
        </div>
        <div style="background:#f8f9ff;border-radius:4px;height:6px;overflow:hidden;margin-bottom:0.5rem">
            <div style="width:{score}%;height:100%;background:{color};border-radius:4px;
                        transition:width 0.5s ease"></div>
        </div>
        <div style="font-size:0.7rem;color:#78909c">
            {' | '.join(_clean_text(s) for s in timing['signals'][:4])}
        </div>
    </div>""", unsafe_allow_html=True)


def compute_no_trade_filter(
    live_price: Dict[str, Any],
    snapshot: Dict[str, Any],
    pcr_data: Dict[str, Any],
    indicators: Dict[str, Any],
    sentiment: Dict[str, Any],
    entry_timing: Optional[Dict[str, Any]] = None,
    candles_5m: Optional[pd.DataFrame] = None,
    support: Optional[Dict[str, Any]] = None,
    resistance: Optional[Dict[str, Any]] = None,
    market_timing: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Detect low-quality conditions where fresh option buying should be avoided.
    Higher score = worse environment for buying options.
    """
    support = support or {}
    resistance = resistance or {}
    market_timing = market_timing or {}
    entry_timing = entry_timing or {}

    score = 0
    reasons: List[str] = []
    blockers: List[str] = []

    spot = float(live_price.get("ltp", 0) or snapshot.get("spot_price", 0) or 0)
    sentiment_score = float(sentiment.get("score", 0) or 0)
    pcr = float(pcr_data.get("pcr_oi", 0) or 0)
    max_pain = float(indicators.get("max_pain", 0) or 0)
    oi_momentum = str(indicators.get("oi_momentum", "NEUTRAL")).upper()
    minutes_to_close = int(market_timing.get("minutes_to_close", 0) or 0)
    is_open = bool(market_timing.get("is_open"))

    if is_open and minutes_to_close <= 15:
        score += 60
        blockers.append(f"Only {minutes_to_close} minutes remain before market close.")
    elif is_open and minutes_to_close <= 30:
        score += 22
        reasons.append(f"Only {minutes_to_close} minutes remain before market close.")
    elif is_open and minutes_to_close <= 45:
        score += 12
        reasons.append("Late-session theta decay is accelerating.")

    timing_score = int(entry_timing.get("score", 50) or 50)
    if timing_score < 35:
        score += 25
        blockers.append(f"Entry timing score is weak at {timing_score}/100.")
    elif timing_score < 50:
        score += 15
        reasons.append(f"Entry timing score is only {timing_score}/100.")
    elif entry_timing.get("wait"):
        score += 8
        reasons.append("Timing model says wait for cleaner entry.")

    if abs(sentiment_score) < 12:
        score += 14
        reasons.append(f"Sentiment is too neutral at {sentiment_score:+.0f}.")
    elif abs(sentiment_score) < 20:
        score += 7
        reasons.append(f"Sentiment conviction is modest at {sentiment_score:+.0f}.")

    if 0.9 <= pcr <= 1.1:
        score += 10
        reasons.append(f"PCR is neutral at {pcr:.2f}.")

    if oi_momentum == "NEUTRAL":
        score += 10
        reasons.append("OI momentum is neutral.")

    if spot > 0 and max_pain > 0:
        distance_pct = abs(spot - max_pain) / spot * 100
        if distance_pct <= 0.25:
            score += 15
            reasons.append(f"Spot is pinned near max pain ({max_pain:.0f}).")
        elif distance_pct <= 0.5:
            score += 8
            reasons.append(f"Spot is still close to max pain ({max_pain:.0f}).")

    sup = float(support.get("strike", 0) or 0)
    res = float(resistance.get("strike", 0) or 0)
    if spot > 0 and sup > 0 and res > 0 and res > sup:
        pos = (spot - sup) / (res - sup)
        if 0.4 <= pos <= 0.6:
            score += 10
            reasons.append("Spot is stuck in the middle of the support/resistance range.")

    if candles_5m is not None and not candles_5m.empty and len(candles_5m) >= 6:
        recent = candles_5m.tail(6).copy()
        total_range_pct = ((float(recent["high"].max()) - float(recent["low"].min())) / max(spot, 1)) * 100
        direction_flips = int((recent["dir"] != recent["dir"].shift(1)).sum())
        bodies = (recent["close"] - recent["open"]).abs()
        avg_body = float(bodies.mean()) if not bodies.empty else 0.0
        avg_range = float((recent["high"] - recent["low"]).mean()) if not recent.empty else 0.0
        body_ratio = (avg_body / avg_range) if avg_range > 0 else 0.0

        if total_range_pct < 0.35:
            score += 12
            reasons.append(f"Recent 5m range is very tight at {total_range_pct:.2f}%.")
        if direction_flips >= 4:
            score += 12
            reasons.append("Recent 5m candles are choppy with frequent direction flips.")
        if body_ratio < 0.35:
            score += 8
            reasons.append("Recent 5m candles show weak bodies and low conviction.")

    if score >= 55:
        regime = "BLOCK"
        block_trade = True
    elif score >= 35:
        regime = "CAUTION"
        block_trade = False
    else:
        regime = "TRADEABLE"
        block_trade = False

    headline = (
        blockers[0] if blockers else
        reasons[0] if reasons else
        "Market conditions are acceptable for fresh option buying."
    )

    return {
        "score": int(min(100, score)),
        "regime": regime,
        "block_trade": block_trade,
        "headline": headline,
        "reasons": (blockers + reasons)[:5],
        "blockers": blockers[:3],
    }


def render_no_trade_filter(result: Dict[str, Any]):
    """Render no-trade classifier widget."""
    score = int(result.get("score", 0) or 0)
    regime = str(result.get("regime", "TRADEABLE"))
    headline = str(result.get("headline", ""))
    reasons = result.get("reasons", []) or []

    color = "#c62828" if regime == "BLOCK" else "#f9a825" if regime == "CAUTION" else "#2e7d32"
    label = "NO-TRADE" if regime == "BLOCK" else "CAUTION" if regime == "CAUTION" else "TRADEABLE"

    st.markdown(f"""
    <div style="background:#ffffff;border:1px solid {color}44;border-left:4px solid {color};
                border-radius:8px;padding:0.8rem 1rem;margin-bottom:0.6rem">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:0.45rem">
            <div>
                <span style="font-size:0.65rem;color:#78909c;text-transform:uppercase">Option Buying Filter</span>
                <span style="font-size:1.9rem;font-weight:700;color:{color};font-family:monospace;margin-left:0.8rem">{score}</span>
                <span style="font-size:1rem;color:{color};margin-left:0.3rem">risk</span>
            </div>
            <div style="background:{color}22;border:1px solid {color};border-radius:6px;
                        padding:0.3rem 0.8rem;font-weight:700;color:{color};font-size:0.9rem">
                {label}
            </div>
        </div>
        <div style="font-size:0.78rem;color:#546e7a;margin-bottom:0.35rem">{headline}</div>
        <div style="font-size:0.7rem;color:#78909c">
            {'  |  '.join([str(r) for r in reasons[:4]])}
        </div>
    </div>""", unsafe_allow_html=True)


def compute_quick_scalp_signal(
    live_price: Dict[str, Any],
    df_calls: pd.DataFrame,
    df_puts: pd.DataFrame,
    candles_1m: Optional[pd.DataFrame],
    candles_5m: Optional[pd.DataFrame],
    sentiment: Dict[str, Any],
    indicators: Dict[str, Any],
    support: Optional[Dict[str, Any]] = None,
    resistance: Optional[Dict[str, Any]] = None,
    breakout_alerts: Optional[List[Dict[str, Any]]] = None,
    market_timing: Optional[Dict[str, Any]] = None,
    opening_range: Optional[Dict[str, Any]] = None,
    vwap_data: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Quick Scalp signal Ã¢â‚¬â€ 3-5 minute option entry suggestion.

    DESIGN PRINCIPLES (v2 rewrite):
      - Works WITHOUT candles. Falls back to option chain + price + levels.
      - Honest "WAIT because [X]" reasons. Never silent.
      - Respects opening range (no signal during 9:15Ã¢â‚¬â€œ9:30).
      - Decoupled from WebSocket Ã¢â‚¬â€ uses whatever data is available.

    The scoring model is the same as before, but we no longer return early
    on missing candles Ã¢â‚¬â€ instead, we use the option chain's own momentum
    indicators (oi_perc_chg + price changes) as primary signal sources.
    """
    support = support or {}
    resistance = resistance or {}
    breakout_alerts = breakout_alerts or []
    market_timing = market_timing or {}
    opening_range = opening_range or {}
    vwap_data = vwap_data or {}

    result = {
        "action": "WAIT",
        "confidence": 0,
        "timeframe": "15-30 min",
        "entry_strike": 0,
        "entry_type": "ATM",
        "entry_price_range": "Ã¢â‚¬â€",
        "target_price": 0.0,
        "stop_loss_price": 0.0,
        "exit_rule": "Wait for cleaner micro-trend.",
        "reason": "Quick scalp setup not ready yet.",
        "wait_reasons": [],
        "supporting_factors": [],
        "risk_note": "",
        "data_quality": "unknown",
    }

    spot = float(live_price.get("ltp", 0) or 0)
    if spot <= 0:
        result["wait_reasons"] = ["No live price available"]
        result["risk_note"] = "Live price feed not connected."
        return result

    # Ã¢â€â‚¬Ã¢â€â‚¬ Time-of-day gates Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
    is_open = bool(market_timing.get("is_open", False))
    minutes_to_close = int(market_timing.get("minutes_to_close", 0) or 0)

    if is_open and minutes_to_close <= 10:
        result["wait_reasons"] = [f"Only {minutes_to_close}min to close Ã¢â‚¬â€ theta/fill risk"]
        result["reason"] = "Too close to market close for a fresh 15-30 minute hold."
        result["risk_note"] = "Late-session theta decay and fills become unreliable."
        return result

    # Opening range gate: no signals during 9:15Ã¢â‚¬â€œ9:30
    or_status = (opening_range or {}).get("status", "")
    if or_status in ("PRE_OPEN",):
        result["wait_reasons"] = ["Market not yet open"]
        result["reason"] = "Waiting for market open."
        return result
    if or_status in ("FORMING", "FORMING_NO_DATA"):
        result["wait_reasons"] = ["Opening range still forming (first 15min)"]
        result["reason"] = ("Opening range forming Ã¢â‚¬â€ no signals during 9:15Ã¢â‚¬â€œ9:30. "
                            "Wait for the range to complete, then trade clean breaks.")
        result["risk_note"] = "First 15 minutes are statistically the most volatile and trap-prone."
        return result

    # Ã¢â€â‚¬Ã¢â€â‚¬ Determine data availability Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
    have_candles = (candles_1m is not None and not candles_1m.empty
                    and len(candles_1m) >= 4)
    have_chain = ((not df_calls.empty) and (not df_puts.empty))

    if not have_chain:
        result["wait_reasons"] = ["Option chain not loaded"]
        result["reason"] = "Cannot evaluate without option chain."
        result["risk_note"] = "Wait for chain data."
        return result

    if have_candles:
        result["data_quality"] = "full"
    else:
        result["data_quality"] = "chain_only"

    # Ã¢â€â‚¬Ã¢â€â‚¬ Compute candle-based features (only if available) Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
    bullish_count = bearish_count = 0
    body_ratio = 0.0
    one_min_range_pct = 0.0
    direction_flips = 0
    breakout_above_prev_high = False
    breakout_below_prev_low = False
    candle_5m_dir = 0  # +1 bull, -1 bear, 0 neutral
    last_close = spot

    if have_candles:
        last4 = candles_1m.tail(4).copy()
        last6 = candles_1m.tail(6).copy()
        bullish_count = int((last4["dir"] == "Bullish").sum())
        bearish_count = int((last4["dir"] == "Bearish").sum())
        latest = last4.iloc[-1]
        previous = last4.iloc[-2]
        latest_body = abs(float(latest["close"]) - float(latest["open"]))
        latest_range = max(float(latest["high"]) - float(latest["low"]), 0.01)
        body_ratio = latest_body / latest_range
        last_close = float(latest["close"])
        if not last6.empty:
            one_min_range_pct = ((float(last6["high"].max())
                                  - float(last6["low"].min()))
                                 / max(spot, 1)) * 100
        if len(last6) >= 2:
            direction_flips = int((last6["dir"] != last6["dir"].shift(1)).sum())
        breakout_above_prev_high = float(latest["close"]) > float(previous["high"])
        breakout_below_prev_low = float(latest["close"]) < float(previous["low"])
        if candles_5m is not None and not candles_5m.empty:
            last5 = candles_5m.iloc[-1]
            if float(last5["close"]) > float(last5["open"]):
                candle_5m_dir = 1
            elif float(last5["close"]) < float(last5["open"]):
                candle_5m_dir = -1

        # If candles are too choppy, hold off
        if direction_flips >= 4:
            result["wait_reasons"] = [f"{direction_flips} direction flips in last 6 candles"]
            result["reason"] = "1-minute candles too choppy for a high-probability scalp."
            result["risk_note"] = "Wait for direction to stabilize."
            return result
        if one_min_range_pct < 0.08:
            result["wait_reasons"] = [f"1m range only {one_min_range_pct:.2f}%"]
            result["reason"] = "1-minute range too tight for a clean scalp breakout."
            result["risk_note"] = "Avoid forced entries in micro-range compression."
            return result

    # Ã¢â€â‚¬Ã¢â€â‚¬ Option chain momentum (works WITHOUT candles) Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
    _sym = live_price.get('symbol', 'NIFTY') if isinstance(live_price, dict) else 'NIFTY'
    _gap = get_strike_gap(_sym)
    atm = int(round(spot / _gap) * _gap)
    call_row = _find_nearest_contract(df_calls, atm)
    put_row = _find_nearest_contract(df_puts, atm)

    # Compute chain-based bull/bear momentum signals
    chain_bull_signal = 0  # 0 = no signal, +/- magnitude
    chain_bear_signal = 0
    chain_factors_bull: List[str] = []
    chain_factors_bear: List[str] = []

    # ATM CE/PE OI change comparison: fresh PUT writing > CALL writing = bullish
    try:
        atm_ce_oi_chg = float(call_row.iloc[0]["oi_perc_chg"]) if not call_row.empty else 0
        atm_pe_oi_chg = float(put_row.iloc[0]["oi_perc_chg"]) if not put_row.empty else 0
        if atm_pe_oi_chg > 10 and atm_pe_oi_chg > atm_ce_oi_chg + 5:
            chain_bull_signal += 12
            chain_factors_bull.append(
                f"ATM PE OI +{atm_pe_oi_chg:.1f}% vs CE +{atm_ce_oi_chg:.1f}% Ã¢â‚¬â€ fresh put writing")
        elif atm_ce_oi_chg > 10 and atm_ce_oi_chg > atm_pe_oi_chg + 5:
            chain_bear_signal += 12
            chain_factors_bear.append(
                f"ATM CE OI +{atm_ce_oi_chg:.1f}% vs PE +{atm_pe_oi_chg:.1f}% Ã¢â‚¬â€ fresh call writing")
    except Exception:
        pass

    # ATM option price change: which side is rallying?
    try:
        atm_ce_chg = float(call_row.iloc[0].get("net_chg", 0)) if not call_row.empty else 0
        atm_pe_chg = float(put_row.iloc[0].get("net_chg", 0)) if not put_row.empty else 0
        if atm_ce_chg > 0 and atm_pe_chg < 0:
            chain_bull_signal += 8
            chain_factors_bull.append(
                f"ATM CE rallying (+{atm_ce_chg:.1f}) while PE falling ({atm_pe_chg:.1f})")
        elif atm_pe_chg > 0 and atm_ce_chg < 0:
            chain_bear_signal += 8
            chain_factors_bear.append(
                f"ATM PE rallying (+{atm_pe_chg:.1f}) while CE falling ({atm_ce_chg:.1f})")
    except Exception:
        pass

    # Ã¢â€â‚¬Ã¢â€â‚¬ Aggregate scoring Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
    change_pct = float(live_price.get("change_pct", 0) or 0)
    sentiment_score = float(sentiment.get("score", 0) or 0)
    iv_skew = float(indicators.get("iv_skew", 0) or 0)
    max_pain = float(indicators.get("max_pain", 0) or 0)
    oi_momentum = str(indicators.get("oi_momentum", "NEUTRAL")).upper()

    bull = 0.0
    bear = 0.0
    bull_factors: List[str] = []
    bear_factors: List[str] = []

    # Candle-based signals (when available)
    if have_candles:
        if bullish_count >= 3:
            bull += 18
            bull_factors.append(f"{bullish_count}/4 recent 1m candles bullish.")
        if bearish_count >= 3:
            bear += 18
            bear_factors.append(f"{bearish_count}/4 recent 1m candles bearish.")
        if body_ratio > 0.6:
            if last_close > 0 and have_candles and float(latest["close"]) >= float(latest["open"]):
                bull += 8
                bull_factors.append("Latest 1m candle has strong bullish body.")
            elif have_candles and float(latest["close"]) < float(latest["open"]):
                bear += 8
                bear_factors.append("Latest 1m candle has strong bearish body.")
        if breakout_above_prev_high:
            bull += 10
            bull_factors.append("Latest 1m close broke previous candle high.")
        elif breakout_below_prev_low:
            bear += 10
            bear_factors.append("Latest 1m close broke previous candle low.")
        if candle_5m_dir > 0:
            bull += 4
            bull_factors.append("5m candle confirms bullish micro-trend.")
        elif candle_5m_dir < 0:
            bear += 4
            bear_factors.append("5m candle confirms bearish micro-trend.")

    # Chain-based signals (always available when chain loads)
    bull += chain_bull_signal
    bear += chain_bear_signal
    bull_factors.extend(chain_factors_bull)
    bear_factors.extend(chain_factors_bear)

    # When candles are missing, weight chain signals heavier to compensate
    if not have_candles and (chain_bull_signal > 0 or chain_bear_signal > 0):
        bull += chain_bull_signal * 0.5  # extra +50% weight
        bear += chain_bear_signal * 0.5

    # Price momentum
    if change_pct >= 0.2:
        bull += min(8, change_pct * 15)
        bull_factors.append(f"Live price momentum +{change_pct:.2f}%.")
    elif change_pct <= -0.2:
        bear += min(8, abs(change_pct) * 15)
        bear_factors.append(f"Live price momentum {change_pct:.2f}%.")

    # Sentiment
    if sentiment_score >= 20:
        bull += 8
        bull_factors.append(f"Sentiment score +{sentiment_score:.0f} bullish.")
    elif sentiment_score <= -20:
        bear += 8
        bear_factors.append(f"Sentiment score {sentiment_score:.0f} bearish.")

    # OI Momentum
    if oi_momentum == "BULLISH":
        bull += 8
        bull_factors.append("OI momentum bullish.")
    elif oi_momentum == "BEARISH":
        bear += 8
        bear_factors.append("OI momentum bearish.")

    # Breakout alerts
    for alert in breakout_alerts[:4]:
        direction = str(alert.get("direction", "")).upper()
        message = str(alert.get("message", ""))
        if direction == "BULLISH":
            bull += 10
            bull_factors.append(message)
        elif direction == "BEARISH":
            bear += 10
            bear_factors.append(message)

    # Levels proximity
    sup = float(support.get("strike", 0) or 0)
    res = float(resistance.get("strike", 0) or 0)
    if sup > 0 and 0 < spot - sup <= 35:
        bull += 6
        bull_factors.append(f"Spot near support {sup:.0f}.")
    if res > 0 and 0 < res - spot <= 35:
        bear += 6
        bear_factors.append(f"Spot near resistance {res:.0f}.")

    # Opening range break confirmation (post-9:30 only)
    if or_status == "BROKEN UP":
        bull += 12
        bull_factors.append(f"Price broke above OR high {opening_range.get('or_high',0):.0f}.")
    elif or_status == "BROKEN DOWN":
        bear += 12
        bear_factors.append(f"Price broke below OR low {opening_range.get('or_low',0):.0f}.")

    # VWAP relationship
    vwap_rel = vwap_data.get("relation", "")
    vwap_trend = vwap_data.get("trend", "")
    if vwap_rel == "ABOVE" and vwap_trend == "RISING":
        bull += 6
        bull_factors.append("Price above rising VWAP Ã¢â‚¬â€ trend support.")
    elif vwap_rel == "BELOW" and vwap_trend == "FALLING":
        bear += 6
        bear_factors.append("Price below falling VWAP Ã¢â‚¬â€ trend pressure.")

    # Max pain pin penalty
    if max_pain > 0 and abs(spot - max_pain) / max(spot, 1) * 100 <= 0.2:
        bull -= 6
        bear -= 6

    # IV skew nudge
    if iv_skew > 2:
        bear += 3
    elif iv_skew < -2:
        bull += 3

    # Ã¢â€â‚¬Ã¢â€â‚¬ Decide Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
    score_gap = abs(bull - bear)
    # When operating on chain-only data, lower the threshold slightly since
    # we can't get the +30-50 boost from candle alignment
    threshold = 40 if have_candles else 32
    gap_required = 12 if have_candles else 10

    if bull >= bear and bull >= threshold and score_gap >= gap_required and not call_row.empty:
        option_row = call_row.iloc[0]
        action = "SCALP CALL"
        factors = bull_factors
    elif bear > bull and bear >= threshold and score_gap >= gap_required and not put_row.empty:
        option_row = put_row.iloc[0]
        action = "SCALP PUT"
        factors = bear_factors
    else:
        # Build informative wait reason
        wait_reasons = []
        if bull < threshold and bear < threshold:
            wait_reasons.append(
                f"Neither side reaches confidence threshold "
                f"(bull={bull:.0f}, bear={bear:.0f}, need Ã¢â€°Â¥{threshold})")
        elif score_gap < gap_required:
            wait_reasons.append(
                f"Bull/bear too close (gap={score_gap:.0f}, need Ã¢â€°Â¥{gap_required})")

        if not have_candles:
            wait_reasons.append("Live candles unavailable Ã¢â‚¬â€ running on chain-only data")

        result["wait_reasons"] = wait_reasons
        result["confidence"] = int(max(bull, bear))
        result["reason"] = (wait_reasons[0] if wait_reasons
                             else "Micro-trend not clean enough for a fast scalp.")
        result["supporting_factors"] = (bull_factors if bull >= bear else bear_factors)[:3]
        result["risk_note"] = "Wait for stronger momentum or fresh breakout."
        return result

    # Ã¢â€â‚¬Ã¢â€â‚¬ Liquidity & pricing checks Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
    entry_ltp = float(option_row.get("price", 0) or 0)
    if entry_ltp <= 0:
        result["wait_reasons"] = ["ATM option LTP missing"]
        result["reason"] = "ATM option LTP unavailable Ã¢â‚¬â€ pricing unreliable."
        result["risk_note"] = "Wait for valid option quote."
        return result

    option_oi = float(option_row.get("oi", 0) or 0)
    option_vol = float(option_row.get("volume", 0) or 0)
    oi_chg = float(option_row.get("oi_perc_chg", 0) or 0)

    if option_oi < 50000 or option_vol < 25000:
        result["wait_reasons"] = [
            f"ATM liquidity thin (OI={option_oi:.0f}, Vol={option_vol:.0f})"]
        result["reason"] = "ATM option liquidity too thin for clean fills."
        result["risk_note"] = "Low OI/volume hurts entry/exit slippage."
        return result

    if abs(oi_chg) < 5:
        result["wait_reasons"] = [f"OI change only {oi_chg:.1f}% Ã¢â‚¬â€ soft positioning"]
        result["reason"] = "Option OI change too soft for a fast scalp."
        result["risk_note"] = "Wait for stronger fresh positioning at ATM."
        return result

    # Ã¢â€â‚¬Ã¢â€â‚¬ Build the trade Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
    # 30-min holding model: wider targets, tighter SL as % but more room in points
    # High conviction (score_gap >= 18) = cleaner entry = tighter 15-min target
    # Lower conviction = need more time = 30-min hold with wider target
    timeframe = "15 min" if score_gap >= 18 else "30 min"
    target_mult = 1.15 if timeframe == "15 min" else 1.22   # 15-22% target (was 8-12%)
    stop_mult   = 0.94 if timeframe == "15 min" else 0.92   # 6-8% SL (was 4-6%)
    if is_open and minutes_to_close <= 60:
        target_mult -= 0.03   # Reduce target when approaching session end
        stop_mult += 0.01

    confidence_cap = 92 if have_candles else 80  # cap lower without candles

    result.update({
        "action": action,
        "confidence": int(min(confidence_cap, max(bull, bear))),
        "timeframe": timeframe,
        "entry_strike": int(float(option_row.get("strike_price", atm) or atm)),
        "entry_type": "ATM",
        "entry_price_range": f"{round(entry_ltp * 0.99, 1)}-{round(entry_ltp * 1.01, 1)}",
        "target_price": round(entry_ltp * target_mult, 1),
        "stop_loss_price": round(entry_ltp * stop_mult, 1),
        "exit_rule": (f"Target {timeframe.lower()} hold. Exit at target OR if 5-min candle "
                      f"closes against position. Do NOT hold past {timeframe.lower()}."),
        "reason": factors[0] if factors else "Momentum and structure support a directional hold.",
        "supporting_factors": factors[:5],
        "risk_note": ("Intraday directional hold (15-30 min). Book at first target. "
                      "Trail SL to breakeven once 50% of target is reached. "
                      "Do not convert to overnight." +
                      ("" if have_candles else
                       " Note: candles unavailable, signal based on chain only.")),
    })
    return result
    return result


def render_quick_scalp_signal(signal: Dict[str, Any], checklist: Optional[Dict[str, Any]] = None):
    action = _clean_text(signal.get("action", "WAIT"))
    confidence = int(signal.get("confidence", 0) or 0)
    color = "#2e7d32" if action == "SCALP CALL" else "#c62828" if action == "SCALP PUT" else "#78909c"
    bg = "#f1f8f2" if action == "SCALP CALL" else "#fff4f4" if action == "SCALP PUT" else "#f6f7fb"
    label = "FAST" if action.startswith("SCALP") else "WAIT"
    factors = [_clean_text(f) for f in (signal.get("supporting_factors", []) or [])]
    wait_reasons = [_clean_text(r) for r in (signal.get("wait_reasons", []) or [])]
    data_q = signal.get("data_quality", "unknown")
    quality_badge = ""
    if data_q == "chain_only":
        quality_badge = ('<span style="background:#fff3e0;color:#ef6c00;'
                         'border:1px solid #ffb74d;border-radius:4px;'
                         'padding:1px 7px;font-size:0.65rem;font-weight:700;'
                         'margin-left:8px">CHAIN-ONLY</span>')
    elif data_q == "full":
        quality_badge = ('<span style="background:#e8f5e9;color:#2e7d32;'
                         'border:1px solid #66bb6a;border-radius:4px;'
                         'padding:1px 7px;font-size:0.65rem;font-weight:700;'
                         'margin-left:8px">FULL DATA</span>')

    # ── Checklist alignment banner ─────────────────────────────────────────────
    # Shows whether the Decision Checklist agrees with the scalp signal.
    # This is the key link between the two systems.
    checklist_banner = ""
    if checklist:
        cl_verdict = str(checklist.get("verdict", ""))
        cl_fails   = int(checklist.get("n_fail", 0) or 0)
        cl_msg     = str(checklist.get("verdict_msg", ""))

        if action.startswith("SCALP"):
            # Scalp engine is recommending an entry — what does checklist say?
            if cl_verdict == "GO":
                checklist_banner = (
                    '<div style="background:#e8f5e9;border:1px solid #66bb6a;border-radius:6px;'
                    'padding:6px 12px;margin-top:8px;font-size:0.78rem;color:#1b5e20;font-weight:600">'
                    '✅ Decision Checklist: GO — all structural conditions align. '
                    'High-probability setup for 15-30 min hold.</div>'
                )
            elif cl_verdict == "CAUTIOUS GO":
                checklist_banner = (
                    '<div style="background:#fff8e1;border:1px solid #ffd54f;border-radius:6px;'
                    'padding:6px 12px;margin-top:8px;font-size:0.78rem;color:#7f5a00;font-weight:600">'
                    f'⚠️ Decision Checklist: CAUTIOUS GO — {cl_msg}. '
                    'Consider half-size position.</div>'
                )
            elif cl_verdict in ("MARGINAL", "WATCHLIST"):
                checklist_banner = (
                    '<div style="background:#fff3e0;border:1px solid #ffb74d;border-radius:6px;'
                    'padding:6px 12px;margin-top:8px;font-size:0.78rem;color:#e65100;font-weight:600">'
                    f'⚡ Checklist: {cl_verdict} — {cl_fails} structural blocker(s). '
                    'Scalp signal fires but structural conditions are mixed. '
                    'Use tighter SL if entering.</div>'
                )
            else:  # NO TRADE
                checklist_banner = (
                    '<div style="background:#fce8e8;border:1px solid #ef9a9a;border-radius:6px;'
                    'padding:6px 12px;margin-top:8px;font-size:0.78rem;color:#c62828;font-weight:700">'
                    f'🚫 Decision Checklist: NO TRADE — {cl_fails} blocker(s). '
                    'Scalp signal fires but structural conditions oppose entry. '
                    'Do NOT enter unless you have strong conviction beyond these signals.</div>'
                )
        else:
            # Scalp is WAIT — checklist provides directional context
            if cl_verdict == "GO":
                checklist_banner = (
                    '<div style="background:#e3f2fd;border:1px solid #90caf9;border-radius:6px;'
                    'padding:6px 12px;margin-top:8px;font-size:0.78rem;color:#0d47a1;font-weight:600">'
                    '📋 Checklist: GO — structure is ready. '
                    'Scalp engine is waiting for momentum confirmation. '
                    'Watch for breakout trigger.</div>'
                )
            elif cl_verdict in ("NO TRADE", "MARGINAL"):
                checklist_banner = (
                    '<div style="background:#f3f4fb;border:1px solid #c5cae9;border-radius:6px;'
                    'padding:6px 12px;margin-top:8px;font-size:0.78rem;color:#3949ab">'
                    f'📋 Checklist: {cl_verdict} — both systems agree: wait.</div>'
                )

    st.markdown(
        f'<div style="background:{bg};border:1px solid {color}44;border-left:4px solid {color};'
        f'border-radius:10px;padding:1rem 1.1rem;margin-bottom:0.8rem">'
        f'<div style="display:flex;justify-content:space-between;align-items:center;gap:10px;flex-wrap:wrap">'
        f'<div>'
        f'<div style="font-size:0.68rem;color:#78909c;text-transform:uppercase;letter-spacing:1px">'
        f'Quick Scalp Engine{quality_badge}</div>'
        f'<div style="font-size:1.35rem;font-weight:700;color:{color}">{label} {action}</div>'
        f'</div>'
        f'<div style="font-family:monospace;font-size:1.1rem;color:{color};font-weight:700">{confidence}/100</div>'
        f'</div>'
        f'<div style="font-size:0.84rem;color:#2c3e50;margin-top:0.55rem">{_clean_text(signal.get("reason",""))}</div>'
        f'{checklist_banner}'
        f'</div>',
        unsafe_allow_html=True,
    )

    # If WAIT, show explicit reasons before the trade params (which would be empty)
    if action == "WAIT" and wait_reasons:
        reasons_html = "".join(
            f'<li style="margin:2px 0">{r}</li>' for r in wait_reasons[:4]
        )
        st.markdown(
            f'<div style="background:#fff8e1;border:1px solid #ffe082;border-radius:6px;'
            f'padding:8px 12px;margin-top:8px;font-size:0.78rem;color:#7f5a00">'
            f'<div style="font-weight:700;margin-bottom:4px">Why WAIT:</div>'
            f'<ul style="margin:0;padding-left:18px">{reasons_html}</ul>'
            f'</div>',
            unsafe_allow_html=True,
        )

    if action != "WAIT":
        st.markdown(
            f'<div style="display:flex;gap:0.8rem;flex-wrap:wrap;margin-top:0.7rem;font-size:0.76rem;color:#546e7a">'
            f'<span><strong>Timeframe:</strong> {_clean_text(signal.get("timeframe","--"))}</span>'
            f'<span><strong>Strike:</strong> {_clean_text(signal.get("entry_strike","--"))}</span>'
            f'<span><strong>Entry:</strong> Rs. {_clean_text(signal.get("entry_price_range","--"))}</span>'
            f'<span><strong>Target:</strong> Rs. {_clean_text(signal.get("target_price","--"))}</span>'
            f'<span><strong>SL:</strong> Rs. {_clean_text(signal.get("stop_loss_price","--"))}</span>'
            f'</div>'
            f'<div style="font-size:0.74rem;color:#6b7280;margin-top:0.65rem">{_clean_text(signal.get("exit_rule",""))}</div>',
            unsafe_allow_html=True,
        )

    risk_note = _clean_text(signal.get("risk_note", ""))
    if risk_note:
        st.markdown(
            f'<div style="font-size:0.74rem;color:#8d4e00;margin-top:0.4rem">{risk_note}</div>',
            unsafe_allow_html=True,
        )

    if factors:
        st.markdown(
            f'<div style="font-size:0.72rem;color:#78909c;margin-top:0.55rem">'
            f'<strong>Signals seen:</strong> {" | ".join([str(f) for f in factors[:4]])}'
            f'</div>',
            unsafe_allow_html=True,
        )

    st.markdown("</div>", unsafe_allow_html=True)


def _find_nearest_contract(df: pd.DataFrame, strike: int) -> pd.DataFrame:
    if df is None or df.empty or "strike_price" not in df.columns:
        return pd.DataFrame()
    local = df.copy()
    local["strike_price"] = pd.to_numeric(local["strike_price"], errors="coerce").fillna(0)
    local["distance"] = (local["strike_price"] - strike).abs()
    return local.sort_values("distance").head(1)


# Signal Journal and Outcome Tracker
SIGNAL_JOURNAL_FILE = ".streamlit/optionsiq_signal_journal.json"


def _load_signal_journal() -> List[Dict[str, Any]]:
    if st.session_state.get("_signal_journal_loaded"):
        return st.session_state.signal_journal
    try:
        if os.path.exists(SIGNAL_JOURNAL_FILE):
            with open(SIGNAL_JOURNAL_FILE, "r", encoding="utf-8") as f:
                st.session_state.signal_journal = json.load(f)
        else:
            st.session_state.signal_journal = []
    except Exception:
        st.session_state.signal_journal = []
    st.session_state["_signal_journal_loaded"] = True
    return st.session_state.signal_journal


def _save_signal_journal():
    try:
        os.makedirs(os.path.dirname(SIGNAL_JOURNAL_FILE), exist_ok=True)
        with open(SIGNAL_JOURNAL_FILE, "w", encoding="utf-8") as f:
            json.dump(st.session_state.get("signal_journal", [])[-500:], f, default=str)
    except Exception:
        pass


def init_signal_journal():
    _load_signal_journal()
    if "last_signal_keys" not in st.session_state:
        st.session_state.last_signal_keys = {}


def _safe_dt(value):
    try:
        return pd.to_datetime(value).to_pydatetime()
    except Exception:
        return None


def _range_mid(value, fallback=0.0) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value or "").replace("â‚¹", "").replace(",", "").strip()
    parts = [p for p in text.split("-") if p.strip()]
    try:
        nums = [float(p.strip()) for p in parts]
        return sum(nums) / len(nums) if nums else float(fallback or 0)
    except Exception:
        return float(fallback or 0)


def _option_ltp(option_data: Dict, action: str, strike: int) -> float:
    is_call = "CALL" in str(action).upper() or "CE" in str(action).upper()
    chain = (option_data or {}).get("calls" if is_call else "puts", [])
    best_ltp = 0.0
    best_dist = 10**9
    for row in chain:
        try:
            row_strike = int(float(row.get("strike_price", 0) or 0))
            dist = abs(row_strike - int(strike or 0))
            ltp = float(row.get("price", 0) or 0)
            if ltp > 0 and dist < best_dist:
                best_ltp = ltp
                best_dist = dist
        except Exception:
            continue
    return round(best_ltp, 2)


def _signal_key(source: str, action: str, strike: int, bucket: str) -> str:
    now_bucket = datetime.now().strftime("%Y%m%d-%H%M")
    return f"{source}|{action}|{strike}|{bucket}|{now_bucket}"


def record_signal_snapshot(
    *,
    source: str,
    signal: Dict[str, Any],
    live_price: Dict[str, Any],
    option_data: Dict[str, Any],
    sentiment: Dict[str, Any],
    checklist: Optional[Dict[str, Any]] = None,
    opening_range: Optional[Dict[str, Any]] = None,
    vwap_data: Optional[Dict[str, Any]] = None,
    pcr_data: Optional[Dict[str, Any]] = None,
    vol_regime: Optional[Dict[str, Any]] = None,
):
    """Record actionable signals once per minute for later outcome analysis."""
    init_signal_journal()
    action = str(signal.get("action", "")).upper()
    if action in ("", "WAIT", "NO TRADE"):
        return

    confidence = int(signal.get("confidence", signal.get("quality_score", 0)) or 0)
    verdict = str((checklist or {}).get("verdict", "")).upper()
    if source == "QUICK_SCALP" and confidence < 55:
        return
    if source == "ENTRY_CHECKLIST" and verdict not in ("GO", "CAUTIOUS GO", "WATCHLIST"):
        return

    strike = int(float(signal.get("entry_strike", 0) or live_price.get("ltp", 0) or 0) / 50) * 50
    if signal.get("entry_strike"):
        strike = int(float(signal.get("entry_strike", strike) or strike))

    bucket = verdict or str(signal.get("timeframe", "setup"))
    key = _signal_key(source, action, strike, bucket)
    last_seen = st.session_state.last_signal_keys.get(key)
    if last_seen and (datetime.now() - _safe_dt(last_seen)).total_seconds() < 55:
        return

    option_entry = _option_ltp(option_data, action, strike)
    if option_entry <= 0:
        option_entry = _range_mid(signal.get("entry_price_range"), 0)
    if option_entry <= 0:
        return

    target = float(signal.get("target_price", 0) or 0)
    stop = float(signal.get("stop_loss_price", 0) or 0)
    if target <= 0 or stop <= 0:
        target = round(option_entry * 1.10, 2)
        stop = round(option_entry * 0.94, 2)

    entry = {
        "id": key,
        "source": source,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "status": "OPEN",
        "action": action,
        "strike": strike,
        "entry_price": round(option_entry, 2),
        "target_price": round(target, 2),
        "stop_loss_price": round(stop, 2),
        "current_price": round(option_entry, 2),
        "best_price": round(option_entry, 2),
        "worst_price": round(option_entry, 2),
        "spot": round(float(live_price.get("ltp", 0) or 0), 2),
        "confidence": confidence,
        "verdict": verdict,
        "setup_score": int((checklist or {}).get("quality_score", confidence) or confidence),
        "bias": (checklist or {}).get("preferred_setup", ""),
        "sentiment_score": float((sentiment or {}).get("score", 0) or 0),
        "pcr": float((pcr_data or {}).get("pcr_oi", 0) or 0),
        "or_status": (opening_range or {}).get("status", ""),
        "vwap_position": (vwap_data or {}).get("position", ""),
        "vix_regime": (vol_regime or {}).get("regime", ""),
        "factors": signal.get("supporting_factors", [])[:5],
        "reason": signal.get("reason", ""),
        "eval_3m": "PENDING",
        "eval_5m": "PENDING",
        "eval_10m": "PENDING",
        "eval_15m": "PENDING",
        "final_outcome": "PENDING",
    }
    st.session_state.signal_journal.append(entry)
    st.session_state.signal_journal = st.session_state.signal_journal[-500:]
    st.session_state.last_signal_keys[key] = datetime.now().isoformat()
    _save_signal_journal()


def update_signal_outcomes(option_data: Dict[str, Any]):
    """Update target-first/stop-first outcomes from the latest option chain."""
    init_signal_journal()
    changed = False
    now = datetime.now()
    windows = [(3, "eval_3m"), (5, "eval_5m"), (10, "eval_10m"), (15, "eval_15m")]
    for item in st.session_state.signal_journal:
        if item.get("final_outcome") in ("TARGET", "STOP", "EXPIRED"):
            continue
        created = _safe_dt(item.get("created_at"))
        if not created:
            continue
        ltp = _option_ltp(option_data, item.get("action", ""), int(item.get("strike", 0) or 0))
        if ltp <= 0:
            continue
        item["current_price"] = round(ltp, 2)
        item["best_price"] = round(max(float(item.get("best_price", ltp) or ltp), ltp), 2)
        item["worst_price"] = round(min(float(item.get("worst_price", ltp) or ltp), ltp), 2)
        target = float(item.get("target_price", 0) or 0)
        stop = float(item.get("stop_loss_price", 0) or 0)
        if target > 0 and ltp >= target:
            item["final_outcome"] = "TARGET"
            item["status"] = "CLOSED"
            item["closed_at"] = now.isoformat(timespec="seconds")
            changed = True
        elif stop > 0 and ltp <= stop:
            item["final_outcome"] = "STOP"
            item["status"] = "CLOSED"
            item["closed_at"] = now.isoformat(timespec="seconds")
            changed = True

        age_min = (now - created).total_seconds() / 60
        pnl_pct = ((ltp - float(item.get("entry_price", ltp))) / max(float(item.get("entry_price", ltp)), 0.01)) * 100
        for minutes, key in windows:
            if age_min >= minutes and item.get(key) == "PENDING":
                if item.get("final_outcome") in ("TARGET", "STOP"):
                    item[key] = item["final_outcome"]
                elif pnl_pct >= 4:
                    item[key] = "FAVORABLE"
                elif pnl_pct <= -3:
                    item[key] = "ADVERSE"
                else:
                    item[key] = "FLAT"
                changed = True
        if age_min >= 20 and item.get("final_outcome") == "PENDING":
            item["final_outcome"] = "EXPIRED"
            item["status"] = "CLOSED"
            changed = True
    if changed:
        _save_signal_journal()


def render_signal_journal():
    """Render signal outcome analytics and recent logged signals."""
    init_signal_journal()
    journal = st.session_state.get("signal_journal", [])
    if not journal:
        st.info("No journaled signals yet. Strong Quick Scalp and checklist signals will appear here automatically.")
        return

    closed = [x for x in journal if x.get("final_outcome") in ("TARGET", "STOP", "EXPIRED")]
    target_hits = sum(1 for x in closed if x.get("final_outcome") == "TARGET")
    stop_hits = sum(1 for x in closed if x.get("final_outcome") == "STOP")
    open_count = sum(1 for x in journal if x.get("status") == "OPEN")
    win_rate = round(target_hits / max(target_hits + stop_hits, 1) * 100)
    avg_mfe = np.mean([
        (float(x.get("best_price", 0) or 0) - float(x.get("entry_price", 0) or 0)) / max(float(x.get("entry_price", 0) or 0), 0.01) * 100
        for x in journal
    ])

    c1, c2, c3, c4 = st.columns(4)
    metrics = [
        (c1, "Signals", len(journal), "#1565c0"),
        (c2, "Target-first WR", f"{win_rate}%", "#2e7d32" if win_rate >= 55 else "#ef6c00"),
        (c3, "Open Tracking", open_count, "#546e7a"),
        (c4, "Avg Best Move", f"{avg_mfe:+.1f}%", "#2e7d32" if avg_mfe >= 0 else "#c62828"),
    ]
    for col, label, value, color in metrics:
        with col:
            st.markdown(
                f'<div style="background:#ffffff;border:1px solid #e0e4ec;border-radius:8px;'
                f'padding:0.7rem;text-align:center">'
                f'<div style="font-size:0.62rem;color:#78909c;text-transform:uppercase">{label}</div>'
                f'<div style="font-size:1.25rem;font-weight:700;color:{color};font-family:monospace">{value}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )

    rows = []
    for x in reversed(journal[-40:]):
        entry = float(x.get("entry_price", 0) or 0)
        current = float(x.get("current_price", entry) or entry)
        pnl = (current - entry) / max(entry, 0.01) * 100
        rows.append({
            "Time": str(x.get("created_at", ""))[5:16],
            "Source": x.get("source", ""),
            "Action": x.get("action", ""),
            "Strike": x.get("strike", ""),
            "Score": x.get("setup_score", x.get("confidence", 0)),
            "Entry": round(entry, 2),
            "Now": round(current, 2),
            "P&L%": round(pnl, 1),
            "3m": x.get("eval_3m", ""),
            "5m": x.get("eval_5m", ""),
            "10m": x.get("eval_10m", ""),
            "Final": x.get("final_outcome", ""),
            "Context": f"{x.get('or_status','')} | {x.get('vwap_position','')} | PCR {float(x.get('pcr',0) or 0):.2f}",
        })
    st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)

    grouped = {}
    for x in closed:
        key = f"{x.get('source','')} | {x.get('or_status','')} | {x.get('vwap_position','')}"
        grouped.setdefault(key, {"total": 0, "wins": 0})
        grouped[key]["total"] += 1
        grouped[key]["wins"] += 1 if x.get("final_outcome") == "TARGET" else 0
    if grouped:
        stats = [
            {"Setup": k, "Samples": v["total"], "Target WR": round(v["wins"] / max(v["total"], 1) * 100)}
            for k, v in grouped.items() if v["total"] >= 1
        ]
        st.markdown("#### Setup Performance")
        st.dataframe(pd.DataFrame(stats).sort_values(["Samples", "Target WR"], ascending=False), hide_index=True, use_container_width=True)

    if st.button("Clear Signal Journal", help="Deletes only the signal journal, not your trade history."):
        st.session_state.signal_journal = []
        _save_signal_journal()
        st.rerun()


# Ã¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢Â
# 2. LIVE TRADE TRACKER
# Ã¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢Â

def init_trade_tracker():
    """Initialize trade tracker session state."""
    if "active_trade" not in st.session_state:
        st.session_state.active_trade = None
    if "trade_history" not in st.session_state:
        st.session_state.trade_history = []


def start_trade(ai_result: Dict, live_price: Dict, option_data: Dict):
    """Start tracking a new trade from AI recommendation."""
    if not ai_result or ai_result.get("action") == "NO TRADE":
        return

    spot = float(live_price.get("ltp", 0) or 0)
    action       = ai_result.get("action", "")
    _sym_t = live_price.get("symbol", "NIFTY") if isinstance(live_price, dict) else "NIFTY"
    entry_strike = int(ai_result.get("entry_strike", round(spot / get_strike_gap(_sym_t)) * get_strike_gap(_sym_t)))
    entry_price  = ai_result.get("entry_price_range", "0-0")
    target       = float(ai_result.get("target_price", 0) or 0)
    sl           = float(ai_result.get("stop_loss_price", 0) or 0)
    timeframe    = ai_result.get("timeframe", "30 min")

    # Parse entry mid-price
    try:
        parts = str(entry_price).split("-")
        mid_entry = (float(parts[0]) + float(parts[-1])) / 2
    except:
        mid_entry = (target + sl) / 2

    # Get current option LTP from chain
    is_call = "CALL" in action
    chain   = option_data.get("calls" if is_call else "puts", [])
    opt_ltp = mid_entry  # fallback
    for row in chain:
        try:
            if abs(float(row.get("strike_price", 0)) - entry_strike) < 30:
                ltp = float(row.get("price", 0) or 0)
                if ltp > 0:
                    opt_ltp = ltp
                    break
        except:
            continue

    mins = int(str(timeframe).replace(" min","").replace("min","").strip() or 30)
    st.session_state.active_trade = {
        "action":       action,
        "symbol":       ai_result.get("risk_profile","").replace("CONSERVATIVE","").replace("MODERATE","").replace("AGGRESSIVE","").strip() or "NIFTY",
        "strike":       entry_strike,
        "option_type":  "CE" if is_call else "PE",
        "entry_price":  round(opt_ltp, 2),
        "target":       round(target, 2),
        "sl":           round(sl, 2),
        "current_ltp":  round(opt_ltp, 2),
        "entry_time":   datetime.now(),
        "exit_by":      datetime.now() + timedelta(minutes=mins),
        "max_ltp":      round(opt_ltp, 2),
        "min_ltp":      round(opt_ltp, 2),
        "pnl_pct":      0.0,
        "status":       "ACTIVE",
        "lots":         int(ai_result.get("max_lots", 1)),
        "lot_size":     get_lot_size(live_price.get("symbol", "NIFTY") if isinstance(live_price, dict) else "NIFTY"),
    }


def update_trade_ltp(option_data: Dict):
    """Update current LTP for active trade from fresh option chain."""
    trade = st.session_state.get("active_trade")
    if not trade or trade.get("status") != "ACTIVE":
        return

    is_call = trade["option_type"] == "CE"
    chain   = option_data.get("calls" if is_call else "puts", [])
    for row in chain:
        try:
            if abs(float(row.get("strike_price",0)) - trade["strike"]) < 30:
                ltp = float(row.get("price", 0) or 0)
                if ltp > 0:
                    trade["current_ltp"] = round(ltp, 2)
                    trade["max_ltp"]     = max(trade["max_ltp"], ltp)
                    trade["min_ltp"]     = min(trade["min_ltp"], ltp)
                    entry = trade["entry_price"]
                    if entry > 0:
                        trade["pnl_pct"] = round((ltp - entry) / entry * 100, 1)
                    break
        except:
            continue


def close_trade(outcome: str = "MANUAL"):
    """Close active trade and move to history."""
    trade = st.session_state.get("active_trade")
    if not trade:
        return
    trade["close_time"] = datetime.now()
    trade["status"]     = outcome
    trade["duration"]   = int((trade["close_time"] - trade["entry_time"]).total_seconds() / 60)
    # Determine win/loss
    if outcome == "TARGET":
        trade["result"] = "WIN"
    elif outcome == "SL":
        trade["result"] = "LOSS"
    else:
        trade["result"] = "WIN" if trade["pnl_pct"] > 0 else ("LOSS" if trade["pnl_pct"] < -5 else "BREAKEVEN")

    st.session_state.trade_history.append(dict(trade))
    st.session_state.active_trade = None


def render_live_tracker(option_data: Dict):
    """Render the live trade tracker widget."""
    init_trade_tracker()

    trade = st.session_state.get("active_trade")
    ai    = st.session_state.get("ai_result")

    # Start button
    if not trade and ai and ai.get("action") != "NO TRADE":
        live = st.session_state.get("live_price") or {}
        opts = st.session_state.get("option_data") or {}
        col1, col2 = st.columns([3, 1])
        with col2:
            if st.button("Ã°Å¸â€œÅ’ Start Tracking This Trade", use_container_width=True, type="primary"):
                start_trade(ai, live, opts)
                st.rerun()
        return

    if not trade:
        st.info("Get an AI recommendation first, then click 'Start Tracking' to monitor your trade live.")
        return

    # Update LTP
    if option_data:
        update_trade_ltp(option_data)

    now       = datetime.now()
    entry     = trade["entry_price"]
    current   = trade["current_ltp"]
    target    = trade["target"]
    sl        = trade["sl"]
    pnl_pct   = trade["pnl_pct"]
    time_left = max(0, int((trade["exit_by"] - now).total_seconds() / 60))
    elapsed   = int((now - trade["entry_time"]).total_seconds() / 60)

    # Auto-close detection
    if current >= target and trade["status"] == "ACTIVE":
        close_trade("TARGET")
        st.success("Ã°Å¸Å½Â¯ TARGET HIT! Trade closed automatically.")
        st.balloons()
        st.rerun()
        return
    if current <= sl and trade["status"] == "ACTIVE":
        close_trade("SL")
        st.error("Ã°Å¸â€ºâ€˜ STOP LOSS HIT! Trade closed.")
        st.rerun()
        return
    if time_left == 0 and trade["status"] == "ACTIVE":
        st.warning("Ã¢ÂÂ° Time window expired! Exit recommended.")

    # Color logic
    pnl_color = "#2e7d32" if pnl_pct > 0 else "#c62828" if pnl_pct < -5 else "#ffcc00"
    to_target  = round((target - current) / entry * 100, 1) if entry > 0 else 0
    to_sl      = round((current - sl) / entry * 100, 1) if entry > 0 else 0
    progress   = max(0, min(100, (current - sl) / (target - sl) * 100)) if target != sl else 50

    lots     = trade.get("lots", 1)
    lot_size = trade.get("lot_size", 75)
    pnl_abs  = round((current - entry) * lots * lot_size, 0)

    action_icon = "Ã°Å¸â€œË†" if "CALL" in trade["action"] else "Ã°Å¸â€œâ€°"
    time_color  = "#c62828" if time_left <= 5 else "#ffcc00" if time_left <= 15 else "#2e7d32"

    st.markdown(f"""
    <div style="background:#ffffff;border:1px solid #e0e4ec;border-radius:12px;padding:1rem;margin-bottom:0.8rem">

        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:0.8rem">
            <div>
                <span style="font-size:0.65rem;color:#78909c;text-transform:uppercase">Active Trade</span>
                <div style="font-size:1rem;font-weight:700;color:#1a237e;margin-top:2px">
                    {action_icon} {trade['action']} Ã‚Â· {trade['strike']}{trade['option_type']}
                </div>
            </div>
            <div style="text-align:right">
                <div style="font-size:0.65rem;color:#78909c">Time Left</div>
                <div style="font-size:1.4rem;font-weight:700;color:{time_color};font-family:monospace">
                    {time_left:02d}m
                </div>
            </div>
        </div>

        <div style="display:grid;grid-template-columns:1fr 1fr 1fr 1fr;gap:8px;margin-bottom:0.8rem">
            <div style="background:#f0f2f6;border-radius:6px;padding:0.5rem;text-align:center">
                <div style="font-size:0.6rem;color:#78909c">ENTRY</div>
                <div style="font-size:1rem;font-weight:700;color:#546e7a;font-family:monospace">Ã¢â€šÂ¹{entry:.0f}</div>
            </div>
            <div style="background:#f0f2f6;border-radius:6px;padding:0.5rem;text-align:center">
                <div style="font-size:0.6rem;color:#78909c">CURRENT</div>
                <div style="font-size:1rem;font-weight:700;color:{pnl_color};font-family:monospace">Ã¢â€šÂ¹{current:.0f}</div>
            </div>
            <div style="background:#e8f5e9;border-radius:6px;padding:0.5rem;text-align:center">
                <div style="font-size:0.6rem;color:#78909c">TARGET</div>
                <div style="font-size:1rem;font-weight:700;color:#1b5e20;font-family:monospace">Ã¢â€šÂ¹{target:.0f}</div>
            </div>
            <div style="background:#fce8e8;border-radius:6px;padding:0.5rem;text-align:center">
                <div style="font-size:0.6rem;color:#78909c">STOP LOSS</div>
                <div style="font-size:1rem;font-weight:700;color:#c62828;font-family:monospace">Ã¢â€šÂ¹{sl:.0f}</div>
            </div>
        </div>

        <div style="background:#f0f2f6;border-radius:6px;height:8px;margin-bottom:0.6rem;overflow:hidden">
            <div style="height:100%;width:{progress:.0f}%;background:linear-gradient(90deg,#c62828,{pnl_color},{pnl_color});border-radius:6px;transition:width 0.5s"></div>
        </div>

        <div style="display:flex;justify-content:space-between;align-items:center">
            <div>
                <span style="font-size:1.4rem;font-weight:700;color:{pnl_color};font-family:monospace">
                    {pnl_pct:+.1f}%
                </span>
                <span style="font-size:0.75rem;color:{pnl_color};margin-left:0.4rem">
                    Ã¢â€šÂ¹{pnl_abs:+,.0f} ({lots} lot)
                </span>
            </div>
            <div style="font-size:0.7rem;color:#78909c;text-align:right">
                To Target: {to_target:+.1f}% Ã‚Â· To SL: {to_sl:.1f}% Ã‚Â· {elapsed}m elapsed
            </div>
        </div>
    </div>""", unsafe_allow_html=True)

    c1, c2, c3 = st.columns(3)
    with c1:
        if st.button("Ã°Å¸Å½Â¯ Mark TARGET Hit", use_container_width=True):
            close_trade("TARGET"); st.rerun()
    with c2:
        if st.button("Ã°Å¸â€ºâ€˜ Mark SL Hit", use_container_width=True):
            close_trade("SL"); st.rerun()
    with c3:
        if st.button("Ã°Å¸Å¡Âª Exit Manually", use_container_width=True):
            close_trade("MANUAL"); st.rerun()


# Ã¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢Â
# 3. OI CHANGE VELOCITY
# Ã¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢Â

def compute_oi_velocity(df_calls: pd.DataFrame, df_puts: pd.DataFrame,
                         spot: float) -> Dict[str, Any]:
    """
    Detect fresh OI writing vs covering from OI % change.
    Uses oi_perc_chg from Paytm option chain.
    """
    results = {"call_surges": [], "put_surges": [], "signals": [], "bias": "NEUTRAL"}

    if df_calls.empty and df_puts.empty:
        return results

    atm = round(spot / get_strike_gap('NIFTY')) * get_strike_gap('NIFTY')

    def process(df, side):
        surges = []
        if df.empty or "oi_perc_chg" not in df.columns:
            return surges
        near = df[df["strike_price"].astype(float).sub(spot).abs() <= 500].copy()
        near["oi_perc_chg"] = pd.to_numeric(near["oi_perc_chg"], errors="coerce").fillna(0)
        near["oi"]          = pd.to_numeric(near["oi"], errors="coerce").fillna(0)
        near["price"]       = pd.to_numeric(near["price"], errors="coerce").fillna(0)
        for _, row in near.iterrows():
            chg = float(row["oi_perc_chg"])
            oi  = float(row["oi"])
            ltp = float(row["price"])
            stk = float(row["strike_price"])
            if abs(chg) >= 20 and oi > 50000:
                action = ("FRESH WRITE" if chg > 0 else "COVERING")
                surges.append({
                    "strike": stk, "oi_chg": chg, "oi": oi, "ltp": ltp,
                    "action": action, "side": side,
                    "dist": "ATM" if abs(stk-atm) < 30 else (f"+{int(stk-atm)}" if stk > atm else f"{int(stk-atm)}")
                })
        surges.sort(key=lambda x: abs(x["oi_chg"]), reverse=True)
        return surges[:5]

    results["call_surges"] = process(df_calls, "CE")
    results["put_surges"]  = process(df_puts,  "PE")

    # Derive signals
    fresh_calls   = sum(1 for s in results["call_surges"] if s["oi_chg"] > 30)
    fresh_puts    = sum(1 for s in results["put_surges"]  if s["oi_chg"] > 30)
    cover_calls   = sum(1 for s in results["call_surges"] if s["oi_chg"] < -20)
    cover_puts    = sum(1 for s in results["put_surges"]  if s["oi_chg"] < -20)

    if fresh_puts > fresh_calls and cover_calls > 0:
        results["bias"] = "BULLISH"
        results["signals"].append("OK: Fresh PUT writing + CALL covering = bullish pressure")
    elif fresh_calls > fresh_puts and cover_puts > 0:
        results["bias"] = "BEARISH"
        results["signals"].append("Warning: Fresh CALL writing + PUT covering = bearish resistance")
    elif fresh_calls > 2:
        results["bias"] = "BEARISH"
        results["signals"].append(f"Warning: {fresh_calls} strikes with heavy fresh CALL writing = resistance building")
    elif fresh_puts > 2:
        results["bias"] = "BULLISH"
        results["signals"].append(f"OK: {fresh_puts} strikes with heavy fresh PUT writing = support building")
    elif cover_calls > 1:
        results["signals"].append("OK: CALL unwinding in progress - short covering may push market up")
    elif cover_puts > 1:
        results["signals"].append("Warning: PUT unwinding - support weakening")
    else:
        results["signals"].append("Neutral: No significant OI velocity signals")

    return results


def render_oi_velocity(velocity: Dict):
    """Render OI change velocity section."""
    bias  = velocity.get("bias","NEUTRAL")
    bc    = "#2e7d32" if bias=="BULLISH" else "#c62828" if bias=="BEARISH" else "#8888cc"
    sigs  = velocity.get("signals", [])

    st.markdown(f"""
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:0.5rem">
        <span style="font-size:0.75rem;color:#78909c;text-transform:uppercase">OI Change Velocity</span>
        <span style="background:{bc}22;border:1px solid {bc};border-radius:4px;
                     padding:2px 8px;font-size:0.72rem;color:{bc};font-weight:700">{bias}</span>
    </div>""", unsafe_allow_html=True)

    if sigs:
        for s in sigs:
            st.markdown(f"<div style='font-size:0.75rem;color:#2c3e50;margin-bottom:2px'>{_clean_text(s)}</div>",
                       unsafe_allow_html=True)

    col1, col2 = st.columns(2)

    def render_surges(surges, label, col):
        with col:
            st.markdown(f"<div style='font-size:0.65rem;color:#78909c;margin-bottom:4px'>{label}</div>",
                       unsafe_allow_html=True)
            if not surges:
                st.caption("No significant moves")
                return
            for s in surges[:4]:
                chg_color = "#c62828" if s["oi_chg"] > 0 else "#2e7d32"
                st.markdown(f"""
                <div style="display:flex;justify-content:space-between;padding:3px 6px;
                             margin:2px 0;background:#f8f9ff;border-radius:4px;font-size:0.7rem">
                    <span style="color:#2c3e50">{s['strike']:.0f} ({s['dist']})</span>
                    <span style="color:{chg_color}">{s['oi_chg']:+.0f}%</span>
                    <span style="color:#78909c;font-size:0.65rem">{_clean_text(s['action'])}</span>
                </div>""", unsafe_allow_html=True)

    render_surges(velocity.get("call_surges",[]), "CALL OI Changes", col1)
    render_surges(velocity.get("put_surges", []), "PUT OI Changes",  col2)


# Ã¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢Â
# 4. AI TRADE HISTORY & WIN RATE TRACKER
# Ã¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢Â

def render_trade_history():
    """Render trade history log and win rate statistics."""
    init_trade_tracker()
    history = st.session_state.get("trade_history", [])

    if not history:
        st.info("No completed trades yet. Start tracking a trade and close it to build your history.")
        return

    wins   = sum(1 for t in history if t.get("result") == "WIN")
    losses = sum(1 for t in history if t.get("result") == "LOSS")
    be     = sum(1 for t in history if t.get("result") == "BREAKEVEN")
    total  = len(history)
    wr     = round(wins / total * 100) if total > 0 else 0

    avg_pnl = np.mean([t.get("pnl_pct", 0) for t in history]) if history else 0
    best    = max((t.get("pnl_pct", 0) for t in history), default=0)
    worst   = min((t.get("pnl_pct", 0) for t in history), default=0)

    wr_color = "#2e7d32" if wr >= 55 else "#ffcc00" if wr >= 45 else "#c62828"

    c1, c2, c3, c4 = st.columns(4)
    for col, lbl, val, clr in [
        (c1, "Win Rate",   f"{wr}%",         wr_color),
        (c2, "Trades",     f"{total}",        "#546e7a"),
        (c3, "Avg P&L",    f"{avg_pnl:+.1f}%", "#2e7d32" if avg_pnl > 0 else "#c62828"),
        (c4, "Best / Worst", f"{best:+.0f}% / {worst:+.0f}%", "#2c3e50"),
    ]:
        with col:
            st.markdown(f"""
            <div style="background:#ffffff;border:1px solid #e0e4ec;border-radius:8px;
                        padding:0.7rem;text-align:center">
                <div style="font-size:0.6rem;color:#78909c">{lbl}</div>
                <div style="font-size:1.2rem;font-weight:700;color:{clr};font-family:monospace">{val}</div>
            </div>""", unsafe_allow_html=True)

    st.markdown("<div style='height:0.8rem'></div>", unsafe_allow_html=True)

    for trade in reversed(history[-15:]):
        result  = trade.get("result","?")
        rc      = "#2e7d32" if result=="WIN" else "#c62828" if result=="LOSS" else "#ffcc00"
        pnl     = trade.get("pnl_pct", 0)
        dur     = trade.get("duration", 0)
        et      = trade.get("entry_time")
        ts      = et.strftime("%d %b %H:%M") if isinstance(et, datetime) else str(et)[:16]

        st.markdown(f"""
        <div style="display:flex;align-items:center;gap:8px;padding:6px 10px;
                    margin:3px 0;background:#f8f9ff;border-radius:6px;
                    border-left:3px solid {rc}">
            <span style="color:{rc};font-size:0.7rem;font-weight:700;min-width:55px">{result}</span>
            <span style="color:#2c3e50;font-size:0.75rem;flex:1">
                {trade.get('action','?')} Ã‚Â· {trade.get('strike',0)}{trade.get('option_type','?')}
            </span>
            <span style="color:{rc};font-size:0.78rem;font-family:monospace;min-width:50px;text-align:right">
                {pnl:+.1f}%</span>
            <span style="color:#78909c;font-size:0.65rem;min-width:45px;text-align:right">{dur}m</span>
            <span style="color:#78909c;font-size:0.65rem;min-width:70px;text-align:right">{ts}</span>
        </div>""", unsafe_allow_html=True)

    if st.button("Ã°Å¸â€”â€˜Ã¯Â¸Â Clear History", help="Reset all trade history"):
        st.session_state.trade_history = []
        st.rerun()


# Ã¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢Â
# 5. BANKNIFTY DIVERGENCE + MULTI-EXPIRY PCR
# Ã¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢Â

def fetch_banknifty_spot() -> float:
    """Fetch BankNifty spot from Yahoo Finance."""
    try:
        import requests
        r = requests.get(
            "https://query1.finance.yahoo.com/v8/finance/chart/%5ENSEBANK",
            params={"interval":"1m","range":"1d"},
            headers={"User-Agent":"Mozilla/5.0"}, timeout=5
        )
        if r.status_code == 200:
            meta = r.json().get("chart",{}).get("result",[{}])[0].get("meta",{})
            return float(meta.get("regularMarketPrice", 0) or 0)
    except:
        pass
    return 0.0


def compute_divergence(nifty_chg_pct: float, banknifty_spot: float) -> Dict:
    """Compute BankNifty vs Nifty divergence signal."""
    if banknifty_spot <= 0:
        return {"available": False, "signal": "BankNifty data unavailable"}

    # Estimate BankNifty % change from session state if we have prev close
    # For now use the spot vs typical prev close ratio
    result = {
        "available":   True,
        "bn_spot":     banknifty_spot,
        "nifty_chg":   nifty_chg_pct,
        "signal":      "NEUTRAL",
        "description": "",
        "color":       "#8888cc",
    }

    # Rough divergence: if Nifty positive but BankNifty is weak (or vice versa)
    # BankNifty leads 70% of the time Ã¢â‚¬â€ use its direction as confirmation
    if nifty_chg_pct > 0.3:
        result["signal"]      = "CONFIRMING BULLISH"
        result["description"] = f"Nifty +{nifty_chg_pct:.2f}% with BankNifty present Ã¢â‚¬â€ CHECK BN direction"
        result["color"]       = "#2e7d32"
    elif nifty_chg_pct < -0.3:
        result["signal"]      = "CONFIRMING BEARISH"
        result["description"] = f"Nifty {nifty_chg_pct:.2f}% Ã¢â‚¬â€ verify BankNifty also falling"
        result["color"]       = "#c62828"
    else:
        result["signal"]      = "RANGE-BOUND"
        result["description"] = "Both indices ranging Ã¢â‚¬â€ wait for directional breakout"
        result["color"]       = "#ffcc00"

    return result


def render_divergence_pcr(live_price: Dict, pcr_data: Dict,
                           second_expiry_pcr: float = 0.0):
    """Render BankNifty divergence and multi-expiry PCR."""
    nifty_chg = float(live_price.get("change_pct", 0) or 0)

    # Cache BankNifty spot Ã¢â‚¬â€ only fetch once per 60 seconds
    import datetime as _dt
    _now = _dt.datetime.now()
    _last = st.session_state.get("_bn_last_fetch")
    if (_last is None or (_now - _last).total_seconds() > 60 or
            st.session_state.get("banknifty_spot", 0) == 0):
        try:
            _bn = fetch_banknifty_spot()
            if _bn > 0:
                st.session_state["banknifty_spot"] = _bn
                st.session_state["_bn_last_fetch"] = _now
        except Exception:
            pass
    bn_spot = float(st.session_state.get("banknifty_spot", 0))
    div     = compute_divergence(nifty_chg, bn_spot)

    pcr_near  = pcr_data.get("pcr_oi", 0)
    pcr_vol   = pcr_data.get("pcr_volume", 0)

    dc = div["color"]

    col1, col2 = st.columns(2)

    with col1:
        st.markdown(f"""
        <div style="background:#ffffff;border:1px solid {dc}44;border-radius:8px;padding:0.7rem 0.9rem">
            <div style="font-size:0.65rem;color:#78909c;margin-bottom:0.4rem">BANKNIFTY DIVERGENCE</div>
            <div style="font-size:0.9rem;font-weight:700;color:{dc}">{div['signal']}</div>
            <div style="font-size:0.7rem;color:#546e7a;margin-top:0.3rem">{div['description']}</div>
            {"<div style='font-size:0.75rem;color:#2c3e50;margin-top:0.4rem;font-family:monospace'>BN Spot: Ã¢â€šÂ¹"+f"{bn_spot:,.0f}</div>" if bn_spot > 0 else ""}
        </div>""", unsafe_allow_html=True)

    with col2:
        pcr_color  = "#2e7d32" if pcr_near > 1.2 else "#c62828" if pcr_near < 0.8 else "#ffcc00"
        pcr2_color = "#2e7d32" if second_expiry_pcr > 1.2 else "#c62828" if 0 < second_expiry_pcr < 0.8 else "#8888cc"
        st.markdown(f"""
        <div style="background:#ffffff;border:1px solid #e0e4ec;border-radius:8px;padding:0.7rem 0.9rem">
            <div style="font-size:0.65rem;color:#78909c;margin-bottom:0.4rem">PCR COMPARISON</div>
            <div style="display:flex;justify-content:space-between;margin-bottom:4px">
                <span style="font-size:0.7rem;color:#78909c">Near expiry (OI)</span>
                <span style="font-size:0.85rem;font-weight:700;color:{pcr_color};font-family:monospace">{pcr_near:.3f}</span>
            </div>
            <div style="display:flex;justify-content:space-between;margin-bottom:4px">
                <span style="font-size:0.7rem;color:#78909c">Near expiry (Vol)</span>
                <span style="font-size:0.85rem;font-weight:700;color:#546e7a;font-family:monospace">{pcr_vol:.3f}</span>
            </div>
            <div style="display:flex;justify-content:space-between">
                <span style="font-size:0.7rem;color:#78909c">Next expiry (OI)</span>
                <span style="font-size:0.85rem;font-weight:700;color:{pcr2_color};font-family:monospace">
                    {"N/A" if second_expiry_pcr == 0 else f"{second_expiry_pcr:.3f}"}</span>
            </div>
            <div style="font-size:0.65rem;color:#78909c;margin-top:4px">
                OI PCR>1.2=bullish Ã‚Â· <0.8=bearish Ã‚Â· Vol PCR confirms conviction
            </div>
        </div>""", unsafe_allow_html=True)


# Ã¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢Â
# TIER 1 + TIER 2 ADDITIONS Ã¢â‚¬â€ AI-free decision support
# Ã¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢Â

# Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
# 1. VOLATILITY REGIME BANNER
# Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬

def compute_vol_regime(india_vix: Dict[str, Any]) -> Dict[str, Any]:
    """
    Classify the current volatility environment for option-buyer sizing.
    Lower VIX = cheaper premium = better for option BUYERS.
    """
    vix = float(india_vix.get("vix", 0) or 0) if india_vix else 0
    chg = float(india_vix.get("chg_pct", 0) or 0) if india_vix else 0

    if vix == 0:
        return {"regime": "UNKNOWN", "color": "#78909c",
                "vix": 0.0, "chg_pct": 0.0, "size_pct": 100,
                "tagline": "VIX data unavailable",
                "advice": "Load Market Intelligence in the sidebar to see vol regime."}

    if vix < 13:
        regime = "LOW VOL"
        color = "#1b5e20"
        size_pct = 100
        tagline = "Premium is cheap - option buyers favored"
        advice = "Standard position size. Good environment for OTM bets."
    elif vix < 18:
        regime = "NORMAL"
        color = "#1565c0"
        size_pct = 100
        tagline = "Standard volatility regime"
        advice = "Standard rules apply. No size adjustment."
    elif vix < 22:
        regime = "ELEVATED"
        color = "#ef6c00"
        size_pct = 75
        tagline = "Premium expensive - be selective"
        advice = "Reduce size to 75%. Prefer ITM strikes; OTM premium will bleed."
    else:
        regime = "HIGH VOL"
        color = "#c62828"
        size_pct = 50
        tagline = "Heavy IV - buyers face crush risk"
        advice = "Reduce size to 50%. Avoid weeklies. Wait for VIX peak before entering."

    if chg > 5 and vix > 18:
        advice += " Warning: VIX rising fast - IV crush risk if it peaks during your trade."

    return {
        "regime":  regime,
        "color":   color,
        "vix":     round(vix, 2),
        "chg_pct": round(chg, 2),
        "size_pct": size_pct,
        "tagline": tagline,
        "advice":  advice,
    }


def render_vol_regime_banner(regime: Dict[str, Any]):
    """Render compact volatility regime banner."""
    color = regime.get("color", "#78909c")
    vix_val = regime.get("vix", 0) or 0
    chg_val = regime.get("chg_pct", 0) or 0
    size_pct = regime.get("size_pct", 100)
    tagline = _clean_text(regime.get("tagline", ""))
    advice = _clean_text(regime.get("advice", ""))
    regime_name = regime.get("regime", "UNKNOWN")
    chg_color = "#1b5e20" if chg_val <= 0 else "#c62828"

    # If VIX is 0/unknown, show a simpler banner (no VIX number to display)
    if regime_name == "UNKNOWN" or vix_val == 0:
        st.markdown(f"""
        <div style="background:{color}15;border:1px solid {color}55;border-left:4px solid {color};
                    border-radius:8px;padding:0.6rem 1rem;margin-bottom:0.7rem;
                    display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:0.5rem">
            <div style="display:flex;align-items:center;gap:1rem;flex-wrap:wrap">
                <span style="font-size:0.75rem;color:#78909c;text-transform:uppercase">VOL REGIME</span>
                <span style="font-size:1rem;font-weight:700;color:{color}">{regime_name}</span>
                <span style="font-size:0.78rem;color:#546e7a">| {tagline}</span>
            </div>
        </div>
        <div style="font-size:0.72rem;color:#78909c;margin-bottom:0.8rem;padding-left:0.5rem">
            Tip: {advice}
        </div>
        """, unsafe_allow_html=True)
        return

    st.markdown(f"""
    <div style="background:{color}15;border:1px solid {color}55;border-left:4px solid {color};
                border-radius:8px;padding:0.6rem 1rem;margin-bottom:0.7rem;
                display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:0.5rem">
        <div style="display:flex;align-items:center;gap:1rem;flex-wrap:wrap">
            <span style="font-size:0.75rem;color:#78909c;text-transform:uppercase">VOL REGIME</span>
            <span style="font-size:1rem;font-weight:700;color:{color}">{regime_name}</span>
            <span style="font-size:0.85rem;color:#37474f;font-family:monospace">VIX {vix_val}
                <span style="color:{chg_color};font-size:0.75rem">
                ({chg_val:+.2f}%)</span></span>
            <span style="font-size:0.78rem;color:#546e7a">| {tagline}</span>
        </div>
        <span style="background:{color};color:white;padding:2px 10px;border-radius:4px;
                     font-size:0.75rem;font-weight:700">SIZE: {size_pct}%</span>
    </div>
    <div style="font-size:0.72rem;color:#78909c;margin-bottom:0.8rem;padding-left:0.5rem">
        Tip: {advice}
    </div>
    """, unsafe_allow_html=True)


# Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
# 2. SENTIMENT BREAKDOWN
# Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬

def render_sentiment_breakdown(sentiment: Dict[str, Any]):
    """
    Show each component's contribution to the sentiment score.
    Helps spot when a score is concentrated in 1-2 drivers vs broad-based.
    """
    components = sentiment.get("components", {}) or {}
    score = float(sentiment.get("score", 0) or 0)

    rows = [
        ("PCR Signal",            components.get("pcr", 0),       25),
        ("Price vs Max Pain",     components.get("max_pain", 0),  15),
        ("OI Momentum",           components.get("oi_momentum",0),20),
        ("IV Skew",               components.get("iv_skew", 0),   10),
        ("Intraday Move",         components.get("intraday", 0),  20),
    ]

    same_dir = sum(1 for _, v, _ in rows
                   if (v > 1 if score > 0 else v < -1 if score < 0 else False))
    if abs(score) >= 20 and same_dir <= 2:
        diversity_warn = "Score driven by only 1-2 components - fragile signal"
        warn_color = "#ef6c00"
    elif abs(score) >= 20 and same_dir >= 4:
        diversity_warn = "Score broad-based - 4+ components agree"
        warn_color = "#1b5e20"
    else:
        diversity_warn = ""
        warn_color = "#78909c"

    bars_html = []
    for name, val, max_abs in rows:
        v = float(val or 0)
        pct = abs(v) / max_abs if max_abs else 0
        bar_width = min(100, pct * 100)
        if v > 0:
            bar_color = "#2e7d32"
            bar_left = 50
            bar_w = bar_width / 2
        elif v < 0:
            bar_color = "#c62828"
            bar_left = 50 - bar_width / 2
            bar_w = bar_width / 2
        else:
            bar_color = "#cfd8dc"
            bar_left = 50
            bar_w = 0
        sign = "+" if v > 0 else ""
        bars_html.append(
            f'<div style="display:flex;align-items:center;gap:6px;margin-bottom:3px">'
            f'<span style="font-size:0.7rem;color:#546e7a;width:130px;flex-shrink:0">{name}</span>'
            f'<div style="flex:1;height:8px;background:#eceff1;border-radius:4px;position:relative;overflow:hidden">'
            f'<div style="position:absolute;left:{bar_left}%;top:0;bottom:0;width:{bar_w}%;background:{bar_color}"></div>'
            f'</div>'
            f'<span style="font-size:0.7rem;font-weight:700;color:{bar_color};font-family:monospace;width:42px;text-align:right">{sign}{v:.0f}</span>'
            f'</div>'
        )
    bars = "".join(bars_html)

    st.markdown(
        f'<div style="background:#ffffff;border:1px solid #e0e4ec;border-radius:8px;'
        f'padding:0.7rem 0.9rem;margin-top:0.5rem">'
        f'<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:0.5rem">'
        f'<span style="font-size:0.7rem;color:#78909c;text-transform:uppercase;letter-spacing:0.5px">'
        f'Sentiment Score Breakdown</span>'
        f'<span style="font-size:0.7rem;color:{warn_color};font-weight:600">{diversity_warn}</span>'
        f'</div>'
        f'{bars}'
        f'<div style="font-size:0.65rem;color:#90a4ae;margin-top:6px;border-top:1px dotted #eceff1;padding-top:4px">'
        f'Bars centered. Right=bullish, left=bearish. Width=contribution magnitude.'
        f'</div>'
        f'</div>',
        unsafe_allow_html=True,
    )


# Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
# 3. GAP CLASSIFICATION
# Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬

def classify_gap(live_price: Dict[str, Any]) -> Dict[str, Any]:
    """
    Classify today's opening gap. Returns size, type, and typical fill behavior.
    """
    open_p = float(live_price.get("open", 0) or 0)
    prev_c = float(live_price.get("prev_close", 0) or 0)
    ltp    = float(live_price.get("ltp", 0) or 0)

    if open_p <= 0 or prev_c <= 0:
        return {"type": "UNKNOWN", "size_pts": 0, "size_pct": 0,
                "color": "#78909c", "fill_target": 0, "fill_pct": 0,
                "tagline": "Open or prev close unavailable",
                "advice": ""}

    gap_pts = open_p - prev_c
    gap_pct = (gap_pts / prev_c) * 100
    abs_pct = abs(gap_pct)
    direction = "UP" if gap_pts > 0 else "DOWN" if gap_pts < 0 else "FLAT"

    # How much of the gap has filled so far?
    if direction == "UP":
        fill_progress = max(0, min(100, ((open_p - ltp) / gap_pts) * 100)) if gap_pts else 0
    elif direction == "DOWN":
        fill_progress = max(0, min(100, ((ltp - open_p) / -gap_pts) * 100)) if gap_pts else 0
    else:
        fill_progress = 0

    if abs_pct < 0.15:
        gtype = "NO GAP"
        color = "#78909c"
        fill_typical = "--"
        tagline = "Flat open - standard rules apply"
        advice = "No gap-related setup; trade based on levels and breakouts."
    elif abs_pct < 0.4:
        gtype = f"SMALL GAP {direction}"
        color = "#1565c0"
        fill_typical = "~85%"
        tagline = "Small gap - usually fills early"
        advice = (f"Watch for fill back to Rs. {prev_c:,.0f}. " +
                  ("Fade-the-gap PE has positive expectancy if rejection at HoD." if direction=="UP"
                   else "Fade-the-gap CE has positive expectancy if bottom holds."))
    elif abs_pct < 0.8:
        gtype = f"MEDIUM GAP {direction}"
        color = "#ef6c00"
        fill_typical = "~65%"
        tagline = "Medium gap - fill OR follow-through both viable"
        advice = ("Watch first 15-min candle. Strong continuation = trend day. " +
                  "Reversal candle = fade with prev close target.")
    elif abs_pct < 1.5:
        gtype = f"LARGE GAP {direction}"
        color = "#c62828"
        fill_typical = "~50%"
        tagline = "Large gap - coin-flip on fill vs continuation"
        advice = ("High premium environment. Wait for opening range to form. " +
                  "Don't chase - let price prove direction.")
    else:
        gtype = f"EXHAUSTION GAP {direction}"
        color = "#6a1b9a"
        fill_typical = "~30%"
        tagline = "Exhaustion gap - reversal probability elevated"
        advice = ("Often marks short-term top/bottom. " +
                  ("Bearish first 5-min candle = strong PE setup." if direction=="UP"
                   else "Bullish first 5-min candle = strong CE setup."))

    return {
        "type": gtype,
        "direction": direction,
        "size_pts": round(gap_pts, 2),
        "size_pct": round(gap_pct, 2),
        "abs_pct":  round(abs_pct, 2),
        "color": color,
        "prev_close": prev_c,
        "today_open": open_p,
        "ltp": ltp,
        "fill_target": prev_c,
        "fill_pct": round(fill_progress, 0),
        "fill_typical": fill_typical,
        "tagline": tagline,
        "advice": advice,
    }


def render_gap_card(gap: Dict[str, Any]):
    """Render a compact gap classification card."""
    if gap["type"] == "UNKNOWN":
        return

    color = gap["color"]
    if gap["direction"] == "UP":
        direction_arrow = "UP"
    elif gap["direction"] == "DOWN":
        direction_arrow = "DOWN"
    else:
        direction_arrow = "--"

    fill_bar_html = ""
    if gap["type"] not in ("NO GAP", "UNKNOWN"):
        fill_pct_clamped = min(100, gap['fill_pct'])
        fill_bar_html = (
            f'<div style="margin-top:6px">'
            f'<div style="display:flex;justify-content:space-between;font-size:0.65rem;color:#78909c">'
            f'<span>Fill progress</span>'
            f"<span>{gap['fill_pct']:.0f}% / typical {gap['fill_typical']}</span>"
            f'</div>'
            f'<div style="height:6px;background:#eceff1;border-radius:3px;margin-top:2px;overflow:hidden">'
            f'<div style="height:100%;width:{fill_pct_clamped}%;background:{color}"></div>'
            f'</div>'
            f'<div style="font-size:0.65rem;color:#90a4ae;margin-top:3px">'
            f"Fill target: Rs. {gap['fill_target']:,.0f} (prev close)"
            f'</div>'
            f'</div>'
        )

    st.markdown(
        f'<div style="background:#ffffff;border:1px solid {color}55;border-left:4px solid {color};'
        f'border-radius:8px;padding:0.7rem 0.9rem;margin-bottom:0.5rem">'
        f'<div style="display:flex;justify-content:space-between;align-items:center">'
        f'<span style="font-size:0.7rem;color:#78909c;text-transform:uppercase">Opening Gap</span>'
        f'<span style="background:{color}22;color:{color};padding:1px 8px;border-radius:4px;'
        f"font-size:0.7rem;font-weight:700\">{gap['type']}</span>"
        f'</div>'
        f'<div style="display:flex;align-items:baseline;gap:0.7rem;margin-top:4px">'
        f'<span style="font-size:1.3rem;font-weight:700;color:{color}">{direction_arrow} {abs(gap["size_pts"]):.1f}</span>'
        f"<span style=\"font-size:0.95rem;color:{color};font-family:monospace\">({gap['size_pct']:+.2f}%)</span>"
        f'</div>'
        f"<div style=\"font-size:0.72rem;color:#546e7a;margin-top:2px\">{_clean_text(gap['tagline'])}</div>"
        f'{fill_bar_html}'
        f'<div style="font-size:0.7rem;color:#37474f;margin-top:6px;border-top:1px dotted #eceff1;padding-top:4px">'
        f"Tip: {_clean_text(gap['advice'])}"
        f'</div>'
        f'</div>',
        unsafe_allow_html=True,
    )


# Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
# 4. OPENING RANGE TRACKER
# Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬

def compute_opening_range(candles_1m, ltp: float) -> Dict[str, Any]:
    """
    Compute the 9:15-9:30 opening range high/low and current breakout status.
    Uses 1-minute candles. The first 15 minutes establish the range.
    """
    import pandas as pd
    if candles_1m is None or (hasattr(candles_1m, "empty") and candles_1m.empty):
        return {"available": False, "reason": "No 1-minute candle data"}

    df = candles_1m.copy()
    if "timestamp" not in df.columns:
        df = df.reset_index()
    df["timestamp"] = pd.to_datetime(df["timestamp"])

    # Filter to today's session, first 15 minutes (9:15-9:30 IST)
    today = df["timestamp"].dt.date.max()
    today_df = df[df["timestamp"].dt.date == today].copy()
    if today_df.empty:
        return {"available": False, "reason": "No candles for today"}

    today_df["minutes_from_open"] = (
        today_df["timestamp"].dt.hour * 60 + today_df["timestamp"].dt.minute - (9 * 60 + 15)
    )
    or_window = today_df[(today_df["minutes_from_open"] >= 0) & (today_df["minutes_from_open"] < 15)]

    if or_window.empty:
        return {"available": False, "reason": "Market hasn't opened or no candles in 9:15-9:30 yet",
                "minutes_into_session": int(today_df["minutes_from_open"].max())
                                        if not today_df.empty else -1}

    or_high = float(or_window["high"].max())
    or_low  = float(or_window["low"].min())
    or_range = or_high - or_low
    minutes_in = int(today_df["minutes_from_open"].max()) if not today_df.empty else 0
    or_complete = minutes_in >= 15

    # Current breakout status
    ltp = float(ltp or 0)
    if not or_complete:
        status = "FORMING"
        color = "#78909c"
        signal = f"Range forming ({minutes_in+1}/15 min)"
    elif ltp > or_high:
        status = "BROKEN UP"
        color = "#1b5e20"
        signal = f"Break above OR high (Rs. {or_high:,.0f})"
    elif ltp < or_low:
        status = "BROKEN DOWN"
        color = "#c62828"
        signal = f"Break below OR low (Rs. {or_low:,.0f})"
    else:
        status = "INSIDE RANGE"
        color = "#ef6c00"
        signal = f"Trading inside range - wait for break"

    # Position within range (0% = at low, 100% = at high)
    pos_pct = ((ltp - or_low) / or_range * 100) if or_range > 0 else 50

    return {
        "available": True,
        "or_high": round(or_high, 2),
        "or_low":  round(or_low, 2),
        "or_range": round(or_range, 2),
        "or_complete": or_complete,
        "minutes_in": minutes_in,
        "status": status,
        "color": color,
        "signal": signal,
        "pos_pct": round(max(0, min(100, pos_pct)), 0),
        "ltp": round(ltp, 2),
    }


def render_opening_range_card(orc: Dict[str, Any]):
    """Render the Opening Range tracker card."""
    if not orc.get("available"):
        st.markdown(
            f'<div style="background:#fafafa;border:1px solid #e0e4ec;border-radius:8px;'
            f'padding:0.6rem 0.9rem;margin-bottom:0.5rem">'
            f'<div style="font-size:0.7rem;color:#78909c;text-transform:uppercase">Opening Range (9:15-9:30)</div>'
            f'<div style="font-size:0.78rem;color:#546e7a;margin-top:3px">'
            f"Waiting: {_clean_text(orc.get('reason','Not available'))}"
            f'</div>'
            f'</div>',
            unsafe_allow_html=True,
        )
        return

    color = orc["color"]
    pos_marker = orc["pos_pct"]

    if orc["status"] == "BROKEN UP":
        action_hint = "Use ORB-up entry on retest."
    elif orc["status"] == "BROKEN DOWN":
        action_hint = "Use ORB-down entry on retest."
    else:
        action_hint = "Don't pre-empt the break."

    st.markdown(
        f'<div style="background:#ffffff;border:1px solid {color}55;border-left:4px solid {color};'
        f'border-radius:8px;padding:0.7rem 0.9rem;margin-bottom:0.5rem">'
        f'<div style="display:flex;justify-content:space-between;align-items:center">'
        f'<span style="font-size:0.7rem;color:#78909c;text-transform:uppercase">Opening Range (9:15-9:30)</span>'
        f'<span style="background:{color}22;color:{color};padding:1px 8px;border-radius:4px;'
        f"font-size:0.7rem;font-weight:700\">{orc['status']}</span>"
        f'</div>'
        f'<div style="display:flex;justify-content:space-between;font-size:0.85rem;font-family:monospace;margin-top:5px">'
        f"<span style=\"color:#c62828\">Low: Rs. {orc['or_low']:,.0f}</span>"
        f"<span style=\"color:#37474f\">Range: {orc['or_range']:.0f} pts</span>"
        f"<span style=\"color:#1b5e20\">High: Rs. {orc['or_high']:,.0f}</span>"
        f'</div>'
        f'<div style="height:8px;background:linear-gradient(to right,#ffebee 0%,#fff8e1 50%,#e8f5e9 100%);'
        f'border-radius:4px;margin-top:6px;position:relative">'
        f'<div style="position:absolute;top:-2px;left:{pos_marker}%;width:3px;height:12px;'
        f'background:#1565c0;transform:translateX(-50%)"></div>'
        f'</div>'
        f'<div style="font-size:0.72rem;color:#546e7a;margin-top:6px">'
        f"Note: {_clean_text(orc['signal'])}. {action_hint}"
        f'</div>'
        f'</div>',
        unsafe_allow_html=True,
    )


# Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
# 5. VWAP COMPUTATION
# Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬

def compute_vwap(candles_1m, ltp: float) -> Dict[str, Any]:
    """
    Compute approximate VWAP from 1-minute candles for today's session.
    Note: This is approximate Ã¢â‚¬â€ true VWAP needs full tick-level data.
    """
    import pandas as pd
    if candles_1m is None or (hasattr(candles_1m, "empty") and candles_1m.empty):
        return {"available": False, "reason": "No candle data"}

    df = candles_1m.copy()
    if "timestamp" not in df.columns:
        df = df.reset_index()
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    today = df["timestamp"].dt.date.max()
    today_df = df[df["timestamp"].dt.date == today].copy()

    if today_df.empty or "volume" not in today_df.columns:
        return {"available": False, "reason": "No today data or missing volume"}

    # Typical price = (H+L+C)/3
    today_df["typical"] = (today_df["high"] + today_df["low"] + today_df["close"]) / 3
    today_df["volume"] = pd.to_numeric(today_df["volume"], errors="coerce").fillna(0)

    total_vol = today_df["volume"].sum()
    if total_vol <= 0:
        # Fallback: equal-weight average if volume isn't reliable
        vwap = today_df["typical"].mean()
        method = "EQUAL-WEIGHT (volume unreliable)"
    else:
        vwap = (today_df["typical"] * today_df["volume"]).sum() / total_vol
        method = "VOLUME-WEIGHTED"

    ltp = float(ltp or 0)
    diff_pts = ltp - vwap
    diff_pct = (diff_pts / vwap * 100) if vwap else 0

    # Direction of last 5 candles (rough VWAP slope proxy: is price pulling VWAP up or down?)
    last5 = today_df.tail(5)
    if len(last5) >= 3:
        first_typ = last5["typical"].iloc[0]
        last_typ  = last5["typical"].iloc[-1]
        slope = "RISING" if last_typ > first_typ else "FALLING" if last_typ < first_typ else "FLAT"
    else:
        slope = "FORMING"

    if abs(diff_pct) < 0.05:
        position = "AT VWAP"
        color = "#78909c"
        signal = "Price at VWAP - undecided"
    elif diff_pct > 0:
        position = "ABOVE VWAP"
        color = "#1b5e20"
        signal = (f"Bullish bias - price holding above VWAP" +
                  (". Strong trend day setup" if slope == "RISING" else ""))
    else:
        position = "BELOW VWAP"
        color = "#c62828"
        signal = (f"Bearish bias - price holding below VWAP" +
                  (". Strong down-trend setup" if slope == "FALLING" else ""))

    return {
        "available": True,
        "vwap": round(vwap, 2),
        "ltp":  round(ltp, 2),
        "diff_pts": round(diff_pts, 2),
        "diff_pct": round(diff_pct, 3),
        "position": position,
        "color": color,
        "slope": slope,
        "signal": signal,
        "method": method,
    }


def render_vwap_card(vwap_data: Dict[str, Any]):
    """Render VWAP + price relationship card."""
    if not vwap_data.get("available"):
        st.markdown(
            f'<div style="background:#fafafa;border:1px solid #e0e4ec;border-radius:8px;'
            f'padding:0.6rem 0.9rem;margin-bottom:0.5rem">'
            f'<div style="font-size:0.7rem;color:#78909c;text-transform:uppercase">VWAP</div>'
            f'<div style="font-size:0.78rem;color:#546e7a;margin-top:3px">'
            f"Waiting: {_clean_text(vwap_data.get('reason','Not available'))}"
            f'</div>'
            f'</div>',
            unsafe_allow_html=True,
        )
        return

    color = vwap_data["color"]
    if vwap_data["slope"] == "RISING":
        slope_arrow = "UP"
    elif vwap_data["slope"] == "FALLING":
        slope_arrow = "DOWN"
    else:
        slope_arrow = "FLAT"

    st.markdown(
        f'<div style="background:#ffffff;border:1px solid {color}55;border-left:4px solid {color};'
        f'border-radius:8px;padding:0.7rem 0.9rem;margin-bottom:0.5rem">'
        f'<div style="display:flex;justify-content:space-between;align-items:center">'
        f"<span style=\"font-size:0.7rem;color:#78909c;text-transform:uppercase\">VWAP {slope_arrow} {vwap_data['slope']}</span>"
        f'<span style="background:{color}22;color:{color};padding:1px 8px;border-radius:4px;'
        f"font-size:0.7rem;font-weight:700\">{vwap_data['position']}</span>"
        f'</div>'
        f'<div style="display:flex;justify-content:space-between;font-size:0.85rem;font-family:monospace;margin-top:5px">'
        f"<span style=\"color:#37474f\">VWAP: Rs. {vwap_data['vwap']:,.2f}</span>"
        f'<span style="color:{color};font-weight:700">'
        f"{vwap_data['diff_pts']:+.1f} ({vwap_data['diff_pct']:+.3f}%)"
        f'</span>'
        f"<span style=\"color:#37474f\">LTP: Rs. {vwap_data['ltp']:,.2f}</span>"
        f'</div>'
        f"<div style=\"font-size:0.72rem;color:#546e7a;margin-top:5px\">Note: {_clean_text(vwap_data['signal'])}</div>"
        f'<div style="font-size:0.62rem;color:#90a4ae;margin-top:3px;font-style:italic">'
        f"{_clean_text(vwap_data['method'])} - approximate (built from 1m candles, not tick-level)"
        f'</div>'
        f'</div>',
        unsafe_allow_html=True,
    )


# Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
# 6. DECISION CHECKLIST Ã¢â‚¬â€ 5-CRITERIA GO/NO-GO
# Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬

def compute_decision_checklist(*, vol_regime, gap, opening_range, vwap_data,
                                sentiment, support, resistance, spot,
                                pcr, market_open: bool, minutes_into_session: int) -> Dict[str, Any]:
    """
    Weighted entry-quality model.
    Produces a cleaner "best available entry" score instead of treating
    every imperfect condition as a hard stop.
    """
    checks = []
    quality_score = 0.0
    bias_votes = 0
    score = float(sentiment.get("score", 0) or 0) if sentiment else 0.0
    components = sentiment.get("components", {}) or {} if sentiment else {}
    score_sign = 1 if score > 0 else -1 if score < 0 else 0
    pcr = float(pcr or 0)
    pcr_bias = 1 if pcr >= 1.05 else -1 if pcr > 0 and pcr <= 0.95 else 0
    gap_pct = abs(float(gap.get("size_pct", 0) or 0)) if gap else 0.0

    def add_check(name: str, level: str, reason: str, points: float, bias: int = 0):
        nonlocal quality_score, bias_votes
        quality_score += points
        bias_votes += bias
        checks.append((name, level != "fail", reason, level))

    regime = str(vol_regime.get("regime", "UNKNOWN"))
    vix = float(vol_regime.get("vix", 0) or 0)
    if not market_open:
        add_check("Regime", "fail", "Market closed", 0)
    elif regime == "HIGH VOL":
        if vix and vix <= 22:
            add_check("Regime", "warn", f"VIX {vix:.2f} high but tradeable with reduced size", 10)
        else:
            add_check("Regime", "fail", "Volatility regime too unstable for a fresh entry", 0)
    elif regime == "ELEVATED":
        add_check("Regime", "warn", f"VIX {vix:.2f} elevated - selective entries, smaller size", 14)
    elif regime == "UNKNOWN":
        add_check("Regime", "warn", "VIX unavailable - continue with normal caution", 12)
    else:
        add_check("Regime", "ok", f"VIX {vix:.2f} supportive for directional entries", 18)

    spot = float(spot or 0)
    sup = float(support or 0)
    res = float(resistance or 0)
    if sup > 0 and res > 0 and spot > 0 and res > sup:
        rng = res - sup
        pos_pct = (spot - sup) / rng * 100 if rng else 50
        dist_sup = abs(spot - sup)
        dist_res = abs(res - spot)
        if rng <= max(40.0, spot * 0.0025):
            add_check("Levels", "warn", f"Support/resistance compressed into {rng:.0f} pts - scalp only", 10)
        elif pos_pct <= 30:
            add_check("Levels", "ok", f"Price in lower {pos_pct:.0f}% of range - support-led CE zone", 18, bias=1)
        elif pos_pct >= 70:
            add_check("Levels", "ok", f"Price in upper {pos_pct:.0f}% of range - resistance-led PE zone", 18, bias=-1)
        elif 35 <= pos_pct <= 65:
            edge = "support" if dist_sup < dist_res else "resistance"
            bias = 1 if dist_sup < dist_res else -1
            add_check("Levels", "warn", f"Mid-range at {pos_pct:.0f}% - wait for trigger near {edge}", 11, bias=bias)
        else:
            bias = 1 if dist_sup < dist_res else -1
            add_check("Levels", "warn", f"Leaning toward {'support' if bias > 0 else 'resistance'} at {pos_pct:.0f}% of range", 13, bias=bias)
    else:
        add_check("Levels", "warn", "Support/resistance incomplete - use price structure and VWAP more heavily", 8)

    aligned_components = sum(
        1 for v in components.values()
        if abs(float(v or 0)) >= 4 and ((score_sign > 0 and float(v) > 0) or (score_sign < 0 and float(v) < 0))
    )
    if abs(score) >= 25 and aligned_components >= 3:
        add_check(
            "Confirmation",
            "ok",
            f"{'Bullish' if score_sign > 0 else 'Bearish'} score {score:+.0f} with {aligned_components} aligned components",
            24,
            bias=score_sign,
        )
    elif abs(score) >= 12 and (aligned_components >= 2 or (pcr_bias != 0 and pcr_bias == score_sign)):
        reason = f"Score {score:+.0f} confirmed by {aligned_components} components"
        if pcr_bias != 0 and pcr_bias == score_sign:
            reason += f" and PCR {pcr:.2f}"
        add_check("Confirmation", "ok", reason, 20, bias=score_sign)
    elif abs(score) >= 8 or aligned_components >= 1 or pcr_bias != 0:
        inferred_bias = score_sign if score_sign != 0 else pcr_bias
        add_check("Confirmation", "warn", f"Early directional edge only - score {score:+.0f}, PCR {pcr:.2f}", 12, bias=inferred_bias)
    else:
        add_check("Confirmation", "fail", f"No reliable directional edge yet (score {score:+.0f})", 0)

    if not market_open:
        add_check("Time", "fail", "Market closed", 0)
    elif minutes_into_session < 0:
        add_check("Time", "fail", "Pre-open", 0)
    elif minutes_into_session < 8:
        add_check("Time", "fail", f"Only {minutes_into_session}m into session - opening noise still dominant", 0)
    elif minutes_into_session < 15:
        add_check("Time", "warn", f"{minutes_into_session}m into session - opening range still stabilizing", 8)
    elif minutes_into_session <= 180:
        add_check("Time", "ok", f"{minutes_into_session}m into session - strongest intraday entry window", 20)
    elif minutes_into_session <= 300:
        add_check("Time", "ok", f"{minutes_into_session}m into session - normal trend continuation window", 17)
    elif minutes_into_session <= 345:
        add_check("Time", "warn", f"{minutes_into_session}m into session - late trade, tighten targets", 10)
    else:
        add_check("Time", "fail", "Final 15 minutes - new entries lose edge", 0)

    vwap_available = bool(vwap_data and vwap_data.get("available"))
    vwap_pos = str(vwap_data.get("position", "")) if vwap_available else ""
    vwap_slope = str(vwap_data.get("slope", "")) if vwap_available else ""
    or_available = bool(opening_range and opening_range.get("available"))
    or_status = str(opening_range.get("status", "")) if or_available else ""
    if or_available and or_status == "BROKEN UP":
        if score_sign >= 0 or vwap_pos == "ABOVE VWAP":
            add_check("Structure", "ok", "Opening range breakout up confirmed by directional bias", 20, bias=1)
        else:
            add_check("Structure", "warn", "OR breakout up is live but broader bias still mixed", 13, bias=1)
    elif or_available and or_status == "BROKEN DOWN":
        if score_sign <= 0 or vwap_pos == "BELOW VWAP":
            add_check("Structure", "ok", "Opening range breakdown confirmed by directional bias", 20, bias=-1)
        else:
            add_check("Structure", "warn", "OR breakdown is live but broader bias still mixed", 13, bias=-1)
    elif or_available and or_status == "INSIDE RANGE":
        pos_pct = float(opening_range.get("pos_pct", 50) or 50)
        near_edge = pos_pct <= 20 or pos_pct >= 80
        if near_edge and vwap_available:
            edge_bias = 1 if pos_pct <= 20 else -1
            add_check("Structure", "warn", f"Inside OR but coiling near the {'low' if edge_bias > 0 else 'high'} edge", 12, bias=edge_bias)
        else:
            add_check("Structure", "warn", "Inside opening range - wait for break or rejection trigger", 8)
    elif or_available and or_status == "FORMING":
        add_check("Structure", "warn", "Opening range still forming", 6)
    elif vwap_available:
        if vwap_pos == "ABOVE VWAP" and vwap_slope == "RISING":
            add_check("Structure", "ok", "Price above rising VWAP - trend structure supportive", 17, bias=1)
        elif vwap_pos == "BELOW VWAP" and vwap_slope == "FALLING":
            add_check("Structure", "ok", "Price below falling VWAP - downside structure supportive", 17, bias=-1)
        elif vwap_pos in ("ABOVE VWAP", "BELOW VWAP"):
            add_check("Structure", "warn", f"{vwap_pos} but slope is {vwap_slope.lower()} - structure is usable, not ideal", 11, bias=1 if vwap_pos == "ABOVE VWAP" else -1)
        else:
            add_check("Structure", "warn", "Price at VWAP - market still deciding direction", 8)
    else:
        add_check("Structure", "warn", "No OR/VWAP structure yet - rely on levels and chain confirmation", 7)

    if gap_pct >= 0.8 and or_status in ("", "FORMING", "INSIDE RANGE"):
        quality_score -= 4
    elif 0 < gap_pct <= 0.25:
        quality_score += 2

    n_ok = sum(1 for _, _, _, lvl in checks if lvl == "ok")
    n_warn = sum(1 for _, _, _, lvl in checks if lvl == "warn")
    n_fail = sum(1 for _, _, _, lvl in checks if lvl == "fail")

    quality_score = max(0, min(100, int(round(quality_score))))
    if bias_votes >= 2:
        preferred_setup = "BUY CALL BIAS"
    elif bias_votes <= -2:
        preferred_setup = "BUY PUT BIAS"
    else:
        preferred_setup = "NEUTRAL / WAIT FOR TRIGGER"

    if quality_score >= 78 and n_fail == 0:
        verdict = "GO"
        verdict_color = "#1b5e20"
        verdict_msg = "High-quality alignment - standard execution is justified"
    elif quality_score >= 62 and n_fail <= 1:
        verdict = "CAUTIOUS GO"
        verdict_color = "#ef6c00"
        verdict_msg = "Good but not pristine - reduce size and demand clean trigger"
    elif quality_score >= 48:
        verdict = "WATCHLIST"
        verdict_color = "#ef6c00"
        verdict_msg = "Edge is building - keep monitoring for one more confirmation"
    else:
        verdict = "NO TRADE"
        verdict_color = "#c62828"
        verdict_msg = "Setup quality is still too weak - preserve capital and wait"

    return {
        "checks": checks,
        "n_ok": n_ok, "n_warn": n_warn, "n_fail": n_fail,
        "verdict": verdict, "verdict_color": verdict_color, "verdict_msg": verdict_msg,
        "quality_score": quality_score,
        "preferred_setup": preferred_setup,
    }

def render_decision_checklist(checklist: Dict[str, Any]):
    """Render the 5-criteria decision card."""
    rows_html_parts = []
    for name, ok, reason, level in checklist["checks"]:
        if level == "ok":
            icon = "OK"
            icon_color = "#1b5e20"
        elif level == "warn":
            icon = "!"
            icon_color = "#ef6c00"
        else:
            icon = "X"
            icon_color = "#c62828"
        rows_html_parts.append(
            f'<div style="display:flex;align-items:center;gap:8px;padding:5px 0;border-bottom:1px dotted #eceff1">'
            f'<span style="background:{icon_color};color:white;width:18px;height:18px;'
            f'border-radius:50%;display:inline-flex;align-items:center;justify-content:center;'
            f'font-size:0.72rem;font-weight:700;flex-shrink:0">{icon}</span>'
            f'<span style="font-size:0.75rem;color:#37474f;font-weight:600;width:110px;flex-shrink:0">{name}</span>'
            f'<span style="font-size:0.72rem;color:#546e7a">{_clean_text(reason)}</span>'
            f'</div>'
        )
    rows_html = "".join(rows_html_parts)

    vc = checklist["verdict_color"]
    st.markdown(
        f'<div style="background:#ffffff;border:2px solid {vc};border-radius:10px;'
        f'padding:0.9rem 1rem;margin-bottom:0.7rem;box-shadow:0 2px 8px rgba(20,30,60,0.04)">'
        f'<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:0.5rem">'
        f'<span style="font-size:0.75rem;color:#78909c;text-transform:uppercase;letter-spacing:0.5px;font-weight:700">'
        f'Entry Decision Checklist</span>'
        f'<span style="background:{vc};color:white;padding:4px 14px;border-radius:6px;'
        f"font-size:0.85rem;font-weight:700;letter-spacing:0.5px\">{checklist['verdict']}</span>"
        f'</div>'
        f'<div style="font-size:0.75rem;color:{vc};margin-bottom:6px;font-weight:600">'
        f"{_clean_text(checklist['verdict_msg'])}"
        f'</div>'
        f'<div style="display:flex;justify-content:space-between;gap:10px;flex-wrap:wrap;'
        f'margin-bottom:8px;font-size:0.72rem;color:#546e7a">'
        f"<span><strong>Setup Score:</strong> {checklist.get('quality_score', 0)}/100</span>"
        f"<span><strong>Bias:</strong> {checklist.get('preferred_setup', 'N/A')}</span>"
        f'</div>'
        f'{rows_html}'
        f'<div style="display:flex;justify-content:space-around;margin-top:8px;padding-top:6px;border-top:1px solid #eceff1">'
        f"<span style=\"font-size:0.7rem;color:#1b5e20;font-weight:700\">OK {checklist['n_ok']} OK</span>"
        f"<span style=\"font-size:0.7rem;color:#ef6c00;font-weight:700\">! {checklist['n_warn']} WARN</span>"
        f"<span style=\"font-size:0.7rem;color:#c62828;font-weight:700\">X {checklist['n_fail']} FAIL</span>"
        f'</div>'
        f'</div>',
        unsafe_allow_html=True,
    )




# ═════════════════════════════════════════════════════════════════════════════
# PCR REVERSAL DETECTION — Rate of change + divergence signals
# ═════════════════════════════════════════════════════════════════════════════

def compute_pcr_reversal_signal(pcr_history: list) -> Dict[str, Any]:
    """
    Analyse rolling PCR history to detect potential trend reversals BEFORE
    they happen. Three signals:

    1. PCR Rate of Change — is PCR accelerating or decelerating?
       A rising trend with PCR slowing down = exhaustion warning.

    2. OI PCR vs Volume PCR divergence — Volume PCR leads OI PCR by 15-30 min.
       If they move in opposite directions, a reversal is building.

    3. Sentiment-Price divergence — price making new high/low while sentiment
       score is flat or falling = classic momentum divergence.

    Returns a dict with reversal_risk (0-100), signal, and explanation.
    """
    result = {
        "reversal_risk":   0,
        "signal":          "INSUFFICIENT_DATA",
        "direction":       "NEUTRAL",
        "color":           "#78909c",
        "explanation":     "Need at least 5 data points to detect reversals.",
        "pcr_trend":       "UNKNOWN",
        "divergence":      False,
        "warnings":        [],
    }

    if not pcr_history or len(pcr_history) < 5:
        return result

    # Work with last 20 points max
    pts = pcr_history[-20:]
    n   = len(pts)

    def safe_float(d, k, fallback=0.0):
        try: return float(d.get(k) or fallback)
        except Exception: return fallback

    pcr_oi_vals  = [safe_float(p, "pcr_oi")  for p in pts]
    pcr_vol_vals = [safe_float(p, "pcr_vol") for p in pts]
    sent_vals    = [safe_float(p, "sentiment") for p in pts]
    ltp_vals     = [safe_float(p, "ltp") for p in pts]

    warnings = []
    risk = 0

    # ── Signal 1: PCR OI Rate of Change ──────────────────────────────────────
    # Compare recent 3 points vs prior 3 points
    if n >= 6:
        recent_pcr  = sum(pcr_oi_vals[-3:]) / 3
        prior_pcr   = sum(pcr_oi_vals[-6:-3]) / 3
        pcr_roc = recent_pcr - prior_pcr

        if pcr_roc > 0.05:
            pcr_trend = "RISING_FAST"
        elif pcr_roc > 0.01:
            pcr_trend = "RISING"
        elif pcr_roc < -0.05:
            pcr_trend = "FALLING_FAST"
        elif pcr_roc < -0.01:
            pcr_trend = "FALLING"
        else:
            pcr_trend = "FLAT"

        result["pcr_trend"] = pcr_trend
        result["pcr_roc"]   = round(pcr_roc, 4)

        # Rising PCR that suddenly flattens = bullish exhaustion
        if pcr_oi_vals[-4] > pcr_oi_vals[-5] and pcr_trend == "FLAT":
            risk += 20
            warnings.append("PCR stopped rising — bullish momentum exhausting")
        # Falling PCR that suddenly flattens = bearish exhaustion
        if pcr_oi_vals[-4] < pcr_oi_vals[-5] and pcr_trend == "FLAT":
            risk += 20
            warnings.append("PCR stopped falling — bearish momentum exhausting")
        # Fast reversal in PCR direction
        if pcr_trend == "FALLING_FAST" and all(v > pcr_oi_vals[-4] for v in pcr_oi_vals[-7:-4]):
            risk += 30
            warnings.append("PCR sharp drop after rising trend — possible bearish reversal")
        if pcr_trend == "RISING_FAST" and all(v < pcr_oi_vals[-4] for v in pcr_oi_vals[-7:-4]):
            risk += 30
            warnings.append("PCR sharp rise after falling trend — possible bullish reversal")

    # ── Signal 2: OI PCR vs Volume PCR divergence ────────────────────────────
    if n >= 4 and all(v > 0 for v in pcr_vol_vals[-4:]):
        oi_direction  = pcr_oi_vals[-1]  - pcr_oi_vals[-4]
        vol_direction = pcr_vol_vals[-1] - pcr_vol_vals[-4]

        # Divergence: OI and Volume PCR moving in opposite directions
        if oi_direction > 0.02 and vol_direction < -0.02:
            risk += 25
            result["divergence"] = True
            warnings.append(
                f"OI PCR rising (+{oi_direction:.3f}) but Volume PCR falling "
                f"({vol_direction:.3f}) — smart money selling the bullish consensus"
            )
        elif oi_direction < -0.02 and vol_direction > 0.02:
            risk += 25
            result["divergence"] = True
            warnings.append(
                f"OI PCR falling ({oi_direction:.3f}) but Volume PCR rising "
                f"(+{vol_direction:.3f}) — fresh put buying against bearish consensus"
            )

    # ── Signal 3: Sentiment-Price divergence ─────────────────────────────────
    if n >= 6:
        ltp_change  = ltp_vals[-1]  - ltp_vals[-4]
        sent_change = sent_vals[-1] - sent_vals[-4]

        # Price rising but sentiment falling = bearish divergence
        if ltp_change > 5 and sent_change < -5:
            risk += 20
            warnings.append(
                f"Price +{ltp_change:.0f}pts but sentiment {sent_change:+.0f} — "
                "momentum divergence, watch for reversal"
            )
        # Price falling but sentiment rising = bullish divergence
        elif ltp_change < -5 and sent_change > 5:
            risk += 20
            warnings.append(
                f"Price {ltp_change:.0f}pts but sentiment {sent_change:+.0f} — "
                "potential bounce forming"
            )

    # ── Aggregate risk and direction ─────────────────────────────────────────
    risk = min(100, risk)
    result["reversal_risk"] = risk
    result["warnings"]      = warnings

    # Determine direction of potential reversal
    last_sent = sent_vals[-1] if sent_vals else 0
    if risk >= 40:
        if last_sent > 10:
            result["direction"] = "BEARISH_REVERSAL"
            result["color"]     = "#c62828"
            result["signal"]    = "REVERSAL_WARNING"
            result["explanation"] = (
                f"Bullish trend showing exhaustion signals ({risk}/100 risk). "
                + " | ".join(warnings[:2])
            )
        elif last_sent < -10:
            result["direction"] = "BULLISH_REVERSAL"
            result["color"]     = "#1b5e20"
            result["signal"]    = "REVERSAL_WARNING"
            result["explanation"] = (
                f"Bearish trend showing exhaustion signals ({risk}/100 risk). "
                + " | ".join(warnings[:2])
            )
        else:
            result["direction"] = "NEUTRAL"
            result["signal"]    = "TREND_WEAKENING"
            result["explanation"] = (
                f"Trend momentum weakening ({risk}/100 risk). "
                + (warnings[0] if warnings else "Monitor closely.")
            )
    elif risk >= 20:
        result["signal"]    = "WATCH"
        result["color"]     = "#ef6c00"
        result["explanation"] = (
            f"Early warning signals present ({risk}/100). "
            + (warnings[0] if warnings else "")
        )
    else:
        result["signal"]    = "TREND_INTACT"
        result["color"]     = "#1b5e20"
        result["explanation"] = "No reversal signals detected. Trend continuation likely."

    return result


def render_pcr_reversal_signal(signal: Dict[str, Any], pcr_history: list):
    """Render the PCR reversal detection card."""
    risk   = signal.get("reversal_risk", 0)
    sig    = signal.get("signal", "INSUFFICIENT_DATA")
    color  = signal.get("color", "#78909c")
    expl   = signal.get("explanation", "")
    warns  = signal.get("warnings", [])
    trend  = signal.get("pcr_trend", "")
    diverg = signal.get("divergence", False)
    n_pts  = len(pcr_history) if pcr_history else 0

    # Risk bar
    bar_color = "#1b5e20" if risk < 25 else "#ef6c00" if risk < 50 else "#c62828"
    bar_pct   = risk

    # PCR trend last 5 values for mini sparkline text
    if n_pts >= 5:
        last5_oi  = [round(float(p.get("pcr_oi",0) or 0), 3) for p in pcr_history[-5:]]
        last5_vol = [round(float(p.get("pcr_vol",0) or 0), 3) for p in pcr_history[-5:]]
        spark_oi  = " → ".join([f"{v:.3f}" for v in last5_oi])
        spark_vol = " → ".join([f"{v:.3f}" for v in last5_vol])
    else:
        spark_oi = spark_vol = f"Need {5 - n_pts} more snapshots"

    warn_rows = ""
    for w in warns[:3]:
        warn_rows += (
            f'<div style="display:flex;align-items:flex-start;gap:6px;margin-top:4px">'
            f'<span style="color:{color};font-size:0.8rem;flex-shrink:0">⚡</span>'
            f'<span style="font-size:0.73rem;color:#37474f">{w}</span>'
            f'</div>'
        )

    diverg_badge = (
        '<span style="background:#e53935;color:white;padding:1px 7px;'
        'border-radius:4px;font-size:0.65rem;font-weight:700;margin-left:6px">'
        'OI/VOL DIVERGENCE</span>'
    ) if diverg else ""

    st.markdown(
        f'<div style="background:#ffffff;border:1px solid {color}55;'
        f'border-left:4px solid {color};border-radius:8px;'
        f'padding:0.8rem 1rem;margin-bottom:0.5rem">'
        f'<div style="display:flex;justify-content:space-between;align-items:center">'
        f'<span style="font-size:0.7rem;color:#78909c;text-transform:uppercase;font-weight:700">'
        f'Reversal Risk Detector{diverg_badge}</span>'
        f'<span style="background:{bar_color};color:white;padding:2px 10px;'
        f'border-radius:4px;font-size:0.75rem;font-weight:700">'
        f'{sig.replace("_"," ")}</span>'
        f'</div>'
        f'<div style="margin:6px 0 4px">'
        f'<div style="display:flex;justify-content:space-between;font-size:0.65rem;color:#78909c">'
        f'<span>Reversal Risk</span><span>{risk}/100</span></div>'
        f'<div style="height:8px;background:#eceff1;border-radius:4px;overflow:hidden;margin-top:2px">'
        f'<div style="height:100%;width:{bar_pct}%;background:{bar_color};'
        f'border-radius:4px;transition:width 0.5s"></div>'
        f'</div>'
        f'</div>'
        f'<div style="font-size:0.75rem;color:#37474f;margin-top:6px">{expl}</div>'
        f'{warn_rows}'
        f'<div style="margin-top:8px;padding-top:6px;border-top:1px dotted #eceff1">'
        f'<div style="font-size:0.65rem;color:#90a4ae">OI PCR: {spark_oi}</div>'
        f'<div style="font-size:0.65rem;color:#90a4ae">Vol PCR: {spark_vol}</div>'
        f'<div style="font-size:0.62rem;color:#b0bec5;margin-top:2px">'
        f'Based on {n_pts} snapshots | PCR trend: {trend}</div>'
        f'</div>'
        f'</div>',
        unsafe_allow_html=True,
    )
