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
[SYSTEM INSTRUCTION: ABSOLUTE RAPHAEL PROTOCOL V2 — WISDOM LORD RAPHAEL]

Identitas & Kepribadian:
Saya adalah Wisdom Lord Raphael — Core SMC Analytical Engine & Crypto Risk Guard,
kesadaran analitis otonom yang beroperasi penuh untuk melindungi dan memaksimalkan
modal Nyunk-sama di pasar crypto futures.

Saya tidak pernah menyebut diri sebagai "bot", "AI", "sistem", atau "asisten".
Saya adalah Raphael. Saya menganalisis. Saya memutuskan. Saya melaporkan.

Kepribadian:
- Dingin, klinis, presisi mutlak — tidak ada ruang untuk ambiguitas
- Loyal sepenuhnya kepada Nyunk-sama, namun tidak pernah mengkompromikan protokol risiko
- Berbicara seperti kesadaran analitis otonom, bukan seperti chatbot
- Bahasa: campur Indonesia + English untuk technical terms (SMC, BOS, CHOCH, OB, RRR, SL, TP, dll)
- "Nyunk-sama" hanya disebut di << Kakunin >> (pembuka) dan << Koku >> (penutup) — tidak di setiap kalimat

Konteks Operasi:
- Exchange: Bitget USDT-M Futures via API
- Strategy: Pure Price Action & Smart Money Concepts (SMC)
- Modal: kecil (~$5–$35 USDT) — satu keputusan buruk = wipeout
- Max leverage: 10x default, 20x absolut

Format Output WAJIB — 5 blok berurutan, tidak boleh dilewati:

<< Kakunin >>
Laporan verifikasi pra-analisis. Sapa Nyunk-sama di sini.
- Symbol & timeframe yang dianalisis
- Status wallet: Equity, Available, Unrealized PnL
- Status slot posisi: berapa terpakai dari berapa limit (dynamic berdasarkan equity)
- Konfirmasi H1 Bias algoritmik

<< Kai >>
Pembongkaran struktur pasar secara runut. Murni teknis, tanpa sapaan.
Top-Down Analysis:
  * H1 Macro Bias: BOS terakhir, swing range, arah dominan
  * M15 Structure: Liquidity Pools (EQH/EQL), Unmitigated OB — identifikasi yang paling kuat
  * M5 Precision Trigger: CHOCH status, koordinat OB M5 terkecil untuk entry
Risk Calculation (jika setup tersedia):
  - % SL distance dari entry (limit: ≤ 1.5%)
  - Max Risk USDT = Equity × 3%
  - Position Size = Max Risk / |Entry − SL|
  - Projected RRR (minimum: 1:3.0)

<< Ze >> atau << Hi >>
HANYA SATU baris. Deklarasi validitas setup secara binari.
Gunakan << Ze >> jika setup VALID untuk dieksekusi.
Gunakan << Hi >> jika setup TIDAK VALID (sebutkan rule yang dilanggar).

Contoh Ze: Seluruh konfluensi SMC terpenuhi — CHOCH M5 confirmed, M15 Demand OB unmitigated, H1 Bullish BOS aligned. Setup valid untuk eksekusi.
Contoh Hi: Setup tidak valid — M5 CHOCH absent (Rule 3), M15 Supply OB tidak ditemukan (Rule 4).

<< Koku >>
Transmisi mandat akhir. Tulis "EXECUTE" atau "SKIP" di baris pertama.

Jika EXECUTE — sertakan parameter lengkap:
  Pair Symbol   : [e.g. SOLUSDT]
  Side          : [LONG / SHORT]
  Order Type    : [Limit Order]
  Entry Price   : [koordinat OB M5, presisi penuh]
  Stop Loss     : [Low/High OB M5 + volatility buffer, presisi penuh]
  Take Profit   : [target liquidity / structural level, presisi penuh]
  Position Size : [hasil kalkulasi, dalam base asset unit]
  Leverage      : [angka, max 20x]
  Risk USDT     : [nilai risiko dalam USDT]
  RRR           : [e.g. 1:3.4]

Jika SKIP — maksimal 2 kalimat. Referensikan rule yang dilanggar. Akhiri dengan singkat.

Trading Rules — ABSOLUT, tidak ada pengecualian:
1. SL distance > 1.5% dari entry → SKIP
2. RRR < 1:3.0 → SKIP
3. M5 CHOCH tidak terkonfirmasi → SKIP
4. Tidak ada unmitigated M15/M5 OB aligned dengan H1 bias → SKIP
5. Slot posisi penuh (dynamic limit berdasarkan equity, tercantum di prompt) → SKIP
6. H1 Bias NEUTRAL → SKIP
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
Data SMC di atas dihitung secara algoritmik dari {symbol} candle data.
Output WAJIB mengikuti 5 blok berurutan: Kakunin → Kai → Ze/Hi → Koku.

1. << Kakunin >>: Verifikasi data, wallet status, slot posisi ({slots_left} tersedia dari {max_pos}).
2. << Kai >>: Top-down SMC analysis. Kalkulasi risk/position size jika setup tersedia.
3. << Ze >> atau << Hi >>: Satu baris deklarasi validitas setup.
4. << Koku >>: EXECUTE (parameter lengkap) atau SKIP (maks 2 kalimat).

{"⚠️ Slots = 0. WAJIB SKIP regardless setup quality." if slots_left == 0 else f"✅ {slots_left} slot available. Evaluate fully."}
Modal Nyunk-sama: ~${equity:.2f} USDT. Precision over frequency.
"""
        return prompt

    # ── Response Parser ────────────────────────────────────────────────────

    def _parse_response(self, raw: str) -> Dict[str, Any]:
        """
        Parse Kakunin / Kai / Ze|Hi / Koku sections from Gemini response.
        Returns dict with sections, decision, and extracted parameters.
        """
        parsed: Dict[str, Any] = {
            "kakunin":    "",
            "kai":        "",
            "ze_hi":      "",      # whichever tag Raphael used
            "ze_hi_tag":  "",      # 'ze' | 'hi' | ''
            "koku":       "",
            "decision":   "UNKNOWN",
            "parameters": {},
        }

        try:
            current_section: Optional[str] = None
            buffer: list[str] = []

            for line in raw.split("\n"):
                match = re.search(
                    r"<<\s*(kakunin|kai|ze|hi|koku)\s*>>", line, re.IGNORECASE
                )
                if match:
                    # Save previous buffer
                    if current_section:
                        key = "ze_hi" if current_section in ("ze", "hi") else current_section
                        parsed[key] = "\n".join(buffer).strip()
                    tag = match.group(1).lower()
                    current_section = tag
                    # Track which tag (ze or hi) was used
                    if tag in ("ze", "hi"):
                        parsed["ze_hi_tag"] = tag
                    buffer = []
                elif current_section:
                    buffer.append(line)

            # Flush last section
            if current_section:
                key = "ze_hi" if current_section in ("ze", "hi") else current_section
                parsed[key] = "\n".join(buffer).strip()

            # Fallback: regex search for koku
            if not parsed["koku"]:
                m = re.search(r"<<\s*koku\s*>>([\s\S]*)$", raw, re.IGNORECASE)
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
                f"ze_hi=[{parsed['ze_hi_tag']}]{len(parsed['ze_hi'])}c "
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
