"""
Position Manager
==================

Manages open positions with:
- Trailing stop (ATR-based)
- Breakeven move
- Partial profit taking (TP1: 50%, TP2: 25%)
- Reversal exit signals

Runs as a background loop polling positions every ~10 seconds.
"""

import asyncio
import logging
import time
from typing import Dict, Optional, TYPE_CHECKING
from dataclasses import dataclass, field

from src.config import Config
from src.trading.executor import TradeExecutor
from src.strategy.engine import StrategyEngine

if TYPE_CHECKING:
    from src.utils.telegram import TelegramAlerter

logger = logging.getLogger(__name__)


@dataclass
class ManagedPosition:
    """Tracked position with risk management state."""
    symbol: str
    side: str  # "LONG" or "SHORT"
    entry_price: float
    current_price: float = 0.0
    stoploss: float = 0.0
    takeprofit: float = 0.0
    tp1_price: float = 0.0
    tp2_price: float = 0.0
    atr_at_entry: float = 0.0

    # State tracking
    breakeven_triggered: bool = False
    tp1_triggered: bool = False
    tp2_triggered: bool = False
    highest_price: float = 0.0  # For long trailing
    lowest_price: float = float('inf')  # For short trailing
    open_time: float = field(default_factory=time.time)


class PositionManager:
    """
    Background position risk manager.

    Polls open positions and manages:
    1. Trailing stop: move SL in profit direction
    2. Breakeven: move SL to entry when profit > trigger
    3. Partial TP: close portions at TP1/TP2
    4. Reversal exits: close on counter-signal
    """

    def __init__(self, config: Config, executor: TradeExecutor, engine: StrategyEngine, telegram: Optional["TelegramAlerter"] = None):
        self.config = config
        self.executor = executor
        self.engine = engine
        self.tg = telegram
        self._positions: Dict[str, ManagedPosition] = {}

    def _tg_fire(self, coro) -> None:
        """Fire-and-forget a TG alert coroutine."""
        if self.tg:
            try:
                asyncio.ensure_future(coro)
            except RuntimeError:
                pass  # No event loop running (e.g. during tests)

    def register_position(
        self, symbol: str, side: str, entry_price: float,
        stoploss: float, takeprofit: float,
        tp1: float = 0.0, tp2: float = 0.0,
        atr: float = 0.0,
    ) -> None:
        """Register a new position for management."""
        pos = ManagedPosition(
            symbol=symbol,
            side=side,
            entry_price=entry_price,
            current_price=entry_price,
            stoploss=stoploss,
            takeprofit=takeprofit,
            tp1_price=tp1,
            tp2_price=tp2,
            atr_at_entry=atr,
            highest_price=entry_price,
            lowest_price=entry_price,
        )
        self._positions[symbol] = pos
        logger.info(
            f"📋 Registered {side} {symbol} @ {entry_price:.4f} | "
            f"SL: {stoploss:.4f} | TP: {takeprofit:.4f}"
        )

    def unregister_position(self, symbol: str) -> None:
        """Remove a position from management."""
        if symbol in self._positions:
            del self._positions[symbol]
            logger.info(f"📋 Unregistered {symbol}")

    def update_price(self, symbol: str, price: float) -> None:
        """Update current price for a managed position."""
        if symbol in self._positions:
            pos = self._positions[symbol]
            pos.current_price = price
            if pos.side == "LONG":
                pos.highest_price = max(pos.highest_price, price)
            else:
                pos.lowest_price = min(pos.lowest_price, price)

    @property
    def active_symbols(self) -> list:
        return list(self._positions.keys())

    def manage_all(self) -> None:
        """Run management checks on all positions."""
        for symbol in list(self._positions.keys()):
            try:
                self._manage_position(symbol)
            except Exception as e:
                logger.error(f"Error managing {symbol}: {e}")

    def _manage_position(self, symbol: str) -> None:
        """Run all management checks for a single position."""
        pos = self._positions.get(symbol)
        if not pos:
            return

        cfg = self.config
        atr = pos.atr_at_entry
        if atr <= 0:
            return

        # 1. Check reversal exit
        if self._check_reversal_exit(pos):
            return

        # 2. Check partial TP1 (50% close)
        if cfg.profit.use_partial_profits and not pos.tp1_triggered and pos.tp1_price > 0:
            self._check_partial_tp1(pos)

        # 3. Check partial TP2 (25% close)
        if cfg.profit.use_partial_profits and not pos.tp2_triggered and pos.tp2_price > 0:
            self._check_partial_tp2(pos)

        # 4. Move to breakeven
        if cfg.risk.use_breakeven and not pos.breakeven_triggered:
            self._check_breakeven(pos, atr)

        # 5. Trailing stop
        if cfg.risk.use_trailing_stop:
            self._check_trailing_stop(pos, atr)

    def _check_reversal_exit(self, pos: ManagedPosition) -> bool:
        """Close position on reversal signal."""
        if pos.side == "LONG" and self.engine.should_exit_long(pos.symbol):
            logger.info(f"🔄 Reversal exit: closing LONG {pos.symbol}")
            self.executor.close_position(pos.symbol, pos.side)
            self._tg_fire(self.tg.send_reversal_exit(pos.symbol, pos.side, "Bearish reversal")) if self.tg else None
            self.unregister_position(pos.symbol)
            return True

        if pos.side == "SHORT" and self.engine.should_exit_short(pos.symbol):
            logger.info(f"🔄 Reversal exit: closing SHORT {pos.symbol}")
            self.executor.close_position(pos.symbol, pos.side)
            self._tg_fire(self.tg.send_reversal_exit(pos.symbol, pos.side, "Bullish reversal")) if self.tg else None
            self.unregister_position(pos.symbol)
            return True

        return False

    def _check_partial_tp1(self, pos: ManagedPosition) -> None:
        """Close 50% at TP1."""
        hit = False
        if pos.side == "LONG" and pos.current_price >= pos.tp1_price:
            hit = True
        elif pos.side == "SHORT" and pos.current_price <= pos.tp1_price:
            hit = True

        if hit:
            logger.info(f"🎯 TP1 hit: closing 50% of {pos.side} {pos.symbol} @ {pos.current_price:.4f}")
            if self.executor.close_partial(pos.symbol, pos.side, 0.5):
                pos.tp1_triggered = True
                self._tg_fire(self.tg.send_partial_tp(pos.symbol, pos.side, 1, 0.5, pos.current_price)) if self.tg else None

    def _check_partial_tp2(self, pos: ManagedPosition) -> None:
        """Close 25% at TP2."""
        hit = False
        if pos.side == "LONG" and pos.current_price >= pos.tp2_price:
            hit = True
        elif pos.side == "SHORT" and pos.current_price <= pos.tp2_price:
            hit = True

        if hit:
            logger.info(f"🎯 TP2 hit: closing 25% of {pos.side} {pos.symbol} @ {pos.current_price:.4f}")
            if self.executor.close_partial(pos.symbol, pos.side, 0.5):  # 50% of remaining = 25% of original
                pos.tp2_triggered = True
                self._tg_fire(self.tg.send_partial_tp(pos.symbol, pos.side, 2, 0.25, pos.current_price)) if self.tg else None

    def _check_breakeven(self, pos: ManagedPosition, atr: float) -> None:
        """Move SL to entry + small buffer when profit reaches trigger."""
        trigger = self.config.risk.breakeven_trigger_atr
        buffer = atr * 0.1  # Small buffer above entry

        if pos.side == "LONG":
            if pos.current_price >= pos.entry_price + (atr * trigger):
                new_sl = pos.entry_price + buffer
                if new_sl > pos.stoploss:
                    logger.info(f"🔒 Breakeven: {pos.symbol} SL → {new_sl:.4f}")
                    if self.executor.set_stoploss(pos.symbol, new_sl):
                        pos.stoploss = new_sl
                        pos.breakeven_triggered = True
                        self._tg_fire(self.tg.send_breakeven_activated(pos.symbol, pos.side, pos.entry_price)) if self.tg else None

        elif pos.side == "SHORT":
            if pos.current_price <= pos.entry_price - (atr * trigger):
                new_sl = pos.entry_price - buffer
                if new_sl < pos.stoploss:
                    logger.info(f"🔒 Breakeven: {pos.symbol} SL → {new_sl:.4f}")
                    if self.executor.set_stoploss(pos.symbol, new_sl):
                        pos.stoploss = new_sl
                        pos.breakeven_triggered = True
                        self._tg_fire(self.tg.send_breakeven_activated(pos.symbol, pos.side, pos.entry_price)) if self.tg else None

    def _check_trailing_stop(self, pos: ManagedPosition, atr: float) -> None:
        """Trail stop-loss behind price using ATR multiplier."""
        trail_dist = atr * self.config.risk.trailing_stop_atr

        if pos.side == "LONG":
            new_sl = pos.highest_price - trail_dist
            if new_sl > pos.stoploss:
                logger.debug(f"📈 Trail SL: {pos.symbol} {pos.stoploss:.4f} → {new_sl:.4f}")
                if self.executor.set_stoploss(pos.symbol, new_sl):
                    old_sl = pos.stoploss
                    pos.stoploss = new_sl
                    # Only alert on significant moves (> 0.5 ATR from last alert)
                    if atr > 0 and (new_sl - old_sl) > atr * 0.5:
                        self._tg_fire(self.tg.send_trailing_stop_update(pos.symbol, pos.side, new_sl, pos.current_price)) if self.tg else None

        elif pos.side == "SHORT":
            new_sl = pos.lowest_price + trail_dist
            if new_sl < pos.stoploss:
                logger.debug(f"📉 Trail SL: {pos.symbol} {pos.stoploss:.4f} → {new_sl:.4f}")
                if self.executor.set_stoploss(pos.symbol, new_sl):
                    old_sl = pos.stoploss
                    pos.stoploss = new_sl
                    if atr > 0 and (old_sl - new_sl) > atr * 0.5:
                        self._tg_fire(self.tg.send_trailing_stop_update(pos.symbol, pos.side, new_sl, pos.current_price)) if self.tg else None
