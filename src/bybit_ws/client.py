"""
Bybit WebSocket Client
======================

Connects to Bybit V5 WebSocket API for real-time market data.
Handles klines, tickers, and orderbook streams.
"""

import asyncio
import json
import logging
import time
from typing import Callable, Dict, List, Optional, Any
from dataclasses import dataclass, field

import websockets
from websockets.exceptions import ConnectionClosed

logger = logging.getLogger(__name__)


def safe_float(value: Any, default: float = 0.0) -> float:
    """Safely convert value to float, returning default for empty/invalid values."""
    if value is None or value == "":
        return default
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def safe_int(value: Any, default: int = 0) -> int:
    """Safely convert value to int, returning default for empty/invalid values."""
    if value is None or value == "":
        return default
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


@dataclass
class OHLCV:
    """OHLCV candle data."""
    timestamp: int
    open: float
    high: float
    low: float
    close: float
    volume: float
    turnover: float
    confirm: bool = False  # True when candle is closed


@dataclass
class Ticker:
    """Ticker data from WebSocket."""
    symbol: str
    last_price: float
    mark_price: float
    index_price: float
    funding_rate: float
    next_funding_time: int
    open_interest: float
    volume_24h: float
    turnover_24h: float
    high_24h: float
    low_24h: float


class BybitWebSocket:
    """
    Bybit V5 WebSocket client for linear perpetuals.
    
    Example:
        async with BybitWebSocket(['BTCUSDT', 'ETHUSDT']) as ws:
            ws.on_kline = lambda symbol, kline: print(f"{symbol}: {kline.close}")
            ws.on_ticker = lambda ticker: print(f"{ticker.symbol}: {ticker.last_price}")
            await ws.run_forever()
    """
    
    WS_URL = "wss://stream.bybit.com/v5/public/linear"
    
    def __init__(
        self,
        symbols: List[str],
        timeframe: str = "5",
        ws_url: Optional[str] = None,
        ping_interval: int = 20,
        reconnect_delay: int = 5,
    ):
        self.symbols = [s.upper() for s in symbols]
        self.timeframe = timeframe
        self.ws_url = ws_url or self.WS_URL
        self.ping_interval = ping_interval
        self.reconnect_delay = reconnect_delay
        
        self._ws = None
        self._running = False
        self._reconnecting = False
        self._connected = False
        
        # Data storage
        self.klines: Dict[str, List[OHLCV]] = {s: [] for s in self.symbols}
        self.tickers: Dict[str, Ticker] = {}
        
        # Callbacks
        self.on_kline: Optional[Callable[[str, OHLCV], None]] = None
        self.on_ticker: Optional[Callable[[Ticker], None]] = None
        self.on_connect: Optional[Callable[[], None]] = None
        self.on_disconnect: Optional[Callable[[], None]] = None
    
    def _is_connected(self) -> bool:
        """Check if WebSocket is connected (version-agnostic)."""
        if not self._ws or not self._connected:
            return False
        try:
            # Try different attributes for different websockets versions
            if hasattr(self._ws, 'open'):
                return self._ws.open
            if hasattr(self._ws, 'closed'):
                return not self._ws.closed
            # If neither exists, trust our flag
            return self._connected
        except Exception:
            return self._connected
    
    async def connect(self) -> None:
        """Connect to WebSocket and subscribe to streams."""
        logger.info(f"Connecting to Bybit WebSocket: {self.ws_url}")
        self._connected = False
        
        try:
            self._ws = await websockets.connect(
                self.ws_url,
                ping_interval=self.ping_interval,
                ping_timeout=10,
            )
            self._connected = True
            logger.info("WebSocket connected successfully")
            
            # Subscribe to streams
            await self._subscribe()
            
            if self.on_connect:
                self.on_connect()
                
        except Exception as e:
            logger.error(f"Failed to connect: {e}")
            raise
    
    async def _subscribe(self) -> None:
        """Subscribe to kline and ticker streams for all symbols."""
        if not self._ws:
            return
        
        # Build subscription topics
        topics = []
        for symbol in self.symbols:
            # Kline stream: kline.{interval}.{symbol}
            topics.append(f"kline.{self.timeframe}.{symbol}")
            # Ticker stream: tickers.{symbol}
            topics.append(f"tickers.{symbol}")
        
        subscribe_msg = {
            "op": "subscribe",
            "args": topics
        }
        
        await self._ws.send(json.dumps(subscribe_msg))
        logger.info(f"Subscribed to topics: {topics}")
    
    async def _handle_message(self, message: str) -> None:
        """Parse and handle incoming WebSocket message."""
        try:
            data = json.loads(message)
            
            # Handle subscription confirmation
            if data.get("op") == "subscribe":
                if data.get("success"):
                    logger.debug(f"Subscription confirmed: {data.get('conn_id')}")
                else:
                    logger.error(f"Subscription failed: {data}")
                return
            
            # Handle pong
            if data.get("op") == "pong":
                return
            
            # Handle data messages
            topic = data.get("topic", "")
            msg_data = data.get("data", [])
            
            if topic.startswith("kline."):
                await self._handle_kline(topic, msg_data)
            elif topic.startswith("tickers."):
                await self._handle_ticker(topic, msg_data)
                
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse message: {e}")
        except Exception as e:
            logger.error(f"Error handling message: {e}")
    
    async def _handle_kline(self, topic: str, data: List[Dict]) -> None:
        """Handle kline/candlestick data."""
        # topic format: kline.{interval}.{symbol}
        parts = topic.split(".")
        if len(parts) < 3:
            return
        
        symbol = parts[2]
        
        for candle in data:
            ohlcv = OHLCV(
                timestamp=safe_int(candle.get("start"), 0),
                open=safe_float(candle.get("open"), 0),
                high=safe_float(candle.get("high"), 0),
                low=safe_float(candle.get("low"), 0),
                close=safe_float(candle.get("close"), 0),
                volume=safe_float(candle.get("volume"), 0),
                turnover=safe_float(candle.get("turnover"), 0),
                confirm=candle.get("confirm", False),
            )
            
            # Update klines storage
            if symbol in self.klines:
                klines = self.klines[symbol]
                
                # Update existing or append new
                if klines and klines[-1].timestamp == ohlcv.timestamp:
                    klines[-1] = ohlcv
                else:
                    klines.append(ohlcv)
                    # Keep last 500 candles
                    if len(klines) > 500:
                        klines.pop(0)
            
            # Fire callback
            if self.on_kline:
                self.on_kline(symbol, ohlcv)
    
    async def _handle_ticker(self, topic: str, data: Any) -> None:
        """Handle ticker data."""
        # topic format: tickers.{symbol}
        parts = topic.split(".")
        if len(parts) < 2:
            return
        
        symbol = parts[1]
        
        # Data can be a dict or list
        if isinstance(data, list):
            ticker_data = data[0] if data else {}
        else:
            ticker_data = data
        
        ticker = Ticker(
            symbol=symbol,
            last_price=safe_float(ticker_data.get("lastPrice"), 0),
            mark_price=safe_float(ticker_data.get("markPrice"), 0),
            index_price=safe_float(ticker_data.get("indexPrice"), 0),
            funding_rate=safe_float(ticker_data.get("fundingRate"), 0),
            next_funding_time=safe_int(ticker_data.get("nextFundingTime"), 0),
            open_interest=safe_float(ticker_data.get("openInterest"), 0),
            volume_24h=safe_float(ticker_data.get("volume24h"), 0),
            turnover_24h=safe_float(ticker_data.get("turnover24h"), 0),
            high_24h=safe_float(ticker_data.get("highPrice24h"), 0),
            low_24h=safe_float(ticker_data.get("lowPrice24h"), 0),
        )
        
        self.tickers[symbol] = ticker
        
        if self.on_ticker:
            self.on_ticker(ticker)
    
    async def run_forever(self) -> None:
        """Run the WebSocket client forever with auto-reconnect."""
        self._running = True
        
        while self._running:
            try:
                if not self._is_connected():
                    await self.connect()
                
                # Listen for messages
                async for message in self._ws:
                    if not self._running:
                        break
                    await self._handle_message(message)
                
                # If we exit the loop normally, connection was lost
                self._connected = False
                    
            except ConnectionClosed as e:
                self._connected = False
                logger.warning(f"WebSocket connection closed: {e}")
                if self.on_disconnect:
                    self.on_disconnect()
                
                if self._running:
                    logger.info(f"Reconnecting in {self.reconnect_delay}s...")
                    await asyncio.sleep(self.reconnect_delay)
                    
            except Exception as e:
                self._connected = False
                logger.warning(f"WebSocket reconnecting: {type(e).__name__}")
                if self._running:
                    await asyncio.sleep(self.reconnect_delay)
    
    async def close(self) -> None:
        """Close the WebSocket connection."""
        self._running = False
        self._connected = False
        if self._ws:
            await self._ws.close()
            logger.info("WebSocket connection closed")
    
    def get_closes(self, symbol: str, count: int = 100) -> List[float]:
        """Get last N close prices for a symbol."""
        klines = self.klines.get(symbol, [])
        return [k.close for k in klines[-count:]]
    
    def get_highs(self, symbol: str, count: int = 100) -> List[float]:
        """Get last N high prices for a symbol."""
        klines = self.klines.get(symbol, [])
        return [k.high for k in klines[-count:]]
    
    def get_lows(self, symbol: str, count: int = 100) -> List[float]:
        """Get last N low prices for a symbol."""
        klines = self.klines.get(symbol, [])
        return [k.low for k in klines[-count:]]
    
    async def __aenter__(self) -> "BybitWebSocket":
        await self.connect()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()
