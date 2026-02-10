"""
ADX / Directional Movement Index
==================================

Implements ADX, DI+, DI- using Wilder's smoothing.
Mirrors PineScript ta.dmi(adxLen, adxLen).
"""

from typing import List, Optional
from dataclasses import dataclass


@dataclass
class ADXIndicator:
    """
    ADX with DI+/DI- for trend strength measurement.

    adx > threshold indicates a strong trend (regardless of direction).
    DI+ > DI- = bullish, DI- > DI+ = bearish.
    """

    period: int = 14

    def __post_init__(self):
        self._highs: List[float] = []
        self._lows: List[float] = []
        self._closes: List[float] = []
        self._adx: Optional[float] = None
        self._di_plus: Optional[float] = None
        self._di_minus: Optional[float] = None

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
        if n < self.period + 1:
            return

        p = self.period

        # True range, +DM, -DM
        tr_list = []
        plus_dm_list = []
        minus_dm_list = []

        for i in range(1, n):
            h, l, c_prev = self._highs[i], self._lows[i], self._closes[i - 1]
            tr = max(h - l, abs(h - c_prev), abs(l - c_prev))
            tr_list.append(tr)

            up_move = self._highs[i] - self._highs[i - 1]
            down_move = self._lows[i - 1] - self._lows[i]

            plus_dm = up_move if up_move > down_move and up_move > 0 else 0.0
            minus_dm = down_move if down_move > up_move and down_move > 0 else 0.0

            plus_dm_list.append(plus_dm)
            minus_dm_list.append(minus_dm)

        if len(tr_list) < p:
            return

        # Wilder smoothed sums (first = simple sum, then smoothed)
        smoothed_tr = sum(tr_list[:p])
        smoothed_plus_dm = sum(plus_dm_list[:p])
        smoothed_minus_dm = sum(minus_dm_list[:p])

        dx_values = []

        for i in range(p, len(tr_list)):
            smoothed_tr = smoothed_tr - (smoothed_tr / p) + tr_list[i]
            smoothed_plus_dm = smoothed_plus_dm - (smoothed_plus_dm / p) + plus_dm_list[i]
            smoothed_minus_dm = smoothed_minus_dm - (smoothed_minus_dm / p) + minus_dm_list[i]

            if smoothed_tr > 0:
                di_plus = (smoothed_plus_dm / smoothed_tr) * 100
                di_minus = (smoothed_minus_dm / smoothed_tr) * 100
            else:
                di_plus = 0.0
                di_minus = 0.0

            di_sum = di_plus + di_minus
            dx = abs(di_plus - di_minus) / di_sum * 100 if di_sum > 0 else 0.0
            dx_values.append(dx)

            self._di_plus = di_plus
            self._di_minus = di_minus

        # ADX = Wilder smoothed average of DX
        if len(dx_values) < p:
            self._adx = sum(dx_values) / len(dx_values) if dx_values else None
        else:
            adx = sum(dx_values[:p]) / p
            for dx in dx_values[p:]:
                adx = (adx * (p - 1) + dx) / p
            self._adx = adx

    @property
    def adx_value(self) -> Optional[float]:
        return self._adx

    @property
    def di_plus(self) -> Optional[float]:
        return self._di_plus

    @property
    def di_minus(self) -> Optional[float]:
        return self._di_minus

    def is_strong_trend(self, threshold: float = 25.0) -> bool:
        """ADX > threshold = strong trend."""
        return self._adx is not None and self._adx > threshold

    def is_ready(self) -> bool:
        return self._adx is not None
