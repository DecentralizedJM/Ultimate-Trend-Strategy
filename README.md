# Ultimate Trend Strategy Bot

**PineScript → Python conversion** of the "Ultimate Trend Strategy" with high win-rate + news filter.

Runs on **Mudrex API** for order execution and **Bybit WebSocket** for real-time market data.

## Features

- 📈 **13+ Indicators**: EMA (4-layer), RSI (with divergence), MACD, ADX, Supertrend, Bollinger Bands, Choppiness, Volume, ATR
- 🔄 **Multi-timeframe** confirmation
- 📰 **News filter** — configurable event blackout
- 🎯 **Support/Resistance** proximity filter
- 🕯️ **Candlestick patterns** — engulfing, hammer, shooting star, doji star
- 🛡️ **Full risk management** — ATR-based SL/TP, trailing stop, breakeven, partial profits
- 📊 **Adaptive sizing** — reduces position after consecutive losses
- ☁️ **Railway-ready** — Dockerfile + railway.toml included

## Quick Start

```bash
# Clone
git clone <repo-url> && cd ultimate-trend-strategy

# Install
pip install -r requirements.txt

# Configure
cp config.example.yaml config.yaml
# Edit config.yaml with your settings

# Dry run
DRY_RUN=true SYMBOLS=BTCUSDT python -m src.main

# Live (set MUDREX_API_SECRET)
MUDREX_API_SECRET=your_secret python -m src.main
```

## Environment Variables

| Variable | Description | Default |
|---|---|---|
| `MUDREX_API_SECRET` | Mudrex API secret (required for live) | — |
| `DRY_RUN` | Simulate trades | `false` |
| `SYMBOLS` | Comma-separated symbols | `BTCUSDT` |
| `TIMEFRAME` | Candle timeframe (minutes) | `5` |
| `MARGIN_PERCENT` | % of balance per trade | `5.0` |
| `DEFAULT_LEVERAGE` | Default leverage | `5` |
| `STOPLOSS_ATR` | SL multiplier | `1.5` |
| `TAKEPROFIT_ATR` | TP multiplier | `3.0` |
| `LOG_LEVEL` | Logging level | `INFO` |

## Testing

```bash
python -m pytest tests/ -v
```
