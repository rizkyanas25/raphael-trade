"""
Configuration Management for Raphael AI Bot
Wisdom Lord Raphael - Core Analytical Engine & Financial Risk Guard

All risk parameters are dynamic and equity-based — nothing hardcoded in IDR.
"""

import os
from pathlib import Path
from typing import Optional, List
from dotenv import load_dotenv


class Config:
    """Configuration management for Raphael AI Bot"""

    def __init__(self, env_file: Optional[str] = None):
        env_path = env_file or Path(__file__).parent / ".env"
        load_dotenv(env_path)

        # ── Telegram ──────────────────────────────────────────────────────
        self.telegram_bot_token = self._get_required("TELEGRAM_BOT_TOKEN")
        self.telegram_user_id   = self._get_required("TELEGRAM_USER_ID")

        # ── Gemini AI ─────────────────────────────────────────────────────
        self.gemini_api_key = self._get_required("GEMINI_API_KEY")
        self.gemini_model   = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")

        # ── MT5 ───────────────────────────────────────────────────────────
        _mt5_login    = os.getenv("MT5_LOGIN", "0")
        self.mt5_login    = int(_mt5_login) if _mt5_login.isdigit() else 0
        self.mt5_password = os.getenv("MT5_PASSWORD", "")
        self.mt5_server   = os.getenv("MT5_SERVER", "")
        self.use_mock_mt5 = os.getenv("USE_MOCK_MT5", "false").lower() == "true"

        # ── Risk Management (equity-based, dynamic) ───────────────────────
        # % of live equity to risk per trade (default 5%)
        self.risk_percent_per_trade: float = float(
            os.getenv("RISK_PERCENT_PER_TRADE", "5.0")
        )
        # Hard SKIP multiplier: risk > percent × multiplier → forced SKIP
        # e.g. 5% × 2.0 = hard SKIP above 10% equity risk
        self.risk_hard_skip_multiplier: float = float(
            os.getenv("RISK_HARD_SKIP_MULTIPLIER", "2.0")
        )
        # USD/IDR conversion rate for pip value calculation
        self.usd_idr_rate: float = float(os.getenv("USD_IDR_RATE", "16000"))

        # Minimum RRR across all setups
        self.min_rrr: float = float(os.getenv("MIN_RRR", "2.0"))

        # Default / minimum lot size
        self.default_lot_size: float = float(os.getenv("DEFAULT_LOT_SIZE", "0.01"))

        # Standard pip value per 1 full lot in USD (applies to most forex pairs)
        self.pip_value_per_lot_usd: float = float(
            os.getenv("PIP_VALUE_PER_LOT_USD", "10.0")
        )

        # ── High-Volatility Instruments ───────────────────────────────────
        self.high_vol_min_equity_idr: float = float(
            os.getenv("HIGH_VOL_MIN_EQUITY_IDR", "1000000")
        )
        _hv_raw = os.getenv(
            "HIGH_VOL_SYMBOLS",
            "XAUUSD,XAGUSD,JPN225,US30,NAS100,UK100,GER40"
        )
        self.high_vol_symbols: List[str] = [
            s.strip().upper() for s in _hv_raw.split(",") if s.strip()
        ]

        # ── Position Limits ───────────────────────────────────────────────
        self.max_positions:             int   = int(os.getenv("MAX_POSITIONS", "3"))
        self.max_margin_usage_percent:  float = float(os.getenv("MAX_MARGIN_USAGE_PERCENT", "50.0"))
        self.min_margin_level_percent:  float = float(os.getenv("MIN_MARGIN_LEVEL_PERCENT", "500.0"))

        # ── Paper Trading ─────────────────────────────────────────────────
        self.paper_trading_enabled: bool = (
            os.getenv("PAPER_TRADING_ENABLED", "true").lower() == "true"
        )
        self.paper_trading_win_rate_threshold: float = float(
            os.getenv("PAPER_TRADING_WIN_RATE_THRESHOLD", "55.0")
        )
        self.paper_trading_rrr_threshold: float = float(
            os.getenv("PAPER_TRADING_RRR_THRESHOLD", "2.0")
        )
        # How often (seconds) the background monitor checks TP/SL
        self.paper_trading_monitor_interval: int = int(
            os.getenv("PAPER_TRADING_MONITOR_INTERVAL", "60")
        )
        # Auto-expire pending orders that never trigger
        self.paper_trading_intraday_expire_days: int = int(
            os.getenv("PAPER_TRADING_INTRADAY_EXPIRE_DAYS", "2")
        )
        self.paper_trading_swing_expire_days: int = int(
            os.getenv("PAPER_TRADING_SWING_EXPIRE_DAYS", "5")
        )
        # Starting virtual equity for paper trading (IDR)
        self.paper_trading_starting_equity_idr: float = float(
            os.getenv("PAPER_TRADING_STARTING_EQUITY_IDR", "570000")
        )

        # ── Database ──────────────────────────────────────────────────────
        self.database_path = os.getenv("DATABASE_PATH", "raphael_trades.db")

        # ── Logging ───────────────────────────────────────────────────────
        self.log_level = os.getenv("LOG_LEVEL", "INFO")
        self.log_file  = os.getenv("LOG_FILE", "raphael.log")

        # ── Retry ─────────────────────────────────────────────────────────
        self.max_retry_attempts:  int = int(os.getenv("MAX_RETRY_ATTEMPTS", "3"))
        self.retry_delay_seconds: int = int(os.getenv("RETRY_DELAY_SECONDS", "5"))

        # ── System ────────────────────────────────────────────────────────
        self.system_timezone = os.getenv("SYSTEM_TIMEZONE", "Asia/Jakarta")

    # ── Helpers ───────────────────────────────────────────────────────────

    def _get_required(self, key: str) -> str:
        value = os.getenv(key)
        if not value:
            raise ValueError(f"Required environment variable '{key}' is not set")
        return value

    def get_max_risk_idr(self, equity_idr: float) -> float:
        """
        Calculate maximum risk in IDR based on live equity.
        This replaces the old hardcoded MAX_RISK_IDR.

        Returns: equity_idr × (risk_percent / 100)
        """
        return equity_idr * (self.risk_percent_per_trade / 100.0)

    def get_hard_skip_risk_idr(self, equity_idr: float) -> float:
        """
        Threshold above which Raphael issues a hard SKIP regardless of setup.
        = max_risk × hard_skip_multiplier
        """
        return self.get_max_risk_idr(equity_idr) * self.risk_hard_skip_multiplier

    def get_pip_value_per_001_lot_idr(self, symbol: str) -> float:
        """
        Calculate pip value in IDR for 0.01 lot using proper USD-based formula.

        Formula:
            pip_value_per_lot_USD × (lot_size / 1.0) × usd_idr_rate
            = 10 × 0.01 × 16000 = 1600 IDR/pip for standard pair at 0.01 lot

        XAUUSD uses different multiplier (pip = 0.1, not 0.0001).
        """
        symbol_upper = symbol.upper()

        # Gold: pip = $0.1 move, 1 lot = $100/pip → 0.01 lot = $1/pip
        if "XAU" in symbol_upper:
            return 1.0 * self.usd_idr_rate  # $1/pip × kurs

        # JPY pairs: pip = 0.01 move, same $10/pip/lot standard
        # (pip multiplier handled in pip distance calculation, not here)
        # Standard: 0.01 lot × $10/pip = $0.10/pip
        return (self.default_lot_size / 1.0) * self.pip_value_per_lot_usd * self.usd_idr_rate

    def get_pip_multiplier(self, symbol: str) -> float:
        """
        Price movement multiplier to convert price diff → pips.

        - Standard 5-digit forex (EURUSD etc): × 10,000
        - JPY pairs (3-digit): × 100
        - XAUUSD (2-digit): × 10
        - Indices: × 1
        """
        symbol_upper = symbol.upper()
        if "JPY" in symbol_upper:
            return 100.0
        if "XAU" in symbol_upper or "XAG" in symbol_upper:
            return 10.0
        if any(idx in symbol_upper for idx in ["JPN225", "US30", "NAS100", "UK100", "GER40"]):
            return 1.0
        return 10000.0  # standard 5-digit forex

    def is_high_volatility(self, symbol: str) -> bool:
        """Check if symbol requires elevated equity to trade."""
        s = symbol.upper()
        return any(hv in s for hv in self.high_vol_symbols)

    def get_swing_timeframes(self) -> list:
        """Timeframes considered 'swing' for RRR and expire rules."""
        return ['H2', 'H4']

    def get_intraday_timeframes(self) -> list:
        """Timeframes considered 'intraday' for RRR and expire rules."""
        return ['M15', 'H1']
