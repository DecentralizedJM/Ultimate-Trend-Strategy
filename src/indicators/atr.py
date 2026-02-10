"""
Average True Range (ATR)
========================

Volatility indicator measuring the average trading range over a period.
Used for dynamic stop-loss calculation.
"""

from typing import List, Optional, Tuple
from dataclasses import dataclass


def calculate_true_range(
    highs: List[float],
    lows: List[float],
    closes: List[float]
) -> List[float]:
    """
    Calculate True Range for each period.
    
    True Range = max(High-Low, |High-PrevClose|, |Low-PrevClose|)
    
    Args:
        highs: List of high prices
        lows: List of low prices
        closes: List of close prices
        
    Returns:
        List of True Range values
    """
    if len(highs) != len(lows) or len(lows) != len(closes):
        raise ValueError("All price lists must have same length")
    
    if len(highs) < 2:
        return [highs[0] - lows[0]] if highs else []
    
    tr_values = [highs[0] - lows[0]]  # First TR is just High-Low
    
    for i in range(1, len(highs)):
        high_low = highs[i] - lows[i]
        high_prev_close = abs(highs[i] - closes[i - 1])
        low_prev_close = abs(lows[i] - closes[i - 1])
        
        tr = max(high_low, high_prev_close, low_prev_close)
        tr_values.append(tr)
    
    return tr_values


def calculate_atr(
    highs: List[float],
    lows: List[float],
    closes: List[float],
    period: int = 14
) -> List[float]:
    """
    Calculate Average True Range using Wilder's smoothing.
    
    Args:
        highs: List of high prices
        lows: List of low prices
        closes: List of close prices
        period: ATR period (default: 14)
        
    Returns:
        List of ATR values
    """
    tr_values = calculate_true_range(highs, lows, closes)
    
    if len(tr_values) < period:
        return [float('nan')] * len(tr_values)
    
    atr_values = [float('nan')] * (period - 1)
    
    # First ATR is SMA of first 'period' TR values
    first_atr = sum(tr_values[:period]) / period
    atr_values.append(first_atr)
    
    # Calculate remaining ATRs using Wilder's smoothing
    for tr in tr_values[period:]:
        atr = (atr_values[-1] * (period - 1) + tr) / period
        atr_values.append(atr)
    
    return atr_values


@dataclass
class ATRIndicator:
    """
    ATR indicator for volatility measurement and stop-loss calculation.
    
    Example:
        atr = ATRIndicator(period=14)
        atr.update(high, low, close)
        stop_loss = current_price - (atr.value * 1.5)
    """
    
    period: int = 14
    
    def __post_init__(self):
        self._highs: List[float] = []
        self._lows: List[float] = []
        self._closes: List[float] = []
        self._atr_values: List[float] = []
    
    def update(self, high: float, low: float, close: float) -> None:
        """Add new OHLC data and recalculate ATR."""
        self._highs.append(high)
        self._lows.append(low)
        self._closes.append(close)
        
        # Recalculate
        self._atr_values = calculate_atr(
            self._highs, self._lows, self._closes, self.period
        )
        
        # Trim to last 500 values
        if len(self._highs) > 500:
            self._highs = self._highs[-500:]
            self._lows = self._lows[-500:]
            self._closes = self._closes[-500:]
            self._atr_values = self._atr_values[-500:]
    
    def update_batch(
        self,
        highs: List[float],
        lows: List[float],
        closes: List[float]
    ) -> None:
        """Batch update with multiple OHLC values."""
        self._highs = highs[-500:]
        self._lows = lows[-500:]
        self._closes = closes[-500:]
        self._atr_values = calculate_atr(
            self._highs, self._lows, self._closes, self.period
        )
    
    @property
    def value(self) -> Optional[float]:
        """Get current ATR value."""
        if self._atr_values and not self._is_nan(self._atr_values[-1]):
            return self._atr_values[-1]
        return None
    
    def get_stoploss_distance(self, multiplier: float = 1.5) -> Optional[float]:
        """
        Calculate stop-loss distance based on ATR.
        
        Args:
            multiplier: ATR multiplier (default: 1.5)
            
        Returns:
            Stop-loss distance from entry price
        """
        if self.value is None:
            return None
        return self.value * multiplier
    
    def calculate_stoploss(
        self,
        entry_price: float,
        side: str,
        multiplier: float = 1.5
    ) -> Optional[float]:
        """
        Calculate stop-loss price.
        
        Args:
            entry_price: Entry price
            side: Trade side ("LONG" or "SHORT")
            multiplier: ATR multiplier
            
        Returns:
            Stop-loss price
        """
        distance = self.get_stoploss_distance(multiplier)
        if distance is None:
            return None
        
        if side.upper() == "LONG":
            return entry_price - distance
        else:
            return entry_price + distance
    
    def calculate_takeprofit(
        self,
        entry_price: float,
        side: str,
        risk_reward: float = 2.0,
        sl_multiplier: float = 1.5
    ) -> Optional[float]:
        """
        Calculate take-profit price based on risk:reward ratio.
        
        Args:
            entry_price: Entry price
            side: Trade side
            risk_reward: Risk:Reward ratio (default: 2.0)
            sl_multiplier: Stop-loss ATR multiplier
            
        Returns:
            Take-profit price
        """
        distance = self.get_stoploss_distance(sl_multiplier)
        if distance is None:
            return None
        
        tp_distance = distance * risk_reward
        
        if side.upper() == "LONG":
            return entry_price + tp_distance
        else:
            return entry_price - tp_distance
    
    def is_volatility_high(self, threshold_pct: float = 3.0, current_price: float = 0) -> bool:
        """Check if volatility is high (ATR > threshold % of price)."""
        if self.value is None or current_price <= 0:
            return False
        return (self.value / current_price) * 100 > threshold_pct
    
    def is_ready(self) -> bool:
        """Check if enough data for valid calculation."""
        return self.value is not None
    
    @staticmethod
    def _is_nan(value: float) -> bool:
        return value != value
