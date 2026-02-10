"""
Telegram Alerter
================

Sends trade signals, execution alerts, position management events,
and daily summary reports to Telegram.
"""

import logging
import time
from datetime import datetime, timezone
from typing import Optional, List, Dict
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class DailyStats:
    """Tracks daily P&L and trade stats for the daily summary."""
    trades_opened: int = 0
    trades_closed: int = 0
    wins: int = 0
    losses: int = 0
    partial_tps: int = 0
    breakevens: int = 0
    trailing_stops_triggered: int = 0
    reversal_exits: int = 0
    symbols_traded: List[str] = field(default_factory=list)
    last_reset: float = field(default_factory=time.time)

    def reset(self) -> None:
        self.trades_opened = 0
        self.trades_closed = 0
        self.wins = 0
        self.losses = 0
        self.partial_tps = 0
        self.breakevens = 0
        self.trailing_stops_triggered = 0
        self.reversal_exits = 0
        self.symbols_traded = []
        self.last_reset = time.time()


class TelegramAlerter:
    """
    Sends alerts to Telegram for all trade lifecycle events.

    Events:
    - Bot startup / shutdown
    - Signal detected
    - Trade opened / failed
    - Partial take-profit hit
    - Trailing stop updated
    - Breakeven activated
    - Position closed (SL / TP / reversal)
    - Daily summary report (24h)

    Usage:
        alerter = TelegramAlerter(bot_token, chat_ids)
        await alerter.send_trade_opened(...)
        await alerter.send_daily_summary(...)
    """

    API_URL = "https://api.telegram.org/bot{token}/sendMessage"

    def __init__(self, bot_token: str, chat_ids: List[str]):
        self.bot_token = bot_token
        self.chat_ids = chat_ids
        self.daily = DailyStats()

    async def send_message(self, text: str, parse_mode: str = "HTML") -> bool:
        """Send a message to all configured Telegram chats."""
        if not self.bot_token or not self.chat_ids:
            return False

        import aiohttp

        try:
            async with aiohttp.ClientSession() as session:
                url = self.API_URL.format(token=self.bot_token)
                ok = 0

                for chat_id in self.chat_ids:
                    payload = {
                        "chat_id": chat_id,
                        "text": text,
                        "parse_mode": parse_mode,
                        "disable_web_page_preview": True,
                    }
                    try:
                        async with session.post(url, json=payload) as resp:
                            if resp.status == 200:
                                ok += 1
                            else:
                                err = await resp.text()
                                logger.debug(f"TG send failed ({chat_id}): {resp.status} {err}")
                    except Exception as e:
                        logger.debug(f"TG send error ({chat_id}): {e}")

                return ok > 0
        except Exception as e:
            logger.debug(f"TG alert error: {e}")
            return False

    # ─── Bot Lifecycle ────────────────────────────────────────────

    async def send_startup(
        self,
        mode: str,
        num_symbols: int,
        margin_pct: float,
        leverage_range: str,
        balance: Optional[float] = None,
    ) -> bool:
        text = f"""
🚀 <b>Ultimate Trend Strategy Started</b>

🔧 <b>Mode:</b> {mode}
📊 <b>Symbols:</b> {num_symbols} pairs
💰 <b>Margin:</b> {margin_pct}% of wallet
⚡ <b>Leverage:</b> {leverage_range}
{f"💵 <b>Balance:</b> ${balance:.2f}" if balance else ""}
⏰ <b>Time:</b> {datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")}
""".strip()
        return await self.send_message(text)

    async def send_shutdown(self, stats: Optional[Dict] = None) -> bool:
        extra = ""
        if stats:
            extra = f"""
📊 <b>Session:</b> {stats.get('total_trades', 0)} trades | WR: {stats.get('win_rate', 'N/A')}"""

        text = f"""
⏹️ <b>Ultimate Trend Strategy Stopped</b>
{extra}
⏰ {datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")}
""".strip()
        return await self.send_message(text)

    # ─── Signal & Trade Events ────────────────────────────────────

    async def send_signal(
        self,
        symbol: str,
        side: str,
        entry_price: float,
        stoploss_price: float,
        takeprofit_price: float,
        reason: str = "",
    ) -> bool:
        emoji = "🟢" if side == "LONG" else "🔴"
        text = f"""
{emoji} <b>SIGNAL: {side} {symbol}</b>

💰 <b>Entry:</b> ${entry_price:,.4f}
🛑 <b>SL:</b> ${stoploss_price:,.4f}
🎯 <b>TP:</b> ${takeprofit_price:,.4f}
{f"📝 {reason}" if reason else ""}
""".strip()
        return await self.send_message(text)

    async def send_trade_opened(
        self,
        symbol: str,
        side: str,
        quantity: str,
        leverage: int,
        margin_used: float,
        position_value: float,
        entry_price: float,
        stoploss_price: float,
        takeprofit_price: float,
        order_id: str,
        tp1_price: Optional[float] = None,
        tp2_price: Optional[float] = None,
    ) -> bool:
        self.daily.trades_opened += 1
        if symbol not in self.daily.symbols_traded:
            self.daily.symbols_traded.append(symbol)

        side_emoji = "🟢" if side == "LONG" else "🔴"
        tp_lines = ""
        if tp1_price:
            tp_lines += f"\n🎯 <b>TP1 (50%):</b> ${tp1_price:,.4f}"
        if tp2_price:
            tp_lines += f"\n🎯 <b>TP2 (25%):</b> ${tp2_price:,.4f}"

        text = f"""
✅ <b>TRADE OPENED</b>

{side_emoji} <b>{side} {symbol}</b>
📦 <b>Qty:</b> {quantity}
⚡ <b>Leverage:</b> {leverage}x
💵 <b>Margin:</b> ${margin_used:.2f}
📊 <b>Position:</b> ${position_value:.2f}

💰 <b>Entry:</b> ${entry_price:,.4f}
🛑 <b>SL:</b> ${stoploss_price:,.4f}
🎯 <b>TP:</b> ${takeprofit_price:,.4f}{tp_lines}

🆔 <code>{order_id}</code>
""".strip()
        return await self.send_message(text)

    async def send_trade_failed(self, symbol: str, side: str, error: str) -> bool:
        text = f"""
❌ <b>TRADE SKIPPED</b>

📉 <b>{side} {symbol}</b>
⚠️ {error}
""".strip()
        return await self.send_message(text)

    # ─── Position Management Events ───────────────────────────────

    async def send_position_closed(
        self,
        symbol: str,
        side: str,
        reason: str = "Stop-Loss",
    ) -> bool:
        self.daily.trades_closed += 1

        text = f"""
🔒 <b>POSITION CLOSED</b>

📉 <b>{side} {symbol}</b>
📝 <b>Reason:</b> {reason}
⏰ {datetime.now(timezone.utc).strftime("%H:%M UTC")}
""".strip()
        return await self.send_message(text)

    async def send_partial_tp(
        self,
        symbol: str,
        side: str,
        tp_level: int,
        pct_closed: float,
        current_price: float,
    ) -> bool:
        self.daily.partial_tps += 1
        text = f"""
💰 <b>PARTIAL TP{tp_level} HIT</b>

📊 <b>{side} {symbol}</b>
📦 <b>Closed:</b> {pct_closed:.0%}
💵 <b>Price:</b> ${current_price:,.4f}
""".strip()
        return await self.send_message(text)

    async def send_trailing_stop_update(
        self,
        symbol: str,
        side: str,
        new_sl: float,
        current_price: float,
    ) -> bool:
        self.daily.trailing_stops_triggered += 1
        text = f"""
📈 <b>TRAILING STOP ↑</b>

📊 <b>{side} {symbol}</b>
🛑 <b>New SL:</b> ${new_sl:,.4f}
💵 <b>Price:</b> ${current_price:,.4f}
""".strip()
        return await self.send_message(text)

    async def send_breakeven_activated(
        self,
        symbol: str,
        side: str,
        entry_price: float,
    ) -> bool:
        self.daily.breakevens += 1
        text = f"""
🔄 <b>BREAKEVEN SET</b>

📊 <b>{side} {symbol}</b>
🛑 <b>SL → Entry:</b> ${entry_price:,.4f}
""".strip()
        return await self.send_message(text)

    async def send_reversal_exit(
        self,
        symbol: str,
        side: str,
        reversal_signal: str,
    ) -> bool:
        self.daily.reversal_exits += 1
        text = f"""
🔀 <b>REVERSAL EXIT</b>

📊 <b>{side} {symbol}</b> closed
📝 Counter-signal: {reversal_signal}
""".strip()
        return await self.send_message(text)

    # ─── Daily Summary ────────────────────────────────────────────

    async def send_daily_summary(
        self,
        balance: Optional[float] = None,
        active_positions: Optional[List[str]] = None,
        risk_stats: Optional[Dict] = None,
    ) -> bool:
        d = self.daily
        total = d.wins + d.losses
        wr = f"{d.wins/total:.0%}" if total > 0 else "N/A"

        pos_text = ", ".join(active_positions) if active_positions else "None"
        balance_text = f"${balance:.2f}" if balance else "N/A"

        streak = ""
        if risk_stats:
            streak = f"\n📉 <b>Streak:</b> {risk_stats.get('consecutive_losses', 0)} losses | Sizing: {risk_stats.get('sizing_multiplier', 1.0)}x"

        text = f"""
📋 <b>DAILY SUMMARY</b>
{'━' * 24}

📊 <b>Trades Opened:</b> {d.trades_opened}
🔒 <b>Trades Closed:</b> {d.trades_closed}
✅ <b>Wins:</b> {d.wins}  |  ❌ <b>Losses:</b> {d.losses}
🎯 <b>Win Rate:</b> {wr}
{'━' * 24}
💰 <b>Partial TPs:</b> {d.partial_tps}
🔄 <b>Breakevens:</b> {d.breakevens}
📈 <b>Trailing Stops:</b> {d.trailing_stops_triggered}
🔀 <b>Reversal Exits:</b> {d.reversal_exits}
{'━' * 24}
💵 <b>Balance:</b> {balance_text}
📈 <b>Active:</b> {pos_text}
🏷️ <b>Symbols Traded:</b> {len(d.symbols_traded)}{streak}
⏰ {datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")}
""".strip()

        result = await self.send_message(text)

        # Reset daily stats after sending
        self.daily.reset()

        return result

    def record_win(self) -> None:
        self.daily.wins += 1

    def record_loss(self) -> None:
        self.daily.losses += 1
