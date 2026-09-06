"""
Technical Indicators Module for Raphael AI Bot
Wisdom Lord Raphael - Core Analytical Engine & Financial Risk Guard

Indicator stack (matches MT5 setup):
  Main Window : Moving Average (EMA 20/50/200) + Bollinger Bands + Ichimoku Kinko Hyo
  Window 1    : RSI (14)
  Window 2    : MACD (12, 26, 9)

Signal context:
  - Arist MD  : Harmonic patterns (Bat/Gartley/Deep Crab/Butterfly/Cypher) with PRZ
                Fibonacci-based XABCD swing legs, multiple TP targets
  - Rayner    : Price action, Bollinger Bands mean reversion, swing structure,
                Ichimoku as trend filter/confirmation

Timeframe roles (top-down):
  H4  — Macro bias, HTF structure, major harmonic pattern completion zone
  H2  — Intermediate structure, TP barrier check, PRZ zone validation
  H1  — Setup location, Ichimoku cloud position, Bollinger Band squeeze
  M15 — Entry trigger, SL precision, micro structure confirmation
"""

import logging
from typing import Optional, Dict, Any, List, Tuple
import pandas as pd
import numpy as np

from config import Config


logger = logging.getLogger(__name__)

_mt5 = None


def _get_mt5():
    global _mt5
    if _mt5 is None:
        from mt5_module.mt5_loader import mt5 as _m
        _mt5 = _m
    return _mt5


class IndicatorCalculator:
    """
    Full indicator stack matching actual MT5 setup.

    MT5 Timeframe constants:
      TIMEFRAME_M15 = 15
      TIMEFRAME_H1  = 60
      TIMEFRAME_H2  = 120  (valid MT5 constant, confirmed mql5.com)
      TIMEFRAME_H4  = 240
    """

    TIMEFRAMES: Dict[str, int] = {
        'M15': 15,
        'H1':  60,
        'H2':  120,
        'H4':  240,
    }

    TIMEFRAME_ROLES: Dict[str, str] = {
        'M15': 'Entry Trigger & SL Precision (micro structure, Ichimoku TK cross)',
        'H1':  'Setup Location & BB Squeeze Check (Ichimoku cloud position)',
        'H2':  'TP Barrier Check & PRZ Zone Validation (intermediate structure)',
        'H4':  'Macro Bias & Harmonic Pattern Completion (HTF structure)',
    }

    # Ichimoku standard settings (9, 26, 52)
    ICHIMOKU_TENKAN  = 9
    ICHIMOKU_KIJUN   = 26
    ICHIMOKU_SENKOU  = 52

    # Bollinger Bands standard settings (20, 2.0)
    BB_PERIOD = 20
    BB_STD    = 2.0

    # MACD standard settings (12, 26, 9)
    MACD_FAST   = 12
    MACD_SLOW   = 26
    MACD_SIGNAL = 9

    def __init__(self, config: Config):
        self.config = config
        self.bars_count = 300  # Need more bars for Ichimoku Senkou B (52-period)

    # ------------------------------------------------------------------ #
    #  OHLC Data                                                           #
    # ------------------------------------------------------------------ #

    def get_ohlc_data(
        self,
        symbol: str,
        timeframe: str,
        bars: int = 300
    ) -> Optional[pd.DataFrame]:
        """Fetch OHLC bars from MT5 for a given timeframe string."""
        try:
            mt5_tf = self.TIMEFRAMES.get(timeframe)
            if mt5_tf is None:
                logger.error(f"❌ Invalid timeframe: {timeframe}")
                return None

            mt5 = _get_mt5()
            rates = mt5.copy_rates_from_pos(symbol, mt5_tf, 0, bars)

            if rates is None or len(rates) == 0:
                logger.warning(f"⚠️  No data returned for {symbol} {timeframe}")
                return None

            df = pd.DataFrame(rates)
            if 'time' in df.columns:
                df['time'] = pd.to_datetime(df['time'], unit='s')
                df.set_index('time', inplace=True)

            return df

        except Exception as e:
            logger.error(f"❌ Error fetching OHLC for {symbol} {timeframe}: {e}")
            return None

    # ------------------------------------------------------------------ #
    #  RSI                                                                 #
    # ------------------------------------------------------------------ #

    def calculate_rsi(self, df: pd.DataFrame, period: int = 14) -> Optional[pd.Series]:
        """Wilder-smoothed RSI (matches MT5 RSI indicator)."""
        try:
            if len(df) < period + 1:
                return None
            delta = df['close'].diff()
            gain = delta.clip(lower=0)
            loss = -delta.clip(upper=0)
            avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
            avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
            rs = avg_gain / avg_loss.replace(0, np.nan)
            return 100 - (100 / (1 + rs))
        except Exception as e:
            logger.error(f"❌ RSI error: {e}")
            return None

    # ------------------------------------------------------------------ #
    #  Moving Averages                                                     #
    # ------------------------------------------------------------------ #

    def calculate_ema(self, df: pd.DataFrame, period: int) -> Optional[pd.Series]:
        """Exponential Moving Average."""
        try:
            if len(df) < period:
                return None
            return df['close'].ewm(span=period, adjust=False).mean()
        except Exception as e:
            logger.error(f"❌ EMA({period}) error: {e}")
            return None

    # ------------------------------------------------------------------ #
    #  Bollinger Bands                                                     #
    # ------------------------------------------------------------------ #

    def calculate_bollinger_bands(
        self,
        df: pd.DataFrame,
        period: int = 20,
        std_dev: float = 2.0
    ) -> Optional[Dict[str, pd.Series]]:
        """
        Bollinger Bands (period=20, std=2.0 — matches MT5 default).

        Returns:
            {
                'upper'     : upper band series,
                'middle'    : middle band (SMA20),
                'lower'     : lower band series,
                'bandwidth' : (upper - lower) / middle  — squeeze indicator,
                'pct_b'     : (close - lower) / (upper - lower) — position within bands
            }
        """
        try:
            if len(df) < period:
                return None
            middle = df['close'].rolling(window=period).mean()
            std    = df['close'].rolling(window=period).std(ddof=0)
            upper  = middle + std_dev * std
            lower  = middle - std_dev * std
            bw     = (upper - lower) / middle
            pct_b  = (df['close'] - lower) / (upper - lower).replace(0, np.nan)
            return {
                'upper':     upper,
                'middle':    middle,
                'lower':     lower,
                'bandwidth': bw,
                'pct_b':     pct_b,
            }
        except Exception as e:
            logger.error(f"❌ Bollinger Bands error: {e}")
            return None

    def _interpret_bb(
        self,
        close: float,
        bb: Dict[str, pd.Series]
    ) -> Dict[str, Any]:
        """Derive Bollinger Band signals from last bar values."""
        upper   = float(bb['upper'].iloc[-1])
        middle  = float(bb['middle'].iloc[-1])
        lower   = float(bb['lower'].iloc[-1])
        bw      = float(bb['bandwidth'].iloc[-1])
        pct_b   = float(bb['pct_b'].iloc[-1]) if not np.isnan(bb['pct_b'].iloc[-1]) else 0.5

        # Squeeze: bandwidth in lower 20th percentile of recent 100 bars
        bw_series = bb['bandwidth'].dropna()
        bw_20pct  = float(bw_series.quantile(0.20)) if len(bw_series) > 20 else bw
        is_squeeze = bw <= bw_20pct

        # Price position
        if close >= upper:
            position = 'at_upper_band'   # overbought / breakout up
        elif close <= lower:
            position = 'at_lower_band'   # oversold / breakout down
        elif close > middle:
            position = 'above_middle'
        else:
            position = 'below_middle'

        # Rayner mean-reversion signal: price at band extreme = potential reversal
        mean_reversion_signal = 'none'
        if close <= lower:
            mean_reversion_signal = 'potential_long'   # buy at lower band
        elif close >= upper:
            mean_reversion_signal = 'potential_short'  # sell at upper band

        return {
            'upper':                  round(upper, 5),
            'middle':                 round(middle, 5),
            'lower':                  round(lower, 5),
            'bandwidth':              round(bw, 6),
            'pct_b':                  round(pct_b, 3),
            'is_squeeze':             is_squeeze,
            'position':               position,
            'mean_reversion_signal':  mean_reversion_signal,
        }

    # ------------------------------------------------------------------ #
    #  Ichimoku Kinko Hyo                                                  #
    # ------------------------------------------------------------------ #

    def calculate_ichimoku(
        self,
        df: pd.DataFrame
    ) -> Optional[Dict[str, pd.Series]]:
        """
        Ichimoku Kinko Hyo (9, 26, 52) — matches MT5 default settings.

        Components:
            tenkan_sen  : (highest_high_9  + lowest_low_9)  / 2  — Conversion Line
            kijun_sen   : (highest_high_26 + lowest_low_26) / 2  — Base Line
            senkou_a    : (tenkan + kijun) / 2, shifted +26      — Leading Span A
            senkou_b    : (highest_high_52 + lowest_low_52) / 2,
                          shifted +26                             — Leading Span B
            chikou_span : close shifted -26                       — Lagging Span
        """
        try:
            if len(df) < self.ICHIMOKU_SENKOU + self.ICHIMOKU_KIJUN:
                return None

            high = df['high']
            low  = df['low']

            tenkan = (high.rolling(self.ICHIMOKU_TENKAN).max() +
                      low.rolling(self.ICHIMOKU_TENKAN).min()) / 2

            kijun  = (high.rolling(self.ICHIMOKU_KIJUN).max() +
                      low.rolling(self.ICHIMOKU_KIJUN).min()) / 2

            senkou_a = ((tenkan + kijun) / 2).shift(self.ICHIMOKU_KIJUN)

            senkou_b = ((high.rolling(self.ICHIMOKU_SENKOU).max() +
                         low.rolling(self.ICHIMOKU_SENKOU).min()) / 2
                        ).shift(self.ICHIMOKU_KIJUN)

            chikou  = df['close'].shift(-self.ICHIMOKU_KIJUN)

            return {
                'tenkan':    tenkan,
                'kijun':     kijun,
                'senkou_a':  senkou_a,
                'senkou_b':  senkou_b,
                'chikou':    chikou,
            }
        except Exception as e:
            logger.error(f"❌ Ichimoku error: {e}")
            return None

    def _interpret_ichimoku(
        self,
        close: float,
        ichi: Dict[str, pd.Series]
    ) -> Dict[str, Any]:
        """Derive Ichimoku trading signals from current bar."""
        tenkan_val   = float(ichi['tenkan'].iloc[-1])
        kijun_val    = float(ichi['kijun'].iloc[-1])

        # Senkou spans at current time (not future-shifted)
        # We use iloc[-27] to get the cloud that's plotted AT current candle
        # (26 periods forward shift means index -1 was computed from data 26 bars ago)
        # Simplified: use the last non-NaN values for cloud position
        senkou_a_s = ichi['senkou_a'].dropna()
        senkou_b_s = ichi['senkou_b'].dropna()
        senkou_a_val = float(senkou_a_s.iloc[-1]) if len(senkou_a_s) > 0 else None
        senkou_b_val = float(senkou_b_s.iloc[-1]) if len(senkou_b_s) > 0 else None

        # TK Cross signal (Tenkan crossing Kijun)
        tenkan_prev = float(ichi['tenkan'].iloc[-2]) if len(ichi['tenkan']) > 1 else tenkan_val
        kijun_prev  = float(ichi['kijun'].iloc[-2])  if len(ichi['kijun'])  > 1 else kijun_val

        tk_cross = 'none'
        if tenkan_prev <= kijun_prev and tenkan_val > kijun_val:
            tk_cross = 'bullish_tk_cross'   # golden cross
        elif tenkan_prev >= kijun_prev and tenkan_val < kijun_val:
            tk_cross = 'bearish_tk_cross'   # death cross

        # Price vs cloud (Kumo)
        cloud_position = 'unknown'
        if senkou_a_val is not None and senkou_b_val is not None:
            cloud_top    = max(senkou_a_val, senkou_b_val)
            cloud_bottom = min(senkou_a_val, senkou_b_val)
            if close > cloud_top:
                cloud_position = 'above_cloud'      # bullish
            elif close < cloud_bottom:
                cloud_position = 'below_cloud'      # bearish
            else:
                cloud_position = 'inside_cloud'     # ranging / transitioning

        # Kumo Twist (future cloud color change — bullish if Senkou A crosses above B)
        kumo_color = 'unknown'
        if senkou_a_val is not None and senkou_b_val is not None:
            kumo_color = 'green' if senkou_a_val > senkou_b_val else 'red'

        # Price vs Tenkan / Kijun
        price_vs_tenkan = 'above' if close > tenkan_val else 'below'
        price_vs_kijun  = 'above' if close > kijun_val  else 'below'

        # Chikou vs past price (simple: chikou vs close 26 bars ago)
        chikou_vals = ichi['chikou'].dropna()
        chikou_confirmation = 'unknown'
        if len(chikou_vals) > 0:
            # chikou is current close shifted back — compare to price of 26 bars ago
            past_price_series = ichi['tenkan'].iloc[:-self.ICHIMOKU_KIJUN] if len(ichi['tenkan']) > self.ICHIMOKU_KIJUN else None
            # Simplified: use tenkan as proxy for past price
            if past_price_series is not None and len(past_price_series) > 0:
                chikou_confirmation = 'bullish' if close > float(past_price_series.iloc[-1]) else 'bearish'

        # Overall Ichimoku bias
        bull_score = sum([
            cloud_position == 'above_cloud',
            price_vs_tenkan == 'above',
            price_vs_kijun == 'above',
            tk_cross == 'bullish_tk_cross',
            kumo_color == 'green',
            chikou_confirmation == 'bullish',
        ])
        bear_score = sum([
            cloud_position == 'below_cloud',
            price_vs_tenkan == 'below',
            price_vs_kijun == 'below',
            tk_cross == 'bearish_tk_cross',
            kumo_color == 'red',
            chikou_confirmation == 'bearish',
        ])

        ichi_bias = 'bullish' if bull_score > bear_score else ('bearish' if bear_score > bull_score else 'neutral')

        return {
            'tenkan':               round(tenkan_val, 5),
            'kijun':                round(kijun_val, 5),
            'senkou_a':             round(senkou_a_val, 5) if senkou_a_val else None,
            'senkou_b':             round(senkou_b_val, 5) if senkou_b_val else None,
            'cloud_position':       cloud_position,
            'cloud_color':          kumo_color,
            'tk_cross':             tk_cross,
            'price_vs_tenkan':      price_vs_tenkan,
            'price_vs_kijun':       price_vs_kijun,
            'chikou_confirmation':  chikou_confirmation,
            'ichimoku_bias':        ichi_bias,
            'bull_score':           bull_score,
            'bear_score':           bear_score,
        }

    # ------------------------------------------------------------------ #
    #  MACD                                                                #
    # ------------------------------------------------------------------ #

    def calculate_macd(
        self,
        df: pd.DataFrame,
        fast: int = 12,
        slow: int = 26,
        signal: int = 9
    ) -> Optional[Dict[str, pd.Series]]:
        """
        MACD (12, 26, 9) — matches MT5 default.

        Returns:
            {
                'macd'      : MACD line (fast EMA - slow EMA),
                'signal'    : Signal line (9-period EMA of MACD),
                'histogram' : MACD - Signal
            }
        """
        try:
            if len(df) < slow + signal:
                return None
            ema_fast = df['close'].ewm(span=fast,   adjust=False).mean()
            ema_slow = df['close'].ewm(span=slow,   adjust=False).mean()
            macd_line   = ema_fast - ema_slow
            signal_line = macd_line.ewm(span=signal, adjust=False).mean()
            histogram   = macd_line - signal_line
            return {
                'macd':      macd_line,
                'signal':    signal_line,
                'histogram': histogram,
            }
        except Exception as e:
            logger.error(f"❌ MACD error: {e}")
            return None

    def _interpret_macd(self, macd: Dict[str, pd.Series]) -> Dict[str, Any]:
        """Derive MACD signals."""
        macd_val  = float(macd['macd'].iloc[-1])
        sig_val   = float(macd['signal'].iloc[-1])
        hist_val  = float(macd['histogram'].iloc[-1])

        macd_prev = float(macd['macd'].iloc[-2])   if len(macd['macd'])      > 1 else macd_val
        sig_prev  = float(macd['signal'].iloc[-2]) if len(macd['signal'])    > 1 else sig_val
        hist_prev = float(macd['histogram'].iloc[-2]) if len(macd['histogram']) > 1 else hist_val

        # Crossover signals
        crossover = 'none'
        if macd_prev <= sig_prev and macd_val > sig_val:
            crossover = 'bullish_crossover'
        elif macd_prev >= sig_prev and macd_val < sig_val:
            crossover = 'bearish_crossover'

        # Histogram momentum
        histogram_trend = 'increasing' if hist_val > hist_prev else 'decreasing'

        # Zero line position
        zero_line = 'above_zero' if macd_val > 0 else 'below_zero'

        # Divergence hint (simplified — momentum vs histogram direction)
        momentum = 'bullish' if hist_val > 0 else 'bearish'

        return {
            'macd_value':       round(macd_val,  6),
            'signal_value':     round(sig_val,   6),
            'histogram_value':  round(hist_val,  6),
            'crossover':        crossover,
            'histogram_trend':  histogram_trend,
            'zero_line':        zero_line,
            'momentum':         momentum,
        }

    # ------------------------------------------------------------------ #
    #  ATR                                                                 #
    # ------------------------------------------------------------------ #

    def calculate_atr(self, df: pd.DataFrame, period: int = 14) -> Optional[pd.Series]:
        """Average True Range — volatility gauge for SL sizing."""
        try:
            if len(df) < period + 1:
                return None
            high       = df['high']
            low        = df['low']
            prev_close = df['close'].shift(1)
            tr = pd.concat([
                high - low,
                (high - prev_close).abs(),
                (low  - prev_close).abs()
            ], axis=1).max(axis=1)
            return tr.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
        except Exception as e:
            logger.error(f"❌ ATR error: {e}")
            return None

    # ------------------------------------------------------------------ #
    #  Swing Structure & Fibonacci                                         #
    # ------------------------------------------------------------------ #

    def _find_swing_highs_lows(
        self,
        df: pd.DataFrame,
        lookback: int = 5
    ) -> Tuple[List[float], List[float]]:
        """Return recent confirmed swing high and swing low price levels."""
        highs = df['high'].values
        lows  = df['low'].values
        swing_highs: List[float] = []
        swing_lows:  List[float] = []

        for i in range(lookback, len(highs) - lookback):
            if all(highs[i] >= highs[i - j] for j in range(1, lookback + 1)) and \
               all(highs[i] >= highs[i + j] for j in range(1, lookback + 1)):
                swing_highs.append(float(highs[i]))
            if all(lows[i] <= lows[i - j] for j in range(1, lookback + 1)) and \
               all(lows[i] <= lows[i + j] for j in range(1, lookback + 1)):
                swing_lows.append(float(lows[i]))

        return swing_highs[-5:], swing_lows[-5:]

    def _determine_market_structure(
        self,
        swing_highs: List[float],
        swing_lows:  List[float]
    ) -> str:
        """HH/HL = uptrend, LH/LL = downtrend, else ranging."""
        if len(swing_highs) >= 2 and len(swing_lows) >= 2:
            hh = swing_highs[-1] > swing_highs[-2]
            hl = swing_lows[-1]  > swing_lows[-2]
            lh = swing_highs[-1] < swing_highs[-2]
            ll = swing_lows[-1]  < swing_lows[-2]
            if hh and hl:
                return 'uptrend'
            if lh and ll:
                return 'downtrend'
        return 'ranging'

    def _calculate_fibonacci_levels(
        self,
        swing_high: float,
        swing_low: float,
        direction: str = 'retracement'
    ) -> Dict[str, float]:
        """
        Calculate Fibonacci retracement / extension levels.
        These are the key ratios used in harmonic patterns (Bat, Gartley, etc.)

        Retracement ratios  : 0.236, 0.382, 0.500, 0.618, 0.786
        Extension ratios    : 1.272, 1.414, 1.618, 2.000, 2.618
        Harmonic key ratios : 0.382, 0.500, 0.618, 0.786, 0.886 (Bat PRZ), 1.272, 1.618
        """
        diff = swing_high - swing_low

        retracement_ratios = {
            'fib_236':  swing_high - diff * 0.236,
            'fib_382':  swing_high - diff * 0.382,
            'fib_500':  swing_high - diff * 0.500,
            'fib_618':  swing_high - diff * 0.618,
            'fib_786':  swing_high - diff * 0.786,
            'fib_886':  swing_high - diff * 0.886,  # key Bat pattern B point
        }
        extension_ratios = {
            'ext_1272': swing_low  - diff * 0.272,   # 127.2% of XA → D point (Gartley/Bat)
            'ext_1414': swing_low  - diff * 0.414,
            'ext_1618': swing_low  - diff * 0.618,   # 161.8% → Deep Crab D point
            'ext_2000': swing_low  - diff * 1.000,
            'ext_2618': swing_low  - diff * 1.618,   # 261.8% → Crab D point
        }

        return {**retracement_ratios, **extension_ratios}

    def get_key_fibonacci_levels(
        self,
        df: pd.DataFrame
    ) -> Dict[str, Any]:
        """
        Compute Fibonacci levels from the most recent significant swing.
        Used by Raphael to identify PRZ zones and harmonic pattern completion areas.
        """
        swing_highs, swing_lows = self._find_swing_highs_lows(df, lookback=5)

        if not swing_highs or not swing_lows:
            return {}

        last_high = swing_highs[-1]
        last_low  = swing_lows[-1]

        # Determine direction of most recent dominant move
        fibs = self._calculate_fibonacci_levels(last_high, last_low)

        return {
            'swing_high':        round(last_high, 5),
            'swing_low':         round(last_low,  5),
            'swing_range':       round(last_high - last_low, 5),
            'fibonacci_levels':  {k: round(v, 5) for k, v in fibs.items()},
            'prz_zone_hint':     {
                # Common harmonic PRZ zones
                'bat_prz':        round(last_high - (last_high - last_low) * 0.886, 5),
                'gartley_prz':    round(last_high - (last_high - last_low) * 0.786, 5),
                'crab_prz':       round(last_low  - (last_high - last_low) * 0.618, 5),
                'butterfly_prz':  round(last_high - (last_high - last_low) * 0.786, 5),
            }
        }

    def get_support_resistance(
        self,
        df: pd.DataFrame,
        lookback: int = 50
    ) -> Dict[str, List[float]]:
        """Identify key S/R levels from recent price action."""
        try:
            recent = df.tail(lookback)
            swing_highs, swing_lows = self._find_swing_highs_lows(recent, lookback=3)
            return {
                'resistance': [round(v, 5) for v in sorted(swing_highs, reverse=True)[:3]],
                'support':    [round(v, 5) for v in sorted(swing_lows)[:3]],
            }
        except Exception as e:
            logger.error(f"❌ S/R error: {e}")
            return {'resistance': [], 'support': []}

    # ------------------------------------------------------------------ #
    #  Per-Timeframe Full Analysis                                         #
    # ------------------------------------------------------------------ #

    def _analyse_single_timeframe(
        self,
        symbol: str,
        timeframe: str
    ) -> Optional[Dict[str, Any]]:
        """
        Complete indicator snapshot for one timeframe.

        Output keys:
          Core:
            timeframe, role, current_price, open, high, low, volume

          RSI:
            rsi, rsi_zone

          EMA:
            ema_20, ema_50, ema_200, ema_alignment
            price_vs_ema20/50/200

          Bollinger Bands (bb_*):
            bb_upper, bb_middle, bb_lower, bb_bandwidth, bb_pct_b
            bb_squeeze, bb_position, bb_mean_reversion_signal

          Ichimoku (ichi_*):
            ichi_tenkan, ichi_kijun, ichi_senkou_a, ichi_senkou_b
            ichi_cloud_position, ichi_cloud_color, ichi_tk_cross
            ichi_price_vs_tenkan, ichi_price_vs_kijun
            ichi_chikou_confirmation, ichi_bias

          MACD (macd_*):
            macd_value, macd_signal, macd_histogram
            macd_crossover, macd_histogram_trend, macd_zero_line, macd_momentum

          ATR:
            atr

          Structure:
            market_structure, swing_highs, swing_lows, sr_levels, fibonacci

          Composite:
            bias  ('bullish' | 'bearish' | 'neutral')
        """
        try:
            df = self.get_ohlc_data(symbol, timeframe, self.bars_count)
            if df is None or len(df) < 60:
                logger.warning(f"⚠️  Insufficient data for {symbol} {timeframe}")
                return None

            last  = df.iloc[-1]
            close = float(last['close'])

            # ── RSI ──────────────────────────────────────────────────────
            rsi     = self.calculate_rsi(df, 14)
            rsi_val = float(rsi.iloc[-1]) if rsi is not None else None
            rsi_zone = _rsi_zone(rsi_val)

            # ── EMA ──────────────────────────────────────────────────────
            ema20  = self.calculate_ema(df, 20)
            ema50  = self.calculate_ema(df, 50)
            ema200 = self.calculate_ema(df, 200)

            ema20_val  = float(ema20.iloc[-1])  if ema20  is not None else None
            ema50_val  = float(ema50.iloc[-1])  if ema50  is not None else None
            ema200_val = float(ema200.iloc[-1]) if ema200 is not None else None
            ema_alignment = _ema_alignment(close, ema20_val, ema50_val, ema200_val)

            # ── Bollinger Bands ──────────────────────────────────────────
            bb = self.calculate_bollinger_bands(df)
            bb_data = self._interpret_bb(close, bb) if bb is not None else {}

            # ── Ichimoku ─────────────────────────────────────────────────
            ichi = self.calculate_ichimoku(df)
            ichi_data = self._interpret_ichimoku(close, ichi) if ichi is not None else {}

            # ── MACD ─────────────────────────────────────────────────────
            macd = self.calculate_macd(df)
            macd_data = self._interpret_macd(macd) if macd is not None else {}

            # ── ATR ──────────────────────────────────────────────────────
            atr     = self.calculate_atr(df, 14)
            atr_val = float(atr.iloc[-1]) if atr is not None else None

            # ── Swing Structure ──────────────────────────────────────────
            swing_highs, swing_lows = self._find_swing_highs_lows(df)
            market_structure = self._determine_market_structure(swing_highs, swing_lows)
            sr = self.get_support_resistance(df)

            # ── Fibonacci / PRZ hint ─────────────────────────────────────
            fib_data = self.get_key_fibonacci_levels(df)

            # ── Composite Bias ───────────────────────────────────────────
            # Weight: Ichimoku (3 pts) > EMA alignment (2) > MACD (2) >
            #         RSI (1) > BB (1) > Structure (1)
            bull = 0
            bear = 0

            if rsi_val is not None:
                bull += (1 if rsi_val > 50 else 0)
                bear += (1 if rsi_val < 50 else 0)

            if ema_alignment in ('strong_uptrend', 'weak_uptrend'):
                bull += 2
            elif ema_alignment in ('strong_downtrend', 'weak_downtrend'):
                bear += 2

            if bb_data.get('mean_reversion_signal') == 'potential_long':
                bull += 1
            elif bb_data.get('mean_reversion_signal') == 'potential_short':
                bear += 1

            ichi_bias = ichi_data.get('ichimoku_bias', 'neutral')
            if ichi_bias == 'bullish':
                bull += 3
            elif ichi_bias == 'bearish':
                bear += 3

            macd_mom = macd_data.get('momentum', 'neutral')
            if macd_mom == 'bullish':
                bull += 2
            elif macd_mom == 'bearish':
                bear += 2

            if market_structure == 'uptrend':
                bull += 1
            elif market_structure == 'downtrend':
                bear += 1

            bias = 'bullish' if bull > bear else ('bearish' if bear > bull else 'neutral')

            # ── Assemble result ──────────────────────────────────────────
            result: Dict[str, Any] = {
                # Core
                'timeframe':        timeframe,
                'role':             self.TIMEFRAME_ROLES[timeframe],
                'current_price':    round(close, 5),
                'open':             round(float(last['open']), 5),
                'high':             round(float(last['high']), 5),
                'low':              round(float(last['low']),  5),
                'volume':           int(last.get('tick_volume', 0)),

                # RSI
                'rsi':              round(rsi_val, 2) if rsi_val is not None else None,
                'rsi_zone':         rsi_zone,

                # EMA
                'ema_20':           round(ema20_val,  5) if ema20_val  is not None else None,
                'ema_50':           round(ema50_val,  5) if ema50_val  is not None else None,
                'ema_200':          round(ema200_val, 5) if ema200_val is not None else None,
                'ema_alignment':    ema_alignment,
                'price_vs_ema20':   'above' if (ema20_val  and close > ema20_val)  else 'below',
                'price_vs_ema50':   'above' if (ema50_val  and close > ema50_val)  else 'below',
                'price_vs_ema200':  'above' if (ema200_val and close > ema200_val) else 'below',

                # ATR
                'atr':              round(atr_val, 5) if atr_val is not None else None,

                # Structure
                'market_structure': market_structure,
                'swing_highs':      [round(v, 5) for v in swing_highs],
                'swing_lows':       [round(v, 5) for v in swing_lows],
                'sr_levels':        sr,
                'fibonacci':        fib_data,

                # Composite
                'bias':             bias,
                'bull_score':       bull,
                'bear_score':       bear,
            }

            # Flatten sub-dicts with prefixes for easy prompt building
            for k, v in bb_data.items():
                result[f'bb_{k}'] = v
            for k, v in ichi_data.items():
                result[f'ichi_{k}'] = v
            for k, v in macd_data.items():
                result[f'macd_{k}'] = v

            rsi_str = f"{rsi_val:.1f}" if rsi_val is not None else "N/A"
            logger.debug(
                f"📊 {symbol} {timeframe} | bias={bias}({bull}B/{bear}R) | "
                f"RSI={rsi_str} | "
                f"Ichi={ichi_bias} | MACD={macd_mom} | "
                f"BB={bb_data.get('position','N/A')} | struct={market_structure}"
            )
            return result

        except Exception as e:
            logger.error(f"❌ Error analysing {symbol} {timeframe}: {e}", exc_info=True)
            return None

    # ------------------------------------------------------------------ #
    #  Full 4-Timeframe Stack                                              #
    # ------------------------------------------------------------------ #

    def get_indicators_for_symbol(self, symbol: str) -> Dict[str, Any]:
        """
        Run the full H4 → H2 → H1 → M15 top-down analysis.

        Returns per-timeframe data + 'summary' confluence key.
        """
        result: Dict[str, Any] = {}

        for tf in ['H4', 'H2', 'H1', 'M15']:
            data = self._analyse_single_timeframe(symbol, tf)
            if data:
                result[tf] = data
            else:
                logger.warning(f"⚠️  {symbol} {tf} — no data, skipped")

        result['summary'] = self._build_confluence_summary(symbol, result)
        return result

    # ------------------------------------------------------------------ #
    #  Confluence Summary                                                  #
    # ------------------------------------------------------------------ #

    def _build_confluence_summary(
        self,
        symbol: str,
        tf_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Synthesise all 4 timeframes into a single confluence summary
        for the AI prompt header.
        """
        htf_votes: List[str] = []
        ltf_votes: List[str] = []

        for tf, tier in [('H4', 'htf'), ('H2', 'htf'), ('H1', 'ltf'), ('M15', 'ltf')]:
            d = tf_data.get(tf)
            if d:
                (htf_votes if tier == 'htf' else ltf_votes).append(d.get('bias', 'neutral'))

        htf_bull = htf_votes.count('bullish')
        htf_bear = htf_votes.count('bearish')
        ltf_bull = ltf_votes.count('bullish')
        ltf_bear = ltf_votes.count('bearish')

        if htf_bull > htf_bear and ltf_bull > ltf_bear:
            confluence = 'FULL_BULLISH'
        elif htf_bear > htf_bull and ltf_bear > ltf_bull:
            confluence = 'FULL_BEARISH'
        elif htf_bull > htf_bear and ltf_bear >= ltf_bull:
            confluence = 'HTF_BULLISH_LTF_PULLBACK'
        elif htf_bear > htf_bull and ltf_bull >= ltf_bear:
            confluence = 'HTF_BEARISH_LTF_PULLBACK'
        else:
            confluence = 'MIXED'

        h4 = tf_data.get('H4', {})
        h2 = tf_data.get('H2', {})
        h1 = tf_data.get('H1', {})
        m15 = tf_data.get('M15', {})

        # TP path obstruction from H2
        current_price = m15.get('current_price') or h4.get('current_price')
        tp_obstruction = 'none'
        h2_sr = h2.get('sr_levels', {})
        if current_price:
            for res in h2_sr.get('resistance', []):
                if 0 < (res - current_price) / current_price < 0.005:
                    tp_obstruction = f'H2 resistance @ {res:.5f}'
                    break
            for sup in h2_sr.get('support', []):
                if 0 < (current_price - sup) / current_price < 0.005:
                    tp_obstruction = f'H2 support @ {sup:.5f}'
                    break

        # Ichimoku cloud alignment across timeframes
        ichi_alignment = {
            tf: tf_data[tf].get('ichi_cloud_position', 'unknown')
            for tf in ['H4', 'H2', 'H1', 'M15']
            if tf in tf_data
        }

        # MACD crossover signals across timeframes
        macd_signals = {
            tf: tf_data[tf].get('macd_crossover', 'none')
            for tf in ['H4', 'H2', 'H1', 'M15']
            if tf in tf_data
        }

        # Bollinger squeeze detection
        bb_squeeze_tfs = [
            tf for tf in ['H4', 'H2', 'H1', 'M15']
            if tf in tf_data and tf_data[tf].get('bb_is_squeeze')
        ]

        # Fibonacci PRZ hints (from H4 as primary harmonic timeframe)
        h4_fib = h4.get('fibonacci', {})

        return {
            'symbol':               symbol,
            'overall_confluence':   confluence,
            'htf_bias':             'bullish' if htf_bull > htf_bear else ('bearish' if htf_bear > htf_bull else 'neutral'),
            'ltf_bias':             'bullish' if ltf_bull > ltf_bear else ('bearish' if ltf_bear > ltf_bull else 'neutral'),
            'h4_structure':         h4.get('market_structure', 'unknown'),
            'h2_structure':         h2.get('market_structure', 'unknown'),
            'h2_tp_obstruction':    tp_obstruction,
            'entry_bias_m15':       m15.get('bias', 'neutral'),
            'atr_m15':              m15.get('atr'),

            # Ichimoku across TFs
            'ichimoku_cloud_by_tf': ichi_alignment,
            'ichi_h4_bias':         h4.get('ichi_ichimoku_bias', 'unknown'),
            'ichi_h1_bias':         h1.get('ichi_ichimoku_bias', 'unknown'),

            # MACD crossover signals
            'macd_crossovers':      macd_signals,

            # Bollinger squeeze
            'bb_squeeze_timeframes': bb_squeeze_tfs,

            # Fibonacci / harmonic PRZ
            'h4_fibonacci':         h4_fib,
            'h4_prz_hint':          h4_fib.get('prz_zone_hint', {}),

            # Trade direction
            'trade_recommendation': _confluence_to_trade_direction(confluence),
        }


# ------------------------------------------------------------------ #
#  Helper functions (module-level)                                    #
# ------------------------------------------------------------------ #

def _rsi_zone(rsi_val: Optional[float]) -> str:
    if rsi_val is None:
        return 'unknown'
    if rsi_val >= 70:
        return 'overbought'
    if rsi_val <= 30:
        return 'oversold'
    if rsi_val >= 55:
        return 'bullish_zone'
    if rsi_val <= 45:
        return 'bearish_zone'
    return 'neutral'


def _ema_alignment(
    close: float,
    ema20: Optional[float],
    ema50: Optional[float],
    ema200: Optional[float]
) -> str:
    if any(v is None for v in [ema20, ema50, ema200]):
        return 'insufficient_data'
    if close > ema20 > ema50 > ema200:
        return 'strong_uptrend'
    if close < ema20 < ema50 < ema200:
        return 'strong_downtrend'
    if close > ema20 and close > ema50 and close < ema200:
        return 'weak_uptrend'
    if close < ema20 and close < ema50 and close > ema200:
        return 'weak_downtrend'
    if ema20 > ema50 > ema200:
        return 'weak_uptrend'
    if ema20 < ema50 < ema200:
        return 'weak_downtrend'
    return 'mixed'


def _confluence_to_trade_direction(confluence: str) -> str:
    return {
        'FULL_BULLISH':             'BUY — semua TF aligned',
        'FULL_BEARISH':             'SELL — semua TF aligned',
        'HTF_BULLISH_LTF_PULLBACK': 'BUY on pullback — tunggu trigger M15',
        'HTF_BEARISH_LTF_PULLBACK': 'SELL on pullback — tunggu trigger M15',
        'MIXED':                    'WAIT — tidak ada confluence jelas',
    }.get(confluence, 'WAIT')
