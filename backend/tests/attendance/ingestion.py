"""Abstract ingestion-source contract (design §2.5).

Interface only — no real adapter, mock connector, or fake data source is built in
2A. Manual entry and CSV import do NOT implement this interface (they're direct
paths); this exists so a FUTURE device/vendor adapter has a defined shape to
implement against.

Risk / conscious tradeoff (Option B): designed without a real device to validate
it against, so it may need revision once an actual device/vendor API is known.
This is a deliberate choice, not an oversight. NOT a validated design.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


@dataclass(frozen=True)
class RawAttendanceRow:
    """Minimal fields any ingestion source must provide. Source-agnostic — no computed values."""

    employee_identifier: str
    login: datetime
    logout: datetime
    source_ref: str | None


class AttendanceIngestionSource(Protocol):
    """Abstract ingestion contract. A future device/vendor adapter implements this."""

    def fetch_records(self) -> list[RawAttendanceRow]:
        """Return raw attendance rows from the external source."""
        ...
