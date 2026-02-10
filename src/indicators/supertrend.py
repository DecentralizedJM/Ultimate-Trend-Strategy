"""
Supertrend Indicator
=====================

Port of PineScript calcSupertrend() function.
Uses ATR-based bands to determine trend direction.
"""

from typing import List, Optional
from dataclasses import dataclass
from src.indicators.atr import calculate_atr


@dataclass
class SupertrendIndicator:
    """
    Supertrend: ATR envelope trend-following indicator.

    direction = +1 (bullish), -1 (bearish)
    supertrend = lowerBand when bullish, upperBand when bearish.
    """

    atr_period: int = 10
    multiplier: float = 3.0

    def __post_init__(self):
        self._highs: List[float] = []
        self._lows: List[float] = []
        self._closes: List[float] = []
        self._supertrend: Optional[float] = None
        self._direction: int = 1  # 1 = bull, -1 = bear
        self._prev_supertrend: Optional[float] = None
        self._prev_direction: int = 1

    def update(self, high: float, low: float, close: float) -> None:
        """Update with new OHLC bar."""
        self._highs.append(high)
        self._lows.append(low)
        self._closes.append(close)
        self._recalculate()

        if len(self._highs) > 500:
            self._highs = self._highs[-500:]
            self._lows = self._lows[-500:]
            self._closes = self._closes[-500:]

    def update_batch(self, highs: List[float], lows: List[float], closes: List[float]) -> None:
        """Batch init from historical data."""
        self._highs = highs[-500:]
        self._lows = lows[-500:]
        self._closes = closes[-500:]
        # Recalculate from scratch
        self._supertrend = None
        self._direction = 1
        self._prev_supertrend = None
        self._prev_direction = 1

        # Walk through bars to build state
        n = len(self._highs)
        if n < self.atr_period + 1:
            return

        atr_values = calculate_atr(self._highs, self._lows, self._closes, self.atr_period)

        for i in range(self.atr_period, n):
            atr_val = atr_values[i]
            if atr_val != atr_val:  # NaN
                continue

            hl2 = (self._highs[i] + self._lows[i]) / 2
            upper_band = hl2 + (self.multiplier * atr_val)
            lower_band = hl2 - (self.multiplier * atr_val)

            if self._supertrend is None:
                self._supertrend = lower_band
                self._direction = 1
                continue

            self._prev_supertrend = self._supertrend
            self._prev_direction = self._direction

            if self._prev_direction == 1:
                lower_band = max(lower_band, self._prev_supertrend)
            else:
                upper_band = min(upper_band, self._prev_supertrend)

            if self._closes[i] > self._prev_supertrend:
                self._direction = 1
            elif self._closes[i] < self._prev_supertrend:
                self._direction = -1
            else:
                self._direction = self._prev_direction

            self._supertrend = lower_band if self._direction == 1 else upper_band

    def _recalculate(self) -> None:
        """Recalculate latest supertrend value."""
        n = len(self._highs)
        if n < self.atr_period + 1:
            return

        atr_values = calculate_atr(self._highs, self._lows, self._closes, self.atr_period)
        atr_val = atr_values[-1]
        if atr_val != atr_val:  # NaN
            return

        hl2 = (self._highs[-1] + self._lows[-1]) / 2
        upper_band = hl2 + (self.multiplier * atr_val)
        lower_band = hl2 - (self.multiplier * atr_val)

        if self._supertrend is None:
            self._supertrend = lower_band
            self._direction = 1
            return

        self._prev_supertrend = self._supertrend
        self._prev_direction = self._direction

        if self._prev_direction == 1:
            lower_band = max(lower_band, self._prev_supertrend)
        else:
            upper_band = min(upper_band, self._prev_supertrend)

        if self._closes[-1] > self._prev_supertrend:
            self._direction = 1
        elif self._closes[-1] < self._prev_supertrend:
            self._direction = -1
        else:
            self._direction = self._prev_direction

        self._supertrend = lower_band if self._direction == 1 else upper_band

    @property
    def value(self) -> Optional[float]:
        return self._supertrend

    @property
    def direction(self) -> int:
        return self._direction

    def is_bullish(self) -> bool:
        return self._direction == 1

    def is_bearish(self) -> bool:
        return self._direction == -1

    def is_ready(self) -> bool:
        return self._supertrend is not None
