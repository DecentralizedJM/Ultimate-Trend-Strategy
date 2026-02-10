"""
Unit Tests for Strategy Engine
==============================
"""

import pytest
import time
from src.strategy.signals import Signal, SignalType, IndicatorStatus
from src.strategy.engine import StrategyEngine, SymbolState
from src.config import Config


class TestSignal:
    def test_signal_actionable(self):
        long_signal = Signal(
            symbol="BTCUSDT",
            signal_type=SignalType.LONG,
        )
        assert long_signal.is_actionable
        assert long_signal.is_long
        assert not long_signal.is_short
        assert long_signal.side == "LONG"

        neutral = Signal(symbol="BTCUSDT", signal_type=SignalType.NEUTRAL)
        assert not neutral.is_actionable

    def test_signal_to_dict(self):
        signal = Signal(
            symbol="ETHUSDT",
            signal_type=SignalType.SHORT,
            entry_price=3000.0,
            stoploss_price=3100.0,
            takeprofit_price=2800.0,
        )
        d = signal.to_dict()
        assert d["symbol"] == "ETHUSDT"
        assert d["type"] == "SHORT"


class TestIndicatorStatus:
    def test_defaults(self):
        status = IndicatorStatus()
        assert not status.ema_fast_above_slow
        assert not status.adx_strong
        assert not status.news_blackout


class TestStrategyEngine:

    @pytest.fixture
    def config(self):
        cfg = Config()
        cfg.symbols = ["BTCUSDT"]
        cfg.timeframe = 5
        # Disable MTF (it requires higher TF data)
        cfg.mtf.enabled = False
        return cfg

    def test_engine_init(self, config):
        engine = StrategyEngine(config)
        assert "BTCUSDT" in engine._symbols

    def test_neutral_when_not_ready(self, config):
        engine = StrategyEngine(config)
        signal = engine.evaluate("BTCUSDT")
        assert signal.signal_type == SignalType.NEUTRAL
        assert "warming" in signal.reason.lower()

    def test_cooldown(self, config):
        engine = StrategyEngine(config)
        state = engine._symbols["BTCUSDT"]
        state.last_signal_time = time.time()

        # Feed enough data
        for i in range(300):
            state.ema.update(100 + i * 0.1)
            state.rsi.update(100 + i * 0.1)
            state.macd.update(100 + i * 0.1)
            state.atr.update(102 + i * 0.1, 98 + i * 0.1, 100 + i * 0.1)

        signal = engine.evaluate("BTCUSDT")
        assert signal.signal_type == SignalType.NEUTRAL
        assert "cooldown" in signal.reason.lower()

    def test_evaluate_indicators(self, config):
        engine = StrategyEngine(config)
        state = engine._symbols["BTCUSDT"]

        for i in range(300):
            state.ema.update(100 + i * 0.1)
            state.rsi.update(100 + i * 0.1)
            state.macd.update(100 + i * 0.1)
            state.atr.update(102 + i * 0.1, 98 + i * 0.1, 100 + i * 0.1)

        status = engine._evaluate_indicators(state)
        assert isinstance(status, IndicatorStatus)

    def test_no_trade_zone_blocks(self, config):
        engine = StrategyEngine(config)
        status = IndicatorStatus(is_choppy=True)
        assert engine._is_no_trade_zone(status)

    def test_news_blackout_blocks(self, config):
        engine = StrategyEngine(config)
        status = IndicatorStatus(news_blackout=True)
        assert engine._is_no_trade_zone(status)

    def test_get_indicator_values(self, config):
        engine = StrategyEngine(config)
        state = engine._symbols["BTCUSDT"]
        for i in range(30):
            state.ema.update(100 + i)
        state.last_price = 129
        values = engine.get_indicator_values("BTCUSDT")
        assert "price" in values
        assert values["price"] == 129


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
