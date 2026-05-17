from typing import List, Optional

from tradingagents.memory.provider import MemoryProvider, MemoryEntry
from tradingagents.agents.utils.memory import TradingMemoryLog


class FileMemoryProvider(MemoryProvider):
    """MemoryProvider backed by the existing append-only markdown log.

    Wraps TradingMemoryLog and translates between its dict-based API
    and the normalized MemoryEntry dataclass.
    """

    def __init__(self, config: dict = None):
        self._log = TradingMemoryLog(config or {})

    def store_decision(
        self,
        ticker: str,
        trade_date: str,
        final_trade_decision: str,
    ) -> None:
        self._log.store_decision(ticker, trade_date, final_trade_decision)

    def load_entries(self) -> List[MemoryEntry]:
        raw_entries = self._log.load_entries()
        return [self._to_entry(e) for e in raw_entries]

    def get_pending_entries(self) -> List[MemoryEntry]:
        raw_entries = self._log.get_pending_entries()
        return [self._to_entry(e) for e in raw_entries]

    def get_past_context(self, ticker: str, n_same: int = 5, n_cross: int = 3) -> str:
        return self._log.get_past_context(ticker, n_same=n_same, n_cross=n_cross)

    def update_with_outcome(
        self,
        ticker: str,
        trade_date: str,
        raw_return: float,
        alpha_return: float,
        holding_days: int,
        reflection: str,
    ) -> None:
        self._log.update_with_outcome(
            ticker, trade_date, raw_return, alpha_return, holding_days, reflection,
        )

    def batch_update_with_outcomes(self, updates: List[dict]) -> None:
        self._log.batch_update_with_outcomes(updates)

    def close(self) -> None:
        pass

    @staticmethod
    def _to_entry(d: dict) -> MemoryEntry:
        return MemoryEntry(
            date=d["date"],
            ticker=d["ticker"],
            rating=d["rating"],
            decision=d.get("decision", ""),
            reflection=d.get("reflection", ""),
            pending=d.get("pending", True),
            raw_return=_parse_float(d.get("raw")),
            alpha_return=_parse_float(d.get("alpha")),
            holding_days=_parse_int(d.get("holding")),
        )


def _parse_float(value) -> Optional[float]:
    if value is None or value == "n/a":
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def _parse_int(value) -> Optional[int]:
    if value is None or value == "n/a":
        return None
    try:
        return int(str(value).rstrip("d"))
    except (ValueError, TypeError):
        return None
