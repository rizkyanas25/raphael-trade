"""
Telegram Bot Module for Raphael AI Bot
Wisdom Lord Raphael - Core Analytical Engine & Financial Risk Guard

Two analysis modes:
  Mode 1 — Signal Evaluation : photo or text signal from group → EXECUTE/SKIP
  Mode 2 — Independent Analysis: /analyse SYMBOL [buy|sell] → EXECUTE/SKIP/WAIT

Paper trade recording:
  User-initiated via inline button after EXECUTE decision.
  Two-step confirmation (Opsi B).
  Auto-monitor runs in background — notifies on TP/SL hit, auto-closes.
"""

import json
import logging
import asyncio
from typing import Optional, Dict, Any
from datetime import datetime
from pathlib import Path
import tempfile
import os
import re

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    CallbackQueryHandler,
)

from config import Config
from mt5_module.mt5_connector import MT5Connector
from mt5_module.indicators import IndicatorCalculator
from database.database import Database
from ai_module.gemini_client import GeminiClient
from risk_management.risk_manager import RiskManager
from paper_trading.paper_trading import PaperTradingEngine
from telegram_module.response_formatter import ResponseFormatter


logger = logging.getLogger(__name__)

# Callback data prefixes
CB_TOGGLE_PAPER      = "toggle_paper"
CB_RECORD_PT_REQUEST = "pt_record_req:"   # + signal_id
CB_RECORD_PT_CONFIRM = "pt_record_yes:"   # + signal_id
CB_RECORD_PT_CANCEL  = "pt_record_no:"    # + signal_id


class RaphaelTelegramBot:
    """Telegram bot for Raphael AI trading signal analysis"""

    def __init__(self, config: Config, mt5_connector: MT5Connector, database: Database):
        self.config               = config
        self.mt5_connector        = mt5_connector
        self.database             = database
        self.indicator_calculator = IndicatorCalculator(config)
        self.gemini_client        = GeminiClient(config)
        self.risk_manager         = RiskManager(config)
        self.paper_trading        = PaperTradingEngine(config, database, self.risk_manager)
        self.response_formatter   = ResponseFormatter()

        # Wire notification callback into paper trading engine
        self.paper_trading.set_notify_callback(self._send_notification)

        # Pending paper trade confirmations: signal_id → trade_params dict
        self._pending_pt_confirm: Dict[str, Dict[str, Any]] = {}

        self.application = Application.builder().token(config.telegram_bot_token).build()
        self._register_handlers()

        logger.info("🤖 Raphael Telegram Bot initialized")

    # ── Handler Registration ──────────────────────────────────────────────

    def _register_handlers(self):
        self.application.add_handler(CommandHandler("start",       self.start_command))
        self.application.add_handler(CommandHandler("help",        self.help_command))
        self.application.add_handler(CommandHandler("status",      self.status_command))
        self.application.add_handler(CommandHandler("balance",     self.balance_command))
        self.application.add_handler(CommandHandler("positions",   self.positions_command))
        self.application.add_handler(CommandHandler("performance", self.performance_command))
        self.application.add_handler(CommandHandler("paper",       self.paper_trading_command))
        self.application.add_handler(CommandHandler("analyse",     self.analyse_command))

        self.application.add_handler(MessageHandler(filters.PHOTO,                    self.handle_signal_image))
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,  self.handle_signal_text))
        self.application.add_handler(CallbackQueryHandler(self.button_callback))
        self.application.add_error_handler(self._global_error_handler)

        logger.info("✅ Telegram bot handlers registered")

    # ── Lifecycle ─────────────────────────────────────────────────────────

    async def start(self):
        logger.info("🚀 Starting Raphael Telegram Bot...")
        await self.application.initialize()
        await self.application.start()
        await self.application.updater.start_polling()

        # Start paper trade background monitor
        await self.paper_trading.start_monitor()

        logger.info("✅ Raphael Telegram Bot is running")

    async def stop(self):
        logger.info("⏸️  Stopping Raphael Telegram Bot...")
        await self.paper_trading.stop_monitor()
        await self.application.updater.stop()
        await self.application.stop()
        await self.application.shutdown()
        logger.info("✅ Raphael Telegram Bot stopped")

    # ── Auth Helper ───────────────────────────────────────────────────────

    def _is_authorised(self, user_id: int) -> bool:
        return str(user_id) == self.config.telegram_user_id

    async def _global_error_handler(self, update: object, context: ContextTypes.DEFAULT_TYPE):
        """Global error handler for all unhandled telegram exceptions."""
        logger.error(f"❌ Telegram Unhandled Exception: {context.error}", exc_info=context.error)
        if isinstance(update, Update) and update.effective_message:
            try:
                await update.effective_message.reply_text(
                    f"⚠️ *Raphael System Notice*\nTerjadi kendala teknis: `{context.error}`",
                    parse_mode="Markdown"
                )
            except Exception:
                pass

    # ── Safe Messaging Helpers ───────────────────────────────────────────

    async def _send_notification(self, message: str):
        """Send Telegram message to the authorised user (used by paper trade engine)."""
        chunks = self._chunk_message(message, max_len=3900)
        for chunk in chunks:
            try:
                await self.application.bot.send_message(
                    chat_id=self.config.telegram_user_id,
                    text=chunk,
                    parse_mode="Markdown",
                )
            except Exception as e:
                logger.warning(f"⚠️ Notification markdown failed ({e}), retrying plain text")
                try:
                    await self.application.bot.send_message(
                        chat_id=self.config.telegram_user_id,
                        text=chunk,
                    )
                except Exception as e2:
                    logger.error(f"❌ Failed to send notification: {e2}")

    async def _safe_reply_text(
        self,
        update: Update,
        text: str,
        reply_markup: Optional[Any] = None
    ):
        """
        Safely reply to user with auto-chunking (max 3900 chars)
        and automatic Markdown parse-error fallback.
        """
        chunks = self._chunk_message(text, max_len=3900)
        for i, chunk in enumerate(chunks):
            # Only attach markup to the last chunk
            markup = reply_markup if i == len(chunks) - 1 else None
            try:
                await update.message.reply_text(
                    chunk,
                    parse_mode="Markdown",
                    reply_markup=markup
                )
            except Exception as e:
                logger.warning(f"⚠️ Telegram Markdown parsing failed ({e}), falling back to plain text")
                try:
                    await update.message.reply_text(
                        chunk,
                        reply_markup=markup
                    )
                except Exception as e2:
                    logger.error(f"❌ Failed to reply text even in plain text: {e2}", exc_info=True)

    def _chunk_message(self, text: str, max_len: int = 3900) -> list[str]:
        """Split long messages at clean section boundaries or line breaks."""
        if len(text) <= max_len:
            return [text]

        chunks = []
        # Try splitting at << Koku >> section first
        if re.search(r'<<\s*koku\s*>>', text, re.IGNORECASE):
            parts = re.split(r'(?=(?:<<\s*koku\s*>>))', text, flags=re.IGNORECASE)
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

        # Fallback to paragraph splitting
        paragraphs = text.split("\n\n")
        current = ""
        for para in paragraphs:
            if len(current) + len(para) + 2 <= max_len:
                current += ("\n\n" if current else "") + para
            else:
                if current.strip():
                    chunks.append(current.strip())
                if len(para) > max_len:
                    # Hard slice if a single paragraph is enormous
                    for sub in range(0, len(para), max_len):
                        chunks.append(para[sub:sub+max_len])
                    current = ""
                else:
                    current = para
        if current.strip():
            chunks.append(current.strip())
        return chunks if chunks else [text]

    # ── Commands ──────────────────────────────────────────────────────────

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        username = user.username or user.first_name or "Unknown"
        logger.info(f"📥 [USER {user.id} (@{username})] Command: /start")
        if not self._is_authorised(update.effective_user.id):
            logger.warning(f"⛔ Unauthorized access attempt by {user.id}")
            await update.message.reply_text("⛔ Access denied. This bot is only authorized for Nyunk-sama.")
            return

        equity = self.mt5_connector.get_account_info().get("equity", 0)
        max_risk = self.config.get_max_risk_idr(equity)

        await update.message.reply_text(f"""
🎯 *Wisdom Lord Raphael — Core Analytical Engine & Financial Risk Guard*

Greetings, Nyunk-sama! Ready to serve with precision.

📡 *Commands:*
/start — Initialize
/help — Full guide
/status — System health
/balance — Account info
/positions — Open positions
/performance — Trade metrics
/paper — Paper trading status
/analyse SYMBOL \\[buy\\|sell\\] — Independent market analysis

📸 *Signal Analysis:*
• Send a signal screenshot → Mode 1 evaluation
• Paste signal text → Mode 1 evaluation
• `/analyse GBPJPY buy` → Mode 2 independent analysis

⚡ *Risk Protocol Active:*
• Max Risk: Rp {max_risk:,.0f} ({self.config.risk_percent_per_trade:.0f}% of equity)
• Multi-timeframe: H4 → H2 → H1 → M15
• RRR minimum: 1:{self.config.min_rrr}
• Paper trading: {'✅ ON' if self.config.paper_trading_enabled else '❌ OFF'}

Ready, Nyunk-sama! 🛡️
""", parse_mode="Markdown")

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        username = user.username or user.first_name or "Unknown"
        logger.info(f"📥 [USER {user.id} (@{username})] Command: /help")
        await update.message.reply_text("""
📚 *Raphael AI Bot — Help Guide*

🎯 *Two Analysis Modes:*
*Mode 1 — Signal Evaluation*
Send a signal photo or paste signal text.
Raphael evaluates against your live equity & indicators.

*Mode 2 — Independent Analysis*
`/analyse GBPJPY` — Raphael finds setup from scratch
`/analyse GBPJPY buy` — with direction hint
`/analyse GBPJPY sell` — with direction hint
Same full analysis, same risk rules.

📊 *Output Format (both modes):*
`<<Kakunin>>` — Data verification & account status
`<<Kai>>` — Top-down analysis H4→H2→H1→M15
`<<Koku>>` — EXECUTE/SKIP with MT5 parameters

📝 *Paper Trading:*
After EXECUTE decision → tap *Record Paper Trade*
→ Confirm → Auto-monitored 24/7
→ Get notified when TP/SL hit

⚙️ *Risk Rules (all modes):*
• Risk = % of live equity (dynamic, not hardcoded)
• RRR minimum 1:2
• Max 3 concurrent positions
• Margin Level minimum 500%
• High-vol instruments require minimum equity

Need assistance, Nyunk-sama? 🛡️
""", parse_mode="Markdown")

    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        username = user.username or user.first_name or "Unknown"
        logger.info(f"📥 [USER {user.id} (@{username})] Command: /status")
        pt_metrics = self.paper_trading.get_performance_metrics()
        msg = self.response_formatter.format_system_status(
            mt5_connected=self.mt5_connector.is_connected,
            ai_ready=True,
            db_ready=True,
            paper_trading_enabled=self.config.paper_trading_enabled,
            pending_trades=pt_metrics.get("pending_trades", 0),
            active_trades=pt_metrics.get("active_trades", 0),
        )
        await update.message.reply_text(msg, parse_mode="Markdown")

    async def balance_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        username = user.username or user.first_name or "Unknown"
        logger.info(f"📥 [USER {user.id} (@{username})] Command: /balance")
        if not self._is_authorised(update.effective_user.id):
            logger.warning(f"⛔ Unauthorized access attempt by {user.id}")
            return
        try:
            info     = self.mt5_connector.get_account_info()
            currency = info.get("currency", "IDR")
            fmt      = lambda v: f"Rp {v:,.2f}" if currency == "IDR" else f"{currency} {v:,.2f}"
            equity   = info.get("equity", 0)
            max_risk = self.config.get_max_risk_idr(equity)

            await update.message.reply_text(f"""
💰 *Account Information*

👤 *Account:* {info.get('login', 'Unknown')}
💵 *Balance:* {fmt(info.get('balance', 0))}
💎 *Equity:* {fmt(equity)}
📊 *Margin:* {fmt(info.get('margin', 0))}
🆓 *Free Margin:* {fmt(info.get('margin_free', 0))}
📈 *Margin Level:* {info.get('margin_level', 0):.2f}%
💹 *Floating P/L:* {fmt(info.get('profit', 0))}

🏦 *Server:* {info.get('server', 'Unknown')}
💱 *Currency:* {currency}

🛡️ *Max Risk per Trade:* Rp {max_risk:,.0f} ({self.config.risk_percent_per_trade:.0f}% equity)
""", parse_mode="Markdown")
        except Exception as e:
            logger.error(f"❌ balance_command: {e}", exc_info=True)
            await update.message.reply_text(f"❌ Error: {e}")

    async def positions_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        username = user.username or user.first_name or "Unknown"
        logger.info(f"📥 [USER {user.id} (@{username})] Command: /positions")
        if not self._is_authorised(update.effective_user.id):
            logger.warning(f"⛔ Unauthorized access attempt by {user.id}")
            return
        try:
            positions = self.mt5_connector.get_open_positions()
            if not positions:
                await update.message.reply_text("📭 No open positions, Nyunk-sama.")
                return
            msg = f"📊 *Open Positions ({len(positions)})*\n\n"
            for p in positions:
                direction = "📈 BUY" if p["type"] == 0 else "📉 SELL"
                msg += (
                    f"{direction} *{p['symbol']}*\n"
                    f"🎫 Ticket: {p['ticket']}\n"
                    f"📊 Volume: {p['volume']:.2f}\n"
                    f"💰 Entry: {p['price_open']:.5f}\n"
                    f"📍 Current: {p['price_current']:.5f}\n"
                    f"🛡️ SL: {p['sl']:.5f}\n"
                    f"🎯 TP: {p['tp']:.5f}\n"
                    f"💹 P/L: Rp {p['profit']:,.2f}\n"
                    f"⏰ {p['time'].strftime('%Y-%m-%d %H:%M')}\n---\n"
                )
            await update.message.reply_text(msg, parse_mode="Markdown")
        except Exception as e:
            logger.error(f"❌ positions_command: {e}", exc_info=True)
            await update.message.reply_text(f"❌ Error: {e}")

    async def performance_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        username = user.username or user.first_name or "Unknown"
        logger.info(f"📥 [USER {user.id} (@{username})] Command: /performance")
        if not self._is_authorised(update.effective_user.id):
            logger.warning(f"⛔ Unauthorized access attempt by {user.id}")
            return
        try:
            metrics = await self.database.calculate_performance_metrics(
                period="all", paper_trade_only=self.config.paper_trading_enabled
            )
            msg = self.response_formatter.format_performance_metrics(
                metrics, self.config.paper_trading_enabled
            )
            await update.message.reply_text(msg, parse_mode="Markdown")
        except Exception as e:
            logger.error(f"❌ performance_command: {e}", exc_info=True)
            await update.message.reply_text(f"❌ Error: {e}")

    async def paper_trading_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        username = user.username or user.first_name or "Unknown"
        logger.info(f"📥 [USER {user.id} (@{username})] Command: /paper")
        if not self._is_authorised(update.effective_user.id):
            logger.warning(f"⛔ Unauthorized access attempt by {user.id}")
            return
        metrics   = self.paper_trading.get_performance_metrics()
        readiness = self.paper_trading.check_readiness_for_live_trading()
        msg       = self.response_formatter.format_paper_trading_status(
            enabled=self.config.paper_trading_enabled,
            metrics=metrics,
            readiness=readiness,
        )
        keyboard = [[InlineKeyboardButton("Toggle Paper Trading", callback_data=CB_TOGGLE_PAPER)]]
        await update.message.reply_text(
            msg, parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    # ── Mode 2: /analyse command ──────────────────────────────────────────

    async def analyse_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Mode 2 — Independent Market Analysis.

        Usage:
          /analyse GBPJPY           → pure objective
          /analyse GBPJPY buy       → with direction hint
          /analyse GBPJPY sell      → with direction hint
        """
        args = context.args or []
        user = update.effective_user
        username = user.username or user.first_name or "Unknown"
        logger.info(f"📥 [USER {user.id} (@{username})] Command: /analyse {' '.join(args) if args else ''}")

        if not self._is_authorised(update.effective_user.id):
            logger.warning(f"⛔ Unauthorized access attempt by {user.id}")
            await update.message.reply_text("⛔ Access denied.")
            return

        if not args:
            await update.message.reply_text(
                "Usage: `/analyse SYMBOL` or `/analyse SYMBOL buy` or `/analyse SYMBOL sell`",
                parse_mode="Markdown",
            )
            return

        symbol = args[0].upper().strip()
        direction_hint: Optional[str] = None

        if len(args) >= 2:
            hint = args[1].lower().strip()
            if hint in ("buy", "long"):
                direction_hint = "BUY"
            elif hint in ("sell", "short"):
                direction_hint = "SELL"

        logger.info(f"📊 Mode 2 Analyse Request -> Symbol: {symbol} | Direction Hint: {direction_hint}")
        await update.message.reply_text(
            f"🔍 Independent analysis dimulai untuk *{symbol}*"
            + (f" dengan direction hint: *{direction_hint}*" if direction_hint else "")
            + "\n\n📡 Collecting MT5 data...",
            parse_mode="Markdown",
        )

        await self._process_signal(
            update,
            image_path=None,
            text_content="",
            symbol_override=symbol,
            direction_hint=direction_hint,
            mode="analyse",
        )

    # ── Signal Handlers ───────────────────────────────────────────────────

    async def handle_signal_image(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        username = user.username or user.first_name or "Unknown"
        logger.info(f"📥 [USER {user.id} (@{username})] Received Photo Signal")

        if not self._is_authorised(update.effective_user.id):
            logger.warning(f"⛔ Unauthorized photo access attempt by {user.id}")
            await update.message.reply_text("⛔ Access denied.")
            return
        try:
            photo_file = await update.message.photo[-1].get_file()
            with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
                await photo_file.download_to_drive(tmp.name)
                temp_path = tmp.name
            logger.info(f"📸 Signal image downloaded to temporary path: {temp_path}")
            await update.message.reply_text("📸 Signal image received. Analyzing with Raphael Protocol...")
            await self._process_signal(update, image_path=temp_path, text_content="", mode="signal")
            os.unlink(temp_path)
        except Exception as e:
            logger.error(f"❌ handle_signal_image: {e}", exc_info=True)
            await update.message.reply_text(f"❌ Error processing signal: {e}")

    async def handle_signal_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        username = user.username or user.first_name or "Unknown"
        text = update.message.text
        logger.info(f"📥 [USER {user.id} (@{username})] Received Text Signal:\n{text}")

        if not self._is_authorised(update.effective_user.id):
            logger.warning(f"⛔ Unauthorized text access attempt by {user.id}")
            await update.message.reply_text("⛔ Access denied.")
            return
        try:
            await update.message.reply_text("📝 Signal text received. Analyzing with Raphael Protocol...")
            await self._process_signal(
                update, image_path=None,
                text_content=text,
                mode="signal",
            )
        except Exception as e:
            logger.error(f"❌ handle_signal_text: {e}", exc_info=True)
            await update.message.reply_text(f"❌ Error processing signal: {e}")

    # ── Core Analysis Pipeline ────────────────────────────────────────────

    async def _process_signal(
        self,
        update: Update,
        image_path: Optional[str] = None,
        text_content: str = "",
        symbol_override: Optional[str] = None,
        direction_hint: Optional[str] = None,
        mode: str = "signal",   # "signal" | "analyse"
    ):
        """
        Unified pipeline for Mode 1 (signal) and Mode 2 (analyse).
        Risk check uses live equity in all cases.
        """
        try:
            signal_id = f"{'sig' if mode == 'signal' else 'ana'}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            logger.info(f"🚀 Processing pipeline [{signal_id}] | Mode: {mode} | Override Symbol: {symbol_override}")

            # ── Collect MT5 data ──────────────────────────────────────────
            account_info      = self.mt5_connector.get_account_info(force_refresh=True)
            current_positions = self.mt5_connector.get_open_positions()
            equity            = account_info.get("equity", 0)

            symbol = symbol_override or self._extract_symbol_from_signal(text_content)
            indicators     = self.indicator_calculator.get_indicators_for_symbol(symbol)
            current_prices = self.mt5_connector.get_current_prices(symbol)

            logger.info(
                f"📊 Live MT5 Snapshot -> Equity: Rp {equity:,.0f} | "
                f"Symbol: {symbol} | Bid: {current_prices.get('bid')} | Ask: {current_prices.get('ask')} | "
                f"Open Positions: {len(current_positions)}"
            )

            mt5_data = {
                "account_info":      account_info,
                "current_positions": current_positions,
                "indicators":        indicators,
                "current_prices":    current_prices,
                "symbol":            symbol,
            }

            # ── Build signal_data for Gemini ──────────────────────────────
            signal_data = {
                "signal_id":      signal_id,
                "image_path":     image_path,
                "text_content":   text_content,
                "mode":           mode,
                "direction_hint": direction_hint,
                "timestamp":      datetime.now().isoformat(),
            }

            # ── AI analysis ───────────────────────────────────────────────
            await update.message.reply_text("🧠 Analyzing with Gemini AI...")
            ai_response = await self.gemini_client.analyze_signal(signal_data, mt5_data)

            parsed     = ai_response.get("parsed_response", {})
            decision   = parsed.get("decision", "UNKNOWN")
            parameters = parsed.get("parameters", {})

            # ── Risk validation (always runs, all modes) ──────────────────
            risk_validation = None
            if parameters and parameters.get("entry_price"):
                risk_validation = self.risk_manager.validate_trade_setup(
                    symbol               = symbol,
                    order_type           = parameters.get("order_type", "BUY"),
                    entry_price          = float(parameters.get("entry_price", 0)),
                    stop_loss            = float(parameters.get("stop_loss", 0)),
                    take_profit          = float(parameters.get("take_profit", 0)),
                    account_equity       = equity,
                    timeframe            = parameters.get("timeframe", "H1"),
                    current_positions    = len(current_positions),
                    margin_level_percent = account_info.get("margin_level", 9999),
                )

                # Override decision to SKIP if hard_skip triggered by risk engine
                if risk_validation.get("hard_skip") and decision == "EXECUTE":
                    decision = "RISK_SKIP"
                    logger.warning(
                        f"⚠️ Decision overridden to RISK_SKIP for {symbol}: "
                        f"{risk_validation['skip_reasons']}"
                    )

            # ── Format and send response ──────────────────────────────────
            formatted = self.response_formatter.format_analysis_response(
                ai_response, mt5_data, {"risk_analysis": risk_validation}, mode=mode
            )
            await self._safe_reply_text(update, formatted)

            # ── Paper trade button (only if EXECUTE and paper trading on) ─
            if decision == "EXECUTE" and self.config.paper_trading_enabled and parameters:
                await self._send_paper_trade_button(
                    update, signal_id, symbol, parameters,
                    risk_validation, equity, mode,
                )

            # ── Save to DB ────────────────────────────────────────────────
            await self.database.save_signal_analysis({
                "signal_id":       signal_id,
                "image_path":      image_path,
                "text_content":    text_content,
                "mt5_data":        mt5_data,
                "ai_response":     ai_response,
                "kakunin_data":    parsed.get("kakunin", ""),
                "kai_data":        parsed.get("kai", ""),
                "koku_decision":   decision,
                "koku_parameters": parameters,
                "processing_time": ai_response.get("processing_time", 0.0),
            })

            logger.info(f"✅ {signal_id} processed | decision={decision}")

        except Exception as e:
            logger.error(f"❌ _process_signal: {e}", exc_info=True)
            err_msg = self.response_formatter.format_error_response(str(e))
            await self._safe_reply_text(update, err_msg)

    # ── Paper Trade Button Flow ───────────────────────────────────────────

    async def _send_paper_trade_button(
        self,
        update: Update,
        signal_id: str,
        symbol: str,
        parameters: Dict[str, Any],
        risk_validation: Optional[Dict[str, Any]],
        equity: float,
        mode: str,
    ):
        """Step 1: Show initial 'Record Paper Trade' button."""
        risk  = risk_validation or {}
        ra    = risk.get("risk_analysis", {}) or {}
        rrra  = risk.get("rrr_analysis", {}) or {}

        lot        = ra.get("recommended_lot", parameters.get("lot_size", 0.01))
        risk_idr   = ra.get("actual_risk_idr", 0)
        risk_pct   = ra.get("risk_percent", 0)
        rrr        = rrra.get("rrr", 0)
        reward_idr = risk_idr * rrr if rrr else 0

        # Store pending confirmation data
        self._pending_pt_confirm[signal_id] = {
            "signal_id":    signal_id,
            "symbol":       symbol,
            "order_type":   parameters.get("order_type", "BUY"),
            "entry_price":  float(parameters.get("entry_price", 0)),
            "stop_loss":    float(parameters.get("stop_loss", 0)),
            "take_profit":  float(parameters.get("take_profit", 0)),
            "lot_size":     lot,
            "timeframe":    parameters.get("timeframe", "H1"),
            "strategy":     f"{'Signal' if mode == 'signal' else 'Analyse'}_Mode{'1' if mode == 'signal' else '2'}",
            "equity":       equity,
            "risk_idr":     risk_idr,
            "reward_idr":   reward_idr,
            "rrr":          rrr,
            "risk_pct":     risk_pct,
        }

        msg = (
            f"📝 *EXECUTE — {symbol} {parameters.get('order_type', '')}*\n"
            f"Entry: `{parameters.get('entry_price', 'N/A')}`  "
            f"SL: `{parameters.get('stop_loss', 'N/A')}`  "
            f"TP: `{parameters.get('take_profit', 'N/A')}`\n"
            f"Lot: `{lot}` | Risk: Rp {risk_idr:,.0f} ({risk_pct:.1f}%) | RRR: 1:{rrr:.2f}"
        )

        keyboard = [[
            InlineKeyboardButton("📝 Record Paper Trade", callback_data=f"{CB_RECORD_PT_REQUEST}{signal_id}"),
        ]]
        await update.message.reply_text(
            msg, parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )

    async def _send_paper_trade_confirm(self, query, signal_id: str):
        """Step 2: Show confirmation dialog with full trade details."""
        data = self._pending_pt_confirm.get(signal_id)
        if not data:
            await query.edit_message_text("❌ Data trade tidak ditemukan atau sudah expired.")
            return

        msg = (
            f"📝 *Konfirmasi Paper Trade?*\n\n"
            f"*{data['symbol']}* {data['order_type']}\n"
            f"Entry : `{data['entry_price']}`\n"
            f"SL    : `{data['stop_loss']}`\n"
            f"TP    : `{data['take_profit']}`\n"
            f"Lot   : `{data['lot_size']}`\n\n"
            f"💰 Risk    : Rp {data['risk_idr']:,.0f} ({data['risk_pct']:.1f}% equity)\n"
            f"🎯 Reward  : Rp {data['reward_idr']:,.0f}\n"
            f"⚖️ RRR    : 1:{data['rrr']:.2f}\n"
            f"📋 Strategy: {data['strategy']}"
        )

        keyboard = [[
            InlineKeyboardButton("✅ Ya, Record", callback_data=f"{CB_RECORD_PT_CONFIRM}{signal_id}"),
            InlineKeyboardButton("❌ Batal",       callback_data=f"{CB_RECORD_PT_CANCEL}{signal_id}"),
        ]]
        await query.edit_message_text(
            msg, parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )

    # ── Button Callback ───────────────────────────────────────────────────

    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query   = update.callback_query
        user_id = query.from_user.id

        if not self._is_authorised(user_id):
            await query.answer("⛔ Access denied.")
            return

        await query.answer()
        data = query.data

        # ── Toggle paper trading ──────────────────────────────────────────
        if data == CB_TOGGLE_PAPER:
            new_state  = not self.config.paper_trading_enabled
            self.config.paper_trading_enabled = new_state
            self.paper_trading.toggle_paper_trading(new_state)
            label = "✅ ENABLED" if new_state else "❌ DISABLED"
            await query.edit_message_text(
                f"📝 Paper trading is now *{label}*\n"
                f"⚠️ Session-only. Update `.env` to persist.",
                parse_mode="Markdown",
            )

        # ── Step 1: Request confirmation ──────────────────────────────────
        elif data.startswith(CB_RECORD_PT_REQUEST):
            signal_id = data[len(CB_RECORD_PT_REQUEST):]
            await self._send_paper_trade_confirm(query, signal_id)

        # ── Step 2a: User confirmed ───────────────────────────────────────
        elif data.startswith(CB_RECORD_PT_CONFIRM):
            signal_id = data[len(CB_RECORD_PT_CONFIRM):]
            pt_data   = self._pending_pt_confirm.pop(signal_id, None)

            if not pt_data:
                await query.edit_message_text("❌ Data trade tidak ditemukan.")
                return

            result = await self.paper_trading.record_paper_trade(
                signal_id    = signal_id,
                symbol       = pt_data["symbol"],
                order_type   = pt_data["order_type"],
                entry_price  = pt_data["entry_price"],
                stop_loss    = pt_data["stop_loss"],
                take_profit  = pt_data["take_profit"],
                lot_size     = pt_data["lot_size"],
                timeframe    = pt_data["timeframe"],
                strategy     = pt_data["strategy"],
                account_equity = pt_data["equity"],
            )

            if result["success"]:
                await query.edit_message_text(
                    f"✅ *Paper Trade Recorded!*\n\n"
                    f"{pt_data['symbol']} {pt_data['order_type']} @ {pt_data['entry_price']}\n"
                    f"Risk: Rp {pt_data['risk_idr']:,.0f} | RRR: 1:{pt_data['rrr']:.2f}\n"
                    f"Expires: {result.get('expire_at', '').strftime('%Y-%m-%d') if result.get('expire_at') else 'N/A'}\n\n"
                    f"🔍 Auto-monitor aktif — akan notif saat TP/SL hit.",
                    parse_mode="Markdown",
                )
            else:
                await query.edit_message_text(
                    f"❌ Gagal record paper trade: {result.get('message', 'Unknown error')}"
                )

        # ── Step 2b: User cancelled ───────────────────────────────────────
        elif data.startswith(CB_RECORD_PT_CANCEL):
            signal_id = data[len(CB_RECORD_PT_CANCEL):]
            self._pending_pt_confirm.pop(signal_id, None)
            await query.edit_message_text("❌ Paper trade dibatalkan.")

    # ── Helpers ───────────────────────────────────────────────────────────

    def _extract_symbol_from_signal(self, text: str) -> str:
        """Extract trading symbol from signal text."""
        known = [
            "EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "NZDUSD", "USDCHF", "USDCAD",
            "EURGBP", "EURJPY", "GBPJPY", "AUDJPY", "CADJPY", "CHFJPY", "NZDCAD",
            "GBPCAD", "EURCAD", "AUDCAD", "AUDNZD", "NZDJPY",
            "XAUUSD", "XAGUSD", "BTCUSD", "ETHUSD",
            "JPN225", "US30", "NAS100", "UK100", "GER40",
        ]
        upper = text.upper()
        for sym in known:
            if sym in upper:
                return sym
        return "EURUSD"
