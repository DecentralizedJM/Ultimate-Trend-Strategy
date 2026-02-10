"""
Volume Analysis Indicator
==========================

Volume SMA with above-average and spike detection.
Mirrors PineScript volumeMA / volumeAboveAvg / volumeSpike.
"""

from typing import List, Optional
from dataclasses import dataclass


@dataclass
class VolumeIndicator:
    """
    Volume analysis: moving average, above-average filter, spike detection.
    """

    period: int = 20

    def __post_init__(self):
        self._volumes: List[float] = []
        self._volume_ma: Optional[float] = None

    def update(self, volume: float) -> None:
        self._volumes.append(volume)
        self._recalculate()

        if len(self._volumes) > 500:
            self._volumes = self._volumes[-500:]

    def update_batch(self, volumes: List[float]) -> None:
        self._volumes = volumes[-500:]
        self._recalculate()

    def _recalculate(self) -> None:
        if len(self._volumes) < self.period:
            self._volume_ma = None
            return
        self._volume_ma = sum(self._volumes[-self.period:]) / self.period

    @property
    def current_volume(self) -> Optional[float]:
        return self._volumes[-1] if self._volumes else None

    @property
    def ma_value(self) -> Optional[float]:
        return self._volume_ma

    def is_above_average(self, multiplier: float = 1.2) -> bool:
        """volume > volumeMA * multiplier"""
        if self._volume_ma is None or not self._volumes:
            return False
        return self._volumes[-1] > self._volume_ma * multiplier

    def is_spike(self, spike_multiplier: float = 2.0) -> bool:
        """volume > volumeMA * spike_multiplier"""
        if self._volume_ma is None or not self._volumes:
            return False
        return self._volumes[-1] > self._volume_ma * spike_multiplier

    def is_ready(self) -> bool:
        return self._volume_ma is not None
