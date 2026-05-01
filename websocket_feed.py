"""
websocket_feed.py — Paytm Money WebSocket Live Price Feed
Uses Paytm's official pyPMClient WebSocket implementation.

Paytm WebSocket details (from official GitHub):
  - Needs: public_access_token (NOT access_token)
  - NIFTY INDEX scripId: '13'
  - BANKNIFTY INDEX scripId: '25'
  - Mode: 'FULL' gives OHLC + LTP + Volume
  - scripType: 'INDEX'

Install: pip install pypmclient
"""

import threading
import time
import json
import queue
from datetime import datetime
from typing import Dict, Any, Optional

# Paytm Money WebSocket URL (from their official docs)
# Paytm Money WebSocket URL — correct format from Paytm's official docs/forums
# Full endpoint: wss://developer-ws.paytmmoney.com/broadcast/user/v1/data?x_jwt_token=<TOKEN>
#   • Subdomain must be `developer-ws.paytmmoney.com` (with -ws suffix)
#   • Path must include /v1/data
#   • Query param name must be x_jwt_token (NOT jwt)
PAYTM_WS_URL = "wss://developer-ws.paytmmoney.com/broadcast/user/v1/data"

# scripId map for indices
SCRIP_ID_MAP = {
    "NIFTY":      "13",
    "BANKNIFTY":  "25",
    "FINNIFTY":   "2885",
    "MIDCPNIFTY": "14366",
}


class PaytmWebSocketFeed:
    """
    Manages a live WebSocket connection to Paytm Money.
    Runs in a background thread, updates shared price dict.
    """

    def __init__(self):
        self._ws = None
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._price_data: Dict[str, Any] = {}
        self._error: Optional[str] = None
        self._connected = False
        self._last_tick: Optional[datetime] = None
        # Thread-safe buffer: holds every tick received by the WebSocket
        # callback so that the Streamlit rerun loop can drain ALL of them
        # on each cycle, not just the latest. Without this, ticks arriving
        # between Streamlit reruns are silently overwritten.
        self._tick_buffer: "queue.Queue[Dict[str, Any]]" = queue.Queue(maxsize=5000)

    # ── Public API ────────────────────────────────────────────────────────

    def start(self, public_access_token: str, symbol: str = "NIFTY") -> bool:
        """
        Start WebSocket feed in background thread.
        Returns True if started successfully.
        """
        if self._running:
            self.stop()

        scrip_id = SCRIP_ID_MAP.get(symbol, "13")

        try:
            # Try pyPMClient first (official Paytm library)
            return self._start_pypmclient(public_access_token, symbol, scrip_id)
        except ImportError:
            # Fallback: raw websocket-client
            return self._start_raw_websocket(public_access_token, symbol, scrip_id)
        except Exception as e:
            self._error = f"WebSocket start error: {e}"
            return False

    def stop(self):
        """Stop the WebSocket connection."""
        self._running = False
        self._connected = False
        try:
            if self._ws:
                self._ws.disconnect()
        except Exception:
            pass
        self._ws = None

    def get_price(self) -> Dict[str, Any]:
        """Get latest price data. Returns empty dict if no data yet."""
        return dict(self._price_data)

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def error(self) -> Optional[str]:
        return self._error

    @property
    def last_tick_age(self) -> Optional[float]:
        """Seconds since last tick received."""
        if self._last_tick:
            return (datetime.now() - self._last_tick).total_seconds()
        return None

    # ── pyPMClient Implementation ─────────────────────────────────────────

    def _start_pypmclient(self, token: str, symbol: str, scrip_id: str) -> bool:
        """Use official Paytm pyPMClient library."""
        from pmClient.WebSocketClient import WebSocketClient

        preferences = [{
            "actionType": "ADD",
            "modeType":   "FULL",   # FULL gives OHLC + LTP + volume
            "scripType":  "INDEX",
            "exchangeType": "NSE",
            "scripId":    scrip_id,
        }]

        ws = WebSocketClient(token)
        self._ws = ws

        def on_open():
            self._connected = True
            self._error = None
            ws.subscribe(preferences)

        def on_message(arr):
            self._last_tick = datetime.now()
            for tick in arr:
                self._parse_tick(tick, symbol)

        def on_error(error):
            self._error = str(error)
            self._connected = False

        def on_close(code, reason):
            self._connected = False

        ws.set_on_open_listener(on_open)
        ws.set_on_message_listener(on_message)
        ws.set_on_error_listener(on_error)
        ws.set_on_close_listener(on_close)
        ws.set_reconnect_config(True, 5)

        self._running = True
        self._thread = threading.Thread(target=ws.connect, daemon=True)
        self._thread.start()
        return True

    # ── Raw WebSocket Fallback ────────────────────────────────────────────

    def _start_raw_websocket(self, token: str, symbol: str, scrip_id: str) -> bool:
        """Fallback using websocket-client library directly."""
        try:
            import websocket
        except ImportError:
            self._error = "Install pypmclient or websocket-client: pip install pypmclient websocket-client"
            return False

        preference = json.dumps([{
            "actionType":   "ADD",
            "modeType":     "FULL",
            "scripType":    "INDEX",
            "exchangeType": "NSE",
            "scripId":      scrip_id,
        }])

        def on_open(ws):
            self._connected = True
            self._error = None
            ws.send(preference)

        def on_message(ws, data):
            self._last_tick = datetime.now()
            try:
                # Paytm sends market data as binary — decoding requires
                # their custom binary protocol which is implemented in
                # pypmclient. When pypmclient is not available, we can
                # only detect that ticks are arriving but not parse them.
                if isinstance(data, bytes):
                    # Record that a tick arrived (updates last_tick_age)
                    # so the UI knows the connection is healthy, even if
                    # we can't extract LTP without pypmclient.
                    self._error = (
                        "Binary tick received but pypmclient not installed. "
                        "Add 'pypmclient>=1.0.1' to requirements.txt to decode ticks."
                    )
                    return
                # Text message — JSON-encoded (status updates, acks, errors)
                ticks = json.loads(data)
                if isinstance(ticks, list):
                    for tick in ticks:
                        self._parse_tick(tick, symbol)
                elif isinstance(ticks, dict):
                    self._parse_tick(ticks, symbol)
            except Exception as e:
                self._error = f"Parse error: {e}"

        def on_error(ws, error):
            self._error = str(error)
            self._connected = False

        def on_close(ws, code, reason):
            self._connected = False
            # Auto-reconnect
            if self._running:
                time.sleep(3)
                self._start_raw_websocket(token, symbol, scrip_id)

        ws_app = websocket.WebSocketApp(
            f"{PAYTM_WS_URL}?x_jwt_token={token}",
            on_open=on_open,
            on_message=on_message,
            on_error=on_error,
            on_close=on_close,
        )
        self._ws = ws_app
        self._running = True
        self._thread = threading.Thread(
            target=lambda: ws_app.run_forever(ping_interval=30, ping_timeout=10),
            daemon=True
        )
        self._thread.start()
        return True

    # ── Tick Parser ───────────────────────────────────────────────────────

    def _parse_tick(self, tick: Any, symbol: str):
        """
        Parse a FULL mode tick from Paytm WebSocket.
        FULL mode fields (from pyPMClient docs):
          last_price, open_price, high_price, low_price,
          close_price (prev close), volume, net_change, percent_change
        """
        if not isinstance(tick, dict):
            return

        def sf(key, default=0.0):
            try: return float(tick.get(key, default) or default)
            except: return default

        ltp   = sf("last_price") or sf("ltp") or sf("price")
        open_ = sf("open_price") or sf("open")
        high  = sf("high_price") or sf("high")
        low   = sf("low_price")  or sf("low")
        prev  = sf("close_price") or sf("prev_close") or sf("close")
        vol   = int(sf("volume") or sf("vol"))
        chg   = sf("net_change") or sf("change") or (ltp - prev if prev else 0)
        chgp  = sf("percent_change") or sf("change_pct") or (
            (chg / prev * 100) if prev else 0)

        if ltp > 0:
            self._price_data = {
                "ltp":        ltp,
                "open":       open_,
                "high":       high,
                "low":        low,
                "prev_close": prev,
                "volume":     vol,
                "change":     chg,
                "change_pct": round(chgp, 2),
                "source":     "Paytm WebSocket (live)",
                "error":      None,
                "52w_high":   sf("upper_circuit") or sf("year_high"),
                "52w_low":    sf("lower_circuit") or sf("year_low"),
                "timestamp":  datetime.now().strftime("%H:%M:%S"),
                "symbol":     symbol,
            }
            # Push the tick into the buffer so Streamlit can drain it later.
            # We push a minimal dict (timestamp + ltp + cum volume) since
            # that's all the candle builder needs. Use put_nowait so the
            # callback never blocks; if the buffer is full (5000 ticks
            # without a Streamlit rerun) we silently drop the oldest.
            try:
                self._tick_buffer.put_nowait({
                    "timestamp": datetime.now().isoformat(),
                    "ltp":       round(ltp, 2),
                    "volume":    vol,
                })
            except queue.Full:
                # Drain one and retry — keeps us bounded even under burst load
                try:
                    self._tick_buffer.get_nowait()
                    self._tick_buffer.put_nowait({
                        "timestamp": datetime.now().isoformat(),
                        "ltp":       round(ltp, 2),
                        "volume":    vol,
                    })
                except Exception:
                    pass


    def drain_ticks(self) -> list:
        """
        Pull all buffered ticks out of the queue and return them as a list.
        Called by the Streamlit rerun loop to capture every tick that
        arrived since the last rerun (typically 30-100 per minute on Nifty).
        """
        ticks = []
        while True:
            try:
                ticks.append(self._tick_buffer.get_nowait())
            except queue.Empty:
                break
        return ticks


# ── Singleton instance ────────────────────────────────────────────────────────
_feed_instance = PaytmWebSocketFeed()


def get_feed() -> PaytmWebSocketFeed:
    """Get the global WebSocket feed instance."""
    return _feed_instance
