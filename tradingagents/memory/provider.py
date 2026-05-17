from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class MemoryEntry:
    """Normalized representation of a memory log entry."""
    date: str
    ticker: str
    rating: str
    decision: str
    reflection: str = ""
    pending: bool = True
    raw_return: Optional[float] = None
    alpha_return: Optional[float] = None
    holding_days: Optional[int] = None
    effectiveness_score: Optional[float] = None
    metadata: dict = field(default_factory=dict)


class MemoryProvider(ABC):
    """Abstract interface for memory storage and retrieval.

    Implementations may use files, databases, vector stores, or hybrid
    backends. The default FileMemoryProvider wraps the existing
    append-only markdown log.
    """

    @abstractmethod
    def store_decision(
        self,
        ticker: str,
        trade_date: str,
        final_trade_decision: str,
    ) -> None:
        """Append a pending decision entry."""

    @abstractmethod
    def load_entries(self) -> List[MemoryEntry]:
        """Return all entries (pending and resolved)."""

    @abstractmethod
    def get_pending_entries(self) -> List[MemoryEntry]:
        """Return entries with outcome:pending."""

    @abstractmethod
    def get_past_context(self, ticker: str, n_same: int = 5, n_cross: int = 3) -> str:
        """Return formatted past context string for agent prompt injection."""

    @abstractmethod
    def update_with_outcome(
        self,
        ticker: str,
        trade_date: str,
        raw_return: float,
        alpha_return: float,
        holding_days: int,
        reflection: str,
    ) -> None:
        """Resolve a pending entry with outcome data and reflection."""

    @abstractmethod
    def batch_update_with_outcomes(self, updates: List[dict]) -> None:
        """Apply multiple outcome updates in a single atomic write."""

    @abstractmethod
    def close(self) -> None:
        """Release resources (no-op for file-based providers)."""
