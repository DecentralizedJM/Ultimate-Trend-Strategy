"""
Unit Tests for Technical Indicators
====================================

Tests all new indicators: Supertrend, Bollinger Bands, ADX,
Choppiness, Volume, MultiEMA, RSI divergence.
"""

import pytest
from src.indicators.ema import EMAIndicator, MultiEMAIndicator, calculate_ema
from src.indicators.rsi import RSIIndicator, calculate_rsi
from src.indicators.macd import MACDIndicator
from src.indicators.atr import ATRIndicator
from src.indicators.supertrend import SupertrendIndicator
from src.indicators.bollinger import BollingerBandsIndicator
from src.indicators.adx import ADXIndicator
from src.indicators.choppiness import ChoppinessIndicator
from src.indicators.volume import VolumeIndicator


# ============================================================================
# EMA Tests
# ============================================================================

class TestEMA:
    def test_calculate_ema_basic(self):
        prices = [44, 44.5, 45, 43.5, 44, 44.5, 44.5, 44.25, 43.25, 44.5]
        result = calculate_ema(prices, period=5)
        assert result[4] == pytest.approx(44.2, rel=0.01)
        assert len(result) == len(prices)

    def test_ema_crossover(self):
        ema = EMAIndicator(fast_period=3, slow_period=5)
        prices = [100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110]
        for p in prices:
            ema.update(p)
        assert ema.is_ready()
        assert ema.is_bullish()


class TestMultiEMA:
    def test_four_ema_init(self):
        ema = MultiEMAIndicator(fast_period=3, slow_period=5, filter_period=10, trend_period=20)
        assert not ema.is_ready()

    def test_strong_bull_trend(self):
        ema = MultiEMAIndicator(fast_period=3, slow_period=5, filter_period=10, trend_period=20)
        # Feed uptrend data
        prices = list(range(100, 150))
        for p in prices:
            ema.update(p)
        # In strong uptrend, all EMAs should be below price
        assert ema.is_ready()
        assert ema.is_fast_above_slow()
        assert ema.is_strong_bull_trend(149)
        assert ema.is_above_trend(149)

    def test_strong_bear_trend(self):
        ema = MultiEMAIndicator(fast_period=3, slow_period=5, filter_period=10, trend_period=20)
        prices = list(range(200, 140, -1))
        for p in prices:
            ema.update(p)
        assert ema.is_ready()
        assert ema.is_strong_bear_trend(141)

    def test_batch_update(self):
        ema = MultiEMAIndicator(fast_period=3, slow_period=5, filter_period=10, trend_period=20)
        prices = list(range(100, 150))
        ema.update_batch(prices)
        assert ema.is_ready()
        assert ema.fast_value is not None


# ============================================================================
# RSI Tests
# ============================================================================

class TestRSI:
    def test_rsi_range(self):
        prices = [44, 44.25, 44.5, 43.75, 44.5, 44.5, 44.25, 44.75,
                  43.5, 44.5, 44.25, 44.5, 45, 44.75, 45.25, 46]
        result = calculate_rsi(prices, period=14)
        valid = [r for r in result if r == r]
        assert len(valid) > 0
        assert all(0 <= r <= 100 for r in valid)

    def test_rsi_bull_zone(self):
        rsi = RSIIndicator(period=5, oversold=30, overbought=70)
        prices = [100, 102, 104, 106, 108, 110, 109, 111]
        for p in prices:
            rsi.update(p)
        assert rsi.is_ready()
        assert rsi.value is not None
        assert rsi.value > 50

    def test_rsi_bear_zone(self):
        rsi = RSIIndicator(period=5, oversold=30, overbought=70)
        prices = [100, 98, 96, 94, 92, 90, 91, 89]
        for p in prices:
            rsi.update(p)
        assert rsi.is_ready()
        assert rsi.value < 50


# ============================================================================
# Supertrend Tests
# ============================================================================

class TestSupertrend:
    def _generate_uptrend(self, n=30, base=100, step=2):
        highs, lows, closes = [], [], []
        for i in range(n):
            c = base + i * step
            highs.append(c + 1)
            lows.append(c - 1)
            closes.append(c)
        return highs, lows, closes

    def _generate_downtrend(self, n=30, base=200, step=2):
        highs, lows, closes = [], [], []
        for i in range(n):
            c = base - i * step
            highs.append(c + 1)
            lows.append(c - 1)
            closes.append(c)
        return highs, lows, closes

    def test_bullish_direction(self):
        st = SupertrendIndicator(atr_period=5, multiplier=2.0)
        highs, lows, closes = self._generate_uptrend()
        for h, l, c in zip(highs, lows, closes):
            st.update(h, l, c)
        assert st.is_ready()
        assert st.is_bullish()

    def test_bearish_direction(self):
        st = SupertrendIndicator(atr_period=5, multiplier=2.0)
        highs, lows, closes = self._generate_downtrend()
        for h, l, c in zip(highs, lows, closes):
            st.update(h, l, c)
        assert st.is_ready()
        assert st.is_bearish()

    def test_batch_update(self):
        st = SupertrendIndicator(atr_period=5, multiplier=2.0)
        highs, lows, closes = self._generate_uptrend(50)
        st.update_batch(highs, lows, closes)
        assert st.is_ready()
        assert st.value is not None

    def test_direction_change(self):
        st = SupertrendIndicator(atr_period=5, multiplier=1.5)
        # Uptrend then sharp reversal
        highs, lows, closes = self._generate_uptrend(20, 100, 2)
        for h, l, c in zip(highs, lows, closes):
            st.update(h, l, c)
        initial_dir = st.direction

        # Sharp downtrend
        h2, l2, c2 = self._generate_downtrend(20, closes[-1], 3)
        for h, l, c in zip(h2, l2, c2):
            st.update(h, l, c)

        # Direction should have changed
        assert st.direction != initial_dir


# ============================================================================
# Bollinger Bands Tests
# ============================================================================

class TestBollingerBands:
    def test_basic(self):
        bb = BollingerBandsIndicator(period=5, std_dev=2.0)
        prices = [100, 101, 102, 103, 104, 105]
        for p in prices:
            bb.update(p)
        assert bb.is_ready()
        assert bb.upper > bb.basis > bb.lower

    def test_width_pct(self):
        bb = BollingerBandsIndicator(period=5, std_dev=2.0)
        # Volatile prices
        prices = [100, 110, 90, 115, 85, 120]
        for p in prices:
            bb.update(p)
        assert bb.is_ready()
        assert bb.width_pct is not None
        assert bb.width_pct > 0

    def test_above_below_basis(self):
        bb = BollingerBandsIndicator(period=5, std_dev=2.0)
        prices = [100, 101, 102, 103, 104]
        for p in prices:
            bb.update(p)
        assert bb.is_above_basis(105)
        assert bb.is_below_basis(99)

    def test_wide_enough(self):
        bb = BollingerBandsIndicator(period=5, std_dev=2.0)
        # Very volatile
        prices = [100, 120, 80, 130, 70]
        for p in prices:
            bb.update(p)
        assert bb.is_wide_enough(5.0)  # Should be very wide

    def test_narrow(self):
        bb = BollingerBandsIndicator(period=5, std_dev=2.0)
        # Flat prices = narrow bands
        prices = [100, 100, 100, 100, 100]
        for p in prices:
            bb.update(p)
        assert not bb.is_wide_enough(1.0)  # Zero width


# ============================================================================
# ADX Tests
# ============================================================================

class TestADX:
    def test_strong_uptrend(self):
        adx = ADXIndicator(period=5)
        for i in range(20):
            high = 100 + i * 2 + 1
            low = 100 + i * 2 - 1
            close = 100 + i * 2
            adx.update(high, low, close)
        assert adx.is_ready()

    def test_adx_values(self):
        adx = ADXIndicator(period=5)
        for i in range(30):
            high = 100 + i * 3 + 2
            low = 100 + i * 3 - 2
            close = 100 + i * 3
            adx.update(high, low, close)
        assert adx.adx_value is not None
        assert adx.di_plus is not None
        assert adx.di_minus is not None

    def test_strong_trend_detection(self):
        adx = ADXIndicator(period=5)
        # Strong trend with big moves
        for i in range(30):
            high = 100 + i * 5 + 3
            low = 100 + i * 5 - 3
            close = 100 + i * 5
            adx.update(high, low, close)
        # In a strong trend, ADX should be above threshold
        assert adx.is_strong_trend(20)

    def test_batch_update(self):
        adx = ADXIndicator(period=5)
        highs = [100 + i * 2 + 1 for i in range(30)]
        lows = [100 + i * 2 - 1 for i in range(30)]
        closes = [100 + i * 2 for i in range(30)]
        adx.update_batch(highs, lows, closes)
        assert adx.is_ready()


# ============================================================================
# Choppiness Tests
# ============================================================================

class TestChoppiness:
    def test_choppy_market(self):
        chop = ChoppinessIndicator(chop_period=10, sideways_period=10)
        # Oscillating prices = choppy
        for i in range(20):
            base = 100 + (i % 2) * 2
            chop.update(base + 1, base - 1, base)
        assert chop.is_ready()

    def test_trending_market(self):
        chop = ChoppinessIndicator(chop_period=10, sideways_period=10)
        # Strong trend
        for i in range(20):
            base = 100 + i * 5
            chop.update(base + 2, base - 2, base)
        assert chop.is_ready()
        assert chop.value is not None

    def test_sideways_detection(self):
        chop = ChoppinessIndicator(chop_period=10, sideways_period=10)
        # Very tight range
        for i in range(20):
            chop.update(100.5, 99.5, 100)
        assert chop.is_sideways(5.0)

    def test_not_sideways(self):
        chop = ChoppinessIndicator(chop_period=10, sideways_period=10)
        # Wide range
        for i in range(20):
            base = 100 + i * 10
            chop.update(base + 5, base - 5, base)
        assert not chop.is_sideways(1.0)


# ============================================================================
# Volume Tests
# ============================================================================

class TestVolume:
    def test_above_average(self):
        vol = VolumeIndicator(period=5)
        # Average volumes
        for _ in range(5):
            vol.update(100)
        # Spike
        vol.update(200)
        assert vol.is_above_average(1.2)

    def test_not_above_average(self):
        vol = VolumeIndicator(period=5)
        for _ in range(6):
            vol.update(100)
        assert not vol.is_above_average(1.2)

    def test_volume_spike(self):
        vol = VolumeIndicator(period=5)
        for _ in range(5):
            vol.update(100)
        vol.update(300)
        assert vol.is_spike(2.0)

    def test_batch_update(self):
        vol = VolumeIndicator(period=5)
        vol.update_batch([100, 100, 100, 100, 100, 200])
        assert vol.is_ready()
        assert vol.is_above_average(1.2)


# ============================================================================
# Candlestick Patterns
# ============================================================================

class TestPatterns:
    def test_bullish_engulfing(self):
        from src.strategy.patterns import bullish_engulfing
        # Previous: bearish (close < open), Current: bullish (close > open) that engulfs
        assert bullish_engulfing(
            open_curr=95, high_curr=110, low_curr=94, close_curr=108,
            open_prev=105, high_prev=106, low_prev=97, close_prev=98,
        )

    def test_bearish_engulfing(self):
        from src.strategy.patterns import bearish_engulfing
        assert bearish_engulfing(
            open_curr=108, high_curr=109, low_curr=93, close_curr=94,
            open_prev=98, high_prev=107, low_prev=97, close_prev=105,
        )

    def test_hammer(self):
        from src.strategy.patterns import hammer
        # Long lower wick, small body at top
        assert hammer(open_p=98, high=100, low=90, close=99)

    def test_shooting_star(self):
        from src.strategy.patterns import shooting_star
        # Long upper wick, small body at bottom
        assert shooting_star(open_p=99, high=110, low=97, close=98)


# ============================================================================
# News Filter
# ============================================================================

class TestNewsFilter:
    def test_blackout(self):
        from datetime import datetime, timezone
        from src.strategy.news_filter import NewsFilter

        nf = NewsFilter(enabled=True, buffer_before=30, buffer_after=30)
        nf.add_event("NFP", month=2, day=7, hour=13, minute=30)

        # During event
        during = datetime(2025, 2, 7, 13, 30, tzinfo=timezone.utc)
        assert nf.is_blackout(during)

        # Before buffer
        before = datetime(2025, 2, 7, 13, 0, tzinfo=timezone.utc)
        assert nf.is_blackout(before)

        # Way before (outside buffer)
        clear = datetime(2025, 2, 7, 12, 0, tzinfo=timezone.utc)
        assert not nf.is_blackout(clear)

    def test_disabled(self):
        from datetime import datetime, timezone
        from src.strategy.news_filter import NewsFilter

        nf = NewsFilter(enabled=False)
        nf.add_event("NFP", month=2, day=7, hour=13, minute=30)
        during = datetime(2025, 2, 7, 13, 30, tzinfo=timezone.utc)
        assert not nf.is_blackout(during)


# ============================================================================
# Risk Manager
# ============================================================================

class TestRiskManager:
    def test_sizing_reduction(self):
        from src.trading.risk_manager import RiskManager
        from src.config import Config

        config = Config()
        config.sizing.max_consecutive_losses = 2
        rm = RiskManager(config)

        assert rm.get_sizing_multiplier() == 1.0

        rm.record_loss()
        rm.record_loss()
        assert rm.get_sizing_multiplier() == 0.75

        rm.record_loss()
        assert rm.get_sizing_multiplier() == 0.5

    def test_reset_on_win(self):
        from src.trading.risk_manager import RiskManager
        from src.config import Config

        config = Config()
        rm = RiskManager(config)

        rm.record_loss()
        rm.record_loss()
        rm.record_loss()
        rm.record_win()
        assert rm.get_sizing_multiplier() == 1.0
        assert rm.consecutive_losses == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
