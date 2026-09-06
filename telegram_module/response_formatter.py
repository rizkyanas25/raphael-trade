"""
Response Formatter for Raphael AI Bot
Wisdom Lord Raphael - Core Analytical Engine & Financial Risk Guard
"""

import logging
import re
from typing import Dict, Any
from datetime import datetime


logger = logging.getLogger(__name__)


class ResponseFormatter:
    """Format AI responses for Telegram with proper styling — all monetary values in IDR"""

    @staticmethod
    def format_analysis_response(
        ai_response: Dict[str, Any],
        mt5_data: Dict[str, Any],
        risk_analysis: Dict[str, Any],
        mode: str = "signal",
    ) -> str:
        """Format complete analysis response for Telegram"""
        try:
            parsed = ai_response.get('parsed_response', {})

            # Fallback if parsing produced completely empty sections but raw response exists
            if not parsed.get('kai') and not parsed.get('koku') and ai_response.get('raw_response'):
                raw_text = ai_response.get('raw_response', '').strip()
                kakunin_section = ResponseFormatter._format_kakunin_section(
                    "", mt5_data, mode=mode
                )
                footer = f"\n\n---\n🛡️ *Raphael Protocol* | ⏰ {datetime.now().strftime('%H:%M:%S')} | Mode: {'Signal Eval' if mode == 'signal' else 'Independent Analysis'}"
                return f"{kakunin_section}\n\n{raw_text}{footer}"

            kakunin_section = ResponseFormatter._format_kakunin_section(
                parsed.get('kakunin', ''), mt5_data, mode=mode
            )
            kai_section = ResponseFormatter._format_kai_section(
                parsed.get('kai', ''), risk_analysis
            )
            koku_section = ResponseFormatter._format_koku_section(
                parsed.get('koku', ''),
                parsed.get('decision', ''),
                parsed.get('parameters', {})
            )

            full_response = f"{kakunin_section}\n\n{kai_section}\n\n{koku_section}"
            footer = f"\n\n---\n🛡️ *Raphael Protocol* | ⏰ {datetime.now().strftime('%H:%M:%S')} | Mode: {'Signal Eval' if mode == 'signal' else 'Independent Analysis'}"
            return full_response + footer

        except Exception as e:
            logger.error(f"❌ Error formatting response: {e}", exc_info=True)
            return f"❌ Error formatting analysis response: {e}"

    @staticmethod
    def _format_kakunin_section(kakunin_content: str, mt5_data: Dict[str, Any], mode: str = "signal") -> str:
        """Format Kakunin section — account values displayed in IDR"""
        account_info = mt5_data.get('account_info', {})
        currency = account_info.get('currency', 'IDR')
        symbol   = mt5_data.get('symbol', 'N/A')

        def fmt(val: float) -> str:
            return f"Rp {val:,.2f}" if currency == 'IDR' else f"{currency} {val:,.2f}"

        mode_label = "📸 Signal Evaluation" if mode == "signal" else "🔍 Independent Analysis"

        return f"""<< Kakunin >>
{mode_label} — *{symbol}*
{kakunin_content}

📊 *Account Status:*
💰 Balance: {fmt(account_info.get('balance', 0))}
💎 Equity: {fmt(account_info.get('equity', 0))}
📈 Margin: {fmt(account_info.get('margin', 0))}
📊 Margin Level: {account_info.get('margin_level', 0):.2f}%
💹 Floating P/L: {fmt(account_info.get('profit', 0))}"""

    @staticmethod
    def _format_kai_section(kai_content: str, risk_analysis: Dict[str, Any]) -> str:
        """Format Kai section with risk analysis in IDR"""
        kai = f"<< Kai >>\n{kai_content}"

        if risk_analysis and risk_analysis.get('risk_analysis'):
            risk = risk_analysis['risk_analysis']
            equity = risk.get('account_equity', 0)
            kai += f"""

🛡️ *Risk Analysis:*
📏 SL Distance: {risk.get('sl_distance_pips', 0):.1f} pips
💰 Risk Amount: Rp {risk.get('actual_risk_idr', 0):,.0f}
📊 Lot Size: {risk.get('max_lot_size', 0):.2f}
⚠️ Risk: {risk.get('risk_percentage', 0):.2f}% of equity"""

        if risk_analysis and risk_analysis.get('rrr_analysis'):
            rrr = risk_analysis['rrr_analysis']
            kai += f"""

⚖️ *Risk-Reward Ratio:*
🎯 RRR: 1:{rrr.get('rrr', 0):.2f}
📈 TP Distance: {rrr.get('reward_distance', 0):.5f}
📉 SL Distance: {rrr.get('risk_distance', 0):.5f}"""

        return kai

    @staticmethod
    def _format_koku_section(
        koku_content: str,
        decision: str,
        parameters: Dict[str, Any]
    ) -> str:
        """Format Koku section with MT5 parameters"""
        cleaned_content = koku_content.strip() if koku_content else ""
        # Clean leading duplicate decision keywords if AI already wrote it
        for prefix in ('EXECUTE', 'SKIP', 'WAIT', 'RISK_SKIP'):
            if cleaned_content.upper().startswith(prefix):
                cleaned_content = re.sub(rf'^{prefix}\s*[:-]?\s*', '', cleaned_content, flags=re.IGNORECASE).strip()
                break

        if decision == 'EXECUTE':
            koku = f"<< Koku >>\n✅ *EXECUTE*\n\n{cleaned_content}" if cleaned_content else "<< Koku >>\n✅ *EXECUTE*"
        elif decision == 'SKIP':
            koku = f"<< Koku >>\n❌ *SKIP*\n\n{cleaned_content}" if cleaned_content else "<< Koku >>\n❌ *SKIP*"
        elif decision in ('WAIT', 'RISK_SKIP'):
            emoji = "⏳" if decision == 'WAIT' else "🛡️"
            label = "WAIT — Kondisi belum terpenuhi" if decision == 'WAIT' else "SKIP — Risk Protocol Override"
            koku = f"<< Koku >>\n{emoji} *{label}*\n\n{cleaned_content}" if cleaned_content else f"<< Koku >>\n{emoji} *{label}*"
        else:
            koku = f"<< Koku >>\n{cleaned_content}"

        if decision == 'EXECUTE' and parameters:
            koku += f"""

📋 *MT5 Parameters:*
🎫 Order Type: {parameters.get('order_type', 'N/A')}
💰 Entry Price: {parameters.get('entry_price', 'N/A')}
🛡️ Stop Loss: {parameters.get('stop_loss', 'N/A')}
🎯 Take Profit: {parameters.get('take_profit', 'N/A')}
📊 Lot Size: {parameters.get('lot_size', 'N/A')}"""

        return koku

    @staticmethod
    def format_error_response(error_message: str) -> str:
        """Format error response"""
        return f"""❌ *Analysis Error*

{error_message}

🛡️ Silakan coba lagi, Nyunk-sama."""

    @staticmethod
    def format_system_status(
        mt5_connected: bool,
        ai_ready: bool,
        db_ready: bool,
        paper_trading_enabled: bool,
        pending_trades: int = 0,
        active_trades: int = 0,
    ) -> str:
        """Format system status response"""
        all_ok = all([mt5_connected, ai_ready, db_ready])
        return f"""🔍 *System Status*

🤖 *Bot Status:* ✅ Online
⏰ *Timestamp:* {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

📡 *MT5 Connection:* {'✅ Connected' if mt5_connected else '❌ Disconnected'}
🧠 *AI Engine:* {'✅ Ready' if ai_ready else '❌ Not Ready'}
💾 *Database:* {'✅ Operational' if db_ready else '❌ Error'}

⚡ *Operational Mode:* {'📝 Paper Trading' if paper_trading_enabled else '💰 Live Trading'}
📊 *Paper Trades:* {pending_trades} pending | {active_trades} active

🛡️ *System Status:* {'✅ OPTIMAL' if all_ok else '⚠️ DEGRADED'}"""

    @staticmethod
    def format_performance_metrics(metrics: Dict[str, Any], paper_trading: bool) -> str:
        """Format performance metrics — P/L in IDR"""
        mode = "📝 Paper Trading" if paper_trading else "💰 Live Trading"
        pnl_idr = metrics.get('total_profit_loss_idr', metrics.get('total_profit_loss', 0))
        status = '✅ OPTIMAL' if metrics.get('win_rate', 0) >= 50 else '⚠️ NEEDS IMPROVEMENT'

        return f"""📈 *Performance Metrics*

{mode}

📊 *Total Trades:* {metrics.get('total_trades', 0)}
✅ *Winning Trades:* {metrics.get('winning_trades', 0)}
❌ *Losing Trades:* {metrics.get('losing_trades', 0)}
🎯 *Win Rate:* {metrics.get('win_rate', 0):.1f}%
💰 *Total P/L:* Rp {pnl_idr:,.0f}
⚖️ *Avg RRR:* 1:{metrics.get('avg_rrr', 0):.2f}

🛡️ *System Performance:* {status}"""

    @staticmethod
    def format_paper_trading_status(
        enabled: bool,
        metrics: Dict[str, Any],
        readiness: Dict[str, Any]
    ) -> str:
        """Format paper trading status — equity in IDR"""
        status = "📝 *ENABLED*" if enabled else "💰 *DISABLED*"
        virtual_equity_idr = metrics.get('virtual_equity_idr', metrics.get('virtual_equity', 0))
        pnl_idr = metrics.get('total_profit_loss_idr', 0)

        response = f"""📝 *Paper Trading Status*

{status}

🎯 *Configuration:*
• Duration: 2 weeks
• Win Rate Target: 55%
• RRR Target: 1:3

📊 *Current Performance:*
• Total Trades: {metrics.get('total_trades', 0)}
• Win Rate: {metrics.get('win_rate', 0):.1f}%
• Avg RRR: 1:{metrics.get('avg_rrr', 0):.2f}
• Total P/L: Rp {pnl_idr:,.0f}
• Virtual Equity: Rp {virtual_equity_idr:,.0f}"""

        if enabled:
            if readiness.get('is_ready'):
                response += "\n\n✅ *Ready for Live Trading*\nAll performance thresholds met!"
            else:
                current_trades = metrics.get('total_trades', 0)
                min_req = readiness.get('min_trades_required', 10)
                response += f"""

📈 *In Validation Phase*
• Trades: {current_trades}/{min_req} minimum
• Win Rate: {readiness.get('current_win_rate', 0):.1f}% (target ≥{readiness.get('win_rate_threshold', 55)}%)
• RRR: 1:{readiness.get('current_rrr', 0):.2f} (target ≥1:{readiness.get('rrr_threshold', 3)})
• P/L: Rp {readiness.get('current_pnl_idr', 0):,.0f} (target > 0)"""

        return response
