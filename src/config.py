"""
Configuration Module
====================

All configurable parameters matching PineScript inputs.
Loads from YAML and overrides from environment variables.
Optimized for Railway deployment.
"""

import os
import logging
from pathlib import Path
from typing import List, Optional
from dataclasses import dataclass, field
import yaml
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


# ============================================================================
# INDICATOR CONFIGS
# ============================================================================

@dataclass
class TrendConfig:
    """📈 Trend Detection"""
    ema_fast: int = 9
    ema_slow: int = 21
    ema_filter: int = 50
    ema_200: int = 200
    adx_period: int = 14
    adx_threshold: int = 25
    use_ema200_filter: bool = True


@dataclass
class SupertrendConfig:
    """⚡ Supertrend"""
    enabled: bool = True
    atr_period: int = 10
    multiplier: float = 3.0


@dataclass
class BollingerConfig:
    """📊 Bollinger Bands"""
    enabled: bool = True
    period: int = 20
    std_dev: float = 2.0
    min_width_pct: float = 2.0


@dataclass
class MTFConfig:
    """🔄 Multi-Timeframe"""
    enabled: bool = True
    higher_timeframe: str = "60"
    confirmation_type: str = "EMA"  # "EMA" or "Trend"


@dataclass
class RSIConfig:
    """💪 RSI"""
    enabled: bool = True
    period: int = 14
    overbought: int = 70
    oversold: int = 30
    use_divergence: bool = True
    divergence_lookback: int = 5


@dataclass
class MACDConfig:
    """📉 MACD"""
    enabled: bool = True
    fast_period: int = 12
    slow_period: int = 26
    signal_period: int = 9


@dataclass
class VolumeConfig:
    """📦 Volume"""
    enabled: bool = True
    period: int = 20
    multiplier: float = 1.2
    detect_spike: bool = True
    spike_multiplier: float = 2.0


@dataclass
class MarketConditionsConfig:
    """🌊 Market Conditions"""
    use_choppiness: bool = True
    chop_period: int = 14
    chop_threshold: float = 61.8
    use_sideways: bool = True
    sideways_period: int = 20
    sideways_threshold: float = 1.5


@dataclass
class VolatilityConfig:
    """💨 Volatility"""
    enabled: bool = True
    min_pct: float = 0.5
    max_pct: float = 5.0


@dataclass
class SRConfig:
    """🎯 Support/Resistance"""
    enabled: bool = True
    lookback: int = 50
    tolerance_pct: float = 0.5


# ============================================================================
# RISK & MONEY MANAGEMENT CONFIGS
# ============================================================================

@dataclass
class RiskConfig:
    """🛡️ Risk Management"""
    atr_period: int = 14
    stoploss_atr: float = 1.5
    takeprofit_atr: float = 3.0
    use_trailing_stop: bool = True
    trailing_stop_atr: float = 1.2
    use_breakeven: bool = True
    breakeven_trigger_atr: float = 1.5
    # Margin / leverage
    margin_percent: float = 5.0
    min_leverage: int = 1
    max_leverage: int = 20
    default_leverage: int = 5
    min_order_value: float = 8.0


@dataclass
class ProfitConfig:
    """💰 Profit Management"""
    use_partial_profits: bool = True
    tp1_atr: float = 1.5  # 50% close
    tp2_atr: float = 2.5  # 25% close


@dataclass
class SizingConfig:
    """💵 Position Sizing"""
    risk_per_trade_pct: float = 2.0
    use_dynamic_sizing: bool = True
    use_adaptive_sizing: bool = True
    max_consecutive_losses: int = 2


# ============================================================================
# TIME & NEWS CONFIGS
# ============================================================================

@dataclass
class TimeConfig:
    """⏰ Time Filters"""
    use_date_filter: bool = False
    start_year: int = 2020
    start_month: int = 1
    start_day: int = 1
    use_session_filter: bool = False
    session_start: int = 9
    session_end: int = 16


@dataclass
class NewsEventConfig:
    """Single news event"""
    enabled: bool = False
    name: str = "Custom Event"
    month: int = 1
    day: int = 1
    hour: int = 13
    minute: int = 30


@dataclass
class NewsConfig:
    """📰 News Filter"""
    enabled: bool = True
    buffer_before: int = 30
    buffer_after: int = 30
    events: List[NewsEventConfig] = field(default_factory=list)


# ============================================================================
# STRATEGY CONFIG
# ============================================================================

@dataclass
class StrategyConfig:
    """Strategy settings"""
    trade_cooldown: int = 300  # seconds between signals
    max_positions_per_symbol: int = 1


# ============================================================================
# INFRA CONFIGS
# ============================================================================

@dataclass
class BybitConfig:
    ws_url: str = "wss://stream.bybit.com/v5/public/linear"
    rest_url: str = "https://api.bybit.com"
    ping_interval: int = 20
    reconnect_delay: int = 5


@dataclass
class LoggingConfig:
    level: str = "INFO"
    file: Optional[str] = None


@dataclass
class TelegramConfig:
    bot_token: str = ""
    chat_ids: List[str] = field(default_factory=list)
    enabled: bool = False

    def is_valid(self) -> bool:
        return bool(self.bot_token and self.chat_ids and self.enabled)


# ============================================================================
# MAIN CONFIG
# ============================================================================

@dataclass
class Config:
    """Main configuration container."""

    mudrex_api_secret: str = ""

    # Trading
    symbols: List[str] = field(default_factory=lambda: ["BTCUSDT"])
    timeframe: int = 5

    # Indicator configs
    trend: TrendConfig = field(default_factory=TrendConfig)
    supertrend: SupertrendConfig = field(default_factory=SupertrendConfig)
    bollinger: BollingerConfig = field(default_factory=BollingerConfig)
    mtf: MTFConfig = field(default_factory=MTFConfig)
    rsi: RSIConfig = field(default_factory=RSIConfig)
    macd: MACDConfig = field(default_factory=MACDConfig)
    volume: VolumeConfig = field(default_factory=VolumeConfig)
    market_conditions: MarketConditionsConfig = field(default_factory=MarketConditionsConfig)
    volatility: VolatilityConfig = field(default_factory=VolatilityConfig)
    sr: SRConfig = field(default_factory=SRConfig)

    # Risk/Money
    risk: RiskConfig = field(default_factory=RiskConfig)
    profit: ProfitConfig = field(default_factory=ProfitConfig)
    sizing: SizingConfig = field(default_factory=SizingConfig)

    # Time/News
    time_filter: TimeConfig = field(default_factory=TimeConfig)
    news: NewsConfig = field(default_factory=NewsConfig)

    # Strategy
    strategy: StrategyConfig = field(default_factory=StrategyConfig)

    # Infrastructure
    bybit: BybitConfig = field(default_factory=BybitConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    telegram: TelegramConfig = field(default_factory=TelegramConfig)

    # Runtime
    dry_run: bool = False

    @classmethod
    def load(cls, config_path: str = "config.yaml") -> "Config":
        config = cls()
        if Path(config_path).exists():
            with open(config_path, "r") as f:
                yaml_config = yaml.safe_load(f) or {}
            config = cls._from_dict(yaml_config)
            logger.info(f"Loaded configuration from {config_path}")
        else:
            logger.warning(f"Config file {config_path} not found, using defaults/env vars")
        config._load_from_env()
        return config

    def _load_from_env(self) -> None:
        """Override from environment variables."""
        self.mudrex_api_secret = os.getenv("MUDREX_API_SECRET", self.mudrex_api_secret)
        self.dry_run = os.getenv("DRY_RUN", "false").lower() == "true"

        if symbols := os.getenv("SYMBOLS"):
            self.symbols = [s.strip().upper() for s in symbols.split(",")]
        if tf := os.getenv("TIMEFRAME"):
            self.timeframe = int(tf)

        # Risk
        if v := os.getenv("MARGIN_PERCENT"): self.risk.margin_percent = float(v)
        if v := os.getenv("DEFAULT_LEVERAGE"): self.risk.default_leverage = int(v)
        if v := os.getenv("MIN_LEVERAGE"): self.risk.min_leverage = int(v)
        if v := os.getenv("MAX_LEVERAGE"): self.risk.max_leverage = int(v)
        if v := os.getenv("MIN_ORDER_VALUE"): self.risk.min_order_value = float(v)
        if v := os.getenv("STOPLOSS_ATR"): self.risk.stoploss_atr = float(v)
        if v := os.getenv("TAKEPROFIT_ATR"): self.risk.takeprofit_atr = float(v)

        # Strategy
        if v := os.getenv("TRADE_COOLDOWN"): self.strategy.trade_cooldown = int(v)
        if v := os.getenv("MAX_POSITIONS_PER_SYMBOL"): self.strategy.max_positions_per_symbol = int(v)

        # Logging
        if v := os.getenv("LOG_LEVEL"): self.logging.level = v

        # Telegram
        if v := os.getenv("TELEGRAM_BOT_TOKEN"): self.telegram.bot_token = v
        if v := os.getenv("TELEGRAM_CHAT_ID"):
            self.telegram.chat_ids = [cid.strip() for cid in v.split(",") if cid.strip()]
        if self.telegram.bot_token and self.telegram.chat_ids:
            self.telegram.enabled = os.getenv("TELEGRAM_ENABLED", "true").lower() == "true"

    @classmethod
    def _from_dict(cls, data: dict) -> "Config":
        config = cls()
        config.symbols = data.get("symbols", config.symbols)
        config.timeframe = data.get("timeframe", config.timeframe)

        if d := data.get("trend"): config.trend = TrendConfig(**d)
        if d := data.get("supertrend"): config.supertrend = SupertrendConfig(**d)
        if d := data.get("bollinger"): config.bollinger = BollingerConfig(**d)
        if d := data.get("mtf"): config.mtf = MTFConfig(**d)
        if d := data.get("rsi"): config.rsi = RSIConfig(**d)
        if d := data.get("macd"): config.macd = MACDConfig(**d)
        if d := data.get("volume"): config.volume = VolumeConfig(**d)
        if d := data.get("market_conditions"): config.market_conditions = MarketConditionsConfig(**d)
        if d := data.get("volatility"): config.volatility = VolatilityConfig(**d)
        if d := data.get("sr"): config.sr = SRConfig(**d)
        if d := data.get("risk"): config.risk = RiskConfig(**d)
        if d := data.get("profit"): config.profit = ProfitConfig(**d)
        if d := data.get("sizing"): config.sizing = SizingConfig(**d)
        if d := data.get("time_filter"): config.time_filter = TimeConfig(**d)
        if d := data.get("strategy"): config.strategy = StrategyConfig(**d)
        if d := data.get("bybit"): config.bybit = BybitConfig(**d)
        if d := data.get("logging"): config.logging = LoggingConfig(**d)

        # News events
        if news_data := data.get("news"):
            config.news = NewsConfig(
                enabled=news_data.get("enabled", True),
                buffer_before=news_data.get("buffer_before", 30),
                buffer_after=news_data.get("buffer_after", 30),
            )
            for evt_data in news_data.get("events", []):
                config.news.events.append(NewsEventConfig(**evt_data))

        return config

    def validate(self) -> bool:
        if not self.mudrex_api_secret and not self.dry_run:
            logger.error("MUDREX_API_SECRET is required for live trading")
            return False
        if not self.symbols:
            logger.error("At least one trading symbol is required")
            return False
        if self.risk.margin_percent > 20:
            logger.warning("Margin percent > 20% is very aggressive!")
        return True

    def print_config(self) -> None:
        logger.info("=" * 60)
        logger.info("ULTIMATE TREND STRATEGY CONFIGURATION")
        logger.info("=" * 60)
        logger.info(f"Mode: {'DRY-RUN' if self.dry_run else 'LIVE'}")
        logger.info(f"Symbols: {', '.join(self.symbols)}")
        logger.info(f"Timeframe: {self.timeframe}m")
        logger.info(f"EMA: {self.trend.ema_fast}/{self.trend.ema_slow}/{self.trend.ema_filter}/{self.trend.ema_200}")
        logger.info(f"ADX Threshold: {self.trend.adx_threshold}")
        logger.info(f"Supertrend: {'ON' if self.supertrend.enabled else 'OFF'} (ATR {self.supertrend.atr_period}, x{self.supertrend.multiplier})")
        logger.info(f"Bollinger: {'ON' if self.bollinger.enabled else 'OFF'} ({self.bollinger.period}, {self.bollinger.std_dev}σ)")
        logger.info(f"RSI: {'ON' if self.rsi.enabled else 'OFF'} ({self.rsi.period})")
        logger.info(f"MACD: {'ON' if self.macd.enabled else 'OFF'}")
        logger.info(f"Volume: {'ON' if self.volume.enabled else 'OFF'}")
        logger.info(f"Choppiness: {'ON' if self.market_conditions.use_choppiness else 'OFF'}")
        logger.info(f"News Filter: {'ON' if self.news.enabled else 'OFF'} ({len(self.news.events)} events)")
        logger.info(f"SL: {self.risk.stoploss_atr}x ATR | TP: {self.risk.takeprofit_atr}x ATR")
        logger.info(f"Trailing: {'ON' if self.risk.use_trailing_stop else 'OFF'} | Breakeven: {'ON' if self.risk.use_breakeven else 'OFF'}")
        logger.info(f"Partial TP: {'ON' if self.profit.use_partial_profits else 'OFF'}")
        logger.info(f"Leverage: {self.risk.min_leverage}-{self.risk.max_leverage}x (default: {self.risk.default_leverage}x)")
        logger.info("=" * 60)
