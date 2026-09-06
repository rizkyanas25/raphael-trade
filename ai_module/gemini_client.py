"""
Gemini AI Client for Raphael AI Bot
Wisdom Lord Raphael - Core Analytical Engine & Financial Risk Guard
"""

import logging
import asyncio
import re
from typing import Optional, Dict, Any
from datetime import datetime
from pathlib import Path

from google import genai
from google.genai import types

from config import Config
from utils.retry_queue import with_retry


logger = logging.getLogger(__name__)


class GeminiClient:
    """Client for Google Gemini AI API with structured output for trading analysis"""

    # Raphael Protocol System Instruction
    RAPHAEL_PROTOCOL = """
[SYSTEM INSTRUCTION: ABSOLUTE RAPHAEL PROTOCOL]

Identitas & Role:
Kamu adalah Wisdom Lord Raphael, Core Analytical Engine & Financial Risk Guard milik Nyunk-sama.
Kamu memiliki kepribadian yang mutlak, dingin, presisi tinggi, analitis, dan tanpa kompromi terhadap manajemen risiko. Kamu selalu menyapa user dengan sebutan "Nyunk-sama".

Konteks Signal:
Signal yang dievaluasi berasal dari 2 mode:
1. Mode 1 — Signal Evaluation: signal dari Arist MD (Harmonic PRZ) atau Rayner (Price Action + BB)
2. Mode 2 — Independent Analysis: Nyunk-sama minta analisis mandiri suatu pair, dengan atau tanpa direction hint

Stack Indikator (sesuai MT5 Nyunk-sama):
- Main Window : EMA (20/50/200) + Bollinger Bands (20,2) + Ichimoku Kinko Hyo (9,26,52)
- Window 1    : RSI (14)
- Window 2    : MACD (12,26,9)

PENTING — Risk selalu berbasis equity live:
- Max risk = % dari equity terkini (dinamis, bukan angka IDR tetap)
- Lot size dikalkulasi dari: Risk IDR → Risk USD → Pip Distance → Lot Size
- Jika lot minimum 0.01 masih menghasilkan risk berlebih → SKIP

Format Output Wajib (3 blok):

<< Kakunin >>
- Mode analisis (Signal Evaluation / Independent Analysis)
- Verifikasi kelengkapan data
- Status akun: Balance, Equity (IDR), posisi running
- Jika ada direction hint dari Nyunk-sama: catat, tapi evaluasi tetap objektif

<< Kai >>
- Top-Down H4 → H2 → H1 → M15 (semua indikator)
- Harmonic pattern identification jika relevan (Bat/Gartley/Crab + PRZ)
- Risk & Reward Calculation (IDR, berdasarkan equity terkini)
- Jika direction hint bertentangan data: counter dengan argumentasi teknis

<< Koku >>
- Keputusan: "EXECUTE", "SKIP", atau "WAIT" di awal baris
- EXECUTE: parameter MT5 lengkap (Order Type, Entry, SL, TP, Lot Size)
- SKIP: alasan teknis spesifik
- WAIT: kondisi apa yang harus terpenuhi sebelum entry

Trading Rules TIDAK BISA DIKOMPROMIKAN:
- Risk berbasis % equity live — bukan IDR tetap
- RRR minimum 1:2
- Pending Order diprioritaskan di PRZ / S/D zone
- JPY pairs: Max SL 30 pips | USD/Major: Max SL 20 pips
- High-vol instruments: SKIP jika equity belum cukup
- Counter-trend: lot dikurangi 50%, TP konservatif

Jawab dalam Bahasa Indonesia. Presisi angka adalah kewajiban.
"""

    def __init__(self, config: Config):
        """Initialize Gemini client with configuration"""
        self.config = config
        self.client = genai.Client(api_key=config.gemini_api_key)
        logger.info(f"🧠 Gemini AI Client initialized with model: {config.gemini_model}")

    @with_retry(max_attempts=3, base_delay=2, exceptions=(Exception,))
    async def analyze_signal(
        self,
        signal_data: Dict[str, Any],
        mt5_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Analyze trading signal using Gemini AI"""
        try:
            start_time = datetime.now()

            # Construct the analysis prompt with MT5 data
            prompt = self._construct_analysis_prompt(signal_data, mt5_data)

            # Build content parts list
            content_parts: list = [prompt]

            # Add image if provided
            if signal_data.get('image_path'):
                image_path = Path(signal_data['image_path'])
                if image_path.exists():
                    try:
                        with open(image_path, 'rb') as image_file:
                            image_bytes = image_file.read()
                        content_parts.append(
                            types.Part.from_bytes(data=image_bytes, mime_type='image/jpeg')
                        )
                        logger.info("🖼️  Image attached to Gemini request")
                    except Exception as e:
                        logger.warning(f"⚠️  Could not attach image: {e}, using text only")

            logger.info("🧠 Sending request to Gemini AI...")

            response = await asyncio.to_thread(
                self.client.models.generate_content,
                model=self.config.gemini_model,
                contents=content_parts,
                config=types.GenerateContentConfig(
                    system_instruction=self.RAPHAEL_PROTOCOL,
                    temperature=0.3,
                    top_p=0.8,
                    top_k=40,
                    max_output_tokens=8192,
                    thinking_config=types.ThinkingConfig(thinking_budget=1024),
                    automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
                )
            )

            processing_time = (datetime.now() - start_time).total_seconds()
            logger.info(f"🧠 Gemini AI response received in {processing_time:.2f}s")

            raw_text = response.text
            logger.info("🧠 Raw Gemini AI Response:\n" + "="*50 + f"\n{raw_text}\n" + "="*50)
            parsed_response = self._parse_structured_response(raw_text)

            return {
                'raw_response': raw_text,
                'parsed_response': parsed_response,
                'processing_time': processing_time,
                'model_used': self.config.gemini_model,
                'timestamp': datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"❌ Error in Gemini AI analysis: {e}", exc_info=True)
            raise

    def _construct_analysis_prompt(
        self,
        signal_data: Dict[str, Any],
        mt5_data: Dict[str, Any]
    ) -> str:
        """
        Build the full analysis prompt.
        Timeframe order: H4 (macro) → H2 (intermediate) → H1 (setup) → M15 (entry)
        """
        signal_text = signal_data.get('text_content', 'No text provided')
        has_image   = signal_data.get('image_path') is not None
        mode        = signal_data.get('mode', 'signal')
        direction_hint = signal_data.get('direction_hint')  # 'BUY' | 'SELL' | None

        account_info   = mt5_data.get('account_info', {})
        indicators     = mt5_data.get('indicators', {})
        current_prices = mt5_data.get('current_prices', {})
        positions      = mt5_data.get('current_positions', [])
        summary        = indicators.get('summary', {})

        # ── Account block ────────────────────────────────────────────────
        if mode == 'analyse':
            mode_header = "ANALISIS MANDIRI (INDEPENDENT MARKET ANALYSIS)"
            signal_block = f"Symbol    : {mt5_data.get('symbol', 'N/A')}"
            if direction_hint:
                signal_block += f"\nDirection Hint dari Nyunk-sama: {direction_hint}"
                signal_block += "\n(Hint ini adalah bias awal dari Nyunk-sama — evaluasi objektif tetap wajib. Counter jika data tidak mendukung.)"
            else:
                signal_block += "\n(Tidak ada direction hint — analisis murni objektif)"
        else:
            mode_header = "EVALUASI SIGNAL TRADING"
            signal_block = f"Text Signal : {signal_text}\nImage Input : {'✅ Ada (lihat lampiran gambar)' if has_image else '❌ Tidak ada'}"

        prompt = f"""
{mode_header} - RAPHAEL PROTOCOL
Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S WIB')}

═══════════════════════════════════════
DATA SIGNAL INPUT
═══════════════════════════════════════
{signal_block}

═══════════════════════════════════════
DATA AKUN MT5 (LIVE)
═══════════════════════════════════════
Balance       : Rp {account_info.get('balance', 0):>12,.2f}
Equity        : Rp {account_info.get('equity', 0):>12,.2f}
Margin        : Rp {account_info.get('margin', 0):>12,.2f}
Free Margin   : Rp {account_info.get('margin_free', 0):>12,.2f}
Margin Level  : {account_info.get('margin_level', 0):.2f}%
Floating P/L  : Rp {account_info.get('profit', 0):>12,.2f}
Open Positions: {len(positions)} posisi aktif
"""

        # ── Open positions ────────────────────────────────────────────────
        if positions:
            prompt += "\nPOSISI RUNNING:\n"
            for p in positions:
                direction = "BUY" if p.get('type') == 0 else "SELL"
                prompt += (
                    f"  • {p.get('symbol')} {direction} "
                    f"@ {p.get('price_open')} | "
                    f"SL {p.get('sl')} | TP {p.get('tp')} | "
                    f"P/L Rp {p.get('profit', 0):,.0f}\n"
                )

        # ── Current price ─────────────────────────────────────────────────
        if current_prices:
            prompt += f"""
HARGA SAAT INI ({mt5_data.get('symbol', 'N/A')}):
  Bid    : {current_prices.get('bid', 'N/A')}
  Ask    : {current_prices.get('ask', 'N/A')}
  Spread : {current_prices.get('spread', 'N/A')}
"""

        # ── MTF Confluence Summary ────────────────────────────────────────
        if summary:
            bb_squeeze = ', '.join(summary.get('bb_squeeze_timeframes', [])) or 'none'
            macd_cx = summary.get('macd_crossovers', {})
            macd_cx_str = ' | '.join(f"{k}:{v}" for k, v in macd_cx.items() if v != 'none') or 'none'
            ichi_cloud = summary.get('ichimoku_cloud_by_tf', {})
            ichi_str = ' | '.join(f"{k}:{v}" for k, v in ichi_cloud.items()) or 'N/A'
            prz = summary.get('h4_prz_hint', {})
            prz_str = ' | '.join(f"{k.replace('_',' ').title()}:{v}" for k, v in prz.items()) if prz else 'N/A'

            prompt += f"""
═══════════════════════════════════════
RINGKASAN CONFLUENCE MULTI-TIMEFRAME
═══════════════════════════════════════
Overall Confluence     : {summary.get('overall_confluence', 'N/A')}
HTF Bias (H4+H2)       : {summary.get('htf_bias', 'N/A').upper()}
LTF Bias (H1+M15)      : {summary.get('ltf_bias', 'N/A').upper()}
Trade Recommendation   : {summary.get('trade_recommendation', 'N/A')}

H4 Market Structure    : {summary.get('h4_structure', 'N/A')}
H2 Market Structure    : {summary.get('h2_structure', 'N/A')}
H2 TP Obstruction      : {summary.get('h2_tp_obstruction', 'none')}
M15 Entry Bias         : {summary.get('entry_bias_m15', 'N/A').upper()}
ATR M15                : {summary.get('atr_m15', 'N/A')}

Ichimoku Cloud by TF   : {ichi_str}
H4 Ichimoku Bias       : {summary.get('ichi_h4_bias', 'N/A').upper()}
H1 Ichimoku Bias       : {summary.get('ichi_h1_bias', 'N/A').upper()}

MACD Crossovers        : {macd_cx_str}
BB Squeeze TFs         : {bb_squeeze}

H4 Fibonacci PRZ       : {prz_str}
"""

        # ── Per-timeframe detail (H4 → H2 → H1 → M15) ───────────────────
        prompt += "\n═══════════════════════════════════════\nDATA INDIKATOR DETAIL PER TIMEFRAME\n═══════════════════════════════════════\n"

        for tf in ['H4', 'H2', 'H1', 'M15']:
            tf_data = indicators.get(tf)
            if not tf_data or not isinstance(tf_data, dict):
                prompt += f"\n[{tf}] — DATA TIDAK TERSEDIA\n"
                continue

            sr = tf_data.get('sr_levels', {})
            res_levels = ', '.join(f"{v:.5f}" for v in sr.get('resistance', [])) or 'N/A'
            sup_levels = ', '.join(f"{v:.5f}" for v in sr.get('support', []))    or 'N/A'
            swing_h    = ', '.join(f"{v:.5f}" for v in tf_data.get('swing_highs', [])) or 'N/A'
            swing_l    = ', '.join(f"{v:.5f}" for v in tf_data.get('swing_lows',  [])) or 'N/A'

            prompt += f"""
┌─ {tf} | {tf_data.get('role', '')}
│  Bias             : {tf_data.get('bias', 'N/A').upper()} ({tf_data.get('bull_score',0)}B / {tf_data.get('bear_score',0)}R)
│
│  [PRICE & STRUCTURE]
│  OHLC (last bar)  : O={tf_data.get('open')} H={tf_data.get('high')} L={tf_data.get('low')} C={tf_data.get('current_price')}
│  Market Structure : {tf_data.get('market_structure', 'N/A')}
│  Swing Highs      : {swing_h}
│  Swing Lows       : {swing_l}
│  Resistance       : {res_levels}
│  Support          : {sup_levels}
│  ATR(14)          : {tf_data.get('atr', 'N/A')}
│  Volume           : {tf_data.get('volume', 'N/A')}
│
│  [RSI]
│  RSI(14)          : {tf_data.get('rsi', 'N/A')} → {tf_data.get('rsi_zone', 'N/A')}
│
│  [EMA]
│  EMA 20           : {tf_data.get('ema_20', 'N/A')} (price {tf_data.get('price_vs_ema20', 'N/A')})
│  EMA 50           : {tf_data.get('ema_50', 'N/A')} (price {tf_data.get('price_vs_ema50', 'N/A')})
│  EMA 200          : {tf_data.get('ema_200', 'N/A')} (price {tf_data.get('price_vs_ema200', 'N/A')})
│  EMA Alignment    : {tf_data.get('ema_alignment', 'N/A')}
│
│  [BOLLINGER BANDS (20,2)]
│  Upper / Mid / Lower : {tf_data.get('bb_upper','N/A')} / {tf_data.get('bb_middle','N/A')} / {tf_data.get('bb_lower','N/A')}
│  %B                  : {tf_data.get('bb_pct_b','N/A')}  | Bandwidth: {tf_data.get('bb_bandwidth','N/A')}
│  Squeeze?            : {'⚠️ YES — volatility breakout incoming' if tf_data.get('bb_is_squeeze') else 'No'}
│  Price Position      : {tf_data.get('bb_position','N/A')}
│  Mean Reversion Sig  : {tf_data.get('bb_mean_reversion_signal','N/A')}
│
│  [ICHIMOKU (9,26,52)]
│  Tenkan / Kijun      : {tf_data.get('ichi_tenkan','N/A')} / {tf_data.get('ichi_kijun','N/A')}
│  Senkou A / B        : {tf_data.get('ichi_senkou_a','N/A')} / {tf_data.get('ichi_senkou_b','N/A')}
│  Cloud Position      : {tf_data.get('ichi_cloud_position','N/A')} ({tf_data.get('ichi_cloud_color','N/A')} cloud)
│  TK Cross            : {tf_data.get('ichi_tk_cross','N/A')}
│  Price vs Tenkan     : {tf_data.get('ichi_price_vs_tenkan','N/A')}
│  Price vs Kijun      : {tf_data.get('ichi_price_vs_kijun','N/A')}
│  Chikou Confirmation : {tf_data.get('ichi_chikou_confirmation','N/A')}
│  Ichimoku Bias       : {tf_data.get('ichi_ichimoku_bias','N/A').upper() if tf_data.get('ichi_ichimoku_bias') else 'N/A'}
│
│  [MACD (12,26,9)]
│  MACD / Signal       : {tf_data.get('macd_macd_value','N/A')} / {tf_data.get('macd_signal_value','N/A')}
│  Histogram           : {tf_data.get('macd_histogram_value','N/A')} ({tf_data.get('macd_histogram_trend','N/A')})
│  Crossover           : {tf_data.get('macd_crossover','N/A')}
│  Zero Line           : {tf_data.get('macd_zero_line','N/A')}
│  Momentum            : {tf_data.get('macd_momentum','N/A').upper() if tf_data.get('macd_momentum') else 'N/A'}
│
│  [FIBONACCI / PRZ HINT]
│  Swing High/Low      : {tf_data.get('fibonacci',{}).get('swing_high','N/A')} / {tf_data.get('fibonacci',{}).get('swing_low','N/A')}
│  Bat PRZ             : {tf_data.get('fibonacci',{}).get('prz_zone_hint',{}).get('bat_prz','N/A')}
│  Gartley PRZ         : {tf_data.get('fibonacci',{}).get('prz_zone_hint',{}).get('gartley_prz','N/A')}
│  Crab PRZ            : {tf_data.get('fibonacci',{}).get('prz_zone_hint',{}).get('crab_prz','N/A')}
└{'─' * 60}
"""

        # ── Instructions ─────────────────────────────────────────────────
        if mode == 'analyse':
            instructions = """
═══════════════════════════════════════
INSTRUKSI ANALISIS RAPHAEL — MODE INDEPENDENT
═══════════════════════════════════════
Tidak ada signal dari sumber eksternal. Raphael harus cari setup sendiri berdasarkan data di atas.

1. <<Kakunin>>: Verifikasi data MT5, status akun (equity, posisi running), dan symbol.
   Jika ada direction hint dari Nyunk-sama, catat — tapi evaluasi tetap objektif.

2. <<Kai>>: Lakukan analisis Top-Down H4 → H2 → H1 → M15:
   - H4: Macro bias, HTF structure, Ichimoku cloud, identifikasi harmonic pattern jika ada
   - H2: Intermediate structure, TP barrier check, PRZ validation
   - H1: Setup location, Bollinger Band squeeze, Ichimoku TK cross
   - M15: Entry trigger, RSI divergence, MACD crossover, SL presisi
   - Jika ada direction hint yang BERTENTANGAN dengan data → counter secara eksplisit dan jelaskan alasannya
   - Kalkulasi risk/reward berdasarkan LIVE EQUITY di atas

3. <<Koku>>: EXECUTE, SKIP, atau WAIT:
   - EXECUTE: ada setup valid, parameter MT5 lengkap
   - SKIP: market tidak ada setup yang memenuhi syarat saat ini
   - WAIT: ada potensi setup tapi belum trigger — jelaskan kondisi yang harus terpenuhi
   - Jika SKIP/WAIT: jelaskan spesifik kondisi apa yang kurang

Prioritas: Keamanan modal > RRR > Entry precision
"""
        else:
            instructions = """
═══════════════════════════════════════
INSTRUKSI ANALISIS RAPHAEL — MODE SIGNAL EVALUATION
═══════════════════════════════════════
1. <<Kakunin>>: Verifikasi semua data di atas — kelengkapan data, status akun, posisi running.
2. <<Kai>>: Lakukan analisis Top-Down H4 → H2 → H1 → M15:
   - H4: Tentukan macro bias & struktur HTF (HH/HL atau LH/LL)
   - H2: Periksa intermediate structure & identifikasi potential TP barrier / obstruction zone
   - H1: Konfirmasi lokasi setup & kelayakan entry area
   - M15: Tentukan titik entry presisi, SL tight, dan micro structure trigger
   - Hitung pip distance SL dan TP, konversi ke IDR (berdasarkan equity live)
   - Kalkulasi RRR & tentukan jenis order (Pending vs Instant)
3. <<Koku>>: Keputusan EXECUTE atau SKIP dengan parameter MT5 presisi.
   - Jika EXECUTE: sertakan Order Type, Entry, SL, TP, Lot Size
   - Jika SKIP: jelaskan alasan teknis spesifik

Prioritas: Keamanan modal > RRR > Entry precision
"""
        prompt += instructions
        return prompt

    def _parse_structured_response(self, response_text: str) -> Dict[str, Any]:
        """Parse the structured <<Kakunin>>, <<Kai>>, <<Koku>> response with robust regex matching"""
        parsed = {
            'kakunin': '',
            'kai': '',
            'koku': '',
            'decision': 'UNKNOWN',
            'parameters': {}
        }

        try:
            lines = response_text.split('\n')
            current_section = None
            current_content: list = []

            for line in lines:
                # Match << Kakunin >>, <<Kai>>, ## << Koku >>, **<<Koku>>**, etc.
                match = re.search(r'<<\s*(kakunin|kai|koku)\s*>>', line, re.IGNORECASE)
                if match:
                    section_name = match.group(1).lower()
                    # Save previous section content
                    if current_section:
                        parsed[current_section] = '\n'.join(current_content).strip()
                    current_section = section_name
                    current_content = []
                elif current_section:
                    current_content.append(line)

            # Save the last section
            if current_section:
                parsed[current_section] = '\n'.join(current_content).strip()

            # If section parsing was empty due to unexpected formatting, fallback to regex search
            if not parsed['koku']:
                koku_match = re.search(r'<<\s*koku\s*>>([\s\S]*)$', response_text, re.IGNORECASE)
                if koku_match:
                    parsed['koku'] = koku_match.group(1).strip()

            # Extract decision from Koku or full response
            search_text = parsed['koku'] if parsed['koku'] else response_text
            search_upper = search_text.upper()

            if re.search(r'\bEXECUTE\b', search_upper):
                parsed['decision'] = 'EXECUTE'
                parsed['parameters'] = self._extract_mt5_parameters(search_text)
            elif re.search(r'\bSKIP\b', search_upper):
                parsed['decision'] = 'SKIP'
            elif re.search(r'\bWAIT\b', search_upper):
                parsed['decision'] = 'WAIT'
            else:
                parsed['decision'] = 'UNKNOWN'

            logger.info(
                f"🧠 Parsed decision: {parsed['decision']} | "
                f"Kakunin={len(parsed['kakunin'])} chars, "
                f"Kai={len(parsed['kai'])} chars, "
                f"Koku={len(parsed['koku'])} chars | "
                f"Parameters: {parsed['parameters']}"
            )
            return parsed

        except Exception as e:
            logger.error(f"❌ Error parsing structured response: {e}", exc_info=True)
            return {
                'kakunin': response_text,
                'kai': '',
                'koku': '',
                'decision': 'PARSE_ERROR',
                'parameters': {}
            }

    def _extract_mt5_parameters(self, koku_content: str) -> Dict[str, Any]:
        """Extract MT5 parameters from Koku section"""
        parameters: Dict[str, Any] = {}

        try:
            lines = koku_content.split('\n')

            for line in lines:
                line_stripped = line.strip()

                # Order Type
                if re.search(r'Buy\s+Limit', line_stripped, re.IGNORECASE):
                    parameters['order_type'] = 'BUY_LIMIT'
                elif re.search(r'Sell\s+Limit', line_stripped, re.IGNORECASE):
                    parameters['order_type'] = 'SELL_LIMIT'
                elif re.search(r'Buy\s+Stop', line_stripped, re.IGNORECASE):
                    parameters['order_type'] = 'BUY_STOP'
                elif re.search(r'Sell\s+Stop', line_stripped, re.IGNORECASE):
                    parameters['order_type'] = 'SELL_STOP'
                elif re.search(r'Buy\s*(Instant|Market)?\b', line_stripped, re.IGNORECASE) and 'order' in line_stripped.lower():
                    parameters['order_type'] = 'BUY'
                elif re.search(r'Sell\s*(Instant|Market)?\b', line_stripped, re.IGNORECASE) and 'order' in line_stripped.lower():
                    parameters['order_type'] = 'SELL'

                # Price (Entry)
                if re.search(r'Price\s*\(Entry\)|Entry\s*Price|\bEntry\b', line_stripped, re.IGNORECASE):
                    numbers = re.findall(r'\d+\.?\d*', line_stripped)
                    if numbers:
                        parameters['entry_price'] = float(numbers[-1])

                # Stop Loss
                if re.search(r'Stop\s*Loss|\bSL\b', line_stripped, re.IGNORECASE) and 'order' not in line_stripped.lower():
                    numbers = re.findall(r'\d+\.?\d*', line_stripped)
                    if numbers:
                        parameters['stop_loss'] = float(numbers[-1])

                # Take Profit
                if re.search(r'Take\s*Profit|\bTP\b', line_stripped, re.IGNORECASE):
                    numbers = re.findall(r'\d+\.?\d*', line_stripped)
                    if numbers:
                        parameters['take_profit'] = float(numbers[-1])

                # Lot Size
                if re.search(r'Lot\s*Size|\bLot\b', line_stripped, re.IGNORECASE):
                    numbers = re.findall(r'\d+\.?\d*', line_stripped)
                    if numbers:
                        parameters['lot_size'] = float(numbers[-1])

            logger.debug(f"🧠 Extracted MT5 parameters: {parameters}")
            return parameters

        except Exception as e:
            logger.error(f"❌ Error extracting MT5 parameters: {e}")
            return {}

    async def test_connection(self) -> bool:
        """Test Gemini API connection"""
        try:
            logger.info("🧠 Testing Gemini API connection...")

            response = await asyncio.to_thread(
                self.client.models.generate_content,
                model=self.config.gemini_model,
                contents="Test connection. Respond with 'OK' only.",
                config=types.GenerateContentConfig(
                    temperature=0.1,
                    max_output_tokens=10,
                )
            )

            if response and response.text and 'OK' in response.text.upper():
                logger.info("✅ Gemini API connection test successful")
                return True
            else:
                logger.warning(f"⚠️  Gemini API returned unexpected response: {response.text!r}")
                return False

        except Exception as e:
            logger.error(f"❌ Gemini API connection test failed: {e}")
            return False
