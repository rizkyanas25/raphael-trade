"""
Risk Management Engine for Raphael AI Bot
Wisdom Lord Raphael - Core Analytical Engine & Financial Risk Guard

All monetary calculations use USD-based pip values converted to IDR.
Risk is always derived from live equity — never hardcoded IDR amounts.
"""

import logging
from typing import Dict, Any, Optional
from config import Config


logger = logging.getLogger(__name__)


class RiskManager:
    """
    Risk management engine.

    Core formula (per Gemini recommendation):
        Risk IDR   = Equity × Risk%
        Risk USD   = Risk IDR / USD_IDR_Rate
        Pip Dist   = |Entry - SL| × pip_multiplier
        Lot Size   = Risk USD / (Pip Dist × pip_value_per_lot_USD)
        Lot Size   = max(0.01, floor_to_0.01(Lot Size))

    If min lot (0.01) still exceeds risk threshold → hard SKIP.
    """

    def __init__(self, config: Config):
        self.config = config
        logger.info("🛡️ Risk Management Engine initialized (equity-based dynamic risk)")

    # ── Pip Utilities ─────────────────────────────────────────────────────

    def _calculate_pip_distance(self, symbol: str, price1: float, price2: float) -> float:
        """Convert price difference to pips using symbol-specific multiplier."""
        multiplier = self.config.get_pip_multiplier(symbol)
        return round(abs(price1 - price2) * multiplier, 1)

    def _pip_value_per_001_lot_idr(self, symbol: str) -> float:
        """
        IDR value of 1 pip movement at 0.01 lot.
        Derived from: 0.01 lot × $10/pip/lot × USD/IDR rate
        Gold uses different base ($1/pip at 0.01 lot).
        """
        return self.config.get_pip_value_per_001_lot_idr(symbol)

    # ── Position Sizing ───────────────────────────────────────────────────

    def calculate_position_size(
        self,
        symbol: str,
        entry_price: float,
        stop_loss: float,
        account_equity: float,
    ) -> Dict[str, Any]:
        """
        Calculate optimal lot size and validate against equity-based risk limits.

        Returns a comprehensive dict used by validate_trade_setup and the AI prompt.
        """
        try:
            equity = account_equity
            max_risk_idr      = self.config.get_max_risk_idr(equity)
            hard_skip_risk_idr = self.config.get_hard_skip_risk_idr(equity)

            sl_pips    = self._calculate_pip_distance(symbol, entry_price, stop_loss)
            pip_val_idr = self._pip_value_per_001_lot_idr(symbol)  # at 0.01 lot

            # Risk at minimum lot (0.01)
            risk_at_min_lot_idr = sl_pips * pip_val_idr  # already at 0.01 lot

            # Ideal lot size to hit exactly max_risk_idr
            if risk_at_min_lot_idr > 0:
                ideal_lot = (max_risk_idr / risk_at_min_lot_idr) * 0.01
            else:
                ideal_lot = self.config.default_lot_size

            # Floor to nearest 0.01, minimum 0.01
            calculated_lot = max(
                self.config.default_lot_size,
                round(int(ideal_lot / 0.01) * 0.01, 2)
            )

            # Actual risk with the calculated lot
            actual_risk_idr = sl_pips * pip_val_idr * (calculated_lot / 0.01)
            actual_risk_pct  = (actual_risk_idr / equity * 100) if equity > 0 else 0.0

            # Risk classification
            within_threshold = actual_risk_idr <= max_risk_idr
            hard_skip        = actual_risk_idr > hard_skip_risk_idr
            warning_only     = (not within_threshold) and (not hard_skip)

            return {
                "symbol":             symbol,
                "entry_price":        entry_price,
                "stop_loss":          stop_loss,
                "sl_distance_pips":   sl_pips,
                "pip_value_idr_001":  round(pip_val_idr, 2),
                "ideal_lot":          round(ideal_lot, 4),
                "recommended_lot":    calculated_lot,
                "actual_risk_idr":    round(actual_risk_idr, 0),
                "max_risk_idr":       round(max_risk_idr, 0),
                "hard_skip_risk_idr": round(hard_skip_risk_idr, 0),
                "risk_percent":       round(actual_risk_pct, 2),
                "risk_threshold_pct": self.config.risk_percent_per_trade,
                "within_threshold":   within_threshold,
                "warning_only":       warning_only,   # above threshold but below hard-skip
                "hard_skip":          hard_skip,       # must not execute
                "account_equity":     equity,
            }

        except Exception as e:
            logger.error(f"❌ Position size calculation error: {e}", exc_info=True)
            raise

    # ── RRR ──────────────────────────────────────────────────────────────

    def calculate_rrr(
        self,
        entry_price: float,
        stop_loss: float,
        take_profit: float,
    ) -> Dict[str, Any]:
        """Calculate Risk-to-Reward Ratio."""
        risk_dist   = abs(entry_price - stop_loss)
        reward_dist = abs(take_profit - entry_price)
        rrr         = (reward_dist / risk_dist) if risk_dist > 0 else 0.0
        meets_min   = rrr >= self.config.min_rrr

        return {
            "entry_price":    entry_price,
            "stop_loss":      stop_loss,
            "take_profit":    take_profit,
            "risk_distance":  risk_dist,
            "reward_distance": reward_dist,
            "rrr":            round(rrr, 2),
            "min_rrr":        self.config.min_rrr,
            "meets_min_rrr":  meets_min,
        }

    # ── Full Trade Validation ─────────────────────────────────────────────

    def validate_trade_setup(
        self,
        symbol: str,
        order_type: str,
        entry_price: float,
        stop_loss: float,
        take_profit: float,
        account_equity: float,
        timeframe: str = "H1",
        current_positions: int = 0,
        margin_level_percent: float = 9999.0,
        is_counter_trend: bool = False,
    ) -> Dict[str, Any]:
        """
        Full validation against all risk management rules.

        Hard SKIP conditions (from Gemini framework):
          1. Risk at min lot (0.01) > hard_skip threshold (2× max risk)
          2. RRR < min_rrr (1:2)
          3. Margin level < 500%
          4. Position count >= max_positions
          5. High-volatility instrument + equity < threshold

        Warning conditions:
          - Risk between threshold and hard-skip threshold
          - Counter-trend setup (lot reduced 50%, TP capped)

        Returns validation dict consumed by Gemini prompt + response formatter.
        """
        result: Dict[str, Any] = {
            "symbol":            symbol,
            "order_type":        order_type,
            "timeframe":         timeframe,
            "is_valid":          True,
            "hard_skip":         False,
            "skip_reasons":      [],
            "warnings":          [],
            "risk_analysis":     None,
            "rrr_analysis":      None,
            "adjusted_lot":      None,
            "counter_trend_adj": False,
        }

        # ── 1. Position sizing ────────────────────────────────────────────
        risk = self.calculate_position_size(
            symbol, entry_price, stop_loss, account_equity
        )
        result["risk_analysis"] = risk

        if risk["hard_skip"]:
            result["is_valid"]   = False
            result["hard_skip"]  = True
            result["skip_reasons"].append(
                f"Risk Rp {risk['actual_risk_idr']:,.0f} ({risk['risk_percent']:.1f}% equity) "
                f"melewati batas hard-skip "
                f"Rp {risk['hard_skip_risk_idr']:,.0f} "
                f"({self.config.risk_percent_per_trade * self.config.risk_hard_skip_multiplier:.0f}% equity)"
            )
        elif risk["warning_only"]:
            result["warnings"].append(
                f"⚠️ Risk Rp {risk['actual_risk_idr']:,.0f} ({risk['risk_percent']:.1f}% equity) "
                f"di atas target {self.config.risk_percent_per_trade:.0f}% — "
                f"pertimbangkan perketat SL"
            )

        # ── 2. RRR ───────────────────────────────────────────────────────
        rrr = self.calculate_rrr(entry_price, stop_loss, take_profit)
        result["rrr_analysis"] = rrr

        if not rrr["meets_min_rrr"]:
            result["is_valid"]  = False
            result["hard_skip"] = True
            result["skip_reasons"].append(
                f"RRR 1:{rrr['rrr']:.2f} di bawah minimum 1:{self.config.min_rrr}"
            )

        # ── 3. Margin level ───────────────────────────────────────────────
        if margin_level_percent < self.config.min_margin_level_percent:
            result["is_valid"]  = False
            result["hard_skip"] = True
            result["skip_reasons"].append(
                f"Margin Level {margin_level_percent:.0f}% di bawah minimum "
                f"{self.config.min_margin_level_percent:.0f}%"
            )

        # ── 4. Position count ─────────────────────────────────────────────
        if current_positions >= self.config.max_positions:
            result["is_valid"]  = False
            result["hard_skip"] = True
            result["skip_reasons"].append(
                f"Sudah ada {current_positions} posisi aktif "
                f"(maksimal {self.config.max_positions})"
            )

        # ── 5. High-volatility equity gate ───────────────────────────────
        if self.config.is_high_volatility(symbol):
            if account_equity < self.config.high_vol_min_equity_idr:
                result["is_valid"]  = False
                result["hard_skip"] = True
                result["skip_reasons"].append(
                    f"{symbol} adalah instrumen high-volatility. "
                    f"Equity Rp {account_equity:,.0f} belum mencapai minimum "
                    f"Rp {self.config.high_vol_min_equity_idr:,.0f}"
                )
            else:
                result["warnings"].append(
                    f"⚠️ {symbol} adalah instrumen high-volatility — "
                    f"pastikan news calendar clear"
                )

        # ── 6. Counter-trend adjustment ───────────────────────────────────
        if is_counter_trend:
            adjusted = max(
                self.config.default_lot_size,
                round(risk["recommended_lot"] * 0.5, 2)
            )
            result["adjusted_lot"]      = adjusted
            result["counter_trend_adj"] = True
            result["warnings"].append(
                f"⚠️ Counter-trend setup — lot dikurangi 50%: "
                f"{risk['recommended_lot']} → {adjusted}. "
                f"TP dikunci konservatif di Middle BB / EMA50 H1."
            )

        logger.info(
            f"🛡️ {symbol} validation: "
            f"{'✅ VALID' if result['is_valid'] else '❌ SKIP'} | "
            f"Risk={risk['risk_percent']:.1f}% | RRR=1:{rrr['rrr']} | "
            f"Lot={risk['recommended_lot']}"
        )

        return result

    # ── Convenience ───────────────────────────────────────────────────────

    def check_position_limits(
        self,
        current_positions: int,
        account_equity: float,
        margin_usage_percent: float,
        margin_level_percent: float = 9999.0,
    ) -> Dict[str, Any]:
        """Quick check before even running full validation."""
        errors   = []
        warnings = []

        if current_positions >= self.config.max_positions:
            errors.append(f"Max posisi ({self.config.max_positions}) tercapai")

        if margin_usage_percent >= self.config.max_margin_usage_percent:
            errors.append(
                f"Margin usage {margin_usage_percent:.1f}% melewati batas "
                f"{self.config.max_margin_usage_percent:.0f}%"
            )
        elif margin_usage_percent >= self.config.max_margin_usage_percent * 0.8:
            warnings.append(
                f"Margin usage {margin_usage_percent:.1f}% mendekati batas"
            )

        if margin_level_percent < self.config.min_margin_level_percent:
            errors.append(
                f"Margin level {margin_level_percent:.0f}% di bawah minimum "
                f"{self.config.min_margin_level_percent:.0f}%"
            )

        return {
            "can_open":           len(errors) == 0,
            "current_positions":  current_positions,
            "margin_usage_pct":   margin_usage_percent,
            "margin_level_pct":   margin_level_percent,
            "errors":             errors,
            "warnings":           warnings,
        }
