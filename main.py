"""
Raphael AI Bot - Main Entry Point
Wisdom Lord Raphael - Core Analytical Engine & Financial Risk Guard
"""

import asyncio
import logging

from config import Config
from utils.logger import setup_logging
from telegram_module.telegram_bot import RaphaelTelegramBot
from database.database import Database
from mt5_module.mt5_connector import MT5Connector


async def main():
    """Main application entry point"""
    setup_logging()
    logger = logging.getLogger(__name__)

    logger.info("🎯 Wisdom Lord Raphael — Core Analytical Engine & Financial Risk Guard")
    logger.info("🚀 Initializing Raphael AI Bot System...")

    bot: RaphaelTelegramBot | None = None

    try:
        # Load configuration
        config = Config()
        logger.info("✅ Configuration loaded")
        logger.info(
            f"🛡️  Risk: {config.risk_percent_per_trade:.0f}% equity per trade | "
            f"Hard-skip: {config.risk_percent_per_trade * config.risk_hard_skip_multiplier:.0f}% | "
            f"RRR min: 1:{config.min_rrr}"
        )

        # Initialize database
        db = Database(config)
        await db.initialize_schema()
        logger.info("✅ Database initialized")

        # Initialize MT5 connector
        mt5_connector = MT5Connector(config)
        mt5_connector.initialize()
        logger.info("✅ MT5 connector initialized")

        # Initialize and start Telegram bot
        # (paper trade monitor is started inside bot.start())
        bot = RaphaelTelegramBot(config, mt5_connector, db)
        logger.info("✅ Telegram bot initialized")

        logger.info("🎉 Raphael AI Bot is ready to serve Nyunk-sama!")
        logger.info("📡 Waiting for signals via Telegram...")

        await bot.start()

        # Keep alive — run until KeyboardInterrupt
        while True:
            await asyncio.sleep(1)

    except KeyboardInterrupt:
        logger.info("⏸️  Shutdown requested by Nyunk-sama")
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}", exc_info=True)
        raise
    finally:
        if bot:
            try:
                await bot.stop()
            except Exception:
                pass
        logger.info("🛡️  Raphael AI Bot shut down gracefully")


if __name__ == "__main__":
    asyncio.run(main())
