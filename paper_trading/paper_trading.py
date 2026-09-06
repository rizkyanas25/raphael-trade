"""
Paper Trading Module for Raphael AI Bot
Wisdom Lord Raphael - Core Analytical Engine & Financial Risk Guard

Features:
  - Full auto-monitor: background task checks TP/SL every N seconds
  - Pending order lifecycle: waiting → active → completed
  - Auto-expire: pending orders that never trigger expire after N days
  - Telegram notifications on TP/SL hit and expiry
  - All monetary values in IDR
"""

import asyncio
import logging
from typing import Dict, Any, Optional, List, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum

from config import Config
from database.database import Database
from risk_management.risk_manager import RiskManager


logger = logging.getLogger(__name__)


class TradeStatus(Enum):
    PENDING_TRIGGER = "pending_trigger"   # placed, waiting for price to hit entry
    ACTIVE          = "active"            # entry triggered, monitoring TP/SL
    COMPLETED       = "completed"         # closed by TP or SL
    EXPIRED         = "expired"           # never triggered, auto-expired
    CANCELLED       = "cancelled"         # manually cancelled


class TradeType(Enum):
    INTRADAY = "intraday"   # M15/H1 — expire in 2 days
    SWING    = "swing"      # H2/H4  — expire in 5 days


@dataclass
class PaperTrade:
    """Paper trade — all monetary values in IDR"""
    signal_id:              str
    symbol:                 str
    order_type:             str          # BUY_LIMIT, SELL_LIMIT, BUY_STOP, SELL_STOP
    entry_price:            float
    stop_loss:              float
    take_profit:            float
    lot_size:               float
    risk_idr:               float
    potential_reward_idr:   float
    rrr:                    float
    timeframe:              str
    strategy:               str          # 'Signal_Mode1' | 'Analyse_Mode2' | etc.
    trade_type:             TradeType
    equity_at_record:       float        # IDR equity when user recorded the trade
    status:                 TradeStatus  = TradeStatus.PENDING_TRIGGER
    record_time:            datetime     = field(default_factory=datetime.now)
    trigger_time:           Optional[datetime] = None
    close_time:             Optional[datetime] = None
    close_price:            Optional[float]    = None
    profit_loss_idr:        Optional[float]    = None
    pip_movement:           Optional[float]    = None
    close_reason:           Optional[str]      = None   # TP_HIT | SL_HIT | EXPIRED | CANCELLED
    expire_at:              Optional[datetime] = None


class PaperTradingEngine:
    """
    Paper trading engine with full auto-monitor background task.

    The background task runs every config.paper_trading_monitor_interval seconds
    and handles:
      1. Pending → Active transition (entry price hit)
      2. Active → Completed (TP or SL hit)
      3. Pending → Expired (never triggered within expiry window)
    """

    def __init__(
        self,
        config: Config,
        database: Database,
        risk_manager: RiskManager,
        notify_callback: Optional[Callable] = None,
    ):
        """
        Args:
            notify_callback: async callable(message: str) that sends Telegram notification.
                             Injected by the bot layer so this module stays decoupled.
        """
        self.config        = config
        self.database      = database
        self.risk_manager  = risk_manager
        self.notify        = notify_callback  # set via set_notify_callback() after init

        self.is_enabled    = config.paper_trading_enabled
        self.virtual_equity_idr  = config.paper_trading_starting_equity_idr
        self.virtual_balance_idr = config.paper_trading_starting_equity_idr

        self.pending_trades: Dict[str, PaperTrade] = {}   # waiting for entry trigger
        self.active_trades:  Dict[str, PaperTrade] = {}   # entry triggered, live
        self.trade_history:  List[PaperTrade]       = []

        # Performance counters
        self.total_trades    = 0
        self.winning_trades  = 0
        self.losing_trades   = 0
        self.total_pnl_idr   = 0.0

        # Background task handle
        self._monitor_task: Optional[asyncio.Task] = None

        logger.info("📝 Paper Trading Engine initialized")
        logger.info(f"📊 Virtual Equity: Rp {self.virtual_equity_idr:,.0f}")
        logger.info(f"📊 Monitor interval: {config.paper_trading_monitor_interval}s")

    def set_notify_callback(self, callback: Callable):
        """Inject Telegram notification callback after bot is initialised."""
        self.notify = callback

    # ── Background Monitor ────────────────────────────────────────────────

    async def start_monitor(self):
        """Start the background price monitor task."""
        if self._monitor_task and not self._monitor_task.done():
            return
        self._monitor_task = asyncio.create_task(self._monitor_loop())
        logger.info("🔍 Paper trade monitor started")

    async def stop_monitor(self):
        """Stop the background monitor task."""
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
        logger.info("⏸️  Paper trade monitor stopped")

    async def _monitor_loop(self):
        """Main monitoring loop — runs every N seconds."""
        while True:
            try:
                await self._check_all_trades()
            except Exception as e:
                logger.error(f"❌ Monitor loop error: {e}", exc_info=True)
            await asyncio.sleep(self.config.paper_trading_monitor_interval)

    async def _check_all_trades(self):
        """Check pending and active trades against current market prices."""
        now = datetime.now()

        # Import here to avoid circular deps — connector is passed via prices dict
        # Prices are fetched by the bot layer and we use the last known price
        # OR we pull directly if mt5 is available
        from mt5_module.mt5_loader import mt5 as _mt5

        # ── Check pending orders (waiting for entry trigger) ──────────────
        for signal_id, trade in list(self.pending_trades.items()):
            try:
                # Check auto-expire
                if trade.expire_at and now > trade.expire_at:
                    await self._expire_trade(signal_id, trade)
                    continue

                tick = _mt5.symbol_info_tick(trade.symbol)
                if tick is None:
                    continue

                bid = float(tick.bid)
                ask = float(tick.ask)

                triggered = False
                if trade.order_type in ('BUY_LIMIT', 'BUY_STOP'):
                    # BUY_LIMIT: entry when ask <= entry_price
                    # BUY_STOP:  entry when ask >= entry_price
                    if trade.order_type == 'BUY_LIMIT':
                        triggered = ask <= trade.entry_price
                    else:
                        triggered = ask >= trade.entry_price
                elif trade.order_type in ('SELL_LIMIT', 'SELL_STOP'):
                    if trade.order_type == 'SELL_LIMIT':
                        triggered = bid >= trade.entry_price
                    else:
                        triggered = bid <= trade.entry_price

                if triggered:
                    await self._trigger_trade(signal_id, trade)

            except Exception as e:
                logger.error(f"❌ Error checking pending trade {signal_id}: {e}")

        # ── Check active trades (monitoring TP/SL) ────────────────────────
        for signal_id, trade in list(self.active_trades.items()):
            try:
                tick = _mt5.symbol_info_tick(trade.symbol)
                if tick is None:
                    continue

                bid = float(tick.bid)
                ask = float(tick.ask)

                # Use bid for BUY positions, ask for SELL positions
                if trade.order_type in ('BUY_LIMIT', 'BUY_STOP', 'BUY'):
                    current = bid
                    tp_hit = current >= trade.take_profit
                    sl_hit = current <= trade.stop_loss
                else:
                    current = ask
                    tp_hit = current <= trade.take_profit
                    sl_hit = current >= trade.stop_loss

                if tp_hit:
                    await self._close_trade(signal_id, trade, trade.take_profit, "TP_HIT")
                elif sl_hit:
                    await self._close_trade(signal_id, trade, trade.stop_loss, "SL_HIT")

            except Exception as e:
                logger.error(f"❌ Error checking active trade {signal_id}: {e}")

    # ── Trade Lifecycle ───────────────────────────────────────────────────

    async def record_paper_trade(
        self,
        signal_id:    str,
        symbol:       str,
        order_type:   str,
        entry_price:  float,
        stop_loss:    float,
        take_profit:  float,
        lot_size:     float,
        timeframe:    str,
        strategy:     str,
        account_equity: float,
    ) -> Dict[str, Any]:
        """
        Record a new paper trade. Called after user confirms via inline button.
        All monetary values in IDR.
        """
        try:
            if not self.is_enabled:
                return {"success": False, "message": "Paper trading is disabled"}

            # Calculate risk/reward in IDR
            pip_val_idr  = self.config.get_pip_value_per_001_lot_idr(symbol)
            sl_pips      = self.risk_manager._calculate_pip_distance(symbol, entry_price, stop_loss)
            tp_pips      = self.risk_manager._calculate_pip_distance(symbol, entry_price, take_profit)
            risk_idr     = sl_pips * pip_val_idr * (lot_size / 0.01)
            reward_idr   = tp_pips * pip_val_idr * (lot_size / 0.01)
            rrr          = tp_pips / sl_pips if sl_pips > 0 else 0.0

            # Determine trade type from timeframe
            trade_type = (
                TradeType.SWING if timeframe in self.config.get_swing_timeframes()
                else TradeType.INTRADAY
            )

            # Calculate expiry
            expire_days = (
                self.config.paper_trading_swing_expire_days
                if trade_type == TradeType.SWING
                else self.config.paper_trading_intraday_expire_days
            )
            expire_at = datetime.now() + timedelta(days=expire_days)

            trade = PaperTrade(
                signal_id            = signal_id,
                symbol               = symbol,
                order_type           = order_type.upper(),
                entry_price          = entry_price,
                stop_loss            = stop_loss,
                take_profit          = take_profit,
                lot_size             = lot_size,
                risk_idr             = risk_idr,
                potential_reward_idr = reward_idr,
                rrr                  = rrr,
                timeframe            = timeframe,
                strategy             = strategy,
                trade_type           = trade_type,
                equity_at_record     = account_equity,
                status               = TradeStatus.PENDING_TRIGGER,
                expire_at            = expire_at,
            )

            self.pending_trades[signal_id] = trade

            # Save to database
            await self.database.save_trade({
                "signal_id":           signal_id,
                "symbol":              symbol,
                "order_type":          order_type,
                "entry_price":         entry_price,
                "stop_loss":           stop_loss,
                "take_profit":         take_profit,
                "lot_size":            lot_size,
                "risk_idr":            risk_idr,
                "potential_reward_idr": reward_idr,
                "rrr":                 rrr,
                "timeframe":           timeframe,
                "strategy":            strategy,
                "equity_at_entry":     account_equity,
                "balance_at_entry":    self.virtual_balance_idr,
                "paper_trade":         True,
            })

            logger.info(
                f"📝 Paper trade recorded: {symbol} {order_type} @ {entry_price} | "
                f"Risk: Rp {risk_idr:,.0f} | RRR: 1:{rrr:.2f} | "
                f"Expires: {expire_at.strftime('%Y-%m-%d')}"
            )

            return {
                "success":            True,
                "signal_id":          signal_id,
                "risk_idr":           risk_idr,
                "potential_reward_idr": reward_idr,
                "rrr":                rrr,
                "expire_at":          expire_at,
                "trade_type":         trade_type.value,
            }

        except Exception as e:
            logger.error(f"❌ Error recording paper trade: {e}", exc_info=True)
            return {"success": False, "message": str(e)}

    async def _trigger_trade(self, signal_id: str, trade: PaperTrade):
        """Move trade from pending → active when entry price is hit."""
        trade.status       = TradeStatus.ACTIVE
        trade.trigger_time = datetime.now()
        self.active_trades[signal_id] = trade
        del self.pending_trades[signal_id]

        self.virtual_equity_idr -= trade.risk_idr  # reserve risk

        msg = (
            f"📡 *Paper Trade Triggered!*\n"
            f"{trade.symbol} {trade.order_type} @ {trade.entry_price}\n"
            f"Risk: Rp {trade.risk_idr:,.0f} | TP: {trade.take_profit} | SL: {trade.stop_loss}"
        )
        logger.info(f"📡 Paper trade triggered: {signal_id}")
        await self._send_notify(msg)

    async def _close_trade(
        self,
        signal_id:   str,
        trade:       PaperTrade,
        close_price: float,
        reason:      str,
    ):
        """Close an active trade on TP or SL hit."""
        pip_val_idr = self.config.get_pip_value_per_001_lot_idr(trade.symbol)
        pip_movement = self.risk_manager._calculate_pip_distance(
            trade.symbol, trade.entry_price, close_price
        )

        is_buy = trade.order_type in ('BUY_LIMIT', 'BUY_STOP', 'BUY')
        if is_buy:
            profit_pips = pip_movement if close_price > trade.entry_price else -pip_movement
        else:
            profit_pips = -pip_movement if close_price > trade.entry_price else pip_movement

        pnl_idr = profit_pips * pip_val_idr * (trade.lot_size / 0.01)

        trade.status        = TradeStatus.COMPLETED
        trade.close_time    = datetime.now()
        trade.close_price   = close_price
        trade.profit_loss_idr = pnl_idr
        trade.pip_movement  = profit_pips
        trade.close_reason  = reason

        # Settle equity
        self.virtual_equity_idr  += trade.risk_idr + pnl_idr
        self.virtual_balance_idr += pnl_idr

        # Update counters
        self.total_trades += 1
        if pnl_idr > 0:
            self.winning_trades += 1
        else:
            self.losing_trades += 1
        self.total_pnl_idr += pnl_idr

        # Move to history
        self.trade_history.append(trade)
        del self.active_trades[signal_id]

        # DB update
        await self.database.update_trade_status(
            signal_id, "completed",
            exit_price=close_price,
            profit_loss=pnl_idr,
        )

        # Notification
        win_rate = self.get_performance_metrics()["win_rate"]
        emoji    = "🎯" if reason == "TP_HIT" else "❌"
        pnl_str  = f"+Rp {pnl_idr:,.0f}" if pnl_idr >= 0 else f"-Rp {abs(pnl_idr):,.0f}"

        msg = (
            f"{emoji} *Paper Trade {reason.replace('_', ' ')}*\n"
            f"{trade.symbol} {trade.order_type} @ {close_price}\n"
            f"P/L: {pnl_str} ({profit_pips:+.1f} pips)\n"
            f"Win Rate: {self.winning_trades}/{self.total_trades} ({win_rate:.1f}%)\n"
            f"Virtual Equity: Rp {self.virtual_equity_idr:,.0f}"
        )

        logger.info(
            f"📊 Paper trade closed: {signal_id} | {reason} | "
            f"P/L: Rp {pnl_idr:,.0f} | Equity: Rp {self.virtual_equity_idr:,.0f}"
        )
        await self._send_notify(msg)

    async def _expire_trade(self, signal_id: str, trade: PaperTrade):
        """Auto-expire a pending trade that never triggered."""
        trade.status       = TradeStatus.EXPIRED
        trade.close_time   = datetime.now()
        trade.close_reason = "EXPIRED"

        self.trade_history.append(trade)
        del self.pending_trades[signal_id]

        await self.database.update_trade_status(signal_id, "expired")

        msg = (
            f"⏰ *Paper Trade Expired*\n"
            f"{trade.symbol} {trade.order_type} @ {trade.entry_price}\n"
            f"Pending order tidak ter-trigger dalam "
            f"{(self.config.paper_trading_swing_expire_days if trade.trade_type == TradeType.SWING else self.config.paper_trading_intraday_expire_days)} hari"
        )

        logger.info(f"⏰ Paper trade expired: {signal_id}")
        await self._send_notify(msg)

    # ── Manual Controls ───────────────────────────────────────────────────

    async def cancel_trade(self, signal_id: str) -> Dict[str, Any]:
        """Manually cancel a pending or active trade."""
        trade = self.pending_trades.get(signal_id) or self.active_trades.get(signal_id)
        if not trade:
            return {"success": False, "message": f"Trade {signal_id} not found"}

        if signal_id in self.pending_trades:
            del self.pending_trades[signal_id]
        elif signal_id in self.active_trades:
            self.virtual_equity_idr += trade.risk_idr  # return reserved risk
            del self.active_trades[signal_id]

        trade.status       = TradeStatus.CANCELLED
        trade.close_time   = datetime.now()
        trade.close_reason = "CANCELLED"
        self.trade_history.append(trade)

        await self.database.update_trade_status(signal_id, "cancelled")
        logger.info(f"🚫 Paper trade cancelled: {signal_id}")

        return {"success": True, "signal_id": signal_id}

    # ── Metrics ───────────────────────────────────────────────────────────

    def get_performance_metrics(self) -> Dict[str, Any]:
        """All monetary values in IDR."""
        win_rate = (
            self.winning_trades / self.total_trades * 100
            if self.total_trades > 0 else 0.0
        )
        avg_rrr = (
            sum(t.rrr for t in self.trade_history if t.status == TradeStatus.COMPLETED)
            / max(self.total_trades, 1)
        )
        return {
            "total_trades":           self.total_trades,
            "winning_trades":         self.winning_trades,
            "losing_trades":          self.losing_trades,
            "win_rate":               round(win_rate, 1),
            "total_profit_loss_idr":  round(self.total_pnl_idr, 0),
            "avg_rrr":                round(avg_rrr, 2),
            "virtual_equity":         self.virtual_equity_idr,
            "virtual_equity_idr":     self.virtual_equity_idr,
            "virtual_balance_idr":    self.virtual_balance_idr,
            "active_trades":          len(self.active_trades),
            "pending_trades":         len(self.pending_trades),
            "is_enabled":             self.is_enabled,
        }

    def check_readiness_for_live_trading(self) -> Dict[str, Any]:
        metrics = self.get_performance_metrics()
        min_trades    = 10
        wr_threshold  = self.config.paper_trading_win_rate_threshold
        rrr_threshold = self.config.paper_trading_rrr_threshold

        is_ready = all([
            metrics["total_trades"] >= min_trades,
            metrics["win_rate"]     >= wr_threshold,
            metrics["avg_rrr"]      >= rrr_threshold,
            metrics["total_profit_loss_idr"] > 0,
        ])

        return {
            "is_ready":          is_ready,
            "min_trades_required": min_trades,
            "current_trades":    metrics["total_trades"],
            "win_rate_threshold": wr_threshold,
            "current_win_rate":  metrics["win_rate"],
            "rrr_threshold":     rrr_threshold,
            "current_rrr":       metrics["avg_rrr"],
            "current_pnl_idr":   metrics["total_profit_loss_idr"],
        }

    def reset_paper_trading(self):
        self.virtual_equity_idr  = self.config.paper_trading_starting_equity_idr
        self.virtual_balance_idr = self.config.paper_trading_starting_equity_idr
        self.pending_trades.clear()
        self.active_trades.clear()
        self.trade_history.clear()
        self.total_trades   = 0
        self.winning_trades = 0
        self.losing_trades  = 0
        self.total_pnl_idr  = 0.0
        logger.info("🔄 Paper trading state reset")

    def toggle_paper_trading(self, enabled: bool):
        self.is_enabled = enabled
        logger.info(f"📝 Paper trading {'enabled' if enabled else 'disabled'}")

    # ── Internal ──────────────────────────────────────────────────────────

    async def _send_notify(self, message: str):
        """Send notification via injected callback (non-blocking)."""
        if self.notify:
            try:
                await self.notify(message)
            except Exception as e:
                logger.warning(f"⚠️ Notification failed: {e}")
