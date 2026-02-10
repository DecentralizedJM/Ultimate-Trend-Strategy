"""
Bollinger Bands Indicator
==========================

SMA-based bands with configurable standard deviation multiplier.
Mirrors PineScript bbUpper/bbLower/bbBasis/bbWidthPct.
"""

import math
from typing import List, Optional
from dataclasses import dataclass


@dataclass
class BollingerBandsIndicator:
    """
    Bollinger Bands: basis (SMA), upper/lower bands, width percentage.
    """

    period: int = 20
    std_dev: float = 2.0

    def __post_init__(self):
        self._prices: List[float] = []
        self._basis: Optional[float] = None
        self._upper: Optional[float] = None
        self._lower: Optional[float] = None

    def update(self, price: float) -> None:
        self._prices.append(price)
        self._recalculate()

        if len(self._prices) > 500:
            self._prices = self._prices[-500:]

    def update_batch(self, prices: List[float]) -> None:
        self._prices = prices[-500:]
        self._recalculate()

    def _recalculate(self) -> None:
        n = len(self._prices)
        if n < self.period:
            self._basis = None
            self._upper = None
            self._lower = None
            return

        window = self._prices[-self.period:]
        self._basis = sum(window) / self.period

        variance = sum((p - self._basis) ** 2 for p in window) / self.period
        deviation = math.sqrt(variance)

        self._upper = self._basis + (self.std_dev * deviation)
        self._lower = self._basis - (self.std_dev * deviation)

    @property
    def basis(self) -> Optional[float]:
        return self._basis

    @property
    def upper(self) -> Optional[float]:
        return self._upper

    @property
    def lower(self) -> Optional[float]:
        return self._lower

    @property
    def width_pct(self) -> Optional[float]:
        """BB width as percentage of basis: ((upper - lower) / basis) * 100"""
        if self._upper is None or self._lower is None or self._basis is None:
            return None
        if self._basis == 0:
            return None
        return ((self._upper - self._lower) / self._basis) * 100

    def is_above_basis(self, price: float) -> bool:
        """close > bbBasis"""
        return self._basis is not None and price > self._basis

    def is_below_basis(self, price: float) -> bool:
        """close < bbBasis"""
        return self._basis is not None and price < self._basis

    def is_wide_enough(self, min_width_pct: float) -> bool:
        """bbWidthPct > bbMinWidth"""
        w = self.width_pct
        return w is not None and w > min_width_pct

    def is_ready(self) -> bool:
        return self._basis is not None
