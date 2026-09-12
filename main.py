"""
Raphael AI Bot v2.0 — Main Entry Point
Wisdom Lord Raphael — Core SMC Analytical Engine & Crypto Risk Guard

Boot sequence:
  1. Load config
  2. Connect to Bitget Futures (ccxt)
  3. Initialise SQLite database
  4. Start Telegram bot + autonomous SMC scanner
  5. Run until KeyboardInterrupt

Run:
    python main.py

Keep alive on macOS (prevent sleep):
    caffeinate -i python main.py
"""

import asyncio
import logging

from config import Config
from database.database import Database
from exchange.bitget_client import BitgetClient
from telegram_module.telegram_bot import RaphaelTelegramBot
from utils.logger import setup_logging


async def main():
    setup_logging()
    logger = logging.getLogger(__name__)

    logger.info("━" * 60)
    logger.info("🎯  Wisdom Lord Raphael v2.0 — SMC Crypto Engine")
    logger.info("📡  Exchange : Bitget USDT-M Futures")
    logger.info("🧠  AI       : Google Gemini")
    logger.info("🛡️   Strategy : Pure Price Action & SMC")
    logger.info("━" * 60)

    exchange: BitgetClient | None = None
    bot: RaphaelTelegramBot | None = None

    try:
        # ── Config ────────────────────────────────────────────────────────
        config = Config()
        logger.info(
            f"⚙️  Risk: {config.risk_percent_per_trade:.0f}% equity/trade | "
            f"Max SL: {config.max_sl_distance_percent:.1f}% | "
            f"Min RRR: 1:{config.min_rrr} | "
            f"Mode: {config.operation_mode.upper()}"
        )

        # ── Exchange ──────────────────────────────────────────────────────
        exchange = BitgetClient(config)
        await exchange.connect()

        # Quick sanity check — fetch balance to confirm credentials work
        balance = await exchange.fetch_balance()
        equity  = balance.get("equity_usdt", 0.0)
        logger.info(
            f"💰  Wallet: ${equity:.4f} USDT equity | "
            f"${balance.get('available_usdt', 0.0):.4f} available"
        )

        if equity < 1.0:
            logger.warning(
                "⚠️  Equity < $1 USDT. Most orders will fail minimum notional checks. "
                "Deposit more funds before live trading."
            )

        # ── Database ──────────────────────────────────────────────────────
        db = Database(config)
        await db.initialize_schema()

        # ── Telegram Bot + Scanner ────────────────────────────────────────
        bot = RaphaelTelegramBot(config, exchange, db)
        await bot.start()

        logger.info("✅  Raphael AI Bot v2.0 is live. Nyunk-sama, siap menerima perintah.")
        logger.info("     Ketik /scan <SYMBOL> di Telegram untuk memulai analisis.")
        logger.info("     Press Ctrl+C to stop.\n")

        # ── Keep-alive loop ───────────────────────────────────────────────
        while True:
            await asyncio.sleep(1)

    except KeyboardInterrupt:
        logger.info("\n⏸️  Shutdown requested by Nyunk-sama")

    except Exception as e:
        logger.error(f"❌ Fatal error during startup: {e}", exc_info=True)
        raise

    finally:
        if bot:
            try:
                await bot.stop()
            except Exception:
                pass
        if exchange:
            try:
                await exchange.close()
            except Exception:
                pass
        logger.info("🛡️  Raphael AI Bot v2.0 shut down gracefully.")


if __name__ == "__main__":
    asyncio.run(main())
