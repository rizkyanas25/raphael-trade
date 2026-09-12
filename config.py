"""
Configuration Management — Raphael AI Bot v2.0 (SMC Crypto Engine)
Wisdom Lord Raphael — Core SMC Analytical Engine & Crypto Risk Guard

All risk parameters are dynamic and equity-based.
Exchange: Bitget USDT-M Futures via ccxt
"""

import os
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv


class Config:
    """Configuration management for Raphael AI Bot v2.0"""

    def __init__(self, env_file: Optional[str] = None):
        env_path = env_file or Path(__file__).parent / ".env"
        load_dotenv(env_path)

        # ── Telegram ──────────────────────────────────────────────────────
        self.telegram_bot_token = self._get_required("TELEGRAM_BOT_TOKEN")
        self.telegram_user_id   = self._get_required("TELEGRAM_USER_ID")

        # ── Gemini AI ─────────────────────────────────────────────────────
        self.gemini_api_key = self._get_required("GEMINI_API_KEY")
        self.gemini_model   = os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite")

        # ── Bitget Exchange ───────────────────────────────────────────────
        self.bitget_api_key    = self._get_required("BITGET_API_KEY")
        self.bitget_api_secret = self._get_required("BITGET_API_SECRET")
        self.bitget_passphrase = self._get_required("BITGET_PASSPHRASE")
        # Set to 'true' to use Bitget sandbox/testnet
        self.bitget_sandbox: bool = (
            os.getenv("BITGET_SANDBOX", "false").lower() == "true"
        )

        # ── Risk Management (equity-based, dynamic) ───────────────────────
        # % of live USDT equity to risk per trade (default 3%)
        self.risk_percent_per_trade: float = float(
            os.getenv("RISK_PERCENT_PER_TRADE", "3.0")
        )
        # Hard SKIP if SL distance from entry > this % (default 1.5%)
        self.max_sl_distance_percent: float = float(
            os.getenv("MAX_SL_DISTANCE_PERCENT", "1.5")
        )
        # Minimum Risk:Reward Ratio
        self.min_rrr: float = float(os.getenv("MIN_RRR", "3.0"))

        # ── Leverage ──────────────────────────────────────────────────────
        # Default leverage for new positions (can be overridden per signal)
        self.default_leverage: int = int(os.getenv("DEFAULT_LEVERAGE", "10"))
        self.max_leverage: int     = int(os.getenv("MAX_LEVERAGE", "20"))

        # ── Watchlist & Scan Interval — REMOVED ──────────────────────────
        # Bot is now on-demand only. No autonomous scanner.
        # All scans initiated via /scan <SYMBOL> from Telegram.

        # ── Position Limits ───────────────────────────────────────────────
        # Hard cap — dynamic method get_max_positions(equity) should be used
        # instead of this value wherever possible. This is the absolute ceiling.
        self.max_positions_hard_cap: int = int(os.getenv("MAX_POSITIONS_HARD_CAP", "3"))

        # ── Operation Mode ────────────────────────────────────────────────
        # 'manual'  → bot sends signal notification, waits for /execute
        # 'auto'    → bot places Limit Order automatically after EXECUTE decision
        self.operation_mode: str = os.getenv("OPERATION_MODE", "manual").lower()

        # ── Database ──────────────────────────────────────────────────────
        self.database_path = os.getenv("DATABASE_PATH", "raphael_trades.db")

        # ── Logging ───────────────────────────────────────────────────────
        self.log_level = os.getenv("LOG_LEVEL", "INFO")
        self.log_file  = os.getenv("LOG_FILE", "raphael.log")

        # ── System ────────────────────────────────────────────────────────
        self.system_timezone = os.getenv("SYSTEM_TIMEZONE", "Asia/Jakarta")

    # ── Helpers ───────────────────────────────────────────────────────────

    def _get_required(self, key: str) -> str:
        value = os.getenv(key)
        if not value:
            raise ValueError(
                f"Required environment variable '{key}' is not set. "
                f"Check your .env file."
            )
        return value

    def get_max_risk_usdt(self, equity_usdt: float) -> float:
        """
        Max allowable risk per trade in USDT.
        = equity × (risk_percent / 100)
        e.g. $5 × 3% = $0.15
        """
        return equity_usdt * (self.risk_percent_per_trade / 100.0)

    def is_sl_distance_valid(self, entry: float, stop_loss: float) -> bool:
        """
        Returns True if SL distance is within the max allowed %.
        AUTO-SKIP if abs(entry - sl) / entry * 100 > max_sl_distance_percent
        """
        if entry == 0:
            return False
        distance_pct = abs(entry - stop_loss) / entry * 100
        return distance_pct <= self.max_sl_distance_percent

    def calculate_position_size(
        self,
        equity_usdt: float,
        entry_price: float,
        stop_loss_price: float,
        leverage: int = 0,
    ) -> float:
        """
        Position size (in base asset units) using SMC Rule 2:
            max_risk_usdt / abs(entry - sl)
        Leverage is factored in: position_size = risk / (sl_distance / leverage)
        Returns 0.0 if inputs are invalid.
        """
        if entry_price == 0 or stop_loss_price == 0:
            return 0.0
        sl_distance = abs(entry_price - stop_loss_price)
        if sl_distance == 0:
            return 0.0
        lev = leverage if leverage > 0 else self.default_leverage
        max_risk = self.get_max_risk_usdt(equity_usdt)
        # With leverage, each unit of position only ties up (price / lev) of margin
        # but the P/L per unit is still (price_move per unit)
        position_size = (max_risk * lev) / (sl_distance * lev / lev)
        # Simplifies to: max_risk / sl_distance (leverage doesn't change dollar risk)
        position_size = max_risk / sl_distance
        return round(position_size, 4)

    def is_auto_mode(self) -> bool:
        return self.operation_mode == "auto"

    def is_manual_mode(self) -> bool:
        return self.operation_mode == "manual"

    def get_max_positions(self, equity_usdt: float) -> int:
        """
        Dynamic max simultaneous positions based on live equity.

        Logic:
          - Minimum notional on Bitget Futures = $5 per order
          - With max_leverage 20x, minimum margin per trade = $5/20 = $0.25
          - But we also need enough margin buffer to avoid margin call
          - Conservative approach: each position should not consume
            more than (equity × risk_percent) × 2 in margin (2x risk as buffer)

        Thresholds (calibrated for $5–$100 equity range):
          equity < $15   → 1 position  (barely enough for 1 viable order)
          equity < $40   → 2 positions (enough margin for 2 small positions)
          equity < $100  → 3 positions
          equity >= $100 → hard cap (max_positions_hard_cap)

        Never exceeds max_positions_hard_cap regardless of equity.
        """
        if equity_usdt < 15.0:
            dynamic = 1
        elif equity_usdt < 40.0:
            dynamic = 2
        elif equity_usdt < 100.0:
            dynamic = 3
        else:
            dynamic = self.max_positions_hard_cap

        return min(dynamic, self.max_positions_hard_cap)
