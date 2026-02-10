"""
Ultimate Trend Strategy Bot
============================

Main entrypoint. Connects Bybit WebSocket for market data,
runs strategy engine on confirmed candles, and executes trades
via Mudrex API with full risk management.

Usage:
    python -m src.main
    DRY_RUN=true SYMBOLS=BTCUSDT python -m src.main
"""

import asyncio
import logging
import signal
import sys
import time
from typing import Optional

from src.config import Config
from src.strategy.engine import StrategyEngine
from src.trading.executor import TradeExecutor
from src.trading.position_manager import PositionManager
from src.trading.risk_manager import RiskManager
from src.bybit_ws.client import BybitWebSocket, OHLCV


def setup_logging(config: Config) -> None:
    log_format = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    log_level = getattr(logging, config.logging.level.upper(), logging.INFO)

    handlers = [logging.StreamHandler(sys.stdout)]
    if config.logging.file:
        handlers.append(logging.FileHandler(config.logging.file))

    logging.basicConfig(
        level=log_level,
        format=log_format,
        handlers=handlers,
    )


logger = logging.getLogger(__name__)


class UltimateTrendBot:
    """
    Main bot orchestrator.

    Lifecycle:
    1. Load config → validate
    2. Init engine, executor, position manager, risk manager
    3. Connect Bybit WebSocket
    4. On each confirmed candle: update → evaluate → execute
    5. Background loop: manage open positions
    6. Graceful shutdown on SIGINT/SIGTERM
    """

    def __init__(self, config: Config):
        self.config = config

        # Core components
        self.engine = StrategyEngine(config)
        self.executor = TradeExecutor(config)
        self.risk_mgr = RiskManager(config)
        self.pos_mgr = PositionManager(config, self.executor, self.engine)

        # WebSocket
        self.ws: Optional[BybitWebSocket] = None

        # Control
        self._running = False
        self._shutdown_event = asyncio.Event()

    async def start(self) -> None:
        """Start the bot."""
        logger.info("=" * 60)
        logger.info("🚀 ULTIMATE TREND STRATEGY BOT")
        logger.info("=" * 60)
        self.config.print_config()

        if self.config.dry_run:
            logger.warning("⚠️  DRY-RUN MODE — no real orders will be placed")

        self._running = True

        # Setup signal handlers
        loop = asyncio.get_event_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, self._handle_shutdown)

        # Connect WebSocket
        try:
            await self._run()
        except Exception as e:
            logger.error(f"Bot error: {e}")
        finally:
            await self._cleanup()

    def _handle_shutdown(self) -> None:
        logger.info("🛑 Shutdown signal received")
        self._running = False
        self._shutdown_event.set()

    async def _run(self) -> None:
        """Main run loop with WebSocket connection."""
        self.ws = BybitWebSocket(
            symbols=self.config.symbols,
            timeframe=str(self.config.timeframe),
            ws_url=self.config.bybit.ws_url,
            ping_interval=self.config.bybit.ping_interval,
            reconnect_delay=self.config.bybit.reconnect_delay,
        )

        # Set kline callback
        self.ws.on_kline = self._on_kline

        # Run WS and position manager concurrently
        await asyncio.gather(
            self._ws_loop(),
            self._position_management_loop(),
            self._status_loop(),
        )

    async def _ws_loop(self) -> None:
        """WebSocket connection loop with reconnect."""
        while self._running:
            try:
                await self.ws.connect()
                await self.ws.run_forever()
            except Exception as e:
                if not self._running:
                    break
                logger.warning(f"WebSocket disconnected: {e}. Reconnecting in {self.config.bybit.reconnect_delay}s...")
                await asyncio.sleep(self.config.bybit.reconnect_delay)

    async def _position_management_loop(self) -> None:
        """Background loop to manage open positions (trailing, breakeven, partial TP)."""
        while self._running:
            try:
                if self.pos_mgr.active_symbols:
                    # Update prices from WS tickers
                    for symbol in self.pos_mgr.active_symbols:
                        if self.ws and symbol in self.ws._tickers:
                            self.pos_mgr.update_price(symbol, self.ws._tickers[symbol].last_price)

                    self.pos_mgr.manage_all()
            except Exception as e:
                logger.error(f"Position management error: {e}")

            # Wait 10 seconds or until shutdown
            try:
                await asyncio.wait_for(self._shutdown_event.wait(), timeout=10.0)
                break
            except asyncio.TimeoutError:
                pass

    async def _status_loop(self) -> None:
        """Periodic status logging."""
        while self._running:
            try:
                await asyncio.wait_for(self._shutdown_event.wait(), timeout=300.0)
                break
            except asyncio.TimeoutError:
                # Log status every 5 minutes
                stats = self.risk_mgr.get_stats()
                positions = self.pos_mgr.active_symbols
                logger.info(
                    f"📊 Status: {stats['total_trades']} trades | "
                    f"Win rate: {stats['win_rate']} | "
                    f"Active positions: {len(positions)} ({', '.join(positions) if positions else 'none'}) | "
                    f"Sizing: {stats['sizing_multiplier']}x"
                )
                for symbol in self.config.symbols:
                    values = self.engine.get_indicator_values(symbol)
                    if values.get("price"):
                        logger.info(
                            f"  {symbol}: ${values['price']:.2f} | "
                            f"RSI: {values.get('rsi', 'N/A')} | "
                            f"ADX: {values.get('adx', 'N/A')} | "
                            f"ATR%: {values.get('atr_pct', 'N/A')} | "
                            f"ST: {'↑' if values.get('supertrend_dir') == 1 else '↓'} | "
                            f"Chop: {values.get('choppiness', 'N/A')}"
                        )

    def _on_kline(self, symbol: str, kline: OHLCV) -> None:
        """Callback for confirmed candle close."""
        if not kline.confirm:
            return  # Only process confirmed candles

        try:
            # Update strategy engine
            self.engine.update_kline(symbol, kline)

            # Evaluate signal
            signal_result = self.engine.evaluate(symbol)

            if signal_result.is_actionable:
                logger.info(
                    f"🔔 SIGNAL: {signal_result.side} {symbol} | "
                    f"Entry: {signal_result.entry_price:.4f} | "
                    f"SL: {signal_result.stoploss_price:.4f} | "
                    f"TP: {signal_result.takeprofit_price:.4f} | "
                    f"Reasons: {signal_result.reason}"
                )

                # Check if we already have a position
                if symbol not in self.pos_mgr.active_symbols:
                    # Get sizing multiplier
                    sizing = self.risk_mgr.get_sizing_multiplier()

                    # Execute trade
                    result = self.executor.execute(signal_result, sizing_multiplier=sizing)

                    if result.success:
                        # Get ATR for position management
                        values = self.engine.get_indicator_values(symbol)
                        atr = values.get("atr", 0.0) or 0.0

                        # Register for position management
                        self.pos_mgr.register_position(
                            symbol=symbol,
                            side=signal_result.side,
                            entry_price=signal_result.entry_price,
                            stoploss=signal_result.stoploss_price,
                            takeprofit=signal_result.takeprofit_price,
                            tp1=signal_result.tp1_price,
                            tp2=signal_result.tp2_price,
                            atr=atr,
                        )
                else:
                    logger.debug(f"Already positioned in {symbol}, skipping signal")
            else:
                logger.debug(f"{symbol}: {signal_result.reason}")

        except Exception as e:
            logger.error(f"Error processing kline for {symbol}: {e}", exc_info=True)

    async def _cleanup(self) -> None:
        """Graceful cleanup."""
        logger.info("🧹 Cleaning up...")
        if self.ws:
            await self.ws.close()
        self.executor.close()
        logger.info("👋 Bot stopped.")


def main():
    """CLI entrypoint."""
    config = Config.load()

    setup_logging(config)

    # Fetch symbols from Mudrex if not set via env var or config
    if not config.symbols:
        from src.utils.symbols import fetch_mudrex_symbols
        logger.info("📡 Fetching symbols from Mudrex API...")
        if config.mudrex_api_secret:
            config.symbols = fetch_mudrex_symbols(config.mudrex_api_secret)
        if not config.symbols:
            logger.error("No symbols available. Set SYMBOLS env var or provide MUDREX_API_SECRET.")
            sys.exit(1)
        logger.info(f"📡 Trading {len(config.symbols)} Mudrex symbols")

    if not config.validate():
        sys.exit(1)

    bot = UltimateTrendBot(config)
    asyncio.run(bot.start())


if __name__ == "__main__":
    main()
