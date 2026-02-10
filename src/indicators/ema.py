"""
Extended Exponential Moving Average (EMA)
==========================================

Supports 4 EMAs (fast, slow, filter, trend) for multi-layer trend detection.
Replicates PineScript EMA 9/21/50/200 logic.
"""

from typing import List, Optional
from dataclasses import dataclass


def calculate_ema(prices: List[float], period: int) -> List[float]:
    """Calculate EMA using standard multiplier."""
    if len(prices) < period:
        return [float('nan')] * len(prices)

    multiplier = 2 / (period + 1)

    # First EMA = SMA of first 'period' prices
    sma = sum(prices[:period]) / period
    ema_values = [float('nan')] * (period - 1)
    ema_values.append(sma)

    for price in prices[period:]:
        ema = (price - ema_values[-1]) * multiplier + ema_values[-1]
        ema_values.append(ema)

    return ema_values


def _is_nan(value: float) -> bool:
    return value != value


@dataclass
class EMAIndicator:
    """
    Dual-EMA indicator with crossover detection.
    Reused from free-weight-strategy with no changes.
    """

    fast_period: int = 9
    slow_period: int = 21

    def __post_init__(self):
        self._prices: List[float] = []
        self._fast_ema: List[float] = []
        self._slow_ema: List[float] = []
        self._prev_fast: Optional[float] = None
        self._prev_slow: Optional[float] = None

    def update(self, price: float) -> None:
        self._prices.append(price)
        if self._fast_ema:
            self._prev_fast = self._fast_ema[-1]
        if self._slow_ema:
            self._prev_slow = self._slow_ema[-1]

        self._fast_ema = calculate_ema(self._prices, self.fast_period)
        self._slow_ema = calculate_ema(self._prices, self.slow_period)

        if len(self._prices) > 500:
            self._prices = self._prices[-500:]
            self._fast_ema = self._fast_ema[-500:]
            self._slow_ema = self._slow_ema[-500:]

    def update_batch(self, prices: List[float]) -> None:
        self._prices = prices[-500:]
        self._fast_ema = calculate_ema(self._prices, self.fast_period)
        self._slow_ema = calculate_ema(self._prices, self.slow_period)

    @property
    def fast_value(self) -> Optional[float]:
        if self._fast_ema and not _is_nan(self._fast_ema[-1]):
            return self._fast_ema[-1]
        return None

    @property
    def slow_value(self) -> Optional[float]:
        if self._slow_ema and not _is_nan(self._slow_ema[-1]):
            return self._slow_ema[-1]
        return None

    def is_bullish(self) -> bool:
        return self.fast_value is not None and self.slow_value is not None and self.fast_value > self.slow_value

    def is_bearish(self) -> bool:
        return self.fast_value is not None and self.slow_value is not None and self.fast_value < self.slow_value

    def is_bullish_crossover(self) -> bool:
        if self._prev_fast is None or self._prev_slow is None or self.fast_value is None or self.slow_value is None:
            return False
        return self._prev_fast <= self._prev_slow and self.fast_value > self.slow_value

    def is_bearish_crossover(self) -> bool:
        if self._prev_fast is None or self._prev_slow is None or self.fast_value is None or self.slow_value is None:
            return False
        return self._prev_fast >= self._prev_slow and self.fast_value < self.slow_value

    def is_ready(self) -> bool:
        return self.fast_value is not None and self.slow_value is not None


@dataclass
class MultiEMAIndicator:
    """
    4-EMA indicator: fast(9), slow(21), filter(50), trend(200).
    Mirrors PineScript's emaFast / emaSlow / emaFilter / ema200.
    """

    fast_period: int = 9
    slow_period: int = 21
    filter_period: int = 50
    trend_period: int = 200

    def __post_init__(self):
        self._prices: List[float] = []
        self._fast: List[float] = []
        self._slow: List[float] = []
        self._filter: List[float] = []
        self._trend: List[float] = []
        self._prev_fast: Optional[float] = None
        self._prev_slow: Optional[float] = None

    def update(self, price: float) -> None:
        self._prices.append(price)

        if self._fast and not _is_nan(self._fast[-1]):
            self._prev_fast = self._fast[-1]
        if self._slow and not _is_nan(self._slow[-1]):
            self._prev_slow = self._slow[-1]

        self._fast = calculate_ema(self._prices, self.fast_period)
        self._slow = calculate_ema(self._prices, self.slow_period)
        self._filter = calculate_ema(self._prices, self.filter_period)
        self._trend = calculate_ema(self._prices, self.trend_period)

        if len(self._prices) > 500:
            self._prices = self._prices[-500:]
            self._fast = self._fast[-500:]
            self._slow = self._slow[-500:]
            self._filter = self._filter[-500:]
            self._trend = self._trend[-500:]

    def update_batch(self, prices: List[float]) -> None:
        self._prices = prices[-500:]
        self._fast = calculate_ema(self._prices, self.fast_period)
        self._slow = calculate_ema(self._prices, self.slow_period)
        self._filter = calculate_ema(self._prices, self.filter_period)
        self._trend = calculate_ema(self._prices, self.trend_period)

    def _val(self, arr: List[float]) -> Optional[float]:
        if arr and not _is_nan(arr[-1]):
            return arr[-1]
        return None

    @property
    def fast_value(self) -> Optional[float]:
        return self._val(self._fast)

    @property
    def slow_value(self) -> Optional[float]:
        return self._val(self._slow)

    @property
    def filter_value(self) -> Optional[float]:
        return self._val(self._filter)

    @property
    def trend_value(self) -> Optional[float]:
        return self._val(self._trend)

    # --- Trend conditions matching PineScript ---

    def is_fast_above_slow(self) -> bool:
        """emaTrendBull = emaFast > emaSlow"""
        f, s = self.fast_value, self.slow_value
        return f is not None and s is not None and f > s

    def is_fast_below_slow(self) -> bool:
        """emaTrendBear = emaFast < emaSlow"""
        f, s = self.fast_value, self.slow_value
        return f is not None and s is not None and f < s

    def is_bullish_crossover(self) -> bool:
        if self._prev_fast is None or self._prev_slow is None:
            return False
        f, s = self.fast_value, self.slow_value
        if f is None or s is None:
            return False
        return self._prev_fast <= self._prev_slow and f > s

    def is_bearish_crossover(self) -> bool:
        if self._prev_fast is None or self._prev_slow is None:
            return False
        f, s = self.fast_value, self.slow_value
        if f is None or s is None:
            return False
        return self._prev_fast >= self._prev_slow and f < s

    def is_strong_bull_trend(self, price: float) -> bool:
        """strongBullTrend = close > emaFilter and emaFast > emaFilter and emaSlow > emaFilter"""
        f, s, flt = self.fast_value, self.slow_value, self.filter_value
        if f is None or s is None or flt is None:
            return False
        return price > flt and f > flt and s > flt

    def is_strong_bear_trend(self, price: float) -> bool:
        """strongBearTrend = close < emaFilter and emaFast < emaFilter and emaSlow < emaFilter"""
        f, s, flt = self.fast_value, self.slow_value, self.filter_value
        if f is None or s is None or flt is None:
            return False
        return price < flt and f < flt and s < flt

    def is_above_trend(self, price: float) -> bool:
        """ema200Bull = close > ema200"""
        t = self.trend_value
        return t is not None and price > t

    def is_below_trend(self, price: float) -> bool:
        """ema200Bear = close < ema200"""
        t = self.trend_value
        return t is not None and price < t

    def is_ready(self) -> bool:
        """Ready when all 4 EMAs have valid values."""
        return all(v is not None for v in [
            self.fast_value, self.slow_value, self.filter_value, self.trend_value
        ])

    def is_ready_no_trend(self) -> bool:
        """Ready for signals that don't require EMA200."""
        return all(v is not None for v in [
            self.fast_value, self.slow_value, self.filter_value
        ])
