"""
Trade Executor
==============

Handles order execution via Mudrex API with rate limiting and error handling.
Enhanced from free-weight-strategy with dynamic position sizing.
"""

import logging
import math
from decimal import Decimal, ROUND_DOWN, ROUND_HALF_UP
from typing import Optional, Tuple, Dict
from dataclasses import dataclass

from src.config import Config
from src.strategy.signals import Signal

logger = logging.getLogger(__name__)


@dataclass
class TradeResult:
    """Result of a trade execution attempt."""
    success: bool = False
    order_id: Optional[str] = None
    symbol: Optional[str] = None
    side: Optional[str] = None
    quantity: Optional[str] = None
    leverage: Optional[int] = None
    margin_used: Optional[float] = None
    position_value: Optional[float] = None
    entry_price: Optional[float] = None
    stoploss_price: Optional[float] = None
    takeprofit_price: Optional[float] = None
    error: Optional[str] = None


class TradeExecutor:
    """
    Execute trades via Mudrex Futures API.

    Features:
    - Dry-run mode for testing
    - Rate limit awareness
    - Auto-leverage scaling to meet min order value
    - Dynamic position sizing using ATR-based risk
    - Adaptive sizing (reduce after losses)
    - Retry-without-SL/TP fallback
    - Asset info caching for precision

    Example:
        executor = TradeExecutor(config)
        result = executor.execute(signal)
    """

    def __init__(self, config: Config):
        self.config = config
        self._client = None
        self._balance_cache: Optional[float] = None
        self._asset_cache: Dict[str, dict] = {}

        if not config.dry_run:
            self._init_client()

    def _init_client(self) -> None:
        """Initialize Mudrex client."""
        try:
            from mudrex import MudrexClient
            self._client = MudrexClient(api_secret=self.config.mudrex_api_secret)
            logger.info("Mudrex client initialized")
        except ImportError:
            logger.error(
                "Mudrex SDK not installed. Install with: "
                "pip install git+https://github.com/DecentralizedJM/mudrex-api-trading-python-sdk.git"
            )
            raise
        except Exception as e:
            logger.error(f"Failed to initialize Mudrex client: {e}")
            raise

    def _get_asset_info(self, symbol: str) -> Optional[dict]:
        """Get asset specifications with caching."""
        if symbol in self._asset_cache:
            return self._asset_cache[symbol]

        if not self._client:
            return None

        try:
            asset = self._client.assets.get(symbol)
            info = {
                "min_quantity": Decimal(str(asset.min_quantity)),
                "quantity_step": Decimal(str(asset.quantity_step)),
                "price_step": Decimal(str(asset.price_step)),
                "min_leverage": int(getattr(asset, 'min_leverage', 1)),
                "max_leverage": int(getattr(asset, 'max_leverage', 50)),
            }
            self._asset_cache[symbol] = info
            return info
        except Exception as e:
            logger.debug(f"Could not fetch asset info for {symbol}: {e}")
            return None

    def execute(self, signal: Signal, sizing_multiplier: float = 1.0) -> TradeResult:
        """
        Execute a trade based on signal.

        Args:
            signal: Trading signal with entry, SL, TP
            sizing_multiplier: Position size multiplier (from risk manager)

        Returns:
            TradeResult with execution details
        """
        if not signal.is_actionable:
            return TradeResult(success=False, error="Signal is not actionable")

        if self.config.dry_run:
            return self._dry_run_execute(signal, sizing_multiplier)

        return self._live_execute(signal, sizing_multiplier)

    def _calculate_position(
        self, signal: Signal, balance: float, sizing_multiplier: float = 1.0
    ) -> Tuple[float, int, float, float]:
        """
        Calculate position size with auto-leverage scaling.

        Returns:
            Tuple of (quantity, leverage, margin_used, position_value)
        """
        risk_cfg = self.config.risk

        # Calculate margin amount (% of balance) * sizing multiplier
        margin_amount = balance * (risk_cfg.margin_percent / 100) * sizing_multiplier

        # Start with default leverage, clamped to configured range
        leverage = max(risk_cfg.min_leverage, risk_cfg.default_leverage)

        # Calculate position value = margin × leverage
        position_value = margin_amount * leverage

        # Auto-scale leverage UP if position value doesn't meet min order ($8)
        min_order = risk_cfg.min_order_value

        if position_value < min_order:
            required_leverage = math.ceil(min_order / margin_amount)
            # Clamp to [min_leverage, max_leverage]
            required_leverage = max(risk_cfg.min_leverage, required_leverage)

            if required_leverage <= risk_cfg.max_leverage:
                leverage = required_leverage
                position_value = margin_amount * leverage
                logger.info(f"Auto-scaled leverage to {leverage}x to meet min order ${min_order}")
            else:
                leverage = risk_cfg.max_leverage
                position_value = margin_amount * leverage
                logger.warning(
                    f"Cannot meet min order ${min_order} even with max leverage "
                    f"{risk_cfg.max_leverage}x. Position value: ${position_value:.2f}"
                )

        # Calculate quantity
        if not signal.entry_price or signal.entry_price <= 0:
            logger.warning(f"Invalid entry price {signal.entry_price} for {signal.symbol}, skipping")
            return 0, leverage, margin_amount, position_value
        quantity = position_value / signal.entry_price

        return quantity, leverage, margin_amount, position_value

    def _format_quantity(self, quantity: float, symbol: str) -> str:
        """Format quantity with appropriate precision using Decimal."""
        asset_info = self._get_asset_info(symbol)

        if asset_info:
            qty_step = asset_info["quantity_step"]
            min_qty = asset_info["min_quantity"]
            qty = Decimal(str(quantity))
            qty = (qty / qty_step).quantize(Decimal("1"), rounding=ROUND_DOWN) * qty_step
            qty = max(min_qty, qty)
            return f"{qty:f}".rstrip('0').rstrip('.')

        # Fallback formatting
        if "BTC" in symbol:
            return f"{quantity:.5f}"
        elif "ETH" in symbol:
            return f"{quantity:.4f}"
        else:
            return f"{quantity:.2f}"

    def _format_price(self, price: float, symbol: str) -> Optional[str]:
        """Format price to match asset's price_step using Decimal."""
        if price is None or price <= 0:
            return None

        asset_info = self._get_asset_info(symbol)

        if asset_info:
            price_step = asset_info["price_step"]
            if price_step > 0:
                p = Decimal(str(price))
                p = (p / price_step).quantize(Decimal("1"), rounding=ROUND_HALF_UP) * price_step
                return f"{p:f}".rstrip('0').rstrip('.')

        return str(round(price, 8))

    def _dry_run_execute(self, signal: Signal, sizing_multiplier: float = 1.0) -> TradeResult:
        """Simulate trade execution."""
        balance = 1000.0

        quantity, leverage, margin_used, position_value = self._calculate_position(
            signal, balance, sizing_multiplier
        )

        quantity_str = self._format_quantity(quantity, signal.symbol)

        logger.info(
            f"[DRY-RUN] {signal.side} {quantity_str} {signal.symbol} | "
            f"Leverage: {leverage}x | Margin: ${margin_used:.2f} | "
            f"Position: ${position_value:.2f} | "
            f"Entry: {signal.entry_price:.4f} | SL: {signal.stoploss_price:.4f} | "
            f"TP: {signal.takeprofit_price:.4f}"
        )
        if signal.tp1_price:
            logger.info(f"[DRY-RUN] TP1: {signal.tp1_price:.4f} | TP2: {signal.tp2_price:.4f}")

        return TradeResult(
            success=True,
            order_id="DRY_RUN_" + signal.symbol,
            symbol=signal.symbol,
            side=signal.side,
            quantity=quantity_str,
            leverage=leverage,
            margin_used=margin_used,
            position_value=position_value,
            entry_price=signal.entry_price,
            stoploss_price=signal.stoploss_price,
            takeprofit_price=signal.takeprofit_price,
        )

    def _live_execute(self, signal: Signal, sizing_multiplier: float = 1.0) -> TradeResult:
        """Execute live trade via Mudrex API with automatic retry."""
        if not self._client:
            return TradeResult(success=False, error="Mudrex client not initialized")

        try:
            balance = self.get_balance()
            if balance is None or balance <= 0:
                return TradeResult(success=False, error="Could not get balance or balance is zero")

            quantity, leverage, margin_used, position_value = self._calculate_position(
                signal, balance, sizing_multiplier
            )

            if quantity <= 0:
                logger.info(f"⏭️ {signal.symbol}: waiting for price data")
                return TradeResult(success=False, symbol=signal.symbol, error="Waiting for price data")

            min_order = self.config.risk.min_order_value
            if position_value < min_order:
                logger.info(f"⏭️ {signal.symbol}: position ${position_value:.2f} below min ${min_order}")
                return TradeResult(
                    success=False,
                    error=f"Position too small (${position_value:.2f} < ${min_order})"
                )

            quantity_str = self._format_quantity(quantity, signal.symbol)
            sl_price_str = self._format_price(signal.stoploss_price, signal.symbol) if signal.stoploss_price else None
            tp_price_str = self._format_price(signal.takeprofit_price, signal.symbol) if signal.takeprofit_price else None

            # Set leverage
            try:
                self._client.leverage.set(
                    symbol=signal.symbol,
                    leverage=str(leverage),
                    margin_type="ISOLATED"
                )
            except Exception as e:
                logger.info(f"⏭️ {signal.symbol}: leverage not supported, skipping")
                return TradeResult(success=False, symbol=signal.symbol, error="Leverage not supported")

            # Attempt 1: with SL/TP
            try:
                order = self._client.orders.create_market_order(
                    symbol=signal.symbol,
                    side=signal.side,
                    quantity=quantity_str,
                    leverage=str(leverage),
                    stoploss_price=sl_price_str,
                    takeprofit_price=tp_price_str,
                )
            except Exception as e:
                error_msg = str(e).lower()
                if "price" in error_msg or "param" in error_msg or "step" in error_msg:
                    logger.info(f"🔄 {signal.symbol}: retrying without SL/TP")
                    try:
                        order = self._client.orders.create_market_order(
                            symbol=signal.symbol,
                            side=signal.side,
                            quantity=quantity_str,
                            leverage=str(leverage),
                        )
                    except Exception:
                        logger.info(f"⏭️ {signal.symbol}: order params incompatible, skipping")
                        return TradeResult(
                            success=False, symbol=signal.symbol, side=signal.side,
                            error=f"Order params incompatible for {signal.symbol}"
                        )
                else:
                    logger.info(f"⏭️ {signal.symbol}: order not accepted, skipping")
                    return TradeResult(
                        success=False, symbol=signal.symbol, side=signal.side,
                        error=f"Order not accepted for {signal.symbol}"
                    )

            logger.info(
                f"✅ Order executed: {signal.side} {quantity_str} {signal.symbol} | "
                f"Leverage: {leverage}x | Margin: ${margin_used:.2f} | "
                f"Position: ${position_value:.2f} | Order ID: {order.order_id}"
            )

            return TradeResult(
                success=True,
                order_id=order.order_id,
                symbol=signal.symbol,
                side=signal.side,
                quantity=quantity_str,
                leverage=leverage,
                margin_used=margin_used,
                position_value=position_value,
                entry_price=signal.entry_price,
                stoploss_price=signal.stoploss_price,
                takeprofit_price=signal.takeprofit_price,
            )

        except Exception as e:
            logger.info(f"⏭️ {signal.symbol}: skipped ({type(e).__name__})")
            return TradeResult(success=False, symbol=signal.symbol, side=signal.side, error=str(e))

    def close_position(self, symbol: str, side: str) -> bool:
        """Close a position."""
        if self.config.dry_run:
            logger.info(f"[DRY-RUN] Close {side} {symbol}")
            return True

        if not self._client:
            return False

        try:
            close_side = "SHORT" if side == "LONG" else "LONG"
            positions = self._client.positions.get_open()
            for pos in positions:
                if pos.symbol == symbol:
                    self._client.orders.create_market_order(
                        symbol=symbol,
                        side=close_side,
                        quantity=str(pos.quantity),
                    )
                    logger.info(f"✅ Closed {side} {symbol}")
                    return True
            return False
        except Exception as e:
            logger.error(f"Failed to close {symbol}: {e}")
            return False

    def close_partial(self, symbol: str, side: str, pct: float) -> bool:
        """Close a percentage of a position."""
        if self.config.dry_run:
            logger.info(f"[DRY-RUN] Close {pct:.0%} of {side} {symbol}")
            return True

        if not self._client:
            return False

        try:
            close_side = "SHORT" if side == "LONG" else "LONG"
            positions = self._client.positions.get_open()
            for pos in positions:
                if pos.symbol == symbol:
                    close_qty = float(pos.quantity) * pct
                    qty_str = self._format_quantity(close_qty, symbol)
                    self._client.orders.create_market_order(
                        symbol=symbol,
                        side=close_side,
                        quantity=qty_str,
                    )
                    logger.info(f"✅ Closed {pct:.0%} of {side} {symbol} ({qty_str})")
                    return True
            return False
        except Exception as e:
            logger.error(f"Failed to partial close {symbol}: {e}")
            return False

    def set_stoploss(self, symbol: str, price: float) -> bool:
        """Update stop-loss for an open position."""
        if self.config.dry_run:
            logger.info(f"[DRY-RUN] Set SL {symbol} → {price:.4f}")
            return True

        if not self._client:
            return False

        try:
            price_str = self._format_price(price, symbol)
            self._client.positions.set_stoploss(symbol=symbol, price=price_str)
            logger.debug(f"SL updated: {symbol} → {price_str}")
            return True
        except Exception as e:
            logger.debug(f"Could not update SL for {symbol}: {e}")
            return False

    def get_balance(self) -> Optional[float]:
        """Get current futures balance."""
        if self.config.dry_run:
            return 1000.0

        try:
            balance = self._client.wallet.get_futures_balance()
            self._balance_cache = float(balance.balance)
            return self._balance_cache
        except Exception as e:
            logger.error(f"Failed to get balance: {e}")
            return self._balance_cache

    def get_open_positions(self) -> list:
        """Get currently open positions."""
        if self.config.dry_run:
            return []

        if not self._client:
            return []

        try:
            return self._client.positions.get_open()
        except Exception as e:
            logger.error(f"Failed to get positions: {e}")
            return []

    def close(self) -> None:
        if self._client:
            self._client.close()
