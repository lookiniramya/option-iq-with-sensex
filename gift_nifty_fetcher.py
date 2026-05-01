"""
gift_nifty_fetcher.py — Standalone GIFT Nifty fetcher.

This module contains the EXACT logic that was just verified to work on your
machine (the standalone test that printed "FOUND price: 24134.0").

USAGE:
  Save this file in the same folder as market_intelligence.py, then in
  market_intelligence.py find the OLD `fetch_gift_nifty` function and
  replace its body with a single line that calls this module:

      def fetch_gift_nifty(force: bool = False):
          from gift_nifty_fetcher import fetch_gift_nifty as _f
          return _f(force=force)
"""
import requests
import re
import time
import datetime
from typing import Dict, Any

_CACHE: Dict[str, Any] = {}

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/json,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


def _sf(v, d=0.0):
    """Safe float."""
    try:
        if isinstance(v, str):
            v = re.sub(r"[₹,\s]", "", v).replace("−", "-")
        return float(v or d)
    except Exception:
        return d


def fetch_gift_nifty(force: bool = False) -> Dict[str, Any]:
    """
    Fetch live GIFT Nifty from Groww (primary) → Moneycontrol → Yahoo (proxy).
    Returns dict with: price, change, chg_pct, open, prev_close, source,
    is_real_gift, signal, error.
    """
    key = "gift_nifty"
    cached = _CACHE.get(key)
    if not force and cached:
        age = (datetime.datetime.now() - cached["ts"]).total_seconds()
        if age < 120:
            return cached["value"]

    result = {
        "price": 0.0, "change": 0.0, "chg_pct": 0.0,
        "open": 0.0, "high": 0.0, "low": 0.0, "prev_close": 0.0,
        "source": "Unknown", "signal": "❓", "error": None,
        "is_real_gift": False,
    }
    errors = []

    # ── Source 1: Groww (server-rendered HTML) ───────────────────────────
    try:
        r = requests.get(
            "https://groww.in/indices/global-indices/sgx-nifty",
            headers=_HEADERS, timeout=10,
        )
        if r.status_code == 200:
            html = r.text
            price = chg = chgp = open_p = prev_c = 0.0

            # Iterate every "GIFT NIFTY" occurrence; pick first that has a
            # price-shaped number in plausible range within next 1500 chars.
            for m_pos in re.finditer(r'GIFT\s*NIFTY', html, re.I):
                window = html[m_pos.end(): m_pos.end() + 1500]
                pm = re.search(r'([2-3]\d[,.]\d{3}\.\d+)', window)
                if pm:
                    candidate = _sf(pm.group(1).replace(",", ""))
                    if 15000 <= candidate <= 40000:
                        price = candidate
                        tail = window[pm.end(): pm.end() + 500]
                        # change number
                        cm = re.search(r'(-?\d+\.\d+)', tail)
                        if cm:
                            chg = _sf(cm.group(1))
                        # percent inside parens
                        pm2 = re.search(r'\(([+\-]?\d+\.\d+)\s*%\)', tail)
                        if pm2:
                            chgp = _sf(pm2.group(1))
                            if chg < 0 and chgp > 0:
                                chgp = -chgp
                        break

            # Open / Prev. Close from the table
            om = re.search(
                r'Open[\s\S]{1,400}?Prev\.?\s*Close'
                r'[\s\S]{1,400}?([2-3]\d[,.]\d{3}\.\d+)'
                r'[\s\S]{1,200}?([2-3]\d[,.]\d{3}\.\d+)',
                html, re.I,
            )
            if om:
                open_p = _sf(om.group(1).replace(",", ""))
                prev_c = _sf(om.group(2).replace(",", ""))

            if price > 10000:
                if not chg and prev_c:
                    chg = price - prev_c
                if not chgp and prev_c:
                    chgp = (chg / prev_c * 100) if prev_c else 0
                if not prev_c and chg:
                    prev_c = price - chg
                result.update({
                    "price":      round(price, 2),
                    "change":     round(chg, 2),
                    "chg_pct":    round(chgp, 2),
                    "prev_close": round(prev_c, 2),
                    "open":       round(open_p, 2),
                    "source":     "Groww (live GIFT Nifty)",
                    "is_real_gift": True, "error": None,
                })
            else:
                errors.append("Groww: 200 OK but no price extracted")
        else:
            errors.append(f"Groww: HTTP {r.status_code}")
    except Exception as e:
        errors.append(f"Groww: {str(e)[:80]}")

    # ── Source 2: Moneycontrol techCharts (fallback) ─────────────────────
    if result["price"] == 0:
        for resolution in ("1", "5", "15", "60", "D"):
            try:
                now_ts = int(time.time())
                r = requests.get(
                    "https://priceapi.moneycontrol.com/techCharts/indianMarket/index/history",
                    params={
                        "symbol": "in;GIFT", "resolution": resolution,
                        "from": now_ts - 86400 * 5, "to": now_ts,
                        "countback": "100",
                    },
                    headers={**_HEADERS,
                             "Referer": "https://www.moneycontrol.com/"},
                    timeout=8,
                )
                if r.status_code == 200:
                    j = r.json()
                    if j.get("s") == "ok" and j.get("c") and len(j["c"]) >= 2:
                        closes = j["c"]
                        price = float(closes[-1])
                        prev = float(closes[-2])
                        if price > 10000:
                            chg = price - prev
                            chgp = (chg / prev * 100) if prev else 0
                            result.update({
                                "price": round(price, 2),
                                "change": round(chg, 2),
                                "chg_pct": round(chgp, 2),
                                "prev_close": round(prev, 2),
                                "source": f"Moneycontrol GIFT ({resolution}m)",
                                "is_real_gift": True, "error": None,
                            })
                            break
            except Exception as e:
                errors.append(f"MC({resolution}): {str(e)[:40]}")

    # ── Source 3: Yahoo ^NSEI Nifty 50 SPOT — PROXY (last resort) ────────
    if result["price"] == 0:
        try:
            r = requests.get(
                "https://query1.finance.yahoo.com/v8/finance/chart/^NSEI",
                params={"interval": "1m", "range": "1d"},
                headers={"User-Agent": "Mozilla/5.0"}, timeout=6,
            )
            if r.status_code == 200:
                meta = r.json().get("chart", {}).get("result", [{}])[0].get("meta", {})
                price = _sf(meta.get("regularMarketPrice"))
                prev = _sf(meta.get("previousClose")
                           or meta.get("chartPreviousClose"))
                if price > 10000:
                    chg = price - prev if prev else 0
                    chgp = (chg / prev * 100) if prev else 0
                    result.update({
                        "price": round(price, 2),
                        "change": round(chg, 2),
                        "chg_pct": round(chgp, 2),
                        "prev_close": round(prev, 2),
                        "open": round(_sf(meta.get("regularMarketOpen")), 2),
                        "high": round(_sf(meta.get("regularMarketDayHigh")), 2),
                        "low":  round(_sf(meta.get("regularMarketDayLow")), 2),
                        "source": "⚠️ Yahoo Nifty 50 SPOT (proxy — NOT real GIFT)",
                        "is_real_gift": False, "error": None,
                    })
        except Exception as e:
            errors.append(f"Yahoo: {str(e)[:40]}")

    if result["price"] == 0 and errors:
        result["error"] = " | ".join(errors[:5])

    chgp = result["chg_pct"]
    if result["price"] > 0:
        result["signal"] = (
            f"🟢 GAP UP +{chgp:.2f}%"   if chgp >  0.3 else
            f"🔴 GAP DOWN {chgp:.2f}%"  if chgp < -0.3 else
            f"⚖️ FLAT {chgp:+.2f}%"
        )

    _CACHE[key] = {"ts": datetime.datetime.now(), "value": result}
    return result


# ── Self-test: run `python gift_nifty_fetcher.py` to verify ──────────────
if __name__ == "__main__":
    print("Testing gift_nifty_fetcher...")
    r = fetch_gift_nifty(force=True)
    print(f"SOURCE: {r['source']}")
    print(f"PRICE:  {r['price']}")
    print(f"CHANGE: {r['change']} ({r['chg_pct']:+.2f}%)")
    print(f"OPEN:   {r['open']}")
    print(f"PREV:   {r['prev_close']}")
    print(f"ERROR:  {r['error']}")
