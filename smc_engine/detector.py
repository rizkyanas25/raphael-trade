"""
SMC Detector — Raphael AI Bot v2.0
Wisdom Lord Raphael — Core SMC Analytical Engine & Crypto Risk Guard

Implements Pure Price Action & Smart Money Concepts (SMC):
  - Break of Structure (BOS) detection on H1 candles
  - Change of Character (CHOCH) detection on M5 candles
  - Unmitigated Order Block (OB) identification on M15/M5
  - Liquidity Pool (Equal Highs / Equal Lows) detection
  - Top-Down structured output for Gemini AI prompt injection

All detection is algorithmic — Gemini AI receives the structured output
and makes the final EXECUTE/SKIP decision.
"""

import logging
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# OHLCV column indices
IDX_TIME  = 0
IDX_OPEN  = 1
IDX_HIGH  = 2
IDX_LOW   = 3
IDX_CLOSE = 4
IDX_VOL   = 5

# How close two highs/lows must be to be considered "equal" (as % of price)
EQUAL_LEVEL_TOLERANCE = 0.0015   # 0.15%

# Minimum candles that must separate an OB from the current candle for it to
# count as "unmitigated" (still fresh, price hasn't returned to it)
OB_MIN_AGE_CANDLES = 3


@dataclass
class OrderBlock:
    """Represents a detected Order Block zone."""
    tf: str                    # timeframe: 'H1' | 'M15' | 'M5'
    ob_type: str               # 'DEMAND' | 'SUPPLY'
    high: float
    low: float
    origin_index: int          # index in the candle array where OB formed
    is_mitigated: bool = False
    strength: str = "NORMAL"   # 'STRONG' | 'NORMAL'

    @property
    def mid(self) -> float:
        return (self.high + self.low) / 2


@dataclass
class LiquidityPool:
    """Represents equal highs or equal lows (liquidity resting above/below)."""
    pool_type: str    # 'EQH' (equal highs) | 'EQL' (equal lows)
    price: float      # approximate price level of the liquidity
    count: int        # how many touches / equal points


@dataclass
class SMCAnalysis:
    """Full SMC analysis output for one symbol across H1 / M15 / M5."""
    symbol: str

    # H1 bias
    h1_bias: str = "NEUTRAL"          # 'BULLISH' | 'BEARISH' | 'NEUTRAL'
    h1_last_bos: str = "NONE"         # 'BULLISH_BOS' | 'BEARISH_BOS' | 'NONE'
    h1_swing_high: float = 0.0
    h1_swing_low: float = 0.0
    h1_current_price: float = 0.0

    # M15 structure
    m15_order_blocks: List[OrderBlock] = field(default_factory=list)
    m15_liquidity_pools: List[LiquidityPool] = field(default_factory=list)
    m15_current_price: float = 0.0

    # M5 precision
    m5_choch_detected: bool = False
    m5_choch_type: str = "NONE"       # 'BULLISH_CHOCH' | 'BEARISH_CHOCH' | 'NONE'
    m5_order_blocks: List[OrderBlock] = field(default_factory=list)
    m5_current_price: float = 0.0

    # Summary flags
    has_valid_setup: bool = False
    setup_bias: str = "NONE"          # 'LONG' | 'SHORT' | 'NONE'
    skip_reason: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol":         self.symbol,
            "h1_bias":        self.h1_bias,
            "h1_last_bos":    self.h1_last_bos,
            "h1_swing_high":  self.h1_swing_high,
            "h1_swing_low":   self.h1_swing_low,
            "h1_price":       self.h1_current_price,
            "m15_obs":        [
                {
                    "type": ob.ob_type, "high": ob.high, "low": ob.low,
                    "mid": ob.mid, "strength": ob.strength,
                    "mitigated": ob.is_mitigated,
                }
                for ob in self.m15_order_blocks
            ],
            "m15_liquidity":  [
                {"type": lp.pool_type, "price": lp.price, "count": lp.count}
                for lp in self.m15_liquidity_pools
            ],
            "m15_price":      self.m15_current_price,
            "m5_choch":       self.m5_choch_detected,
            "m5_choch_type":  self.m5_choch_type,
            "m5_obs":         [
                {
                    "type": ob.ob_type, "high": ob.high, "low": ob.low,
                    "mid": ob.mid, "strength": ob.strength,
                }
                for ob in self.m5_order_blocks
            ],
            "m5_price":       self.m5_current_price,
            "has_valid_setup": self.has_valid_setup,
            "setup_bias":     self.setup_bias,
            "skip_reason":    self.skip_reason,
        }


class SMCDetector:
    """
    SMC algorithmic detector.

    Usage:
        detector = SMCDetector()
        analysis = detector.analyse(symbol, h1_candles, m15_candles, m5_candles)
    """

    def analyse(
        self,
        symbol: str,
        h1_candles: List[List[float]],
        m15_candles: List[List[float]],
        m5_candles: List[List[float]],
    ) -> SMCAnalysis:
        """
        Run full top-down SMC analysis.

        Args:
            symbol:      trading pair, e.g. 'SOLUSDT'
            h1_candles:  list of [ts,o,h,l,c,v] — 100 H1 candles
            m15_candles: list of [ts,o,h,l,c,v] — 100 M15 candles
            m5_candles:  list of [ts,o,h,l,c,v] — 100 M5 candles

        Returns:
            SMCAnalysis dataclass with all detected structures.
        """
        result = SMCAnalysis(symbol=symbol)

        if not h1_candles or not m15_candles or not m5_candles:
            result.skip_reason = "Insufficient candle data"
            logger.warning(f"⚠️  {symbol}: insufficient candle data for SMC analysis")
            return result

        # ── H1: Macro Bias & BOS ─────────────────────────────────────────
        h1_bias, h1_bos, h1_sh, h1_sl = self._detect_bias_and_bos(h1_candles)
        result.h1_bias        = h1_bias
        result.h1_last_bos    = h1_bos
        result.h1_swing_high  = h1_sh
        result.h1_swing_low   = h1_sl
        result.h1_current_price = h1_candles[-1][IDX_CLOSE]

        logger.debug(f"📊 {symbol} H1 | Bias: {h1_bias} | BOS: {h1_bos} | SH: {h1_sh:.4f} | SL: {h1_sl:.4f}")

        # ── M15: Order Blocks + Liquidity Pools ──────────────────────────
        m15_obs = self._detect_order_blocks(m15_candles, "M15", h1_bias)
        m15_lps = self._detect_liquidity_pools(m15_candles)
        # Mark mitigated OBs (price has already traded through them)
        m15_current = m15_candles[-1][IDX_CLOSE]
        for ob in m15_obs:
            ob.is_mitigated = self._is_ob_mitigated(ob, m15_candles, ob.origin_index)

        result.m15_order_blocks   = [ob for ob in m15_obs if not ob.is_mitigated]
        result.m15_liquidity_pools = m15_lps
        result.m15_current_price  = m15_current

        logger.debug(
            f"📊 {symbol} M15 | OBs: {len(result.m15_order_blocks)} unmitigated "
            f"| Liquidity pools: {len(m15_lps)}"
        )

        # ── M5: CHOCH + Precision OBs ───────────────────────────────────
        m5_choch, m5_choch_type = self._detect_choch(m5_candles, h1_bias)
        m5_obs = self._detect_order_blocks(m5_candles, "M5", h1_bias)
        result.m5_choch_detected = m5_choch
        result.m5_choch_type     = m5_choch_type
        result.m5_order_blocks   = [ob for ob in m5_obs if not self._is_ob_mitigated(ob, m5_candles, ob.origin_index)]
        result.m5_current_price  = m5_candles[-1][IDX_CLOSE]

        logger.debug(
            f"📊 {symbol} M5 | CHOCH: {m5_choch} ({m5_choch_type}) "
            f"| OBs: {len(result.m5_order_blocks)}"
        )

        # ── Setup Validity ───────────────────────────────────────────────
        result.has_valid_setup, result.setup_bias, result.skip_reason = (
            self._evaluate_setup_validity(result)
        )

        logger.info(
            f"🔍 {symbol} | Bias: {h1_bias} | BOS: {h1_bos} | "
            f"CHOCH: {m5_choch_type} | Valid: {result.has_valid_setup} "
            f"| Bias: {result.setup_bias}"
            + (f" | Skip: {result.skip_reason}" if result.skip_reason else "")
        )
        return result

    # ── H1: Bias & BOS Detection ───────────────────────────────────────────

    def _detect_bias_and_bos(
        self, candles: List[List[float]]
    ) -> Tuple[str, str, float, float]:
        """
        Identify the last Break of Structure (BOS) and macro bias.

        Returns: (bias, bos_type, last_swing_high, last_swing_low)
        """
        if len(candles) < 10:
            return "NEUTRAL", "NONE", 0.0, 0.0

        swing_highs = self._find_swing_highs(candles, lookback=5)
        swing_lows  = self._find_swing_lows(candles,  lookback=5)

        if not swing_highs or not swing_lows:
            return "NEUTRAL", "NONE", 0.0, 0.0

        last_sh = swing_highs[-1]
        last_sl = swing_lows[-1]

        # Current close
        current_close = candles[-1][IDX_CLOSE]

        bias    = "NEUTRAL"
        bos     = "NONE"

        # Bullish BOS: price closes above the most recent swing high
        if len(swing_highs) >= 2:
            prev_sh = swing_highs[-2]
            if current_close > prev_sh[IDX_HIGH]:
                bias = "BULLISH"
                bos  = "BULLISH_BOS"

        # Bearish BOS: price closes below the most recent swing low
        if len(swing_lows) >= 2:
            prev_sl = swing_lows[-2]
            if current_close < prev_sl[IDX_LOW]:
                bias = "BEARISH"
                bos  = "BEARISH_BOS"

        # Fallback: use EMA-like slope of closes
        if bias == "NEUTRAL":
            mid   = len(candles) // 2
            first_half_avg  = sum(c[IDX_CLOSE] for c in candles[:mid])  / mid
            second_half_avg = sum(c[IDX_CLOSE] for c in candles[mid:])  / (len(candles) - mid)
            if second_half_avg > first_half_avg * 1.002:
                bias = "BULLISH"
            elif second_half_avg < first_half_avg * 0.998:
                bias = "BEARISH"

        return bias, bos, last_sh[IDX_HIGH], last_sl[IDX_LOW]

    # ── Order Block Detection ──────────────────────────────────────────────

    def _detect_order_blocks(
        self,
        candles: List[List[float]],
        tf: str,
        h1_bias: str,
        lookback: int = 30,
    ) -> List[OrderBlock]:
        """
        Detect Order Blocks from candle data.

        SMC definition:
          DEMAND OB: last bearish candle before a strong bullish impulse move up
          SUPPLY OB: last bullish candle before a strong bearish impulse move down

        We look for candles followed by an impulse of ≥2 consecutive
        same-direction candles that break structure.
        """
        obs: List[OrderBlock] = []
        scan = candles[-lookback:] if len(candles) > lookback else candles
        offset = max(0, len(candles) - lookback)

        for i in range(len(scan) - OB_MIN_AGE_CANDLES - 1):
            candle  = scan[i]
            is_bull = candle[IDX_CLOSE] > candle[IDX_OPEN]
            is_bear = candle[IDX_CLOSE] < candle[IDX_OPEN]

            # Look at the next N candles for impulse
            subsequent = scan[i + 1: i + 4]
            if len(subsequent) < 2:
                continue

            bull_impulse = all(c[IDX_CLOSE] > c[IDX_OPEN] for c in subsequent)
            bear_impulse = all(c[IDX_CLOSE] < c[IDX_OPEN] for c in subsequent)

            # DEMAND OB: bearish candle followed by bullish impulse
            if is_bear and bull_impulse and h1_bias in ("BULLISH", "NEUTRAL"):
                strength = "STRONG" if self._is_strong_impulse(subsequent) else "NORMAL"
                obs.append(OrderBlock(
                    tf           = tf,
                    ob_type      = "DEMAND",
                    high         = candle[IDX_HIGH],
                    low          = candle[IDX_LOW],
                    origin_index = offset + i,
                    strength     = strength,
                ))

            # SUPPLY OB: bullish candle followed by bearish impulse
            elif is_bull and bear_impulse and h1_bias in ("BEARISH", "NEUTRAL"):
                strength = "STRONG" if self._is_strong_impulse(subsequent) else "NORMAL"
                obs.append(OrderBlock(
                    tf           = tf,
                    ob_type      = "SUPPLY",
                    high         = candle[IDX_HIGH],
                    low          = candle[IDX_LOW],
                    origin_index = offset + i,
                    strength     = strength,
                ))

        # Keep only the 3 most recent per type
        demand_obs = sorted(
            [ob for ob in obs if ob.ob_type == "DEMAND"],
            key=lambda x: x.origin_index, reverse=True
        )[:3]
        supply_obs = sorted(
            [ob for ob in obs if ob.ob_type == "SUPPLY"],
            key=lambda x: x.origin_index, reverse=True
        )[:3]

        return demand_obs + supply_obs

    def _is_strong_impulse(self, candles: List[List[float]]) -> bool:
        """True if the impulse move is large (body > 60% of range)."""
        total_body = sum(abs(c[IDX_CLOSE] - c[IDX_OPEN]) for c in candles)
        total_range = sum(c[IDX_HIGH] - c[IDX_LOW] for c in candles)
        if total_range == 0:
            return False
        return (total_body / total_range) >= 0.60

    def _is_ob_mitigated(
        self,
        ob: OrderBlock,
        candles: List[List[float]],
        origin_index: int,
    ) -> bool:
        """
        Returns True if price has traded INTO the OB zone after it formed.
        Mitigation = price low went below OB high (DEMAND) or price high went above OB low (SUPPLY).
        """
        subsequent = candles[origin_index + 1:]
        if not subsequent:
            return False

        for c in subsequent:
            if ob.ob_type == "DEMAND" and c[IDX_LOW] <= ob.high:
                return True
            if ob.ob_type == "SUPPLY" and c[IDX_HIGH] >= ob.low:
                return True
        return False

    # ── CHOCH Detection ────────────────────────────────────────────────────

    def _detect_choch(
        self,
        candles: List[List[float]],
        h1_bias: str,
        lookback: int = 30,
    ) -> Tuple[bool, str]:
        """
        Detect Change of Character (CHOCH) on M5.

        CHOCH = structure break AGAINST the previous micro trend,
        signalling a potential reversal in the direction of H1 bias.

        Returns: (choch_detected: bool, choch_type: str)
        """
        scan = candles[-lookback:] if len(candles) > lookback else candles
        if len(scan) < 10:
            return False, "NONE"

        swing_highs = self._find_swing_highs(scan, lookback=3)
        swing_lows  = self._find_swing_lows(scan,  lookback=3)

        if len(swing_highs) < 2 or len(swing_lows) < 2:
            return False, "NONE"

        current_close = scan[-1][IDX_CLOSE]
        prev_sh       = swing_highs[-2]
        prev_sl       = swing_lows[-2]
        last_sh       = swing_highs[-1]
        last_sl       = swing_lows[-1]

        # Bullish CHOCH: in a bearish M5 micro-trend, price breaks above last SH
        # (aligned with H1 bullish bias → confirms reversal up)
        if h1_bias == "BULLISH":
            if current_close > last_sh[IDX_HIGH] and last_sh[IDX_HIGH] > prev_sh[IDX_HIGH]:
                return True, "BULLISH_CHOCH"

        # Bearish CHOCH: in a bullish M5 micro-trend, price breaks below last SL
        elif h1_bias == "BEARISH":
            if current_close < last_sl[IDX_LOW] and last_sl[IDX_LOW] < prev_sl[IDX_LOW]:
                return True, "BEARISH_CHOCH"

        # Neutral bias — check both
        else:
            if current_close > last_sh[IDX_HIGH]:
                return True, "BULLISH_CHOCH"
            if current_close < last_sl[IDX_LOW]:
                return True, "BEARISH_CHOCH"

        return False, "NONE"

    # ── Liquidity Pool Detection ───────────────────────────────────────────

    def _detect_liquidity_pools(
        self, candles: List[List[float]]
    ) -> List[LiquidityPool]:
        """
        Detect Equal Highs (EQH) and Equal Lows (EQL) as liquidity pools.

        A pool forms when 2+ swing points cluster within EQUAL_LEVEL_TOLERANCE.
        """
        pools: List[LiquidityPool] = []
        highs = [c[IDX_HIGH] for c in candles]
        lows  = [c[IDX_LOW]  for c in candles]

        # EQH: cluster of similar highs
        eqh = self._cluster_levels(highs)
        for price, count in eqh:
            if count >= 2:
                pools.append(LiquidityPool("EQH", price, count))

        # EQL: cluster of similar lows
        eql = self._cluster_levels(lows)
        for price, count in eql:
            if count >= 2:
                pools.append(LiquidityPool("EQL", price, count))

        return pools

    def _cluster_levels(
        self, prices: List[float]
    ) -> List[Tuple[float, int]]:
        """Group price levels within tolerance and return (representative_price, count)."""
        clusters: List[Tuple[float, int]] = []
        sorted_prices = sorted(prices)

        i = 0
        while i < len(sorted_prices):
            ref   = sorted_prices[i]
            group = [ref]
            j = i + 1
            while j < len(sorted_prices):
                if abs(sorted_prices[j] - ref) / ref <= EQUAL_LEVEL_TOLERANCE:
                    group.append(sorted_prices[j])
                    j += 1
                else:
                    break
            avg = sum(group) / len(group)
            clusters.append((avg, len(group)))
            i = j

        return clusters

    # ── Swing Point Helpers ────────────────────────────────────────────────

    def _find_swing_highs(
        self, candles: List[List[float]], lookback: int = 5
    ) -> List[List[float]]:
        """
        Find local swing highs: candle whose HIGH is the highest among
        `lookback` candles on each side.
        """
        swings: List[List[float]] = []
        n = len(candles)
        for i in range(lookback, n - lookback):
            high = candles[i][IDX_HIGH]
            left  = all(candles[i - k][IDX_HIGH] < high for k in range(1, lookback + 1))
            right = all(candles[i + k][IDX_HIGH] < high for k in range(1, lookback + 1))
            if left and right:
                swings.append(candles[i])
        return swings

    def _find_swing_lows(
        self, candles: List[List[float]], lookback: int = 5
    ) -> List[List[float]]:
        """
        Find local swing lows: candle whose LOW is the lowest among
        `lookback` candles on each side.
        """
        swings: List[List[float]] = []
        n = len(candles)
        for i in range(lookback, n - lookback):
            low  = candles[i][IDX_LOW]
            left  = all(candles[i - k][IDX_LOW] > low for k in range(1, lookback + 1))
            right = all(candles[i + k][IDX_LOW] > low for k in range(1, lookback + 1))
            if left and right:
                swings.append(candles[i])
        return swings

    # ── Setup Validity Check ───────────────────────────────────────────────

    def _evaluate_setup_validity(
        self, result: SMCAnalysis
    ) -> Tuple[bool, str, str]:
        """
        Determine if the full SMC structure constitutes a valid trade setup.

        Minimum requirements (Rule 1 logic):
          1. H1 bias must not be NEUTRAL
          2. At least 1 unmitigated M15 OB aligned with H1 bias
          3. CHOCH confirmed on M5 in the bias direction

        Returns: (is_valid, setup_bias, skip_reason)
        """
        if result.h1_bias == "NEUTRAL":
            return False, "NONE", "H1 bias is NEUTRAL — no clear macro direction"

        # Find M15 OBs aligned with H1 bias
        aligned_obs = [
            ob for ob in result.m15_order_blocks
            if (result.h1_bias == "BULLISH" and ob.ob_type == "DEMAND")
            or (result.h1_bias == "BEARISH" and ob.ob_type == "SUPPLY")
        ]

        if not aligned_obs:
            return (
                False, "NONE",
                f"No unmitigated M15 {'Demand' if result.h1_bias == 'BULLISH' else 'Supply'} OB aligned with H1 {result.h1_bias} bias"
            )

        # CHOCH must be confirmed and in the same direction
        if not result.m5_choch_detected:
            return (
                False, "NONE",
                "M5 CHOCH not confirmed — waiting for structure shift trigger"
            )

        choch_direction = "LONG" if result.m5_choch_type == "BULLISH_CHOCH" else "SHORT"
        bias_direction  = "LONG" if result.h1_bias == "BULLISH" else "SHORT"

        if choch_direction != bias_direction:
            return (
                False, "NONE",
                f"CHOCH direction ({choch_direction}) conflicts with H1 bias ({bias_direction})"
            )

        return True, bias_direction, ""

    # ── Prompt Builder ─────────────────────────────────────────────────────

    def build_gemini_prompt_section(self, analysis: SMCAnalysis) -> str:
        """
        Build the SMC data block to inject into the Gemini prompt.
        This feeds into the <<Kai>> section of Raphael Protocol v2.
        """
        a = analysis
        lines = [
            "═══════════════════════════════════════",
            f"SMC ANALYSIS DATA — {a.symbol}",
            "═══════════════════════════════════════",
            "",
            f"── H1 MACRO BIAS ──",
            f"  Bias          : {a.h1_bias}",
            f"  Last BOS      : {a.h1_last_bos}",
            f"  Swing High    : {a.h1_swing_high:.6f}",
            f"  Swing Low     : {a.h1_swing_low:.6f}",
            f"  Current Price : {a.h1_current_price:.6f}",
            "",
            f"── M15 STRUCTURE ──",
            f"  Current Price : {a.m15_current_price:.6f}",
            f"  Unmitigated OBs: {len(a.m15_order_blocks)}",
        ]

        for ob in a.m15_order_blocks:
            lines.append(
                f"    [{ob.ob_type} OB | {ob.strength}] "
                f"High={ob.high:.6f}  Low={ob.low:.6f}  Mid={ob.mid:.6f}"
            )

        lines += [
            "",
            f"  Liquidity Pools: {len(a.m15_liquidity_pools)}",
        ]
        for lp in a.m15_liquidity_pools:
            lines.append(
                f"    [{lp.pool_type}] Price≈{lp.price:.6f}  Touches={lp.count}"
            )

        lines += [
            "",
            f"── M5 PRECISION TRIGGER ──",
            f"  Current Price : {a.m5_current_price:.6f}",
            f"  CHOCH         : {'✅ ' + a.m5_choch_type if a.m5_choch_detected else '❌ Not detected'}",
            f"  M5 OBs        : {len(a.m5_order_blocks)}",
        ]
        for ob in a.m5_order_blocks:
            lines.append(
                f"    [{ob.ob_type} OB | {ob.strength}] "
                f"High={ob.high:.6f}  Low={ob.low:.6f}  Mid={ob.mid:.6f}"
            )

        lines += [
            "",
            f"── SETUP SUMMARY ──",
            f"  Valid Setup   : {'✅ YES' if a.has_valid_setup else '❌ NO'}",
            f"  Setup Bias    : {a.setup_bias}",
        ]
        if a.skip_reason:
            lines.append(f"  Skip Reason   : {a.skip_reason}")

        lines.append("═══════════════════════════════════════")
        return "\n".join(lines)
