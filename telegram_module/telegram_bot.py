"""
Telegram Bot — Raphael AI Bot v2.0 (SMC Crypto Engine)
Wisdom Lord Raphael — Core SMC Analytical Engine & Crypto Risk Guard

On-demand only. No autonomous scanner. All scans initiated by Nyunk-sama.

Commands:
  /scan <SYM>   — run SMC scan for a symbol
  /start        — greeting + wallet overview
  /help         — command guide
  /balance      — wallet equity info
  /positions    — active positions + pending orders
  /cancelall    — cancel all pending limit orders
  /mode         — show or change operation mode (auto/manual)
  /history      — last 10 closed trades + win rate
  /status       — system health check

Operation Modes:
  manual (default) — bot sends EXECUTE signal + inline buttons, you confirm
  auto             — bot places Limit Order on Bitget automatically on EXECUTE
"""

import asyncio
import logging
import re
from datetime import datetime
from typing import Any, Dict, Optional

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
)

from ai_module.gemini_client import GeminiClient
from config import Config
from database.database import Database
from exchange.bitget_client import BitgetClient
from smc_engine.detector import SMCDetector


logger = logging.getLogger(__name__)

CB_EXECUTE_PREFIX = "exec:"
CB_SKIP_PREFIX    = "skip:"


class RaphaelTelegramBot:
    """
    On-demand Telegram interface for Raphael v2.0.

    Lifecycle:
        bot = RaphaelTelegramBot(config, exchange, db)
        await bot.start()
        ...
        await bot.stop()
    """

    def __init__(
        self,
        config: Config,
        exchange: BitgetClient,
        database: Database,
    ):
        self.config   = config
        self.exchange = exchange
        self.db       = database
        self.detector = SMCDetector()
        self.gemini   = GeminiClient(config)

        # Pending EXECUTE signals awaiting manual confirmation
        # key = scan_id, value = extracted order params dict
        self._pending_signals: Dict[str, Dict[str, Any]] = {}

        self.application = (
            Application.builder().token(config.telegram_bot_token).build()
        )
        self._register_handlers()
        logger.info("🤖 RaphaelTelegramBot v2.0 initialized (on-demand mode)")

    # ── Handler Registration ───────────────────────────────────────────────

    def _register_handlers(self):
        app = self.application
        app.add_handler(CommandHandler("start",     self._cmd_start))
        app.add_handler(CommandHandler("help",      self._cmd_help))
        app.add_handler(CommandHandler("scan",      self._cmd_scan))
        app.add_handler(CommandHandler("balance",   self._cmd_balance))
        app.add_handler(CommandHandler("positions", self._cmd_positions))
        app.add_handler(CommandHandler("cancelall", self._cmd_cancelall))
        app.add_handler(CommandHandler("mode",      self._cmd_mode))
        app.add_handler(CommandHandler("history",   self._cmd_history))
        app.add_handler(CommandHandler("status",    self._cmd_status))
        app.add_handler(CallbackQueryHandler(self._cb_handler))
        app.add_error_handler(self._error_handler)
        logger.info("✅ Telegram handlers registered")

    # ── Lifecycle ──────────────────────────────────────────────────────────

    async def start(self):
        logger.info("🚀 Starting Raphael Telegram Bot...")
        await self.application.initialize()
        await self.application.start()
        await self.application.updater.start_polling(drop_pending_updates=True)

        # Restore operation mode from DB if previously saved
        saved_mode = await self.db.get_state("operation_mode")
        if saved_mode in ("auto", "manual"):
            self.config.operation_mode = saved_mode
            logger.info(f"⚙️  Operation mode restored: {saved_mode}")

        logger.info(
            f"✅ Raphael Bot running | mode={self.config.operation_mode}"
        )

    async def stop(self):
        logger.info("⏸️  Stopping Raphael Telegram Bot...")
        await self.application.updater.stop()
        await self.application.stop()
        await self.application.shutdown()
        logger.info("✅ Raphael Telegram Bot stopped")

    # ── Auth ───────────────────────────────────────────────────────────────

    def _is_authorised(self, user_id: int) -> bool:
        return str(user_id) == str(self.config.telegram_user_id)

    # ── Commands ───────────────────────────────────────────────────────────

    async def _cmd_start(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if not self._is_authorised(update.effective_user.id):
            await update.message.reply_text("⛔ Access denied.")
            return

        balance  = await self.exchange.fetch_balance()
        equity   = balance.get("equity_usdt", 0.0)
        max_risk = self.config.get_max_risk_usdt(equity)
        max_pos  = self.config.get_max_positions(equity)
        mode_icon = "🤖" if self.config.is_auto_mode() else "✋"

        await self._safe_reply(update, f"""
🎯 *Wisdom Lord Raphael v2.0 — SMC Crypto Engine*

Selamat datang, Nyunk-sama. Sistem siap beroperasi.

💰 *Wallet Equity:* `${equity:.4f} USDT`
🛡️ *Max Risk/Trade:* `${max_risk:.4f} USDT` ({self.config.risk_percent_per_trade:.0f}%)
📊 *Max Positions:* `{max_pos}` (dynamic)
⚙️ *Leverage:* `{self.config.default_leverage}x default / {self.config.max_leverage}x max`
{mode_icon} *Mode:* `{self.config.operation_mode.upper()}`

*Commands:*
`/scan SOLUSDT` — SMC scan on-demand
`/balance` — wallet info
`/positions` — posisi aktif
`/cancelall` — cancel semua order
`/mode [auto|manual]` — ganti mode
`/history` — riwayat trade
`/status` — system health
""")

    async def _cmd_help(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        await self._safe_reply(update, """
📚 *Raphael v2.0 — Help Guide*

*On-Demand Scan:*
`/scan SOLUSDT` — jalankan SMC scan lengkap.
Bot pull candle data dari Bitget → SMC detection →
Gemini AI analysis → Kakunin/Kai/Koku response.

*Manual Mode (default):*
Setelah EXECUTE signal → muncul tombol ✅ EXECUTE / ❌ SKIP.
Lu yang putuskan. Bot tidak otomatis order.

*Auto Mode:*
Bot langsung pasang Limit Order di Bitget setelah EXECUTE.
Aktifkan dengan `/mode auto`.

*SMC Rules (tidak bisa dikompromikan):*
• SL distance ≤ 1.5% dari entry
• RRR minimum 1:3.0
• CHOCH M5 wajib terkonfirmasi
• H1 Bias NEUTRAL → SKIP
• Max positions dynamic (equity-based)

*Commands:*
`/scan <SYMBOL>` — scan on-demand
`/balance` — equity, available, uPnL
`/positions` — posisi running + pending
`/cancelall` — cancel semua pending order
`/mode` — lihat mode aktif
`/mode auto` — aktifkan auto-execute
`/mode manual` — kembali ke manual
`/history` — 10 trade terakhir + win rate
`/status` — system health

Presisi adalah segalanya, Nyunk-sama. 🛡️
""")

    async def _cmd_scan(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if not self._is_authorised(update.effective_user.id):
            await update.message.reply_text("⛔ Access denied.")
            return

        args = ctx.args or []
        if not args:
            await update.message.reply_text(
                "Usage: `/scan SOLUSDT`", parse_mode="Markdown"
            )
            return

        symbol = args[0].upper().strip()
        await self._safe_reply(
            update, f"🔍 Memulai SMC scan untuk *{symbol}*...", md=True
        )

        result = await self._run_scan(symbol)
        await self._deliver_scan_result(update, result)

    async def _cmd_balance(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if not self._is_authorised(update.effective_user.id):
            return
        try:
            b        = await self.exchange.fetch_balance()
            equity   = b.get("equity_usdt", 0.0)
            max_risk = self.config.get_max_risk_usdt(equity)
            await self._safe_reply(update, f"""
💰 *Wallet — Bitget USDT-M Futures*

Total Equity    : `${equity:.4f} USDT`
Available       : `${b.get('available_usdt', 0.0):.4f} USDT`
Used Margin     : `${b.get('used_usdt', 0.0):.4f} USDT`
Unrealized PnL  : `${b.get('unrealized_pnl', 0.0):.4f} USDT`

🛡️ Max Risk/Trade : `${max_risk:.4f} USDT` ({self.config.risk_percent_per_trade:.0f}% equity)
""")
        except Exception as e:
            await update.message.reply_text(f"❌ Error: {e}")

    async def _cmd_positions(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if not self._is_authorised(update.effective_user.id):
            return
        try:
            positions = await self.exchange.fetch_positions()
            orders    = await self.exchange.fetch_open_orders()

            if not positions and not orders:
                await update.message.reply_text(
                    "📭 Tidak ada posisi aktif atau pending order, Nyunk-sama."
                )
                return

            msg = ""
            if positions:
                msg += f"📊 *Active Positions ({len(positions)})*\n\n"
                for p in positions:
                    upnl = p.get("unrealized_pnl", 0.0)
                    icon = "🟢" if upnl >= 0 else "🔴"
                    msg += (
                        f"{icon} *{p['symbol']}* {p['side']}\n"
                        f"  Size: `{p['size']}` | Entry: `{p['entry_price']}`\n"
                        f"  Mark: `{p['mark_price']}` | Liq: `{p['liquidation_price']}`\n"
                        f"  uPnL: `${upnl:.4f}` | {p['leverage']}x {p['margin_mode']}\n\n"
                    )
            if orders:
                msg += f"⏳ *Pending Orders ({len(orders)})*\n\n"
                for o in orders:
                    msg += (
                        f"📌 *{o['symbol']}* {o['side'].upper()}\n"
                        f"  Type: `{o['type']}` | Price: `{o['price']}`\n"
                        f"  Amount: `{o['amount']}` | ID: `{o['order_id']}`\n\n"
                    )
            await self._safe_reply(update, msg)
        except Exception as e:
            await update.message.reply_text(f"❌ Error: {e}")

    async def _cmd_cancelall(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if not self._is_authorised(update.effective_user.id):
            return
        try:
            await update.message.reply_text("🗑️ Cancelling all pending orders...")
            n = await self.exchange.cancel_all_orders()
            await update.message.reply_text(
                f"✅ {n} pending order{'s' if n != 1 else ''} cancelled, Nyunk-sama."
            )
        except Exception as e:
            await update.message.reply_text(f"❌ Error: {e}")

    async def _cmd_mode(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if not self._is_authorised(update.effective_user.id):
            return

        args = ctx.args or []
        if not args:
            icon = "🤖" if self.config.is_auto_mode() else "✋"
            await update.message.reply_text(
                f"{icon} Current mode: *{self.config.operation_mode.upper()}*\n\n"
                "Use `/mode auto` or `/mode manual` to switch.",
                parse_mode="Markdown",
            )
            return

        new_mode = args[0].lower().strip()
        if new_mode not in ("auto", "manual"):
            await update.message.reply_text(
                "❌ Invalid. Use `/mode auto` or `/mode manual`.",
                parse_mode="Markdown",
            )
            return

        self.config.operation_mode = new_mode
        await self.db.set_state("operation_mode", new_mode)

        if new_mode == "auto":
            await update.message.reply_text(
                "🤖 *Auto mode aktif.*\n"
                "Bot akan otomatis pasang Limit Order ke Bitget saat EXECUTE.\n\n"
                "⚠️ Pastikan balance cukup, Nyunk-sama.",
                parse_mode="Markdown",
            )
        else:
            await update.message.reply_text(
                "✋ *Manual mode aktif.*\n"
                "Bot kirim notifikasi + tombol konfirmasi untuk setiap EXECUTE.",
                parse_mode="Markdown",
            )

    async def _cmd_history(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if not self._is_authorised(update.effective_user.id):
            return
        try:
            trades  = await self.db.get_trade_history(limit=10)
            summary = await self.db.get_performance_summary()

            if not trades:
                await update.message.reply_text(
                    "📭 Belum ada riwayat trade, Nyunk-sama."
                )
                return

            msg = (
                f"📈 *Trade History (last {len(trades)})*\n\n"
                f"Win Rate : `{summary['win_rate']:.1f}%` "
                f"({summary['wins']}W / {summary['losses']}L)\n"
                f"Total PnL: `${summary['total_pnl']:.4f} USDT`\n"
                f"Avg RRR  : `1:{summary['avg_rrr']:.2f}`\n\n"
            )
            for t in trades:
                icon = {"CLOSED_TP": "🟢", "CLOSED_SL": "🔴", "CANCELLED": "⚫"}.get(
                    t["status"], "⚪"
                )
                pnl = t.get("pnl_usdt", 0.0) or 0.0
                msg += (
                    f"{icon} *{t['symbol']}* {t['side']}\n"
                    f"  Entry: `{t['entry_price']}` | PnL: `${pnl:.4f}`\n"
                    f"  {t['created_at'][:16]}\n\n"
                )
            await self._safe_reply(update, msg)
        except Exception as e:
            await update.message.reply_text(f"❌ Error: {e}")

    async def _cmd_status(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if not self._is_authorised(update.effective_user.id):
            return
        try:
            bitget_ok = await self.exchange.test_connection()
            gemini_ok = await self.gemini.test_connection()
            balance   = await self.exchange.fetch_balance()
            equity    = balance.get("equity_usdt", 0.0)
            max_pos   = self.config.get_max_positions(equity)

            live_pos = await self.exchange.fetch_positions()
            live_ord = await self.exchange.fetch_open_orders()
            live_active = len(live_pos) + len(live_ord)

            mode_icon = "🤖" if self.config.is_auto_mode() else "✋"
            await update.message.reply_text(
                f"🛠️ *System Status — Raphael v2.0*\n\n"
                f"Bitget API : {'✅ Connected' if bitget_ok else '❌ Error'}\n"
                f"Gemini AI  : {'✅ Connected' if gemini_ok else '❌ Error'}\n"
                f"Database   : ✅ Connected\n\n"
                f"{mode_icon} Mode      : `{self.config.operation_mode.upper()}`\n"
                f"💰 Equity   : `${equity:.4f} USDT`\n"
                f"📊 Positions: `{live_active}/{max_pos}` (dynamic limit)\n"
                f"⚙️ Leverage : `{self.config.default_leverage}x / {self.config.max_leverage}x max`\n"
                f"🧠 Model    : `{self.config.gemini_model}`",
                parse_mode="Markdown",
            )
        except Exception as e:
            await update.message.reply_text(f"❌ Status check error: {e}")

    # ── Inline Button Callbacks ────────────────────────────────────────────

    async def _cb_handler(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()

        if not self._is_authorised(query.from_user.id):
            await query.edit_message_text("⛔ Access denied.")
            return

        data = query.data or ""

        if data.startswith(CB_EXECUTE_PREFIX):
            scan_id = data[len(CB_EXECUTE_PREFIX):]
            await self._handle_execute_confirm(query, scan_id)
        elif data.startswith(CB_SKIP_PREFIX):
            scan_id = data[len(CB_SKIP_PREFIX):]
            self._pending_signals.pop(scan_id, None)
            await query.edit_message_text(
                f"⏭️ Signal `{scan_id}` skipped by Nyunk-sama.",
                parse_mode="Markdown",
            )

    async def _handle_execute_confirm(self, query, scan_id: str):
        params = self._pending_signals.get(scan_id)
        if not params:
            await query.edit_message_text(
                f"⚠️ Signal `{scan_id}` sudah expired atau tidak ditemukan.",
                parse_mode="Markdown",
            )
            return

        await query.edit_message_text(
            f"⚙️ Menempatkan Limit Order untuk `{params.get('symbol')}`...",
            parse_mode="Markdown",
        )

        try:
            order = await self.exchange.place_limit_order(
                symbol      = params["symbol"],
                side        = params.get("side_ccxt", "buy"),
                amount      = params["position_size"],
                price       = params["entry_price"],
                stop_loss   = params["stop_loss"],
                take_profit = params["take_profit"],
                leverage    = params.get("leverage", self.config.default_leverage),
            )

            trade_id = await self.db.save_trade({
                "trade_id":          scan_id,
                "symbol":            params["symbol"],
                "side":              params.get("side", "LONG"),
                "entry_price":       params["entry_price"],
                "stop_loss":         params["stop_loss"],
                "take_profit":       params["take_profit"],
                "position_size":     params["position_size"],
                "leverage":          params.get("leverage", self.config.default_leverage),
                "risk_usdt":         params.get("risk_usdt", 0.0),
                "rrr":               params.get("rrr", 0.0),
                "status":            "PENDING",
                "exchange_order_id": order.get("id"),
            })

            self._pending_signals.pop(scan_id, None)

            await query.edit_message_text(
                f"✅ *Order placed!*\n\n"
                f"Symbol  : `{params['symbol']}`\n"
                f"Side    : `{params.get('side', 'N/A')}`\n"
                f"Entry   : `{params['entry_price']}`\n"
                f"SL      : `{params['stop_loss']}`\n"
                f"TP      : `{params['take_profit']}`\n"
                f"Size    : `{params['position_size']}`\n"
                f"Leverage: `{params.get('leverage', self.config.default_leverage)}x`\n"
                f"Risk    : `${params.get('risk_usdt', 0.0):.4f} USDT`\n"
                f"Order ID: `{order.get('id', 'N/A')}`\n\n"
                f"Trade ID: `{trade_id}`",
                parse_mode="Markdown",
            )

        except Exception as e:
            logger.error(f"❌ _handle_execute_confirm({scan_id}): {e}", exc_info=True)
            await query.edit_message_text(
                f"❌ Order failed: `{e}`\n\nOrder tidak dieksekusi.",
                parse_mode="Markdown",
            )

    # ── Core Scan Pipeline ─────────────────────────────────────────────────

    async def _run_scan(self, symbol: str) -> Dict[str, Any]:
        """
        Full scan pipeline for one symbol:
          1. Fetch OHLCV (H1, M15, M5) from Bitget
          2. Run SMC detector
          3. Fetch wallet + live positions
          4. Send to Gemini AI
          5. Save scan to DB
          6. Return result dict
        """
        scan_id = f"scan_{symbol}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        logger.info(f"🔍 Starting scan: {scan_id}")

        try:
            # Fetch candles concurrently
            h1_candles, m15_candles, m5_candles = await asyncio.gather(
                self.exchange.fetch_ohlcv(symbol, "H1",  limit=100),
                self.exchange.fetch_ohlcv(symbol, "M15", limit=100),
                self.exchange.fetch_ohlcv(symbol, "M5",  limit=100),
            )

            # SMC algorithmic detection
            analysis    = self.detector.analyse(symbol, h1_candles, m15_candles, m5_candles)
            smc_section = self.detector.build_gemini_prompt_section(analysis)

            # Wallet + live positions concurrently
            balance, positions, open_orders = await asyncio.gather(
                self.exchange.fetch_balance(),
                self.exchange.fetch_positions(),
                self.exchange.fetch_open_orders(),
            )

            # Dynamic position limit from live equity
            equity      = balance.get("equity_usdt", 0.0)
            max_pos     = self.config.get_max_positions(equity)
            live_active = len(positions) + len(open_orders)

            logger.info(
                f"📊 {symbol} | Live: {len(positions)} pos + {len(open_orders)} orders "
                f"= {live_active}/{max_pos} | equity ${equity:.2f}"
            )

            # Gemini AI evaluation
            ai_result = await self.gemini.analyse_smc(
                symbol             = symbol,
                smc_data           = analysis.to_dict(),
                balance_data       = balance,
                positions          = positions,
                open_orders        = open_orders,
                smc_prompt_section = smc_section,
                live_active        = live_active,
                max_pos            = max_pos,
            )

            parsed   = ai_result.get("parsed_response", {})
            decision = parsed.get("decision", "UNKNOWN")

            # Persist SMC zones and scan
            await self.db.save_smc_zones(symbol, analysis.to_dict())
            await self.db.save_scan({
                "scan_id":         scan_id,
                "symbol":          symbol,
                "h1_bias":         analysis.h1_bias,
                "h1_bos":          analysis.h1_last_bos,
                "m5_choch":        analysis.m5_choch_type,
                "has_valid_setup": analysis.has_valid_setup,
                "setup_bias":      analysis.setup_bias,
                "skip_reason":     analysis.skip_reason,
                "parsed_response": parsed,
                "processing_time": ai_result.get("processing_time", 0.0),
            })

            # Cache signal params for manual confirmation
            if decision == "EXECUTE" and parsed.get("parameters"):
                params = parsed["parameters"]
                params["symbol"] = symbol
                self._pending_signals[scan_id] = params

            return {
                "scan_id":    scan_id,
                "symbol":     symbol,
                "decision":   decision,
                "analysis":   analysis,
                "ai_result":  ai_result,
                "balance":    balance,
                "positions":  positions,
                "open_orders": open_orders,
            }

        except Exception as e:
            logger.error(f"❌ _run_scan({symbol}): {e}", exc_info=True)
            return {
                "scan_id":  scan_id,
                "symbol":   symbol,
                "decision": "ERROR",
                "error":    str(e),
            }

    async def _deliver_scan_result(
        self,
        update: Update,
        result: Dict[str, Any],
    ):
        """Format and send scan result to Telegram."""
        symbol   = result.get("symbol", "?")
        scan_id  = result.get("scan_id", "?")
        decision = result.get("decision", "UNKNOWN")

        if decision == "ERROR":
            await self._safe_reply(
                update, f"❌ Scan error untuk *{symbol}*: `{result.get('error')}`"
            )
            return

        ai_result = result.get("ai_result", {})
        parsed    = ai_result.get("parsed_response", {})
        analysis  = result.get("analysis")
        params    = parsed.get("parameters", {})

        decision_icon = "✅" if decision == "EXECUTE" else "⏭️"

        msg = (
            f"🔍 *{symbol}* — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        )

        if analysis:
            msg += (
                f"🧭 H1 Bias   : `{analysis.h1_bias}` ({analysis.h1_last_bos})\n"
                f"🔷 M15 OBs   : `{len(analysis.m15_order_blocks)}` unmitigated\n"
                f"⚡ M5 CHOCH  : `{analysis.m5_choch_type}`\n"
                f"🎯 Valid Setup: `{'YES' if analysis.has_valid_setup else 'NO'}`\n\n"
            )

        msg += f"{decision_icon} *Decision: {decision}*\n\n"

        kakunin = parsed.get("kakunin", "")
        kai     = parsed.get("kai", "")
        koku    = parsed.get("koku", "")

        if kakunin:
            msg += f"*<< Kakunin >>*\n{kakunin}\n\n"
        if kai:
            msg += f"*<< Kai >>*\n{kai}\n\n"
        if koku:
            msg += f"*<< Koku >>*\n{koku}\n"

        if decision == "EXECUTE" and params:
            if self.config.is_manual_mode():
                keyboard = InlineKeyboardMarkup([[
                    InlineKeyboardButton(
                        "✅ EXECUTE", callback_data=f"{CB_EXECUTE_PREFIX}{scan_id}"
                    ),
                    InlineKeyboardButton(
                        "❌ SKIP",    callback_data=f"{CB_SKIP_PREFIX}{scan_id}"
                    ),
                ]])
                await self._notify(update, msg, reply_markup=keyboard)
            else:
                await self._notify(update, msg)
                await self._auto_execute(scan_id, symbol, params, update)
        else:
            await self._notify(update, msg)

    async def _auto_execute(
        self,
        scan_id: str,
        symbol: str,
        params: Dict[str, Any],
        update: Update,
    ):
        """Place order automatically in auto mode."""
        try:
            live_pos = await self.exchange.fetch_positions()
            live_ord = await self.exchange.fetch_open_orders()
            balance  = await self.exchange.fetch_balance()
            equity   = balance.get("equity_usdt", 0.0)
            max_pos  = self.config.get_max_positions(equity)
            active   = len(live_pos) + len(live_ord)

            if active >= max_pos:
                await self._notify(
                    update,
                    f"⚠️ Auto-execute skipped — {active}/{max_pos} positions occupied.",
                )
                return

            order = await self.exchange.place_limit_order(
                symbol      = symbol,
                side        = params.get("side_ccxt", "buy"),
                amount      = params["position_size"],
                price       = params["entry_price"],
                stop_loss   = params["stop_loss"],
                take_profit = params["take_profit"],
                leverage    = params.get("leverage", self.config.default_leverage),
            )

            await self.db.save_trade({
                "trade_id":          scan_id,
                "symbol":            symbol,
                "side":              params.get("side", "LONG"),
                "entry_price":       params["entry_price"],
                "stop_loss":         params["stop_loss"],
                "take_profit":       params["take_profit"],
                "position_size":     params["position_size"],
                "leverage":          params.get("leverage", self.config.default_leverage),
                "risk_usdt":         params.get("risk_usdt", 0.0),
                "rrr":               params.get("rrr", 0.0),
                "status":            "PENDING",
                "exchange_order_id": order.get("id"),
            })

            self._pending_signals.pop(scan_id, None)
            await self._notify(
                update,
                f"🤖 *Auto-execute complete!*\n"
                f"Symbol  : `{symbol}`\n"
                f"Entry   : `{params['entry_price']}`\n"
                f"SL      : `{params['stop_loss']}`\n"
                f"TP      : `{params['take_profit']}`\n"
                f"Size    : `{params['position_size']}`\n"
                f"Order ID: `{order.get('id', 'N/A')}`",
            )

        except Exception as e:
            logger.error(f"❌ _auto_execute({scan_id}): {e}", exc_info=True)
            await self._notify(
                update,
                f"❌ *Auto-execute FAILED* for `{symbol}`:\n`{e}`",
            )

    # ── Messaging Helpers ──────────────────────────────────────────────────

    async def _notify(
        self,
        update: Optional[Update],
        text: str,
        reply_markup: Optional[InlineKeyboardMarkup] = None,
    ):
        chunks = self._chunk(text)
        for i, chunk in enumerate(chunks):
            markup = reply_markup if i == len(chunks) - 1 else None
            try:
                if update and update.message:
                    await update.message.reply_text(
                        chunk, parse_mode="Markdown", reply_markup=markup
                    )
                else:
                    await self.application.bot.send_message(
                        chat_id      = self.config.telegram_user_id,
                        text         = chunk,
                        parse_mode   = "Markdown",
                        reply_markup = markup,
                    )
            except Exception as e:
                logger.warning(f"⚠️ Markdown failed ({e}), retrying plain text")
                try:
                    if update and update.message:
                        await update.message.reply_text(chunk, reply_markup=markup)
                    else:
                        await self.application.bot.send_message(
                            chat_id      = self.config.telegram_user_id,
                            text         = chunk,
                            reply_markup = markup,
                        )
                except Exception as e2:
                    logger.error(f"❌ Notification failed: {e2}")

    async def _safe_reply(self, update: Update, text: str, md: bool = True):
        for chunk in self._chunk(text):
            try:
                await update.message.reply_text(
                    chunk, parse_mode="Markdown" if md else None
                )
            except Exception:
                await update.message.reply_text(chunk)

    def _chunk(self, text: str, max_len: int = 3900) -> list[str]:
        if len(text) <= max_len:
            return [text]
        chunks: list[str] = []
        # Try split at << Koku >> boundary
        if re.search(r"<<\s*koku\s*>>", text, re.IGNORECASE):
            parts = re.split(r"(?=(?:<<\s*koku\s*>>))", text, flags=re.IGNORECASE)
            current = ""
            for p in parts:
                if len(current) + len(p) <= max_len:
                    current += p
                else:
                    if current.strip():
                        chunks.append(current.strip())
                    current = p
            if current.strip():
                chunks.append(current.strip())
            if all(len(c) <= max_len for c in chunks):
                return chunks
        # Fallback: paragraph splits
        chunks = []
        paragraphs = text.split("\n\n")
        current = ""
        for para in paragraphs:
            if len(current) + len(para) + 2 <= max_len:
                current += ("\n\n" if current else "") + para
            else:
                if current.strip():
                    chunks.append(current.strip())
                if len(para) > max_len:
                    for i in range(0, len(para), max_len):
                        chunks.append(para[i: i + max_len])
                    current = ""
                else:
                    current = para
        if current.strip():
            chunks.append(current.strip())
        return chunks or [text]

    # ── Error Handler ──────────────────────────────────────────────────────

    async def _error_handler(self, update: object, ctx: ContextTypes.DEFAULT_TYPE):
        logger.error(f"❌ Telegram error: {ctx.error}", exc_info=ctx.error)
        if isinstance(update, Update) and update.effective_message:
            try:
                await update.effective_message.reply_text(
                    f"⚠️ System error: `{ctx.error}`", parse_mode="Markdown"
                )
            except Exception:
                pass
