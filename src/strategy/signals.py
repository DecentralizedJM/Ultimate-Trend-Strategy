"""
Trading Signals
================

Signal and IndicatorStatus dataclasses used by the strategy engine.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List


class SignalType(str, Enum):
    LONG = "LONG"
    SHORT = "SHORT"
    NEUTRAL = "NEUTRAL"


@dataclass
class IndicatorStatus:
    """Snapshot of all indicator filter results for one evaluation."""

    # EMA Trend
    ema_fast_above_slow: bool = False
    ema_strong_bull_trend: bool = False
    ema_strong_bear_trend: bool = False
    ema_above_200: bool = False
    ema_below_200: bool = False
    ema_bullish_crossover: bool = False
    ema_bearish_crossover: bool = False

    # ADX
    adx_strong: bool = False

    # Supertrend
    supertrend_bullish: bool = False
    supertrend_bearish: bool = False

    # Bollinger Bands
    bb_above_basis: bool = False
    bb_below_basis: bool = False
    bb_wide_enough: bool = False

    # Multi-timeframe
    mtf_bullish: bool = False
    mtf_bearish: bool = False

    # RSI
    rsi_bull_zone: bool = False
    rsi_bear_zone: bool = False
    rsi_bullish_divergence: bool = False
    rsi_bearish_divergence: bool = False

    # MACD
    macd_bullish: bool = False
    macd_bearish: bool = False

    # Volume
    volume_above_avg: bool = False
    volume_spike: bool = False

    # Volatility
    volatility_ok: bool = False

    # Market conditions
    is_choppy: bool = False
    is_sideways: bool = False

    # Support/Resistance
    near_support: bool = False
    near_resistance: bool = False

    # News
    news_blackout: bool = False

    # Candlestick patterns
    bullish_engulfing: bool = False
    bearish_engulfing: bool = False
    hammer: bool = False
    shooting_star: bool = False
    morning_doji_star: bool = False
    evening_doji_star: bool = False


@dataclass
class Signal:
    """
    Trading signal produced by the strategy engine.

    Contains entry/exit levels, reason for signal, and all indicator states.
    """

    symbol: str
    signal_type: SignalType
    entry_price: float = 0.0
    stoploss_price: float = 0.0
    takeprofit_price: float = 0.0
    tp1_price: float = 0.0  # Partial TP1
    tp2_price: float = 0.0  # Partial TP2
    leverage: int = 5
    position_size_pct: float = 2.0
    indicator_status: IndicatorStatus = field(default_factory=IndicatorStatus)
    reasons: List[str] = field(default_factory=list)
    reason: str = ""

    @property
    def is_actionable(self) -> bool:
        return self.signal_type in (SignalType.LONG, SignalType.SHORT)

    @property
    def is_long(self) -> bool:
        return self.signal_type == SignalType.LONG

    @property
    def is_short(self) -> bool:
        return self.signal_type == SignalType.SHORT

    @property
    def side(self) -> str:
        return self.signal_type.value

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "type": self.signal_type.value,
            "entry": self.entry_price,
            "sl": self.stoploss_price,
            "tp": self.takeprofit_price,
            "tp1": self.tp1_price,
            "tp2": self.tp2_price,
            "leverage": self.leverage,
            "reasons": self.reasons,
        }
