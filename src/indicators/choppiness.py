"""
Choppiness Index & Sideways Detection
=======================================

Choppiness Index: 100 * log10(sum(ATR(1), N) / (HH - LL)) / log10(N)
High values (>61.8) = choppy/ranging market.
Low values (<38.2) = trending market.

Also includes sideways detection via price range percentage.
"""

import math
from typing import List, Optional
from dataclasses import dataclass


@dataclass
class ChoppinessIndicator:
    """
    Combined choppiness index + sideways detection.
    Mirrors PineScript calcChoppiness() and calcSideways().
    """

    chop_period: int = 14
    sideways_period: int = 20

    def __post_init__(self):
        self._highs: List[float] = []
        self._lows: List[float] = []
        self._closes: List[float] = []
        self._choppiness: Optional[float] = None

    def update(self, high: float, low: float, close: float) -> None:
        self._highs.append(high)
        self._lows.append(low)
        self._closes.append(close)
        self._recalculate()

        if len(self._highs) > 500:
            self._highs = self._highs[-500:]
            self._lows = self._lows[-500:]
            self._closes = self._closes[-500:]

    def update_batch(self, highs: List[float], lows: List[float], closes: List[float]) -> None:
        self._highs = highs[-500:]
        self._lows = lows[-500:]
        self._closes = closes[-500:]
        self._recalculate()

    def _recalculate(self) -> None:
        n = len(self._highs)
        if n < self.chop_period + 1:
            self._choppiness = None
            return

        # Sum of ATR(1) over chop_period bars
        atr1_sum = 0.0
        for i in range(n - self.chop_period, n):
            tr = self._highs[i] - self._lows[i]
            if i > 0:
                tr = max(tr, abs(self._highs[i] - self._closes[i - 1]),
                         abs(self._lows[i] - self._closes[i - 1]))
            atr1_sum += tr

        # Highest high and lowest low over chop_period
        window_h = self._highs[-self.chop_period:]
        window_l = self._lows[-self.chop_period:]
        hh = max(window_h)
        ll = min(window_l)
        hl_range = hh - ll

        if hl_range <= 0:
            self._choppiness = 50.0
            return

        self._choppiness = 100 * math.log10(atr1_sum / hl_range) / math.log10(self.chop_period)

    @property
    def value(self) -> Optional[float]:
        return self._choppiness

    def is_choppy(self, threshold: float = 61.8) -> bool:
        """Market is choppy/ranging when choppiness > threshold."""
        return self._choppiness is not None and self._choppiness > threshold

    def is_trending(self, threshold: float = 38.2) -> bool:
        """Market is trending when choppiness < threshold."""
        return self._choppiness is not None and self._choppiness < threshold

    def is_sideways(self, threshold_pct: float = 1.5) -> bool:
        """
        Sideways detection: price range < threshold % of average price.
        Mirrors PineScript calcSideways().
        """
        n = len(self._highs)
        if n < self.sideways_period:
            return False

        window_h = self._highs[-self.sideways_period:]
        window_l = self._lows[-self.sideways_period:]
        hh = max(window_h)
        ll = min(window_l)
        avg_price = (hh + ll) / 2

        if avg_price <= 0:
            return False

        range_pct = ((hh - ll) / avg_price) * 100
        return range_pct < threshold_pct

    def is_ready(self) -> bool:
        return self._choppiness is not None
