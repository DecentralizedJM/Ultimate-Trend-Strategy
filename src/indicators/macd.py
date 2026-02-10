"""
Moving Average Convergence Divergence (MACD)
============================================

Trend-following momentum indicator showing relationship between two EMAs.
"""

from typing import List, Optional, Tuple
from dataclasses import dataclass

from src.indicators.ema import calculate_ema


def calculate_macd(
    prices: List[float],
    fast_period: int = 12,
    slow_period: int = 26,
    signal_period: int = 9
) -> Tuple[List[float], List[float], List[float]]:
    """
    Calculate MACD, Signal line, and Histogram.
    
    Args:
        prices: List of price values
        fast_period: Fast EMA period (default: 12)
        slow_period: Slow EMA period (default: 26)
        signal_period: Signal line period (default: 9)
        
    Returns:
        Tuple of (MACD line, Signal line, Histogram)
    """
    if len(prices) < slow_period:
        nan_list = [float('nan')] * len(prices)
        return nan_list, nan_list, nan_list
    
    # Calculate fast and slow EMAs
    fast_ema = calculate_ema(prices, fast_period)
    slow_ema = calculate_ema(prices, slow_period)
    
    # MACD line = Fast EMA - Slow EMA
    macd_line = []
    for f, s in zip(fast_ema, slow_ema):
        if f != f or s != s:  # Check for NaN
            macd_line.append(float('nan'))
        else:
            macd_line.append(f - s)
    
    # Signal line = EMA of MACD line
    # Filter out NaN values for signal calculation
    valid_macd = [m for m in macd_line if m == m]
    signal_line = [float('nan')] * (len(macd_line) - len(valid_macd))
    signal_line.extend(calculate_ema(valid_macd, signal_period))
    
    # Histogram = MACD - Signal
    histogram = []
    for m, s in zip(macd_line, signal_line):
        if m != m or s != s:
            histogram.append(float('nan'))
        else:
            histogram.append(m - s)
    
    return macd_line, signal_line, histogram


@dataclass
class MACDIndicator:
    """
    MACD indicator with crossover and histogram analysis.
    
    Example:
        macd = MACDIndicator()
        macd.update(price)
        if macd.is_bullish_crossover():
            # MACD crossed above signal line
    """
    
    fast_period: int = 12
    slow_period: int = 26
    signal_period: int = 9
    
    def __post_init__(self):
        self._prices: List[float] = []
        self._macd_line: List[float] = []
        self._signal_line: List[float] = []
        self._histogram: List[float] = []
        self._prev_macd: Optional[float] = None
        self._prev_signal: Optional[float] = None
        self._prev_histogram: Optional[float] = None
    
    def update(self, price: float) -> None:
        """Add new price and recalculate MACD."""
        self._prices.append(price)
        
        # Store previous values
        if self._macd_line and not self._is_nan(self._macd_line[-1]):
            self._prev_macd = self._macd_line[-1]
        if self._signal_line and not self._is_nan(self._signal_line[-1]):
            self._prev_signal = self._signal_line[-1]
        if self._histogram and not self._is_nan(self._histogram[-1]):
            self._prev_histogram = self._histogram[-1]
        
        # Recalculate
        self._macd_line, self._signal_line, self._histogram = calculate_macd(
            self._prices, self.fast_period, self.slow_period, self.signal_period
        )
        
        # Trim to last 500 values
        if len(self._prices) > 500:
            self._prices = self._prices[-500:]
            self._macd_line = self._macd_line[-500:]
            self._signal_line = self._signal_line[-500:]
            self._histogram = self._histogram[-500:]
    
    def update_batch(self, prices: List[float]) -> None:
        """Batch update with multiple prices."""
        self._prices = prices[-500:]
        self._macd_line, self._signal_line, self._histogram = calculate_macd(
            self._prices, self.fast_period, self.slow_period, self.signal_period
        )
    
    @property
    def macd(self) -> Optional[float]:
        """Get current MACD line value."""
        if self._macd_line and not self._is_nan(self._macd_line[-1]):
            return self._macd_line[-1]
        return None
    
    @property
    def signal(self) -> Optional[float]:
        """Get current Signal line value."""
        if self._signal_line and not self._is_nan(self._signal_line[-1]):
            return self._signal_line[-1]
        return None
    
    @property
    def histogram(self) -> Optional[float]:
        """Get current Histogram value."""
        if self._histogram and not self._is_nan(self._histogram[-1]):
            return self._histogram[-1]
        return None
    
    def is_bullish(self) -> bool:
        """Check if MACD is above signal line."""
        return self.macd is not None and self.signal is not None and self.macd > self.signal
    
    def is_bearish(self) -> bool:
        """Check if MACD is below signal line."""
        return self.macd is not None and self.signal is not None and self.macd < self.signal
    
    def is_bullish_crossover(self) -> bool:
        """Check if MACD just crossed above signal line."""
        if (self._prev_macd is None or self._prev_signal is None or
            self.macd is None or self.signal is None):
            return False
        
        was_below = self._prev_macd <= self._prev_signal
        is_above = self.macd > self.signal
        return was_below and is_above
    
    def is_bearish_crossover(self) -> bool:
        """Check if MACD just crossed below signal line."""
        if (self._prev_macd is None or self._prev_signal is None or
            self.macd is None or self.signal is None):
            return False
        
        was_above = self._prev_macd >= self._prev_signal
        is_below = self.macd < self.signal
        return was_above and is_below
    
    def is_histogram_rising(self) -> bool:
        """Check if histogram is rising (momentum increasing)."""
        if self.histogram is None or self._prev_histogram is None:
            return False
        return self.histogram > self._prev_histogram
    
    def is_histogram_falling(self) -> bool:
        """Check if histogram is falling (momentum decreasing)."""
        if self.histogram is None or self._prev_histogram is None:
            return False
        return self.histogram < self._prev_histogram
    
    def is_above_zero(self) -> bool:
        """Check if MACD is above zero (bullish trend)."""
        return self.macd is not None and self.macd > 0
    
    def is_below_zero(self) -> bool:
        """Check if MACD is below zero (bearish trend)."""
        return self.macd is not None and self.macd < 0
    
    def is_ready(self) -> bool:
        """Check if enough data for valid calculation."""
        return self.macd is not None and self.signal is not None
    
    @staticmethod
    def _is_nan(value: float) -> bool:
        return value != value
