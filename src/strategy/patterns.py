"""
Candlestick Pattern Detection
===============================

Detects: bullish/bearish engulfing, hammer, shooting star,
morning/evening doji star.

Each pattern function takes recent OHLC bars and returns bool.
Mirrors PineScript pattern logic.
"""

from typing import List, Tuple


def _body(open_p: float, close: float) -> float:
    return abs(close - open_p)


def _range(high: float, low: float) -> float:
    return high - low


def bullish_engulfing(
    open_curr: float, high_curr: float, low_curr: float, close_curr: float,
    open_prev: float, high_prev: float, low_prev: float, close_prev: float,
) -> bool:
    """
    close > open (bullish bar) AND
    close[1] < open[1] (previous bearish) AND
    close > open[1] AND open < close[1]
    """
    return (
        close_curr > open_curr and
        close_prev < open_prev and
        close_curr > open_prev and
        open_curr < close_prev
    )


def bearish_engulfing(
    open_curr: float, high_curr: float, low_curr: float, close_curr: float,
    open_prev: float, high_prev: float, low_prev: float, close_prev: float,
) -> bool:
    """
    close < open (bearish) AND
    close[1] > open[1] (previous bullish) AND
    close < open[1] AND open > close[1]
    """
    return (
        close_curr < open_curr and
        close_prev > open_prev and
        close_curr < open_prev and
        open_curr > close_prev
    )


def hammer(open_p: float, high: float, low: float, close: float) -> bool:
    """
    Bullish bar with small body, long lower wick.
    close > open AND (close - open) < (high - low) * 0.3
    AND (min(close, open) - low) > (high - low) * 0.6
    """
    rng = _range(high, low)
    if rng == 0:
        return False
    return (
        close > open_p and
        (close - open_p) < rng * 0.3 and
        (min(close, open_p) - low) > rng * 0.6
    )


def shooting_star(open_p: float, high: float, low: float, close: float) -> bool:
    """
    Bearish bar with small body, long upper wick.
    close < open AND (open - close) < (high - low) * 0.3
    AND (high - max(close, open)) > (high - low) * 0.6
    """
    rng = _range(high, low)
    if rng == 0:
        return False
    return (
        close < open_p and
        (open_p - close) < rng * 0.3 and
        (high - max(close, open_p)) > rng * 0.6
    )


def morning_doji_star(
    bars: List[Tuple[float, float, float, float]],
) -> bool:
    """
    3-bar pattern (bars = [(O,H,L,C)] for bars[-3], bars[-2], bars[-1]):
    bar[-3] bearish, bar[-2] doji, bar[-1] bullish that recovers.
    """
    if len(bars) < 3:
        return False
    o2, h2, l2, c2 = bars[-3]
    o1, h1, l1, c1 = bars[-2]
    o0, h0, l0, c0 = bars[-1]

    rng1 = _range(h1, l1)
    if rng1 == 0:
        return False

    return (
        c2 < o2 and  # bar[-3] bearish
        abs(c1 - o1) < rng1 * 0.1 and  # bar[-2] doji
        c0 > o0 and  # bar[-1] bullish
        c0 > c2  # recovery
    )


def evening_doji_star(
    bars: List[Tuple[float, float, float, float]],
) -> bool:
    """
    3-bar pattern (bars = [(O,H,L,C)] for bars[-3], bars[-2], bars[-1]):
    bar[-3] bullish, bar[-2] doji, bar[-1] bearish that falls.
    """
    if len(bars) < 3:
        return False
    o2, h2, l2, c2 = bars[-3]
    o1, h1, l1, c1 = bars[-2]
    o0, h0, l0, c0 = bars[-1]

    rng1 = _range(h1, l1)
    if rng1 == 0:
        return False

    return (
        c2 > o2 and  # bar[-3] bullish
        abs(c1 - o1) < rng1 * 0.1 and  # bar[-2] doji
        c0 < o0 and  # bar[-1] bearish
        c0 < c2  # fall
    )
