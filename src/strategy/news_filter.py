"""
News Filter
============

Time-based news event blackout to avoid trading during high-impact events.
Mirrors PineScript isNewsTime() function.
"""

from datetime import datetime, timezone
from typing import List, Optional
from dataclasses import dataclass, field


@dataclass
class NewsEvent:
    """A scheduled news event."""
    name: str
    month: int
    day: int
    hour: int  # UTC
    minute: int

    def matches_date(self, dt: datetime) -> bool:
        return dt.month == self.month and dt.day == self.day


@dataclass
class NewsFilter:
    """
    Checks if current time falls within a news blackout window.

    buffer_before: minutes before the event to start blocking
    buffer_after: minutes after the event to keep blocking
    events: list of NewsEvent instances
    """

    enabled: bool = True
    buffer_before: int = 30
    buffer_after: int = 30
    events: List[NewsEvent] = field(default_factory=list)

    def is_blackout(self, current_utc: Optional[datetime] = None) -> bool:
        """Check if current time is within any news blackout window."""
        if not self.enabled or not self.events:
            return False

        if current_utc is None:
            current_utc = datetime.now(timezone.utc)

        current_month = current_utc.month
        current_day = current_utc.day
        current_total_minutes = current_utc.hour * 60 + current_utc.minute

        for event in self.events:
            if event.month == current_month and event.day == current_day:
                event_total_minutes = event.hour * 60 + event.minute
                start_minutes = event_total_minutes - self.buffer_before
                end_minutes = event_total_minutes + self.buffer_after

                if start_minutes <= current_total_minutes <= end_minutes:
                    return True

        return False

    def add_event(self, name: str, month: int, day: int, hour: int, minute: int) -> None:
        self.events.append(NewsEvent(name=name, month=month, day=day, hour=hour, minute=minute))
