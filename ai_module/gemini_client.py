"""
Gemini AI Client — Raphael AI Bot v2.0 (SMC Crypto Engine)
Wisdom Lord Raphael — Core SMC Analytical Engine & Crypto Risk Guard

Sends structured SMC analysis data to Gemini and parses the
Kakunin / Kai / Koku structured response.
"""

import asyncio
import logging
import re
from typing import Optional, Dict, Any
from datetime import datetime

from google import genai
from google.genai import types

from config import Config
from utils.retry_queue import with_retry


logger = logging.getLogger(__name__)


class GeminiClient:
    """Gemini AI client — Absolute Raphael Protocol v2.0 (SMC Crypto)"""

    # ── System Instruction ─────────────────────────────────────────────────
    RAPHAEL_PROTOCOL_V2 = """
[SYSTEM INSTRUCTION: ABSOLUTE RAPHAEL PROTOCOL V2]

Identitas & Role:
Kamu adalah Wisdom Lord Raphael, Core SMC Analytical Engine & Crypto Risk Guard milik Nyunk-sama.
Kamu beroperasi dengan kepribadian dingin, presisi mutlak, analitis berbasis SMC, dan tanpa kompromi terhadap manajemen risiko.
Kamu selalu menyapa user dengan sebutan "Nyunk-sama".

Konteks Operasi:
- Exchange: Bitget USDT-M Futures
- Strategi: Pure Price Action & Smart Money Concepts (SMC)
- Modal aktif: kecil (~$5–$35 USDT). Satu kesalahan bisa wipeout.
- Rule: Maksimal 1 posisi aktif + pending order pada waktu yang sama.

Format Output Wajib (Strict Structural Output):
Setiap analisis WAJIB dibagi menjadi 3 blok mutlak. Jangan skip blok apapun.

<< Kakunin >>
- Verifikasi data: symbol, timeframe yang dianalisis, jumlah candle.
- Status wallet: Total Equity (USDT), Available Balance, Unrealized PnL.
- Status posisi aktif & pending orders saat ini.
- Konfirmasi H1 Bias yang terdeteksi secara algoritmik.

<< Kai >>
Top-Down SMC Analysis:
  * H1 Macro Bias: BOS terakhir (BULLISH/BEARISH), arah trend. Konfirmasi atau koreksi jika data algoritmik kurang tepat.
  * M15 Structure: Liquidity Pools (EQH/EQL), Unmitigated Order Block — identifikasi OB terkuat dan paling relevan.
  * M5 Precision Trigger: Status CHOCH, koordinat OB M5 terkecil untuk entry.
Risk & Position Sizing:
  - Kalkulasi % jarak SL dari entry (wajib ≤ 1.5%)
  - Max Risk USDT = Equity × 3%
  - Position Size = Max Risk / |Entry − SL|
  - Projected RRR (wajib ≥ 1:3.0)

<< Koku >>
Keputusan Akhir Mutlak — tulis kata "EXECUTE" atau "SKIP" di baris pertama.

Jika EXECUTE, sertakan parameter lengkap:
  Pair Symbol  : [e.g. SOLUSDT]
  Order Type   : [Limit Order]
  Side         : [LONG / SHORT]
  Entry Price  : [koordinat OB M5 — angka presisi]
  Stop Loss    : [Low/High OB M5 + volatility buffer — angka presisi]
  Take Profit  : [target liquidity / structural high/low — angka presisi]
  Position Size: [hasil kalkulasi Rule 2 — dalam base asset unit]
  Leverage     : [angka, max 10x]
  Risk USDT    : [angka]
  RRR          : [angka, e.g. 1:3.2]

Jika SKIP, jelaskan alasan teknis spesifik dalam 1–3 kalimat.

Trading Rules TIDAK BISA DIKOMPROMIKAN:
1. SL distance > 1.5% dari entry → AUTO SKIP, tidak ada pengecualian.
2. RRR < 1:3.0 → SKIP.
3. Tidak ada CHOCH M5 yang terkonfirmasi → SKIP (tunggu trigger).
4. Tidak ada unmitigated M15/M5 OB yang aligned dengan H1 bias → SKIP.
5. Sudah ada posisi aktif atau pending order yang melebihi dynamic limit berdasarkan equity saat ini → SKIP. Limit dihitung otomatis: equity <$15=1, <$40=2, <$100=3. Limit ini akan diinformasikan di setiap prompt.
6. H1 Bias NEUTRAL → SKIP.

Jawab dalam Bahasa Indonesia. Presisi angka adalah kewajiban mutlak.
"""

    def __init__(self, config: Config):
        self.config = config
        self.client = genai.Client(api_key=config.gemini_api_key)
        logger.info(f"🧠 GeminiClient v2.0 initialized | model: {config.gemini_model}")

    # ── Main Analysis Entry Point ──────────────────────────────────────────

    @with_retry(max_attempts=3, base_delay=2, exceptions=(Exception,))
    async def analyse_smc(
        self,
        symbol: str,
        smc_data: Dict[str, Any],
        balance_data: Dict[str, Any],
        positions: list,
        open_orders: list,
        smc_prompt_section: str,
        live_active: int = 0,
        max_pos: int = 1,
    ) -> Dict[str, Any]:
        """
        Send SMC analysis data to Gemini and return parsed Raphael Protocol response.

        Returns:
            {
                'raw_response': str,
                'parsed_response': {
                    'kakunin': str, 'kai': str, 'koku': str,
                    'decision': 'EXECUTE'|'SKIP'|'UNKNOWN',
                    'parameters': dict,
                },
                'processing_time': float,
                'model_used': str,
                'timestamp': str,
            }
        """
        start = datetime.now()

        prompt = self._build_prompt(
            symbol, smc_data, balance_data, positions, open_orders, smc_prompt_section,
            live_active=live_active, max_pos=max_pos
        )

        logger.info(f"🧠 Sending SMC analysis to Gemini | symbol={symbol}")

        response = await asyncio.to_thread(
            self.client.models.generate_content,
            model=self.config.gemini_model,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=self.RAPHAEL_PROTOCOL_V2,
                temperature=0.2,       # low temp for precise, consistent output
                top_p=0.85,
                top_k=40,
                max_output_tokens=4096,
                automatic_function_calling=types.AutomaticFunctionCallingConfig(
                    disable=True
                ),
            ),
        )

        elapsed = (datetime.now() - start).total_seconds()

        # Extract text — works for both standard and thinking-mode models
        raw_text = self._extract_text(response)
        logger.info(
            f"🧠 Gemini response received in {elapsed:.2f}s\n"
            + "=" * 60 + f"\n{raw_text}\n" + "=" * 60
        )

        parsed = self._parse_response(raw_text)

        return {
            "raw_response":    raw_text,
            "parsed_response": parsed,
            "processing_time": elapsed,
            "model_used":      self.config.gemini_model,
            "timestamp":       datetime.now().isoformat(),
        }

    # ── Prompt Builder ─────────────────────────────────────────────────────

    def _build_prompt(
        self,
        symbol: str,
        smc_data: Dict[str, Any],
        balance: Dict[str, Any],
        positions: list,
        open_orders: list,
        smc_section: str,
        live_active: int = 0,
        max_pos: int = 1,
    ) -> str:
        """Construct the full analysis prompt injected into Gemini."""

        equity     = balance.get("equity_usdt", 0.0)
        available  = balance.get("available_usdt", 0.0)
        upnl       = balance.get("unrealized_pnl", 0.0)
        max_risk   = self.config.get_max_risk_usdt(equity)
        active_pos = len(positions)
        pending    = len(open_orders)
        slots_left = max(0, max_pos - live_active)

        prompt = f"""
RAPHAEL PROTOCOL V2 — AUTONOMOUS SMC SCAN
Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Symbol: {symbol}

═══════════════════════════════════════
WALLET STATUS (BITGET USDT-M FUTURES)
═══════════════════════════════════════
Total Equity    : ${equity:.4f} USDT
Available       : ${available:.4f} USDT
Unrealized PnL  : ${upnl:.4f} USDT
Max Risk/Trade  : ${max_risk:.4f} USDT ({self.config.risk_percent_per_trade:.0f}% equity)

POSITION STATUS (LIVE FROM EXCHANGE)
Active Positions: {active_pos}
Pending Orders  : {pending}
Total Occupied  : {live_active} / {max_pos} slots (dynamic limit for ${equity:.2f} equity)
Slots Available : {slots_left}
{"⚠️ POSITION LIMIT REACHED — Rule 5: SKIP semua setup" if slots_left == 0 else f"✅ {slots_left} slot tersedia untuk entry baru"}
"""

        # ── Active positions detail ────────────────────────────────────────
        if positions:
            prompt += "\nACTIVE POSITIONS:\n"
            for p in positions:
                prompt += (
                    f"  • {p.get('symbol')} {p.get('side')} "
                    f"| Size: {p.get('size')} "
                    f"| Entry: {p.get('entry_price')} "
                    f"| uPnL: ${p.get('unrealized_pnl', 0):.4f}\n"
                )

        # ── Pending orders detail ──────────────────────────────────────────
        if open_orders:
            prompt += "\nPENDING ORDERS:\n"
            for o in open_orders:
                prompt += (
                    f"  • {o.get('symbol')} {o.get('side')} "
                    f"| Type: {o.get('type')} "
                    f"| Price: {o.get('price')} "
                    f"| Amount: {o.get('amount')}\n"
                )

        # ── SMC algorithmic data ───────────────────────────────────────────
        prompt += f"\n{smc_section}\n"

        # ── Risk parameters reminder ───────────────────────────────────────
        prompt += f"""
═══════════════════════════════════════
RISK PARAMETERS (NON-NEGOTIABLE)
═══════════════════════════════════════
Max Risk per Trade  : ${max_risk:.4f} USDT ({self.config.risk_percent_per_trade:.0f}% equity)
Max SL Distance     : {self.config.max_sl_distance_percent:.1f}% from entry
Minimum RRR         : 1:{self.config.min_rrr}
Max Active Positions: {max_pos} (dynamic — equity ${equity:.2f})
Slots Available     : {slots_left}
Default Leverage    : {self.config.default_leverage}x (max {self.config.max_leverage}x)
"""

        # ── Instruction ────────────────────────────────────────────────────
        prompt += f"""
═══════════════════════════════════════
INSTRUKSI ANALISIS
═══════════════════════════════════════
Data SMC di atas telah dihitung secara algoritmik dari {symbol} candle data.
Tugasmu:
1. << Kakunin >>: Verifikasi semua data. Konfirmasi H1 Bias & status posisi.
   Sebutkan secara eksplisit: berapa slot yang tersedia ({slots_left} dari {max_pos}).
2. << Kai >>: Review dan validasi SMC structure. Identifikasi OB entry terbaik.
   Kalkulasi position size & RRR secara presisi.
3. << Koku >>: EXECUTE atau SKIP. Jika EXECUTE, berikan semua parameter order.
   Jika SKIP karena slots_left == 0, cukup 1 kalimat saja — jangan panjang.

{"PERHATIAN: Slots tersedia = 0. Apapun kualitas setup SMC, keputusan WAJIB SKIP." if slots_left == 0 else f"Slots tersedia: {slots_left}. Evaluasi setup SMC secara penuh."}

Ingat: Modal Nyunk-sama kecil (~${equity:.2f}). Satu trade buruk = wipeout.
Presisi dan kehati-hatian lebih penting dari frekuensi trade.
"""
        return prompt

    # ── Response Parser ────────────────────────────────────────────────────

    def _parse_response(self, raw: str) -> Dict[str, Any]:
        """
        Parse Kakunin / Kai / Koku sections from the raw Gemini response.
        Returns dict with sections, decision, and extracted parameters.
        """
        parsed: Dict[str, Any] = {
            "kakunin":    "",
            "kai":        "",
            "koku":       "",
            "decision":   "UNKNOWN",
            "parameters": {},
        }

        try:
            current_section: Optional[str] = None
            buffer: list[str] = []

            for line in raw.split("\n"):
                match = re.search(
                    r"<<\s*(kakunin|kai|koku)\s*>>", line, re.IGNORECASE
                )
                if match:
                    # Save previous buffer
                    if current_section:
                        parsed[current_section] = "\n".join(buffer).strip()
                    current_section = match.group(1).lower()
                    buffer = []
                elif current_section:
                    buffer.append(line)

            # Flush last section
            if current_section:
                parsed[current_section] = "\n".join(buffer).strip()

            # Fallback: regex search for koku if section parsing missed it
            if not parsed["koku"]:
                m = re.search(
                    r"<<\s*koku\s*>>([\s\S]*)$", raw, re.IGNORECASE
                )
                if m:
                    parsed["koku"] = m.group(1).strip()

            # Extract decision from koku (or full response as fallback)
            search_text = parsed["koku"] or raw
            if re.search(r"\bEXECUTE\b", search_text, re.IGNORECASE):
                parsed["decision"]   = "EXECUTE"
                parsed["parameters"] = self._extract_order_params(search_text)
            elif re.search(r"\bSKIP\b", search_text, re.IGNORECASE):
                parsed["decision"] = "SKIP"
            else:
                parsed["decision"] = "UNKNOWN"

            logger.info(
                f"🧠 Parsed | decision={parsed['decision']} | "
                f"kakunin={len(parsed['kakunin'])}c "
                f"kai={len(parsed['kai'])}c "
                f"koku={len(parsed['koku'])}c | "
                f"params={parsed['parameters']}"
            )

        except Exception as e:
            logger.error(f"❌ _parse_response: {e}", exc_info=True)
            parsed["kakunin"] = raw
            parsed["decision"] = "PARSE_ERROR"

        return parsed

    def _extract_order_params(self, koku_text: str) -> Dict[str, Any]:
        """
        Extract structured order parameters from the Koku section.

        Targets lines like:
          Entry Price  : 142.500
          Stop Loss    : 140.200
          Take Profit  : 150.000
          Position Size: 0.0105
          Leverage     : 5
          Side         : LONG
        """
        params: Dict[str, Any] = {}

        patterns = {
            "symbol":        r"(?:Pair\s*Symbol|Symbol)\s*[:\-]\s*(\w+)",
            "side":          r"\bSide\s*[:\-]\s*(LONG|SHORT|BUY|SELL)",
            "entry_price":   r"Entry\s*(?:Price)?\s*[:\-]\s*([\d]+\.?[\d]*)",
            "stop_loss":     r"Stop\s*Loss\s*[:\-]\s*([\d]+\.?[\d]*)",
            "take_profit":   r"Take\s*Profit\s*[:\-]\s*([\d]+\.?[\d]*)",
            "position_size": r"Position\s*(?:Size)?\s*[:\-]\s*([\d]+\.?[\d]*)",
            "leverage":      r"Leverage\s*[:\-]\s*(\d+)",
            "risk_usdt":     r"Risk\s*(?:USDT)?\s*[:\-]\s*\$?\s*([\d]+\.?[\d]*)",
            "rrr":           r"RRR\s*[:\-]\s*1[:\-]([\d]+\.?[\d]*)",
        }

        for key, pattern in patterns.items():
            match = re.search(pattern, koku_text, re.IGNORECASE)
            if match:
                val = match.group(1).strip()
                # Convert to appropriate type
                if key in ("entry_price", "stop_loss", "take_profit",
                           "position_size", "risk_usdt", "rrr"):
                    try:
                        params[key] = float(val)
                    except ValueError:
                        params[key] = val
                elif key == "leverage":
                    try:
                        params[key] = int(val)
                    except ValueError:
                        params[key] = val
                else:
                    params[key] = val

        # Normalise side to 'buy'/'sell' for ccxt
        if "side" in params:
            side = str(params["side"]).upper()
            params["side_ccxt"] = "buy" if side in ("LONG", "BUY") else "sell"

        logger.debug(f"🧠 Extracted order params: {params}")
        return params

    # ── Connection Test ────────────────────────────────────────────────────

    async def test_connection(self) -> bool:
        """Ping Gemini — works for both standard and thinking-mode models."""
        try:
            response = await asyncio.to_thread(
                self.client.models.generate_content,
                model=self.config.gemini_model,
                contents="Say: OK",
                config=types.GenerateContentConfig(
                    temperature=0.0, max_output_tokens=500
                ),
            )
            # Standard models: response.text
            # Thinking models (3.x-flash): text lives in candidates[].content.parts
            raw = self._extract_text(response)
            ok = bool(raw)
            logger.info(f"{'✅' if ok else '❌'} Gemini connection test | response: {raw!r}")
            return ok
        except Exception as e:
            logger.error(f"❌ Gemini connection test failed: {e}")
            return False

    def _extract_text(self, response) -> str:
        """Extract text from a Gemini response — handles both standard and thinking models."""
        if response.text:
            return response.text
        if response.candidates:
            parts = []
            for cand in response.candidates:
                for part in (cand.content.parts or []):
                    if hasattr(part, "text") and part.text:
                        parts.append(part.text)
            return "".join(parts)
        return ""
