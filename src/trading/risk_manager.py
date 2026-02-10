"""
Risk Manager
=============

Tracks win/loss streaks and provides adaptive position sizing.
Mirrors PineScript consecutive win/loss tracking and positionSizeMultiplier.
"""

import logging
from dataclasses import dataclass

from src.config import Config

logger = logging.getLogger(__name__)


@dataclass
class RiskManager:
    """
    Adaptive risk manager.

    Tracks consecutive wins/losses and adjusts position sizing:
    - Normal: 1.0x
    - After max_losses: 0.75x
    - After max_losses+1: 0.5x
    """

    def __init__(self, config: Config):
        self.config = config
        self._consecutive_wins: int = 0
        self._consecutive_losses: int = 0
        self._total_trades: int = 0
        self._total_wins: int = 0
        self._total_losses: int = 0

    def record_win(self) -> None:
        self._consecutive_wins += 1
        self._consecutive_losses = 0
        self._total_trades += 1
        self._total_wins += 1
        logger.info(f"📊 Win streak: {self._consecutive_wins} | Total: {self._total_wins}W / {self._total_losses}L")

    def record_loss(self) -> None:
        self._consecutive_losses += 1
        self._consecutive_wins = 0
        self._total_trades += 1
        self._total_losses += 1
        logger.info(f"📊 Loss streak: {self._consecutive_losses} | Total: {self._total_wins}W / {self._total_losses}L")

    def get_sizing_multiplier(self) -> float:
        """
        Get position sizing multiplier based on consecutive losses.
        Mirrors PineScript positionSizeMultiplier logic.
        """
        if not self.config.sizing.use_adaptive_sizing:
            return 1.0

        max_losses = self.config.sizing.max_consecutive_losses

        if self._consecutive_losses >= max_losses + 1:
            return 0.5
        elif self._consecutive_losses >= max_losses:
            return 0.75
        else:
            return 1.0

    @property
    def consecutive_wins(self) -> int:
        return self._consecutive_wins

    @property
    def consecutive_losses(self) -> int:
        return self._consecutive_losses

    @property
    def win_rate(self) -> float:
        if self._total_trades == 0:
            return 0.0
        return self._total_wins / self._total_trades * 100

    def get_stats(self) -> dict:
        return {
            "total_trades": self._total_trades,
            "wins": self._total_wins,
            "losses": self._total_losses,
            "win_rate": f"{self.win_rate:.1f}%",
            "consecutive_wins": self._consecutive_wins,
            "consecutive_losses": self._consecutive_losses,
            "sizing_multiplier": self.get_sizing_multiplier(),
        }
