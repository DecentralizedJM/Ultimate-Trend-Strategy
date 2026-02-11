"""
Strategy Engine
================

Multi-indicator confluence engine replicating the PineScript
"Ultimate Trend Strategy" logic.

All conditions must align for a setup. A trigger event
(crossover, pattern, divergence, spike) converts a setup into a signal.
"""

import logging
import time
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field

from src.config import Config
from src.indicators import (
    MultiEMAIndicator, RSIIndicator, MACDIndicator, ATRIndicator,
    SupertrendIndicator, BollingerBandsIndicator, ADXIndicator,
    ChoppinessIndicator, VolumeIndicator,
)
from src.strategy.signals import Signal, SignalType, IndicatorStatus
from src.strategy.news_filter import NewsFilter, NewsEvent
from src.strategy import patterns as pat
from src.bybit_ws.client import OHLCV

logger = logging.getLogger(__name__)


@dataclass
class OHLCBar:
    """Single OHLC bar for pattern detection."""
    open: float
    high: float
    low: float
    close: float


@dataclass
class SymbolState:
    """Per-symbol indicator and state tracking."""
    ema: MultiEMAIndicator = field(default_factory=MultiEMAIndicator)
    rsi: RSIIndicator = field(default_factory=RSIIndicator)
    macd: MACDIndicator = field(default_factory=MACDIndicator)
    atr: ATRIndicator = field(default_factory=ATRIndicator)
    supertrend: SupertrendIndicator = field(default_factory=SupertrendIndicator)
    bollinger: BollingerBandsIndicator = field(default_factory=BollingerBandsIndicator)
    adx: ADXIndicator = field(default_factory=ADXIndicator)
    choppiness: ChoppinessIndicator = field(default_factory=ChoppinessIndicator)
    volume: VolumeIndicator = field(default_factory=VolumeIndicator)

    last_price: float = 0.0
    last_signal_time: float = 0.0
    last_signal_type: SignalType = SignalType.NEUTRAL

    # Recent bars for pattern detection (last 3)
    recent_bars: List[OHLCBar] = field(default_factory=list)

    # S/R levels
    highest_high: float = 0.0
    lowest_low: float = float('inf')
    highs_buffer: List[float] = field(default_factory=list)
    lows_buffer: List[float] = field(default_factory=list)


class StrategyEngine:
    """
    Multi-indicator confluence strategy.

    Setup = ALL conditions aligned.
    Trigger = crossover / pattern / divergence / volume spike.
    """

    def __init__(self, config: Config):
        self.config = config
        self._symbols: Dict[str, SymbolState] = {}
        self._news_filter = self._init_news_filter()

        for symbol in config.symbols:
            self._init_symbol(symbol)

    def _init_news_filter(self) -> NewsFilter:
        nf = NewsFilter(
            enabled=self.config.news.enabled,
            buffer_before=self.config.news.buffer_before,
            buffer_after=self.config.news.buffer_after,
        )
        for evt in self.config.news.events:
            if evt.enabled:
                nf.add_event(evt.name, evt.month, evt.day, evt.hour, evt.minute)
        return nf

    def _init_symbol(self, symbol: str) -> None:
        cfg = self.config
        state = SymbolState(
            ema=MultiEMAIndicator(
                fast_period=cfg.trend.ema_fast,
                slow_period=cfg.trend.ema_slow,
                filter_period=cfg.trend.ema_filter,
                trend_period=cfg.trend.ema_200,
            ),
            rsi=RSIIndicator(
                period=cfg.rsi.period,
                oversold=cfg.rsi.oversold,
                overbought=cfg.rsi.overbought,
                use_divergence=cfg.rsi.use_divergence,
                divergence_lookback=cfg.rsi.divergence_lookback,
            ),
            macd=MACDIndicator(
                fast_period=cfg.macd.fast_period,
                slow_period=cfg.macd.slow_period,
                signal_period=cfg.macd.signal_period,
            ),
            atr=ATRIndicator(period=cfg.risk.atr_period),
            supertrend=SupertrendIndicator(
                atr_period=cfg.supertrend.atr_period,
                multiplier=cfg.supertrend.multiplier,
            ),
            bollinger=BollingerBandsIndicator(
                period=cfg.bollinger.period,
                std_dev=cfg.bollinger.std_dev,
            ),
            adx=ADXIndicator(period=cfg.trend.adx_period),
            choppiness=ChoppinessIndicator(
                chop_period=cfg.market_conditions.chop_period,
                sideways_period=cfg.market_conditions.sideways_period,
            ),
            volume=VolumeIndicator(period=cfg.volume.period),
        )
        self._symbols[symbol] = state
        logger.debug(f"Initialized indicators for {symbol}")

    def update_kline(self, symbol: str, kline: OHLCV) -> None:
        """Update all indicators with new candle data."""
        if symbol not in self._symbols:
            self._init_symbol(symbol)

        state = self._symbols[symbol]
        state.last_price = kline.close

        # Update all indicators
        state.ema.update(kline.close)
        state.rsi.update(kline.close, kline.high, kline.low)
        state.macd.update(kline.close)
        state.atr.update(kline.high, kline.low, kline.close)
        state.supertrend.update(kline.high, kline.low, kline.close)
        state.bollinger.update(kline.close)
        state.adx.update(kline.high, kline.low, kline.close)
        state.choppiness.update(kline.high, kline.low, kline.close)
        state.volume.update(kline.volume)

        # Track recent bars for pattern detection
        bar = OHLCBar(open=kline.open, high=kline.high, low=kline.low, close=kline.close)
        state.recent_bars.append(bar)
        if len(state.recent_bars) > 5:
            state.recent_bars = state.recent_bars[-5:]

        # Track S/R levels
        sr_lookback = self.config.sr.lookback
        state.highs_buffer.append(kline.high)
        state.lows_buffer.append(kline.low)
        if len(state.highs_buffer) > sr_lookback:
            state.highs_buffer = state.highs_buffer[-sr_lookback:]
            state.lows_buffer = state.lows_buffer[-sr_lookback:]
        if state.highs_buffer:
            state.highest_high = max(state.highs_buffer)
            state.lowest_low = min(state.lows_buffer)

    def update_batch(self, symbol: str, klines: List[OHLCV]) -> None:
        """Batch update from historical klines."""
        if symbol not in self._symbols:
            self._init_symbol(symbol)

        state = self._symbols[symbol]

        closes = [k.close for k in klines]
        highs = [k.high for k in klines]
        lows = [k.low for k in klines]
        volumes = [k.volume for k in klines]

        state.ema.update_batch(closes)
        state.rsi.update_batch(closes, highs, lows)
        state.macd.update_batch(closes)
        state.atr.update_batch(highs, lows, closes)
        state.supertrend.update_batch(highs, lows, closes)
        state.bollinger.update_batch(closes)
        state.adx.update_batch(highs, lows, closes)
        state.choppiness.update_batch(highs, lows, closes)
        state.volume.update_batch(volumes)

        # Build recent bars
        for k in klines[-5:]:
            state.recent_bars.append(OHLCBar(open=k.open, high=k.high, low=k.low, close=k.close))
        state.recent_bars = state.recent_bars[-5:]

        # S/R
        sr_lookback = self.config.sr.lookback
        state.highs_buffer = highs[-sr_lookback:]
        state.lows_buffer = lows[-sr_lookback:]
        if state.highs_buffer:
            state.highest_high = max(state.highs_buffer)
            state.lowest_low = min(state.lows_buffer)

        if klines:
            state.last_price = klines[-1].close

        logger.debug(f"Batch updated {symbol} with {len(klines)} candles")

    def evaluate(self, symbol: str) -> Signal:
        """Evaluate all indicators and generate a signal."""
        if symbol not in self._symbols:
            return self._neutral_signal(symbol, "Symbol not initialized")

        state = self._symbols[symbol]

        # Cooldown check
        if not self._check_cooldown(state):
            return self._neutral_signal(symbol, "Cooldown active")

        # Readiness check (at least core indicators)
        if not self._indicators_ready(state):
            return self._neutral_signal(symbol, "Indicators warming up")

        # Build indicator status
        status = self._evaluate_indicators(state)

        # Check no-trade zone
        if self._is_no_trade_zone(status):
            return self._neutral_signal(symbol, "No-trade zone (choppy/sideways/news)")

        # Check setups
        long_setup = self._check_long_setup(status)
        short_setup = self._check_short_setup(status)

        # Check triggers
        long_trigger = long_setup and self._check_long_trigger(status, state)
        short_trigger = short_setup and self._check_short_trigger(status, state)

        if long_trigger:
            return self._create_signal(symbol, SignalType.LONG, state, status)
        elif short_trigger:
            return self._create_signal(symbol, SignalType.SHORT, state, status)
        else:
            # Periodic debug: log setup state for select symbols
            if long_setup or short_setup:
                logger.info(
                    f"⏳ {symbol} setup passed (L:{long_setup} S:{short_setup}) "
                    f"but no trigger fired | EMA_xo:{status.ema_bullish_crossover}/{status.ema_bearish_crossover} "
                    f"engulf:{status.bullish_engulfing}/{status.bearish_engulfing} "
                    f"vol_spike:{status.volume_spike}"
                )
            return self._neutral_signal(symbol, f"No trigger (L:{long_setup} S:{short_setup})")

    # ========================================================================
    # INDICATOR EVALUATION
    # ========================================================================

    def _evaluate_indicators(self, state: SymbolState) -> IndicatorStatus:
        """Build IndicatorStatus from current indicator values."""
        cfg = self.config
        price = state.last_price
        status = IndicatorStatus()

        # EMA
        status.ema_fast_above_slow = state.ema.is_fast_above_slow()
        status.ema_strong_bull_trend = state.ema.is_strong_bull_trend(price)
        status.ema_strong_bear_trend = state.ema.is_strong_bear_trend(price)
        status.ema_above_200 = state.ema.is_above_trend(price)
        status.ema_below_200 = state.ema.is_below_trend(price)
        status.ema_bullish_crossover = state.ema.is_bullish_crossover()
        status.ema_bearish_crossover = state.ema.is_bearish_crossover()

        # ADX
        status.adx_strong = state.adx.is_strong_trend(cfg.trend.adx_threshold)

        # Supertrend
        if state.supertrend.is_ready():
            status.supertrend_bullish = state.supertrend.is_bullish()
            status.supertrend_bearish = state.supertrend.is_bearish()

        # Bollinger Bands
        if state.bollinger.is_ready():
            status.bb_above_basis = state.bollinger.is_above_basis(price)
            status.bb_below_basis = state.bollinger.is_below_basis(price)
            status.bb_wide_enough = state.bollinger.is_wide_enough(cfg.bollinger.min_width_pct)

        # RSI
        if state.rsi.is_ready():
            status.rsi_bull_zone = state.rsi.is_bull_zone()
            status.rsi_bear_zone = state.rsi.is_bear_zone()
            status.rsi_bullish_divergence = state.rsi.bullish_divergence
            status.rsi_bearish_divergence = state.rsi.bearish_divergence

        # MACD
        if state.macd.is_ready():
            status.macd_bullish = state.macd.is_bullish() and state.macd.histogram is not None and state.macd.histogram > 0
            status.macd_bearish = not state.macd.is_bullish() and state.macd.histogram is not None and state.macd.histogram < 0

        # Volume
        if state.volume.is_ready():
            status.volume_above_avg = state.volume.is_above_average(cfg.volume.multiplier)
            status.volume_spike = state.volume.is_spike(cfg.volume.spike_multiplier)

        # Volatility
        atr_val = state.atr.value
        if atr_val is not None and price > 0:
            atr_pct = (atr_val / price) * 100
            status.volatility_ok = cfg.volatility.min_pct <= atr_pct <= cfg.volatility.max_pct
        else:
            status.volatility_ok = True  # Don't block if ATR not ready

        # Market conditions
        if state.choppiness.is_ready():
            status.is_choppy = state.choppiness.is_choppy(cfg.market_conditions.chop_threshold)
            status.is_sideways = state.choppiness.is_sideways(cfg.market_conditions.sideways_threshold)

        # S/R proximity
        if cfg.sr.enabled and price > 0 and state.highest_high > 0:
            dist_resistance = abs(price - state.highest_high) / price * 100
            dist_support = abs(price - state.lowest_low) / price * 100
            status.near_resistance = dist_resistance < cfg.sr.tolerance_pct
            status.near_support = dist_support < cfg.sr.tolerance_pct

        # News
        status.news_blackout = self._news_filter.is_blackout()

        # Candlestick patterns
        if len(state.recent_bars) >= 2:
            curr = state.recent_bars[-1]
            prev = state.recent_bars[-2]
            status.bullish_engulfing = pat.bullish_engulfing(
                curr.open, curr.high, curr.low, curr.close,
                prev.open, prev.high, prev.low, prev.close,
            )
            status.bearish_engulfing = pat.bearish_engulfing(
                curr.open, curr.high, curr.low, curr.close,
                prev.open, prev.high, prev.low, prev.close,
            )
            status.hammer = pat.hammer(curr.open, curr.high, curr.low, curr.close)
            status.shooting_star = pat.shooting_star(curr.open, curr.high, curr.low, curr.close)

        if len(state.recent_bars) >= 3:
            bars_3 = [
                (b.open, b.high, b.low, b.close)
                for b in state.recent_bars[-3:]
            ]
            status.morning_doji_star = pat.morning_doji_star(bars_3)
            status.evening_doji_star = pat.evening_doji_star(bars_3)

        return status

    # ========================================================================
    # SETUP CHECKS — all conditions must align
    # ========================================================================

    def _check_long_setup(self, s: IndicatorStatus) -> bool:
        """PineScript longSetup: all conditions must be True."""
        cfg = self.config

        # Core trend
        if not s.ema_fast_above_slow:
            return False
        if not s.ema_strong_bull_trend:
            return False
        if cfg.trend.use_ema200_filter and not s.ema_above_200:
            return False
        if not s.adx_strong:
            return False

        # Optional filters (skip if disabled)
        if cfg.supertrend.enabled and not s.supertrend_bullish:
            return False
        if cfg.bollinger.enabled and not (s.bb_above_basis and s.bb_wide_enough):
            return False
        if cfg.mtf.enabled and not s.mtf_bullish:
            return False
        if cfg.rsi.enabled and not s.rsi_bull_zone:
            return False
        if cfg.macd.enabled and not s.macd_bullish:
            return False
        if cfg.volatility.enabled and not s.volatility_ok:
            return False

        # S/R: don't go long near resistance
        if cfg.sr.enabled and s.near_resistance:
            return False

        return True

    def _check_short_setup(self, s: IndicatorStatus) -> bool:
        """PineScript shortSetup: all conditions must be True."""
        cfg = self.config

        if not s.ema_fast_above_slow == False:  # Must be bearish
            pass
        if s.ema_fast_above_slow:
            return False
        if not s.ema_strong_bear_trend:
            return False
        if cfg.trend.use_ema200_filter and not s.ema_below_200:
            return False
        if not s.adx_strong:
            return False

        if cfg.supertrend.enabled and not s.supertrend_bearish:
            return False
        if cfg.bollinger.enabled and not (s.bb_below_basis and s.bb_wide_enough):
            return False
        if cfg.mtf.enabled and not s.mtf_bearish:
            return False
        if cfg.rsi.enabled and not s.rsi_bear_zone:
            return False
        if cfg.macd.enabled and not s.macd_bearish:
            return False
        if cfg.volatility.enabled and not s.volatility_ok:
            return False

        # S/R: don't go short near support
        if cfg.sr.enabled and s.near_support:
            return False

        return True

    # ========================================================================
    # TRIGGER CHECKS — need at least one trigger event
    # ========================================================================

    def _check_long_trigger(self, s: IndicatorStatus, state: SymbolState) -> bool:
        """
        PineScript longTrigger: setup AND one of:
        - EMA crossover
        - Bullish engulfing
        - Hammer near support
        - RSI bullish divergence
        - Morning doji star
        - Volume spike
        """
        cfg = self.config

        return (
            s.ema_bullish_crossover or
            s.bullish_engulfing or
            (s.hammer and s.near_support) or
            s.rsi_bullish_divergence or
            s.morning_doji_star or
            (cfg.volume.detect_spike and s.volume_spike)
        )

    def _check_short_trigger(self, s: IndicatorStatus, state: SymbolState) -> bool:
        """
        PineScript shortTrigger: setup AND one of:
        - EMA crossunder
        - Bearish engulfing
        - Shooting star near resistance
        - RSI bearish divergence
        - Evening doji star
        - Volume spike
        """
        cfg = self.config

        return (
            s.ema_bearish_crossover or
            s.bearish_engulfing or
            (s.shooting_star and s.near_resistance) or
            s.rsi_bearish_divergence or
            s.evening_doji_star or
            (cfg.volume.detect_spike and s.volume_spike)
        )

    # ========================================================================
    # NO-TRADE ZONE
    # ========================================================================

    def _is_no_trade_zone(self, s: IndicatorStatus) -> bool:
        """Choppy, sideways, or news blackout."""
        cfg = self.config
        is_choppy = cfg.market_conditions.use_choppiness and s.is_choppy
        is_sideways = cfg.market_conditions.use_sideways and s.is_sideways
        return is_choppy or is_sideways or s.news_blackout

    # ========================================================================
    # SIGNAL CREATION
    # ========================================================================

    def _create_signal(
        self, symbol: str, signal_type: SignalType,
        state: SymbolState, status: IndicatorStatus,
    ) -> Signal:
        """Create a trading signal with entry, SL, TP levels."""
        entry_price = state.last_price
        cfg = self.config
        atr = state.atr.value or 0.0

        # Calculate SL/TP
        if signal_type == SignalType.LONG:
            sl = entry_price - (atr * cfg.risk.stoploss_atr)
            tp = entry_price + (atr * cfg.risk.takeprofit_atr)
            tp1 = entry_price + (atr * cfg.profit.tp1_atr) if cfg.profit.use_partial_profits else 0.0
            tp2 = entry_price + (atr * cfg.profit.tp2_atr) if cfg.profit.use_partial_profits else 0.0
        else:
            sl = entry_price + (atr * cfg.risk.stoploss_atr)
            tp = entry_price - (atr * cfg.risk.takeprofit_atr)
            tp1 = entry_price - (atr * cfg.profit.tp1_atr) if cfg.profit.use_partial_profits else 0.0
            tp2 = entry_price - (atr * cfg.profit.tp2_atr) if cfg.profit.use_partial_profits else 0.0

        # Build reasons
        reasons = []
        if status.ema_bullish_crossover:
            reasons.append("EMA crossover ↑")
        if status.ema_bearish_crossover:
            reasons.append("EMA crossunder ↓")
        if status.bullish_engulfing:
            reasons.append("Bullish engulfing")
        if status.bearish_engulfing:
            reasons.append("Bearish engulfing")
        if status.hammer:
            reasons.append("Hammer")
        if status.shooting_star:
            reasons.append("Shooting star")
        if status.rsi_bullish_divergence:
            reasons.append("RSI bull divergence")
        if status.rsi_bearish_divergence:
            reasons.append("RSI bear divergence")
        if status.morning_doji_star:
            reasons.append("Morning doji star")
        if status.evening_doji_star:
            reasons.append("Evening doji star")
        if status.volume_spike:
            reasons.append("Volume spike")

        state.last_signal_time = time.time()
        state.last_signal_type = signal_type

        return Signal(
            symbol=symbol,
            signal_type=signal_type,
            entry_price=entry_price,
            stoploss_price=sl,
            takeprofit_price=tp,
            tp1_price=tp1,
            tp2_price=tp2,
            leverage=cfg.risk.default_leverage,
            position_size_pct=cfg.sizing.risk_per_trade_pct,
            indicator_status=status,
            reasons=reasons,
            reason=", ".join(reasons),
        )

    def _neutral_signal(self, symbol: str, reason: str = "") -> Signal:
        return Signal(symbol=symbol, signal_type=SignalType.NEUTRAL, reason=reason)

    # ========================================================================
    # REVERSAL EXIT CHECK
    # ========================================================================

    def should_exit_long(self, symbol: str) -> bool:
        """Check if a long position should be closed due to reversal signals."""
        if symbol not in self._symbols:
            return False
        state = self._symbols[symbol]
        status = self._evaluate_indicators(state)

        return (
            status.ema_bearish_crossover or
            status.bearish_engulfing or
            (status.shooting_star and status.near_resistance) or
            status.supertrend_bearish
        )

    def should_exit_short(self, symbol: str) -> bool:
        """Check if a short position should be closed due to reversal signals."""
        if symbol not in self._symbols:
            return False
        state = self._symbols[symbol]
        status = self._evaluate_indicators(state)

        return (
            status.ema_bullish_crossover or
            status.bullish_engulfing or
            (status.hammer and status.near_support) or
            status.supertrend_bullish
        )

    # ========================================================================
    # HELPERS
    # ========================================================================

    def _check_cooldown(self, state: SymbolState) -> bool:
        if state.last_signal_time == 0:
            return True
        return time.time() - state.last_signal_time >= self.config.strategy.trade_cooldown

    def _indicators_ready(self, state: SymbolState) -> bool:
        return (
            state.ema.is_ready_no_trend() and
            state.rsi.is_ready() and
            state.macd.is_ready() and
            state.atr.is_ready()
        )

    def get_indicator_values(self, symbol: str) -> dict:
        """Get current indicator values for debugging."""
        if symbol not in self._symbols:
            return {}

        state = self._symbols[symbol]
        atr_pct = 0.0
        if state.atr.value and state.last_price > 0:
            atr_pct = (state.atr.value / state.last_price) * 100

        return {
            "price": state.last_price,
            "ema_fast": state.ema.fast_value,
            "ema_slow": state.ema.slow_value,
            "ema_filter": state.ema.filter_value,
            "ema_200": state.ema.trend_value,
            "rsi": state.rsi.value,
            "macd_histogram": state.macd.histogram,
            "atr": state.atr.value,
            "atr_pct": round(atr_pct, 3),
            "supertrend": state.supertrend.value,
            "supertrend_dir": state.supertrend.direction,
            "bb_upper": state.bollinger.upper,
            "bb_lower": state.bollinger.lower,
            "bb_width_pct": state.bollinger.width_pct,
            "adx": state.adx.adx_value,
            "choppiness": state.choppiness.value,
            "volume_ma": state.volume.ma_value,
            "highest_high": state.highest_high,
            "lowest_low": state.lowest_low,
        }
