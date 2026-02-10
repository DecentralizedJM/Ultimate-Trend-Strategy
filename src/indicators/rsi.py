"""
Extended RSI with Divergence Detection
========================================

RSI momentum oscillator with pivot-based bullish/bearish divergence scanning.
Mirrors PineScript RSI + divergence logic.
"""

from typing import List, Optional, Tuple
from dataclasses import dataclass


def calculate_rsi(prices: List[float], period: int = 14) -> List[float]:
    """Calculate RSI using Wilder's smoothing."""
    if len(prices) < period + 1:
        return [float('nan')] * len(prices)

    changes = [prices[i] - prices[i - 1] for i in range(1, len(prices))]
    gains = [max(0, c) for c in changes]
    losses = [abs(min(0, c)) for c in changes]

    rsi_values = [float('nan')] * period

    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    if avg_loss == 0:
        rsi_values.append(100.0)
    else:
        rs = avg_gain / avg_loss
        rsi_values.append(100 - (100 / (1 + rs)))

    for i in range(period, len(changes)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period

        if avg_loss == 0:
            rsi_values.append(100.0)
        else:
            rs = avg_gain / avg_loss
            rsi_values.append(100 - (100 / (1 + rs)))

    return rsi_values


def _is_nan(value: float) -> bool:
    return value != value


def _find_pivot_highs(values: List[float], lookback: int) -> List[Tuple[int, float]]:
    """Find pivot highs: value[i] is highest within lookback on both sides."""
    pivots = []
    for i in range(lookback, len(values) - lookback):
        if _is_nan(values[i]):
            continue
        is_pivot = True
        for j in range(1, lookback + 1):
            if _is_nan(values[i - j]) or _is_nan(values[i + j]):
                is_pivot = False
                break
            if values[i] <= values[i - j] or values[i] <= values[i + j]:
                is_pivot = False
                break
        if is_pivot:
            pivots.append((i, values[i]))
    return pivots


def _find_pivot_lows(values: List[float], lookback: int) -> List[Tuple[int, float]]:
    """Find pivot lows: value[i] is lowest within lookback on both sides."""
    pivots = []
    for i in range(lookback, len(values) - lookback):
        if _is_nan(values[i]):
            continue
        is_pivot = True
        for j in range(1, lookback + 1):
            if _is_nan(values[i - j]) or _is_nan(values[i + j]):
                is_pivot = False
                break
            if values[i] >= values[i - j] or values[i] >= values[i + j]:
                is_pivot = False
                break
        if is_pivot:
            pivots.append((i, values[i]))
    return pivots


@dataclass
class RSIIndicator:
    """
    RSI with divergence detection.

    Divergence logic mirrors PineScript:
    - Bearish divergence: price makes higher high but RSI makes lower high
    - Bullish divergence: price makes lower low but RSI makes higher low
    """

    period: int = 14
    oversold: float = 30.0
    overbought: float = 70.0
    use_divergence: bool = True
    divergence_lookback: int = 5

    def __post_init__(self):
        self._prices: List[float] = []
        self._highs: List[float] = []
        self._lows: List[float] = []
        self._rsi_values: List[float] = []
        self._prev_rsi: Optional[float] = None
        self._bullish_divergence: bool = False
        self._bearish_divergence: bool = False

    def update(self, price: float, high: float = 0.0, low: float = 0.0) -> None:
        """Update RSI. Pass high/low for divergence detection."""
        self._prices.append(price)
        self._highs.append(high if high > 0 else price)
        self._lows.append(low if low > 0 else price)

        if self._rsi_values and not _is_nan(self._rsi_values[-1]):
            self._prev_rsi = self._rsi_values[-1]

        self._rsi_values = calculate_rsi(self._prices, self.period)

        # Detect divergences
        if self.use_divergence and len(self._rsi_values) > self.divergence_lookback * 2 + 1:
            self._detect_divergences()

        if len(self._prices) > 500:
            self._prices = self._prices[-500:]
            self._highs = self._highs[-500:]
            self._lows = self._lows[-500:]
            self._rsi_values = self._rsi_values[-500:]

    def update_batch(self, prices: List[float], highs: List[float] = None, lows: List[float] = None) -> None:
        self._prices = prices[-500:]
        self._highs = (highs or prices)[-500:]
        self._lows = (lows or prices)[-500:]
        self._rsi_values = calculate_rsi(self._prices, self.period)
        if self.use_divergence and len(self._rsi_values) > self.divergence_lookback * 2 + 1:
            self._detect_divergences()

    def _detect_divergences(self) -> None:
        """Detect bullish and bearish divergences using pivot points."""
        lb = self.divergence_lookback
        rsi = self._rsi_values

        # Bearish divergence: higher price high + lower RSI high
        self._bearish_divergence = False
        price_highs = _find_pivot_highs(self._highs, lb)
        rsi_highs = _find_pivot_highs(rsi, lb)

        if len(price_highs) >= 2 and len(rsi_highs) >= 2:
            ph_prev, ph_curr = price_highs[-2], price_highs[-1]
            rh_prev, rh_curr = rsi_highs[-2], rsi_highs[-1]
            if ph_curr[1] > ph_prev[1] and rh_curr[1] < rh_prev[1]:
                self._bearish_divergence = True

        # Bullish divergence: lower price low + higher RSI low
        self._bullish_divergence = False
        price_lows = _find_pivot_lows(self._lows, lb)
        rsi_lows = _find_pivot_lows(rsi, lb)

        if len(price_lows) >= 2 and len(rsi_lows) >= 2:
            pl_prev, pl_curr = price_lows[-2], price_lows[-1]
            rl_prev, rl_curr = rsi_lows[-2], rsi_lows[-1]
            if pl_curr[1] < pl_prev[1] and rl_curr[1] > rl_prev[1]:
                self._bullish_divergence = True

    @property
    def value(self) -> Optional[float]:
        if self._rsi_values and not _is_nan(self._rsi_values[-1]):
            return self._rsi_values[-1]
        return None

    @property
    def previous_value(self) -> Optional[float]:
        return self._prev_rsi

    def is_oversold(self) -> bool:
        return self.value is not None and self.value < self.oversold

    def is_overbought(self) -> bool:
        return self.value is not None and self.value > self.overbought

    def is_bull_zone(self) -> bool:
        """RSI > 50 and < overbought (PineScript: rsiBullZone)"""
        return self.value is not None and 50 < self.value < self.overbought

    def is_bear_zone(self) -> bool:
        """RSI < 50 and > oversold (PineScript: rsiBearZone)"""
        return self.value is not None and self.oversold < self.value < 50

    def is_recovering_from_oversold(self) -> bool:
        if self.value is None or self._prev_rsi is None:
            return False
        return self._prev_rsi < self.oversold and self.value > self._prev_rsi and self.value < 50

    def is_falling_from_overbought(self) -> bool:
        if self.value is None or self._prev_rsi is None:
            return False
        return self._prev_rsi > self.overbought and self.value < self._prev_rsi and self.value > 50

    @property
    def bullish_divergence(self) -> bool:
        return self._bullish_divergence

    @property
    def bearish_divergence(self) -> bool:
        return self._bearish_divergence

    def is_ready(self) -> bool:
        return self.value is not None
