"""
bse_sensex_chain.py — Fetch SENSEX option chain directly from BSE India's
public API. Used as a fallback when Paytm Money's API doesn't expose BSE F&O.

BSE publishes option chain data via their public API, no auth required.
Data is same-quality as Paytm (it comes from the exchange itself).
"""
import requests
import re
from datetime import datetime
from typing import Dict, Any, List, Tuple, Optional

BSE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://www.bseindia.com/",
    "Origin": "https://www.bseindia.com",
}


def _safe_float(v, default=0.0) -> float:
    try:
        return float(v or default)
    except (TypeError, ValueError):
        return default


def fetch_sensex_expiry_dates() -> Tuple[List[str], Optional[str]]:
    """
    Fetch SENSEX option expiry dates from BSE's public API.
    Returns (dates_list_DD-MM-YYYY, error_string_or_None)
    """
    urls = [
        "https://api.bseindia.com/BseIndiaAPI/api/ddlExpiry_iv/w?Type=IO&Underlying=SENSEX&Category=IO",
        "https://api.bseindia.com/BseIndiaAPI/api/GetOptionChainMaster/w?Underlying=SENSEX",
        "https://www.bseindia.com/indices/IndexOptExpirDate.html?index=SENSEX&flag=1",
    ]
    errors = []
    for url in urls:
        try:
            r = requests.get(url, headers=BSE_HEADERS, timeout=10)
            if r.status_code == 200:
                j = r.json() if "json" in r.headers.get("content-type","") else {}
                # Shape 1: list of {"ExpiryDate": "02 May 2024"} dicts
                if isinstance(j, list) and j and "ExpiryDate" in j[0]:
                    dates = []
                    for item in j:
                        raw = str(item.get("ExpiryDate","")).strip()
                        try:
                            dt = datetime.strptime(raw, "%d %b %Y")
                            dates.append(dt.strftime("%d-%m-%Y"))
                        except ValueError:
                            try:
                                dt = datetime.strptime(raw, "%Y-%m-%d")
                                dates.append(dt.strftime("%d-%m-%Y"))
                            except ValueError:
                                pass
                    if dates:
                        return sorted(dates,
                            key=lambda d: datetime.strptime(d, "%d-%m-%Y")), None
                # Shape 2: {"Table": [...]} with Expiry field
                table = j.get("Table") or j.get("data") or []
                if table:
                    dates = []
                    for item in table:
                        raw = str(item.get("Expiry","") or item.get("ExpiryDate","")).strip()
                        if not raw:
                            continue
                        for fmt in ("%d %b %Y", "%Y-%m-%d", "%d/%m/%Y",
                                    "%d-%b-%Y", "%d-%m-%Y"):
                            try:
                                dt = datetime.strptime(raw, fmt)
                                dates.append(dt.strftime("%d-%m-%Y"))
                                break
                            except ValueError:
                                continue
                    if dates:
                        return sorted(set(dates),
                            key=lambda d: datetime.strptime(d, "%d-%m-%Y")), None
        except Exception as e:
            errors.append(f"{url[:50]}: {str(e)[:40]}")

    # Fallback: scrape BSE option chain page for expiry list
    try:
        r = requests.get(
            "https://www.bseindia.com/derivatives/MarketWatch/OptionChain.aspx",
            headers=BSE_HEADERS, timeout=10,
        )
        if r.status_code == 200:
            # Regex for DD Mon YYYY or YYYY-MM-DD date patterns
            dates_raw = re.findall(
                r'\b(\d{1,2}[\s-][A-Za-z]{3}[\s-]\d{4}|\d{4}-\d{2}-\d{2})\b',
                r.text
            )
            dates = []
            for raw in set(dates_raw):
                for fmt in ("%d %b %Y", "%d-%b-%Y", "%Y-%m-%d"):
                    try:
                        dt = datetime.strptime(raw.strip(), fmt)
                        if dt > datetime.now():
                            dates.append(dt.strftime("%d-%m-%Y"))
                        break
                    except ValueError:
                        continue
            if dates:
                return sorted(set(dates),
                    key=lambda d: datetime.strptime(d, "%d-%m-%Y")), None
    except Exception as e:
        errors.append(f"BSE page scrape: {str(e)[:50]}")

    return [], f"BSE API: {' | '.join(errors[:3])}"


def fetch_sensex_option_chain(expiry_dd_mm_yyyy: str) -> Tuple[Dict[str, Any], Optional[str]]:
    """
    Fetch SENSEX option chain for a given expiry from BSE.
    Returns ({"calls": [...], "puts": [...], "spot_price": float}, error)
    Each record matches the format used by fetch_option_chain_both for NIFTY.
    """
    # Convert DD-MM-YYYY to BSE API formats
    try:
        dt = datetime.strptime(expiry_dd_mm_yyyy, "%d-%m-%Y")
        expiry_bse     = dt.strftime("%Y%m%d")      # 20240502
        expiry_display = dt.strftime("%d %b %Y")    # 02 May 2024
    except ValueError:
        return {}, f"Invalid expiry format: {expiry_dd_mm_yyyy}"

    urls_to_try = [
        f"https://api.bseindia.com/BseIndiaAPI/api/GetOptionChain/w"
        f"?Underlying=SENSEX&Type=IO&Expiry={expiry_bse}",
        f"https://api.bseindia.com/BseIndiaAPI/api/GetOptionChain/w"
        f"?Underlying=SENSEX&Category=IO&ExpiryDate={expiry_bse}",
        f"https://api.bseindia.com/BseIndiaAPI/api/IndicesDeriOptChain/w"
        f"?str=SENSEX|{expiry_bse}",
    ]
    errors = []

    for url in urls_to_try:
        try:
            r = requests.get(url, headers=BSE_HEADERS, timeout=12)
            if r.status_code != 200:
                errors.append(f"HTTP {r.status_code}")
                continue

            j = r.json()
            # The BSE API returns different shapes — try to normalise
            records = (
                j.get("Table") or j.get("data") or
                j.get("OptionChain") or j.get("results") or
                (j if isinstance(j, list) else [])
            )

            if not records:
                errors.append(f"Empty response from {url[:60]}")
                continue

            calls, puts = [], []
            spot = 0.0

            for rec in records:
                if isinstance(rec, dict):
                    opt_type = str(rec.get("OType") or rec.get("optionType","")).upper().strip()
                    if not opt_type:
                        opt_type = "CE" if rec.get("CE") else "PE" if rec.get("PE") else ""

                    ltp     = _safe_float(rec.get("LTP") or rec.get("lastPrice") or rec.get("CMP"))
                    strike  = _safe_float(rec.get("StrikePrice") or rec.get("strikePrice") or rec.get("SP"))
                    oi      = _safe_float(rec.get("OI") or rec.get("openInterest") or 0)
                    oi_chg  = _safe_float(rec.get("OIChg") or rec.get("changeinOpenInterest") or 0)
                    vol     = _safe_float(rec.get("Volume") or rec.get("volume") or 0)
                    iv      = _safe_float(rec.get("IV") or rec.get("impliedVolatility") or 0)
                    delta   = _safe_float(rec.get("Delta") or rec.get("delta") or 0)
                    theta   = _safe_float(rec.get("Theta") or rec.get("theta") or 0)
                    vega    = _safe_float(rec.get("Vega") or rec.get("vega") or 0)
                    sp_raw  = _safe_float(rec.get("SpotPrice") or rec.get("spotPrice") or 0)

                    if sp_raw > 10000:
                        spot = sp_raw

                    if strike <= 0:
                        continue

                    # OI percent change — compute if not supplied
                    oi_perc = _safe_float(rec.get("OIChgPct") or rec.get("pchangeinOpenInterest") or 0)
                    if oi_perc == 0 and oi > 0 and oi_chg != 0:
                        prev_oi = oi - oi_chg
                        if prev_oi > 0:
                            oi_perc = round((oi_chg / prev_oi) * 100, 2)

                    normalized = {
                        "strike_price":  strike,
                        "price":         ltp,
                        "oi":            oi,
                        "oi_perc_chg":   oi_perc,
                        "net_chg":       oi_chg,
                        "volume":        vol,
                        "iv":            iv,
                        "delta":         delta,
                        "theta":         theta,
                        "vega":          vega,
                        "gamma":         _safe_float(rec.get("Gamma") or rec.get("gamma") or 0),
                        "spot_price":    sp_raw,
                        "expiry":        expiry_dd_mm_yyyy,
                        "pml_symbol":    f"SENSEX{expiry_bse}{'C' if 'CE' in opt_type else 'P'}{int(strike)}",
                        "source":        "BSE India API",
                    }

                    if "CE" in opt_type or opt_type == "C":
                        calls.append(normalized)
                    elif "PE" in opt_type or opt_type == "P":
                        puts.append(normalized)
                    else:
                        # Sometimes BSE returns both CE/PE in same row
                        ce_data = rec.get("CE") or {}
                        pe_data = rec.get("PE") or {}
                        if ce_data and isinstance(ce_data, dict):
                            ce_norm = {**normalized,
                                       "price": _safe_float(ce_data.get("lastPrice") or ce_data.get("LTP")),
                                       "oi": _safe_float(ce_data.get("openInterest") or ce_data.get("OI")),
                                       "volume": _safe_float(ce_data.get("volume") or ce_data.get("Volume")),
                            }
                            calls.append(ce_norm)
                        if pe_data and isinstance(pe_data, dict):
                            pe_norm = {**normalized,
                                       "price": _safe_float(pe_data.get("lastPrice") or pe_data.get("LTP")),
                                       "oi": _safe_float(pe_data.get("openInterest") or pe_data.get("OI")),
                                       "volume": _safe_float(pe_data.get("volume") or pe_data.get("Volume")),
                            }
                            puts.append(pe_norm)

            if calls or puts:
                # Sort by strike price
                calls.sort(key=lambda x: x["strike_price"])
                puts.sort(key=lambda x: x["strike_price"])
                return {"calls": calls, "puts": puts, "spot_price": spot}, None

            errors.append(f"Parsed 0 records from {url[:60]}")

        except Exception as e:
            errors.append(f"{url[:50]}: {str(e)[:60]}")

    return {}, f"BSE chain fetch failed: {' | '.join(errors[:3])}"


if __name__ == "__main__":
    print("Testing BSE SENSEX expiry fetch...")
    dates, err = fetch_sensex_expiry_dates()
    if err:
        print(f"Error: {err}")
    else:
        print(f"Found {len(dates)} expiries: {dates[:5]}")
        if dates:
            print(f"\nTesting option chain for {dates[0]}...")
            chain, err2 = fetch_sensex_option_chain(dates[0])
            if err2:
                print(f"Chain error: {err2}")
            else:
                print(f"Calls: {len(chain['calls'])}, Puts: {len(chain['puts'])}")
                print(f"Spot: {chain.get('spot_price')}")
                if chain['calls']:
                    print(f"Sample call: {chain['calls'][len(chain['calls'])//2]}")
