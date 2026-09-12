"""
Response Formatter — Raphael AI Bot v2.0 (SMC Crypto Engine)

Lightweight helper for formatting reusable Telegram message snippets.
Main analysis output is formatted inline in telegram_bot.py.
"""

from typing import Any, Dict


class ResponseFormatter:
    """Utility formatters for Raphael v2.0 Telegram messages."""

    @staticmethod
    def format_error(error: str) -> str:
        return (
            f"❌ *Raphael System Error*\n\n"
            f"`{error}`\n\n"
            f"Cek log untuk detail, Nyunk-sama."
        )

    @staticmethod
    def format_balance(balance: Dict[str, Any], risk_percent: float) -> str:
        equity   = balance.get("equity_usdt", 0.0)
        avail    = balance.get("available_usdt", 0.0)
        used     = balance.get("used_usdt", 0.0)
        upnl     = balance.get("unrealized_pnl", 0.0)
        max_risk = equity * (risk_percent / 100.0)
        return (
            f"💰 *Wallet — Bitget USDT-M Futures*\n\n"
            f"Total Equity   : `${equity:.4f} USDT`\n"
            f"Available      : `${avail:.4f} USDT`\n"
            f"Used Margin    : `${used:.4f} USDT`\n"
            f"Unrealized PnL : `${upnl:.4f} USDT`\n\n"
            f"🛡️ Max Risk/Trade: `${max_risk:.4f} USDT` ({risk_percent:.0f}%)"
        )

    @staticmethod
    def format_performance(summary: Dict[str, Any]) -> str:
        total = summary.get("total_trades", 0)
        wins  = summary.get("wins", 0)
        losses = summary.get("losses", 0)
        wr    = summary.get("win_rate", 0.0)
        pnl   = summary.get("total_pnl", 0.0)
        rrr   = summary.get("avg_rrr", 0.0)
        pnl_icon = "🟢" if pnl >= 0 else "🔴"
        return (
            f"📈 *Performance Summary*\n\n"
            f"Total Trades  : `{total}`\n"
            f"Win / Loss    : `{wins}W / {losses}L`\n"
            f"Win Rate      : `{wr:.1f}%`\n"
            f"{pnl_icon} Total PnL   : `${pnl:.4f} USDT`\n"
            f"Avg RRR       : `1:{rrr:.2f}`"
        )
