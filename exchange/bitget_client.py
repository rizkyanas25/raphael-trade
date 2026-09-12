"""
Bitget Exchange Client — Raphael AI Bot v2.0
Wisdom Lord Raphael — Core SMC Analytical Engine & Crypto Risk Guard

Handles all exchange I/O:
  - OHLCV data fetch (H1, M15, M5) for SMC analysis
  - Account balance & open positions
  - Limit order placement & cancellation
  - Minimum contract size validation

Exchange: Bitget USDT-M Futures via ccxt.async_support
"""

import asyncio
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime

import ccxt.async_support as ccxt

from config import Config


logger = logging.getLogger(__name__)

# Candle OHLCV column indices
O, H, L, C, V = 1, 2, 3, 4, 5  # index 0 = timestamp


class BitgetClient:
    """Async Bitget Futures client built on ccxt.async_support"""

    # Timeframe map: internal label → ccxt string
    TF_MAP: Dict[str, str] = {
        "H1":  "1h",
        "M15": "15m",
        "M5":  "5m",
        "M1":  "1m",
        "H4":  "4h",
    }

    def __init__(self, config: Config):
        self.config = config
        self._exchange: Optional[ccxt.bitget] = None
        self._market_cache: Dict[str, Any] = {}
        logger.info("🔌 BitgetClient initialized (not yet connected)")

    # ── Lifecycle ──────────────────────────────────────────────────────────

    async def connect(self):
        """Create and load the ccxt Bitget exchange instance."""
        self._exchange = ccxt.bitget({
            "apiKey":     self.config.bitget_api_key,
            "secret":     self.config.bitget_api_secret,
            "password":   self.config.bitget_passphrase,  # Bitget calls it 'passphrase'
            "options": {
                "defaultType": "swap",          # USDT-M Futures
                "defaultMarginMode": "cross",
            },
            "enableRateLimit": True,
        })

        if self.config.bitget_sandbox:
            self._exchange.set_sandbox_mode(True)
            logger.info("⚠️  Bitget SANDBOX mode active")

        # Load markets once at startup (caches symbol metadata)
        self._market_cache = await self._exchange.load_markets()
        logger.info(
            f"✅ Bitget connected | sandbox={self.config.bitget_sandbox} | "
            f"{len(self._market_cache)} markets loaded"
        )

    async def close(self):
        """Cleanly close the aiohttp session inside ccxt."""
        if self._exchange:
            await self._exchange.close()
            logger.info("🔌 Bitget connection closed")

    def _require_connected(self):
        if not self._exchange:
            raise RuntimeError("BitgetClient.connect() has not been called yet.")

    # ── Market Data ────────────────────────────────────────────────────────

    async def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str,
        limit: int = 100,
    ) -> List[List[float]]:
        """
        Fetch OHLCV candles from Bitget Futures.

        Args:
            symbol:    e.g. 'SOLUSDT'
            timeframe: 'H1' | 'M15' | 'M5' (internal labels, mapped to ccxt)
            limit:     number of candles (max 200 per call on Bitget)

        Returns:
            List of [timestamp_ms, open, high, low, close, volume]
        """
        self._require_connected()
        ccxt_tf = self.TF_MAP.get(timeframe, timeframe)
        ccxt_symbol = self._normalise_symbol(symbol)

        try:
            candles = await self._exchange.fetch_ohlcv(
                ccxt_symbol, ccxt_tf, limit=limit
            )
            logger.debug(
                f"📊 {symbol} {timeframe}: {len(candles)} candles fetched"
            )
            return candles
        except ccxt.BadSymbol:
            logger.error(f"❌ Symbol not found on Bitget: {ccxt_symbol}")
            return []
        except Exception as e:
            logger.error(f"❌ fetch_ohlcv({symbol},{timeframe}): {e}")
            raise

    async def fetch_ticker(self, symbol: str) -> Dict[str, Any]:
        """Fetch latest ticker (last price, bid, ask) for a symbol."""
        self._require_connected()
        ccxt_symbol = self._normalise_symbol(symbol)
        try:
            ticker = await self._exchange.fetch_ticker(ccxt_symbol)
            return {
                "symbol": symbol,
                "last":   ticker.get("last", 0.0),
                "bid":    ticker.get("bid", 0.0),
                "ask":    ticker.get("ask", 0.0),
                "change_pct": ticker.get("percentage", 0.0),
                "volume_24h": ticker.get("baseVolume", 0.0),
            }
        except Exception as e:
            logger.error(f"❌ fetch_ticker({symbol}): {e}")
            raise

    # ── Account ────────────────────────────────────────────────────────────

    async def fetch_balance(self) -> Dict[str, Any]:
        """
        Fetch USDT Futures wallet balance.

        Returns dict with:
            total_usdt, available_usdt, used_usdt, unrealized_pnl
        """
        self._require_connected()
        try:
            balance = await self._exchange.fetch_balance({"type": "swap"})
            usdt = balance.get("USDT", {})
            # Bitget returns info as a list of account dicts
            info_raw = balance.get("info", {})
            upnl = 0.0
            if isinstance(info_raw, dict):
                info_list = info_raw.get("data", [{}])
                if info_list and isinstance(info_list[0], dict):
                    upnl = float(info_list[0].get("unrealizedPL", 0.0))
            elif isinstance(info_raw, list) and info_raw:
                upnl = float(info_raw[0].get("unrealizedPL", 0.0) if isinstance(info_raw[0], dict) else 0.0)

            result = {
                "total_usdt":      float(usdt.get("total", 0.0) or 0.0),
                "available_usdt":  float(usdt.get("free",  0.0) or 0.0),
                "used_usdt":       float(usdt.get("used",  0.0) or 0.0),
                "unrealized_pnl":  upnl,
                "equity_usdt":     float(usdt.get("total", 0.0) or 0.0) + upnl,
            }
            logger.debug(f"💰 Balance fetched: {result}")
            return result
        except Exception as e:
            logger.error(f"❌ fetch_balance: {e}")
            raise

    async def fetch_positions(self) -> List[Dict[str, Any]]:
        """
        Fetch all open futures positions.

        Returns list of dicts with standardised fields.
        """
        self._require_connected()
        try:
            raw_positions = await self._exchange.fetch_positions()
            positions = []
            for p in raw_positions:
                size = float(p.get("contracts", 0) or 0)
                if size == 0:
                    continue  # skip empty positions
                positions.append({
                    "symbol":        p.get("symbol", "").replace("/USDT:USDT", "USDT"),
                    "side":          p.get("side", "").upper(),      # 'LONG' | 'SHORT'
                    "size":          size,
                    "entry_price":   float(p.get("entryPrice", 0) or 0),
                    "mark_price":    float(p.get("markPrice", 0) or 0),
                    "unrealized_pnl": float(p.get("unrealizedPnl", 0) or 0),
                    "leverage":      int(p.get("leverage", 1) or 1),
                    "margin_mode":   p.get("marginMode", "cross"),
                    "liquidation_price": float(p.get("liquidationPrice", 0) or 0),
                })
            logger.debug(f"📊 Positions fetched: {len(positions)} active")
            return positions
        except Exception as e:
            logger.error(f"❌ fetch_positions: {e}")
            raise

    async def fetch_open_orders(self, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        """Fetch open (pending) limit orders, optionally filtered by symbol."""
        self._require_connected()
        try:
            ccxt_symbol = self._normalise_symbol(symbol) if symbol else None
            raw = await self._exchange.fetch_open_orders(ccxt_symbol)
            orders = []
            for o in raw:
                orders.append({
                    "order_id":    o.get("id"),
                    "symbol":      o.get("symbol", "").replace("/USDT:USDT", "USDT"),
                    "side":        o.get("side", "").upper(),
                    "type":        o.get("type", ""),
                    "price":       float(o.get("price", 0) or 0),
                    "amount":      float(o.get("amount", 0) or 0),
                    "filled":      float(o.get("filled", 0) or 0),
                    "status":      o.get("status", ""),
                    "created_at":  o.get("datetime", ""),
                })
            return orders
        except Exception as e:
            logger.error(f"❌ fetch_open_orders: {e}")
            raise

    # ── Order Execution ────────────────────────────────────────────────────

    async def set_leverage(self, symbol: str, leverage: int) -> bool:
        """Set leverage for a symbol before placing an order."""
        self._require_connected()
        ccxt_symbol = self._normalise_symbol(symbol)
        try:
            await self._exchange.set_leverage(leverage, ccxt_symbol)
            logger.info(f"⚙️  Leverage set: {symbol} → {leverage}x")
            return True
        except Exception as e:
            logger.warning(f"⚠️  set_leverage({symbol},{leverage}x): {e}")
            return False

    async def place_limit_order(
        self,
        symbol: str,
        side: str,          # 'buy' | 'sell'
        amount: float,      # position size in base asset (e.g. SOL)
        price: float,       # limit entry price
        stop_loss: float,
        take_profit: float,
        leverage: int = 5,
    ) -> Dict[str, Any]:
        """
        Place a Limit Order on Bitget Futures with SL/TP attached.

        Bitget supports attaching SL/TP at order creation via params.
        Returns the ccxt order dict on success.
        """
        self._require_connected()
        ccxt_symbol = self._normalise_symbol(symbol)

        # Validate minimum notional before sending to exchange
        min_notional_ok, reason = self.check_min_notional(symbol, amount, price)
        if not min_notional_ok:
            raise ValueError(f"Order rejected (min notional): {reason}")

        await self.set_leverage(symbol, leverage)

        params = {
            "stopLoss":   {"triggerPrice": str(stop_loss),   "type": "fill_price"},
            "takeProfit": {"triggerPrice": str(take_profit), "type": "fill_price"},
            "tdMode":     "cross",   # cross margin
            "side":       side,
        }

        try:
            order = await self._exchange.create_limit_order(
                ccxt_symbol,
                side,
                amount,
                price,
                params=params,
            )
            logger.info(
                f"✅ Limit order placed | {symbol} {side.upper()} "
                f"{amount} @ {price} | SL {stop_loss} | TP {take_profit} | "
                f"order_id={order.get('id')}"
            )
            return order
        except Exception as e:
            logger.error(f"❌ place_limit_order({symbol}): {e}")
            raise

    async def cancel_order(self, order_id: str, symbol: str) -> bool:
        """Cancel a specific pending order by ID."""
        self._require_connected()
        ccxt_symbol = self._normalise_symbol(symbol)
        try:
            await self._exchange.cancel_order(order_id, ccxt_symbol)
            logger.info(f"🗑️  Order cancelled: {order_id} ({symbol})")
            return True
        except Exception as e:
            logger.error(f"❌ cancel_order({order_id}): {e}")
            return False

    async def cancel_all_orders(self, symbol: Optional[str] = None) -> int:
        """
        Cancel all pending limit orders.
        Returns number of cancelled orders.
        """
        self._require_connected()
        try:
            open_orders = await self.fetch_open_orders(symbol)
            cancelled = 0
            for order in open_orders:
                ok = await self.cancel_order(order["order_id"], order["symbol"])
                if ok:
                    cancelled += 1
            logger.info(f"🗑️  Cancelled {cancelled}/{len(open_orders)} orders")
            return cancelled
        except Exception as e:
            logger.error(f"❌ cancel_all_orders: {e}")
            return 0

    # ── Validation Helpers ─────────────────────────────────────────────────

    def check_min_notional(
        self, symbol: str, amount: float, price: float
    ) -> tuple[bool, str]:
        """
        Check if the order meets Bitget minimum notional value.
        Returns (is_valid, reason_string).
        """
        notional = amount * price
        # Bitget USDT-M generally requires min $5 notional per order
        min_notional = 5.0
        if notional < min_notional:
            return (
                False,
                f"Notional ${notional:.2f} < minimum ${min_notional:.2f}. "
                f"Increase leverage or choose a lower-priced asset."
            )
        return (True, "OK")

    def get_price_precision(self, symbol: str) -> int:
        """Return number of decimal places for price on this symbol."""
        ccxt_symbol = self._normalise_symbol(symbol)
        market = self._market_cache.get(ccxt_symbol, {})
        precision = market.get("precision", {}).get("price", 4)
        return int(precision) if isinstance(precision, (int, float)) else 4

    def get_amount_precision(self, symbol: str) -> int:
        """Return number of decimal places for amount on this symbol."""
        ccxt_symbol = self._normalise_symbol(symbol)
        market = self._market_cache.get(ccxt_symbol, {})
        precision = market.get("precision", {}).get("amount", 4)
        return int(precision) if isinstance(precision, (int, float)) else 4

    def get_min_amount(self, symbol: str) -> float:
        """Return minimum order size (base asset) for this symbol."""
        ccxt_symbol = self._normalise_symbol(symbol)
        market = self._market_cache.get(ccxt_symbol, {})
        limits = market.get("limits", {}).get("amount", {})
        return float(limits.get("min", 0.0) or 0.0)

    # ── Utilities ──────────────────────────────────────────────────────────

    def _normalise_symbol(self, symbol: str) -> str:
        """
        Convert internal symbol format to ccxt Bitget swap format.
        'SOLUSDT' → 'SOL/USDT:USDT'
        Handles both SOLUSDT and SOL/USDT inputs.
        """
        s = symbol.upper().strip()
        # Already in ccxt format
        if "/" in s:
            return s
        # Strip USDT suffix and rebuild
        if s.endswith("USDT"):
            base = s[:-4]
            return f"{base}/USDT:USDT"
        return s

    async def test_connection(self) -> bool:
        """Quick connectivity test — fetches server time."""
        self._require_connected()
        try:
            time_ms = await self._exchange.fetch_time()
            server_time = datetime.fromtimestamp(time_ms / 1000).strftime(
                "%Y-%m-%d %H:%M:%S"
            )
            logger.info(f"✅ Bitget connection OK | Server time: {server_time}")
            return True
        except Exception as e:
            logger.error(f"❌ Bitget connection test failed: {e}")
            return False
