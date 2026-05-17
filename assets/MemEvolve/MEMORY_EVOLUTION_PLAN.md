# Memory Evolution Implementation Plan

> **Inspired by:** MemEvolve: Meta-Evolution of Agent Memory Systems (ICML 2026)
> **Target:** TradingAgents — append-only markdown decision journal
> **Goal:** Transform static memory into a self-adapting, effectiveness-driven system
> **Timeline:** 8 weeks (5 phases)
> **Risk:** Low — backward compatible, opt-in evolution, zero breaking changes

---

## Table of Contents

1. [Current State Analysis](#1-current-state-analysis)
2. [MemEvolve Core Concepts Applied](#2-memevolve-core-concepts-applied)
3. [Architecture Overview](#3-architecture-overview)
4. [Phase 1: Modular Memory Interface](#4-phase-1-modular-memory-interface)
5. [Phase 2: Effectiveness Tracking](#5-phase-2-effectiveness-tracking)
6. [Phase 3: Diagnose-and-Design Evolution](#6-phase-3-diagnose-and-design-evolution)
7. [Phase 4: Advanced Memory Providers](#7-phase-4-advanced-memory-providers)
8. [Phase 5: Integration, CLI & Validation](#8-phase-5-integration-cli--validation)
9. [File Structure](#9-file-structure)
10. [Config Schema](#10-config-schema)
11. [Migration Path](#11-migration-path)
12. [Testing Strategy](#12-testing-strategy)
13. [Risk Assessment](#13-risk-assessment)
14. [Success Metrics](#14-success-metrics)

---

## 1. Current State Analysis

### 1.1 Existing Memory System

**File:** `tradingagents/agents/utils/memory.py` — `TradingMemoryLog` class

**Storage:** Single append-only markdown file (`~/.tradingagents/memory/trading_memory.md`)

**Entry Format:**
```
[2026-01-10 | NVDA | Buy | +4.2% | +2.1% | 5d]

DECISION:
Rating: Buy
Enter at $189-192, 6% portfolio cap.

REFLECTION:
Directionally correct. The AI capex thesis held as data center demand exceeded expectations.

<!-- ENTRY_END -->
```

**Lifecycle:**
- **Phase A (Store):** `store_decision()` appends `[date | ticker | rating | pending]` + DECISION
- **Phase B (Resolve):** `_resolve_pending_entries()` fetches returns, generates LLM reflection, replaces `pending` tag
- **Retrieval:** `get_past_context(ticker, n_same=5, n_cross=3)` returns 5 same-ticker + 3 cross-ticker entries
- **Rotation:** `_apply_rotation()` drops oldest resolved entries when `memory_log_max_entries` cap is exceeded (default: `None` = unlimited)

### 1.2 Identified Weaknesses

| Weakness | Impact | Severity |
|----------|--------|----------|
| Fixed `n_same=5, n_cross=3` | No adaptation to context window or decision quality | High |
| Single retrieval metric (recency) | Ignores rating patterns, outcome variance, relevance | High |
| No effectiveness tracking | Cannot measure if memory actually helps PM decisions | High |
| Default unbounded growth | File grows indefinitely, O(N) parse cost every run | Medium |
| Same-ticker-only resolution | Cross-ticker pending entries accumulate forever | Medium |
| Single-point injection | Only Portfolio Manager sees memory; analysts/researchers don't | Medium |
| No semantic search | Pure chronological — no relevance ranking | Low |
| Full file rewrite on update | Every `update_with_outcome` rewrites entire file | Low |

### 1.3 What Works Well

- **Simplicity:** Single markdown file — human-readable, git-trackable, zero dependencies
- **Crash safety:** Atomic writes via `os.replace()` prevent corruption
- **Idempotency:** Duplicate store attempts silently ignored
- **Deferred reflection:** Outcome-aware learning without blocking the pipeline
- **Rating extraction:** Centralized 5-tier vocabulary prevents drift

---

## 2. MemEvolve Core Concepts Applied

### 2.1 The 4-Component Modular Design Space

MemEvolve decomposes any memory system into four functionally distinct components:

```
Ω = (Encode, Store, Retrieve, Manage)
```

| Component | Role | Current TradingAgents | Evolved Target |
|-----------|------|----------------------|----------------|
| **Encode** | Transform raw experience into structured representation | Extract rating from PM decision markdown | Multi-level encoding: rating + key thesis + risk factors + outcome tags |
| **Store** | Persist encoded experience to storage | Append to markdown file | Pluggable: file, SQLite, vector DB, hybrid |
| **Retrieve** | Provide task-relevant context for current decision | Last 5 same-ticker + 3 cross-ticker (recency only) | Adaptive: effectiveness-weighted, rating-grouped, stage-aware |
| **Manage** | Offline consolidation, pruning, abstraction | Optional rotation by count | LLM-driven consolidation, semantic deduplication, pattern extraction |

### 2.2 Dual-Evolution Process

```
Inner Loop (Every Run):
  Agent runs with fixed memory Ω → produces decision → store → resolve outcome

Outer Loop (Every N Runs):
  Analyze effectiveness → Diagnose bottlenecks → Design new Ω → Validate → Deploy
```

### 2.3 Diagnose-and-Design Evolution

```
Diagnosis:
  - Collect feedback from last N runs
  - Compute effectiveness metrics
  - LLM analyzes trajectory evidence
  - Produce structured defect profile D(Ω)

Design:
  - Conditioned on D(Ω), propose S variants
  - Each variant modifies permissible components
  - All conform to MemoryProvider interface
  - Select best via Pareto optimization
```

### 2.4 Pragmatic Adaptation for TradingAgents

| MemEvolve (Paper) | TradingAgents (This Plan) | Rationale |
|-------------------|---------------------------|-----------|
| Evolves Python code for E/U/R/G modules | Evolves config parameters + retrieval strategy | Lower risk, no code generation needed |
| Tournament across 3+ candidate systems | Single-system self-adaptation | 10x lower LLM cost per evolution |
| 40 tasks per evaluation round | 20 decisions per evolution check | Matches trading cadence |
| Task success rate as metric | Alpha return + rating accuracy + context utilization | Domain-specific |
| Generates new provider classes | Selects from pre-built provider strategies | Safer, testable, auditable |
| Cross-benchmark transfer | Cross-ticker and cross-market transfer | Same domain, different assets |

---

## 3. Architecture Overview

```
┌──────────────────────────────────────────────────────────────────────┐
│                        TradingAgents Graph                           │
│  Analyst → Research → Trader → Risk → Portfolio Manager              │
└──────────────────┬───────────────────────────┬──────────────────────┘
                   │                           │
                   ▼                           ▼
┌──────────────────────────────┐  ┌──────────────────────────────────┐
│  Inner Loop (Every Run)      │  │  Outer Loop (Every N Decisions)  │
│                              │  │                                  │
│  1. Encode: PM decision      │  │  1. Diagnose:                    │
│     → MemoryEntry            │  │     - Collect feedback history   │
│                              │  │     - Compute effectiveness      │
│  2. Store: append to log     │  │     - LLM analyzes bottlenecks   │
│                              │  │                                  │
│  3. Retrieve: context for    │  │  2. Design:                      │
│     next PM decision         │◄─┤     - Propose config variants    │
│     (n_same, n_cross, format)│  │     - Pareto-optimal selection   │
│                              │  │                                  │
│  4. Manage: rotation,        │  │  3. Apply:                       │
│     dedup, consolidation     │  │     - Update provider config     │
│                              │  │     - Log evolution event        │
└──────────────────────────────┘  └──────────────────────────────────┘
                   │
                   ▼
┌──────────────────────────────────────────────────────────────────────┐
│                     Memory Provider Layer                            │
│                                                                      │
│  ┌─────────────┐  ┌──────────────────┐  ┌──────────────────────┐   │
│  │FileProvider │  │RatingGroupedProv │  │OutcomeWeightedProv   │   │
│  │(current)    │  │(by rating group) │  │(by alpha performance)│   │
│  └─────────────┘  └──────────────────┘  └──────────────────────┘   │
│                                                                      │
│  Protocol: encode() → store() → retrieve() → manage() → evolve()   │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 4. Phase 1: Modular Memory Interface

**Timeline:** Week 1
**Goal:** Refactor `TradingMemoryLog` into the 4-component MemEvolve interface without changing behavior.

### 4.1 Create Memory Protocol and Data Classes

**File:** `tradingagents/memory/provider.py`

```python
"""Memory Provider Protocol — MemEvolve-style 4-component interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from enum import Enum


class MemoryComponent(Enum):
    ENCODE = "encode"
    STORE = "store"
    RETRIEVE = "retrieve"
    MANAGE = "manage"


@dataclass
class MemoryEntry:
    """Structured representation of a trading decision."""
    date: str
    ticker: str
    rating: str                          # Buy / Overweight / Hold / Underweight / Sell
    decision: str                        # Full PM decision text
    reflection: str = ""                 # Post-outcome reflection (empty when pending)
    raw_return: Optional[float] = None   # e.g., 0.042 = +4.2%
    alpha_return: Optional[float] = None # Alpha vs benchmark
    holding_days: Optional[int] = None
    pending: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)
        # Future: sector, market_cap, thesis_keywords, risk_factors


@dataclass
class MemoryRequest:
    """Context for memory retrieval."""
    ticker: str
    trade_date: str
    n_same: int = 5                      # Max same-ticker entries
    n_cross: int = 3                     # Max cross-ticker entries
    min_effectiveness: float = 0.0       # Filter by historical effectiveness
    rating_filter: Optional[str] = None  # Filter by rating


@dataclass
class MemoryResponse:
    """Retrieved memory context."""
    context: str                         # Formatted markdown for prompt injection
    entries: List[MemoryEntry]
    total_available: int                 # Total entries in storage (for diagnostics)
    retrieval_time_ms: float = 0.0


@dataclass
class EvolutionFeedback:
    """Feedback signal for memory evolution."""
    run_id: str
    ticker: str
    trade_date: str
    decision: str
    rating: str
    memory_injected: bool
    memory_context_length: int
    outcome_known: bool
    raw_return: Optional[float] = None
    alpha_return: Optional[float] = None
    decision_matches_memory_pattern: Optional[bool] = None
    effectiveness_score: Optional[float] = None  # 0.0 - 1.0


@dataclass
class DiagnosisReport:
    """Structured defect profile from evolution diagnosis."""
    issues: List[Dict[str, Any]]
    llm_analysis: str
    component_scores: Dict[MemoryComponent, float]
    recommended_actions: List[str]


@dataclass
class MemoryConfig:
    """Configurable parameters for a memory provider."""
    provider_type: str = "file"
    n_same: int = 5
    n_cross: int = 3
    max_context_length: int = 4000
    format_style: str = "full"           # full, reflection_only, summary
    selection_strategy: str = "recency"  # recency, rating_grouped, outcome_weighted
    rotation_max_entries: Optional[int] = None
    dedup_enabled: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


class MemoryProvider(ABC):
    """Abstract base for all memory providers.

    Implements the MemEvolve 4-component interface:
      Ω = (Encode, Store, Retrieve, Manage)

    All providers must implement these four methods. The optional
    evolve() method enables architectural self-adaptation.
    """

    def __init__(self, config: MemoryConfig):
        self.config = config

    @abstractmethod
    def encode(self, decision_text: str, ticker: str, date: str,
               rating: Optional[str] = None) -> MemoryEntry:
        """Transform raw PM decision into structured MemoryEntry.

        This is the Encode (E) component. It extracts rating,
        parses decision text, and optionally enriches with metadata.
        """

    @abstractmethod
    def store(self, entry: MemoryEntry) -> bool:
        """Persist entry to storage.

        This is the Store (U) component. Returns True on success.
        Must be idempotent for duplicate (ticker, date) pairs.
        """

    @abstractmethod
    def retrieve(self, request: MemoryRequest) -> MemoryResponse:
        """Return task-relevant context for current run.

        This is the Retrieve (R) component. The implementation
        determines selection strategy (recency, rating, outcome, etc.).
        """

    @abstractmethod
    def manage(self) -> Dict[str, Any]:
        """Offline consolidation, rotation, pruning.

        This is the Manage (G) component. Returns stats dict.
        Called periodically or after store operations.
        """

    def evolve(self, feedback: EvolutionFeedback) -> bool:
        """Adapt architecture based on effectiveness feedback.

        Default: no-op. Subclasses override to implement self-evolution.
        Returns True if architecture was modified.
        """
        return False

    def get_config(self) -> MemoryConfig:
        """Return current configuration."""
        return self.config

    def update_config(self, config: MemoryConfig) -> None:
        """Update configuration (used by evolution)."""
        self.config = config
```

### 4.2 Create FileMemoryProvider (Current Behavior)

**File:** `tradingagents/memory/file_provider.py`

```python
"""File-based memory provider — drop-in replacement for TradingMemoryLog."""

from __future__ import annotations

import os
import re
import tempfile
from pathlib import Path
from typing import Dict, Any, List, Optional
import time

from .provider import (
    MemoryProvider, MemoryConfig, MemoryEntry, MemoryRequest,
    MemoryResponse, EvolutionFeedback, DiagnosisReport,
)
from tradingagents.agents.utils.rating import parse_rating


class FileMemoryProvider(MemoryProvider):
    """Append-only markdown file storage.

    Maintains exact same format as TradingMemoryLog for backward
    compatibility. Wraps existing logic into the 4-component interface.
    """

    _SEPARATOR = "\n\n<!-- ENTRY_END -->\n\n"
    _DECISION_RE = re.compile(r"DECISION:\n(.*?)(?=\nREFLECTION:|\Z)", re.DOTALL)
    _REFLECTION_RE = re.compile(r"REFLECTION:\n(.*?)$", re.DOTALL)

    def __init__(self, config: MemoryConfig, log_path: Optional[str] = None):
        super().__init__(config)
        self._log_path = Path(log_path).expanduser() if log_path else None
        if self._log_path:
            self._log_path.parent.mkdir(parents=True, exist_ok=True)

    # --- Encode ---

    def encode(self, decision_text: str, ticker: str, date: str,
               rating: Optional[str] = None) -> MemoryEntry:
        if rating is None:
            rating = parse_rating(decision_text)
        return MemoryEntry(
            date=date,
            ticker=ticker,
            rating=rating,
            decision=decision_text.strip(),
            pending=True,
        )

    # --- Store ---

    def store(self, entry: MemoryEntry) -> bool:
        if not self._log_path:
            return False

        # Idempotency guard
        if self._log_path.exists():
            raw = self._log_path.read_text(encoding="utf-8")
            for line in raw.splitlines():
                if line.startswith(f"[{entry.date} | {entry.ticker} |") and line.endswith("| pending]"):
                    return True  # Already stored

        tag = f"[{entry.date} | {entry.ticker} | {entry.rating} | pending]"
        block = f"{tag}\n\nDECISION:\n{entry.decision}{self._SEPARATOR}"

        with open(self._log_path, "a", encoding="utf-8") as f:
            f.write(block)
        return True

    # --- Retrieve ---

    def retrieve(self, request: MemoryRequest) -> MemoryResponse:
        start = time.time()
        entries = self._load_entries()
        resolved = [e for e in entries if not e.pending]

        if not resolved:
            return MemoryResponse(context="", entries=[], total_available=len(entries))

        same, cross = [], []
        for e in reversed(resolved):
            if len(same) >= request.n_same and len(cross) >= request.n_cross:
                break
            if e.ticker == request.ticker and len(same) < request.n_same:
                same.append(e)
            elif e.ticker != request.ticker and len(cross) < request.n_cross:
                cross.append(e)

        context = self._format_context(request.ticker, same, cross)
        elapsed = (time.time() - start) * 1000

        return MemoryResponse(
            context=context,
            entries=same + cross,
            total_available=len(entries),
            retrieval_time_ms=elapsed,
        )

    # --- Manage ---

    def manage(self) -> Dict[str, Any]:
        entries = self._load_entries()
        resolved = [e for e in entries if not e.pending]
        pending = [e for e in entries if e.pending]

        max_entries = self.config.rotation_max_entries
        pruned = 0
        if max_entries and len(resolved) > max_entries:
            pruned = len(resolved) - max_entries
            self._rotate(max_entries)

        return {
            "total_entries": len(entries),
            "resolved": len(resolved),
            "pending": len(pending),
            "pruned": pruned,
            "file_size_kb": self._log_path.stat().st_size / 1024 if self._log_path and self._log_path.exists() else 0,
        }

    # --- Helpers (ported from TradingMemoryLog) ---

    def _load_entries(self) -> List[MemoryEntry]:
        if not self._log_path or not self._log_path.exists():
            return []
        text = self._log_path.read_text(encoding="utf-8")
        raw_entries = [e.strip() for e in text.split(self._SEPARATOR) if e.strip()]
        entries = []
        for raw in raw_entries:
            entry = self._parse_entry(raw)
            if entry:
                entries.append(entry)
        return entries

    def _parse_entry(self, raw: str) -> Optional[MemoryEntry]:
        lines = raw.strip().splitlines()
        if not lines:
            return None
        tag_line = lines[0].strip()
        if not (tag_line.startswith("[") and tag_line.endswith("]")):
            return None
        fields = [f.strip() for f in tag_line[1:-1].split("|")]
        if len(fields) < 4:
            return None
        body = "\n".join(lines[1:]).strip()
        decision_match = self._DECISION_RE.search(body)
        reflection_match = self._REFLECTION_RE.search(body)
        return MemoryEntry(
            date=fields[0],
            ticker=fields[1],
            rating=fields[2],
            pending=(fields[3] == "pending"),
            raw_return=float(fields[4].strip().replace("%", "")) / 100 if len(fields) > 4 and fields[4].strip() != "n/a" else None,
            alpha_return=float(fields[5].strip().replace("%", "")) / 100 if len(fields) > 5 and fields[5].strip() != "n/a" else None,
            holding_days=int(fields[6].replace("d", "")) if len(fields) > 6 and fields[6].strip() != "n/a" else None,
            decision=decision_match.group(1).strip() if decision_match else "",
            reflection=reflection_match.group(1).strip() if reflection_match else "",
        )

    def _format_context(self, ticker: str, same: List[MemoryEntry], cross: List[MemoryEntry]) -> str:
        parts = []
        if same:
            parts.append(f"Past analyses of {ticker} (most recent first):")
            for e in same:
                parts.append(self._format_full(e))
        if cross:
            parts.append("Recent cross-ticker lessons:")
            for e in cross:
                parts.append(self._format_reflection_only(e))
        return "\n\n".join(parts)

    def _format_full(self, e: MemoryEntry) -> str:
        raw = f"{e.raw_return:+.1%}" if e.raw_return else "n/a"
        alpha = f"{e.alpha_return:+.1%}" if e.alpha_return else "n/a"
        holding = f"{e.holding_days}d" if e.holding_days else "n/a"
        tag = f"[{e.date} | {e.ticker} | {e.rating} | {raw} | {alpha} | {holding}]"
        parts = [tag, f"DECISION:\n{e.decision}"]
        if e.reflection:
            parts.append(f"REFLECTION:\n{e.reflection}")
        return "\n\n".join(parts)

    def _format_reflection_only(self, e: MemoryEntry) -> str:
        raw = f"{e.raw_return:+.1%}" if e.raw_return else "n/a"
        tag = f"[{e.date} | {e.ticker} | {e.rating} | {raw}]"
        if e.reflection:
            return f"{tag}\n{e.reflection}"
        text = e.decision[:300]
        suffix = "..." if len(e.decision) > 300 else ""
        return f"{tag}\n{text}{suffix}"

    def _rotate(self, max_entries: int) -> None:
        """Drop oldest resolved entries, keep all pending."""
        if not self._log_path or not self._log_path.exists():
            return
        text = self._log_path.read_text(encoding="utf-8")
        blocks = text.split(self._SEPARATOR)
        decisions = []
        for block in blocks:
            stripped = block.strip()
            if not stripped:
                decisions.append((block, False))
                continue
            tag_line = stripped.splitlines()[0].strip()
            is_resolved = tag_line.startswith("[") and tag_line.endswith("]") and not tag_line.endswith("| pending]")
            decisions.append((block, is_resolved))
        resolved_count = sum(1 for _, r in decisions if r)
        if resolved_count <= max_entries:
            return
        to_drop = resolved_count - max_entries
        kept = []
        for block, is_resolved in decisions:
            if is_resolved and to_drop > 0:
                to_drop -= 1
                continue
            kept.append(block)
        new_text = self._SEPARATOR.join(kept)
        tmp = self._log_path.with_suffix(".tmp")
        tmp.write_text(new_text, encoding="utf-8")
        tmp.replace(self._log_path)

    def update_entry(self, entry: MemoryEntry, reflection: str) -> bool:
        """Resolve a pending entry with outcome and reflection."""
        if not self._log_path or not self._log_path.exists():
            return False
        text = self._log_path.read_text(encoding="utf-8")
        blocks = text.split(self._SEPARATOR)
        pending_prefix = f"[{entry.date} | {entry.ticker} |"
        raw_pct = f"{entry.raw_return:+.1%}" if entry.raw_return else "n/a"
        alpha_pct = f"{entry.alpha_return:+.1%}" if entry.alpha_return else "n/a"
        holding = f"{entry.holding_days}d" if entry.holding_days else "n/a"
        new_tag = f"[{entry.date} | {entry.ticker} | {entry.rating} | {raw_pct} | {alpha_pct} | {holding}]"
        updated = False
        new_blocks = []
        for block in blocks:
            stripped = block.strip()
            if not stripped:
                new_blocks.append(block)
                continue
            lines = stripped.splitlines()
            tag_line = lines[0].strip()
            if tag_line.startswith(pending_prefix) and tag_line.endswith("| pending]"):
                rest = "\n".join(lines[1:])
                new_blocks.append(f"{new_tag}\n\n{rest.lstrip()}\n\nREFLECTION:\n{reflection}")
                updated = True
            else:
                new_blocks.append(block)
        if not updated:
            return False
        # Apply rotation
        max_entries = self.config.rotation_max_entries
        if max_entries:
            new_blocks = self._rotate_blocks(new_blocks, max_entries)
        new_text = self._SEPARATOR.join(new_blocks)
        tmp = self._log_path.with_suffix(".tmp")
        tmp.write_text(new_text, encoding="utf-8")
        tmp.replace(self._log_path)
        return True

    def _rotate_blocks(self, blocks: List[str], max_entries: int) -> List[str]:
        decisions = []
        for block in blocks:
            stripped = block.strip()
            if not stripped:
                decisions.append((block, False))
                continue
            tag_line = stripped.splitlines()[0].strip()
            is_resolved = tag_line.startswith("[") and tag_line.endswith("]") and not tag_line.endswith("| pending]")
            decisions.append((block, is_resolved))
        resolved_count = sum(1 for _, r in decisions if r)
        if resolved_count <= max_entries:
            return blocks
        to_drop = resolved_count - max_entries
        kept = []
        for block, is_resolved in decisions:
            if is_resolved and to_drop > 0:
                to_drop -= 1
                continue
            kept.append(block)
        return kept
```

### 4.3 Update TradingAgentsGraph

**File:** `tradingagents/graph/trading_graph.py` — modifications

```python
# Replace existing imports:
# from tradingagents.agents.utils.memory import TradingMemoryLog
# With:
from tradingagents.memory.provider import MemoryConfig
from tradingagents.memory.file_provider import FileMemoryProvider

# In __init__():
# Replace:
#   self.memory_log = TradingMemoryLog(self.config)
# With:
memory_log_path = self.config.get("memory_log_path")
memory_config = MemoryConfig(
    rotation_max_entries=self.config.get("memory_log_max_entries"),
)
self.memory_provider = FileMemoryProvider(memory_config, log_path=memory_log_path)

# Backward compat alias (for gradual migration):
self.memory_log = self.memory_provider  # Enables drop-in replacement

# In _run_graph():
# Replace:
#   past_context = self.memory_log.get_past_context(company_name)
# With:
from tradingagents.memory.provider import MemoryRequest
request = MemoryRequest(ticker=company_name, trade_date=str(trade_date))
response = self.memory_provider.retrieve(request)
past_context = response.context

# In propagate():
# Replace:
#   self.memory_log.store_decision(...)
# With:
entry = self.memory_provider.encode(final_trade_decision, company_name, str(trade_date))
self.memory_provider.store(entry)

# In _resolve_pending_entries():
# Replace batch_update_with_outcomes with:
for upd in updates:
    entry = MemoryEntry(
        date=upd["trade_date"],
        ticker=upd["ticker"],
        rating=...,  # parse from stored entry
        decision=...,
        raw_return=upd["raw_return"],
        alpha_return=upd["alpha_return"],
        holding_days=upd["holding_days"],
        pending=False,
    )
    self.memory_provider.update_entry(entry, upd["reflection"])
```

### 4.4 Backward Compatibility Layer

**File:** `tradingagents/agents/utils/memory.py` — updated

```python
"""TradingMemoryLog — deprecated, wraps FileMemoryProvider for backward compat."""

from tradingagents.memory.provider import MemoryConfig, MemoryRequest
from tradingagents.memory.file_provider import FileMemoryProvider


class TradingMemoryLog:
    """Deprecated: use FileMemoryProvider directly.

    This class wraps FileMemoryProvider to maintain API compatibility
    with existing code during the migration period.
    """

    def __init__(self, config: dict = None):
        cfg = config or {}
        memory_config = MemoryConfig(
            rotation_max_entries=cfg.get("memory_log_max_entries"),
        )
        self._provider = FileMemoryProvider(memory_config, log_path=cfg.get("memory_log_path"))

    def store_decision(self, ticker, trade_date, final_trade_decision):
        entry = self._provider.encode(final_trade_decision, ticker, trade_date)
        self._provider.store(entry)

    def load_entries(self):
        return self._provider._load_entries()

    def get_pending_entries(self):
        return [e for e in self._provider._load_entries() if e.pending]

    def get_past_context(self, ticker, n_same=5, n_cross=3):
        request = MemoryRequest(ticker=ticker, n_same=n_same, n_cross=n_cross)
        return self._provider.retrieve(request).context

    def update_with_outcome(self, ticker, trade_date, raw_return, alpha_return, holding_days, reflection):
        entries = self._provider._load_entries()
        for e in entries:
            if e.date == trade_date and e.ticker == ticker and e.pending:
                e.raw_return = raw_return
                e.alpha_return = alpha_return
                e.holding_days = holding_days
                e.pending = False
                self._provider.update_entry(e, reflection)
                break

    def batch_update_with_outcomes(self, updates):
        for upd in updates:
            self.update_with_outcome(
                upd["ticker"], upd["trade_date"],
                upd["raw_return"], upd["alpha_return"],
                upd["holding_days"], upd["reflection"],
            )
```

### 4.5 Phase 1 Deliverables Checklist

- [ ] `tradingagents/memory/__init__.py` — exports
- [ ] `tradingagents/memory/provider.py` — protocol + dataclasses
- [ ] `tradingagents/memory/file_provider.py` — current behavior wrapper
- [ ] `tradingagents/agents/utils/memory.py` — backward compat layer
- [ ] `tradingagents/graph/trading_graph.py` — provider injection
- [ ] All existing tests pass unchanged
- [ ] No behavioral change from current system

---

## 5. Phase 2: Effectiveness Tracking

**Timeline:** Week 2
**Goal:** Track whether retrieved memory actually influences PM decisions.

### 5.1 Memory Effectiveness Analyzer

**File:** `tradingagents/memory/analyzer.py`

```python
"""Analyzes whether memory context influences Portfolio Manager decisions."""

from __future__ import annotations

import re
import json
from pathlib import Path
from datetime import datetime
from typing import List, Optional, Dict, Any
from dataclasses import asdict

from .provider import MemoryEntry, EvolutionFeedback


class MemoryEffectivenessAnalyzer:
    """Diagnoses whether past_context influenced the PM decision.

    Computes an effectiveness score (0.0 - 1.0) based on:
    1. Ticker reference overlap: does PM mention tickers from memory?
    2. Rating alignment: does PM rating match historically successful patterns?
    3. Reflection adoption: does PM language echo past reflections?
    4. Context utilization: is the injected context length proportional to decision detail?
    """

    def __init__(self, feedback_log_path: Optional[str] = None):
        self._log_path = Path(feedback_log_path) if feedback_log_path else None
        if self._log_path:
            self._log_path.parent.mkdir(parents=True, exist_ok=True)
        self._run_counter = 0

    def analyze(self, past_context: str, pm_decision: str,
                historical_entries: List[MemoryEntry],
                ticker: str, trade_date: str,
                rating: str) -> EvolutionFeedback:
        """Run effectiveness analysis after PM decision."""
        self._run_counter += 1
        run_id = f"run_{self._run_counter:04d}"

        # 1. Ticker reference overlap
        referenced_tickers = self._extract_tickers(pm_decision)
        memory_tickers = {e.ticker for e in historical_entries}
        ticker_overlap = referenced_tickers & memory_tickers
        ticker_score = min(len(ticker_overlap) / max(len(memory_tickers), 1), 1.0)

        # 2. Rating alignment with successful patterns
        successful_ratings = self._get_successful_rating_distribution(historical_entries)
        rating_score = self._compute_rating_alignment(rating, successful_ratings)

        # 3. Reflection adoption (keyword overlap with past reflections)
        reflection_keywords = self._extract_reflection_keywords(historical_entries)
        reflection_score = self._compute_reflection_adoption(pm_decision, reflection_keywords)

        # 4. Composite effectiveness score
        effectiveness = (
            0.35 * ticker_score +
            0.30 * rating_score +
            0.35 * reflection_score
        )

        feedback = EvolutionFeedback(
            run_id=run_id,
            ticker=ticker,
            trade_date=trade_date,
            decision=pm_decision,
            rating=rating,
            memory_injected=bool(past_context),
            memory_context_length=len(past_context),
            outcome_known=False,
            decision_matches_memory_pattern=bool(ticker_overlap or reflection_score > 0.3),
            effectiveness_score=round(effectiveness, 3),
        )

        # Persist to sidecar file
        self._log_feedback(feedback)

        return feedback

    def update_with_outcome(self, run_id: str, raw_return: float,
                            alpha_return: float, holding_days: int) -> None:
        """Update a feedback entry with actual outcome."""
        if not self._log_path or not self._log_path.exists():
            return
        lines = self._log_path.read_text(encoding="utf-8").strip().splitlines()
        new_lines = []
        for line in lines:
            entry = json.loads(line)
            if entry.get("run_id") == run_id:
                entry["outcome_known"] = True
                entry["raw_return"] = raw_return
                entry["alpha_return"] = alpha_return
                entry["holding_days"] = holding_days
            new_lines.append(json.dumps(entry))
        self._log_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")

    def get_feedback_history(self, limit: int = 100) -> List[EvolutionFeedback]:
        """Load recent feedback entries."""
        if not self._log_path or not self._log_path.exists():
            return []
        lines = self._log_path.read_text(encoding="utf-8").strip().splitlines()
        feedbacks = []
        for line in lines[-limit:]:
            try:
                data = json.loads(line)
                fb = EvolutionFeedback(**data)
                feedbacks.append(fb)
            except (json.JSONDecodeError, TypeError):
                continue
        return feedbacks

    def get_stats(self) -> Dict[str, Any]:
        """Compute aggregate statistics."""
        history = self.get_feedback_history()
        if not history:
            return {"total_runs": 0}
        scores = [f.effectiveness_score for f in history if f.effectiveness_score is not None]
        return {
            "total_runs": len(history),
            "avg_effectiveness": round(sum(scores) / len(scores), 3) if scores else 0,
            "min_effectiveness": round(min(scores), 3) if scores else 0,
            "max_effectiveness": round(max(scores), 3) if scores else 0,
            "runs_with_memory": sum(1 for f in history if f.memory_injected),
            "runs_matching_pattern": sum(1 for f in history if f.decision_matches_memory_pattern),
            "last_10_avg": round(sum(s for s in scores[-10:]) / min(len(scores), 10), 3) if scores else 0,
        }

    # --- Private Methods ---

    def _extract_tickers(self, text: str) -> set:
        """Extract ticker symbols from text (2-5 uppercase chars, optionally with .XX suffix)."""
        return set(re.findall(r'\b([A-Z]{1,5}(?:\.[A-Z]{1,3})?)\b', text))

    def _get_successful_rating_distribution(self, entries: List[MemoryEntry]) -> Dict[str, float]:
        """Get distribution of ratings that produced positive alpha."""
        dist = {}
        for e in entries:
            if e.alpha_return is not None and e.alpha_return > 0:
                dist[e.rating] = dist.get(e.rating, 0) + 1
        total = sum(dist.values())
        if total == 0:
            return {}
        return {r: c / total for r, c in dist.items()}

    def _compute_rating_alignment(self, current_rating: str,
                                   successful_dist: Dict[str, float]) -> float:
        """Score how well current rating aligns with historically successful patterns."""
        if not successful_dist:
            return 0.5  # Neutral
        return successful_dist.get(current_rating, 0.0)

    def _extract_reflection_keywords(self, entries: List[MemoryEntry]) -> set:
        """Extract meaningful keywords from past reflections."""
        keywords = set()
        stop_words = {"the", "a", "an", "is", "was", "were", "be", "been", "being",
                      "have", "has", "had", "do", "does", "did", "will", "would",
                      "could", "should", "may", "might", "shall", "can", "need",
                      "dare", "ought", "used", "to", "of", "in", "for", "on", "with",
                      "at", "by", "from", "as", "into", "through", "during", "before",
                      "after", "above", "below", "between", "under", "again", "further",
                      "then", "once", "and", "but", "or", "nor", "not", "so", "yet",
                      "both", "either", "neither", "each", "every", "all", "any", "few",
                      "more", "most", "other", "some", "such", "no", "only", "own",
                      "same", "than", "too", "very", "just", "because", "if", "when",
                      "where", "which", "while", "who", "whom", "this", "that", "these",
                      "those", "i", "me", "my", "myself", "we", "our", "ours", "ourselves",
                      "you", "your", "yours", "yourself", "yourselves", "he", "him", "his",
                      "himself", "she", "her", "hers", "herself", "it", "its", "itself",
                      "they", "them", "their", "theirs", "themselves", "what", "about"}
        for e in entries:
            if e.reflection:
                words = re.findall(r'\b[a-z]{4,}\b', e.reflection.lower())
                keywords.update(w for w in words if w not in stop_words)
        return keywords

    def _compute_reflection_adoption(self, decision: str, keywords: set) -> float:
        """Score how many past reflection keywords appear in current decision."""
        if not keywords:
            return 0.5
        decision_words = set(re.findall(r'\b[a-z]{4,}\b', decision.lower()))
        overlap = decision_words & keywords
        return min(len(overlap) / max(len(keywords), 1), 1.0)

    def _log_feedback(self, feedback: EvolutionFeedback) -> None:
        if not self._log_path:
            return
        data = asdict(feedback)
        with open(self._log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(data) + "\n")
```

### 5.2 Integration in Trading Graph

**File:** `tradingagents/graph/trading_graph.py` — additions

```python
# In __init__():
from tradingagents.memory.analyzer import MemoryEffectivenessAnalyzer
feedback_log_path = os.path.join(
    os.path.expanduser("~"), ".tradingagents", "memory", "effectiveness_log.jsonl"
)
self.effectiveness_analyzer = MemoryEffectivenessAnalyzer(feedback_log_path)

# In _run_graph(), after final_trade_decision is produced:
# Extract rating from decision
from tradingagents.agents.utils.rating import parse_rating
rating = parse_rating(final_trade_decision)

# Get historical entries for analysis
historical_entries = self.memory_provider._load_entries()

# Run effectiveness analysis
feedback = self.effectiveness_analyzer.analyze(
    past_context=past_context,
    pm_decision=final_trade_decision,
    historical_entries=historical_entries,
    ticker=company_name,
    trade_date=str(trade_date),
    rating=rating,
)

# Store feedback run_id for later outcome update
self._current_feedback_run_id = feedback.run_id

# In _resolve_pending_entries(), after computing returns:
# Update feedback with outcome
if hasattr(self, '_current_feedback_run_id'):
    self.effectiveness_analyzer.update_with_outcome(
        run_id=self._current_feedback_run_id,
        raw_return=raw,
        alpha_return=alpha,
        holding_days=days,
    )
```

### 5.3 Phase 2 Deliverables Checklist

- [ ] `tradingagents/memory/analyzer.py` — effectiveness analyzer
- [ ] Integration in `trading_graph.py` post-PM decision
- [ ] Sidecar JSONL file at `~/.tradingagents/memory/effectiveness_log.jsonl`
- [ ] Outcome update hook in `_resolve_pending_entries()`
- [ ] Tests for analyzer scoring logic
- [ ] No behavioral change to existing memory system

---

## 6. Phase 3: Diagnose-and-Design Evolution

**Timeline:** Week 3-4
**Goal:** Implement the outer-loop evolution that adapts memory architecture based on effectiveness feedback.

### 6.1 Evolution Engine

**File:** `tradingagents/memory/evolution.py`

```python
"""Diagnose-and-Design evolution engine for memory providers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
from dataclasses import asdict

from .provider import (
    MemoryProvider, MemoryConfig, MemoryEntry, EvolutionFeedback,
    DiagnosisReport, MemoryComponent,
)


class MemoryEvolver:
    """Implements MemEvolve's Diagnose-and-Design evolution loop.

    Triggered every N decisions or when effectiveness drops below threshold.
    Uses LLM to analyze feedback history and propose architecture changes.
    """

    def __init__(self, llm, provider: MemoryProvider,
                 evolution_log_path: Optional[str] = None):
        self.llm = llm
        self.provider = provider
        self._log_path = Path(evolution_log_path) if evolution_log_path else None
        if self._log_path:
            self._log_path.parent.mkdir(parents=True, exist_ok=True)

    def should_evolve(self, feedback_history: List[EvolutionFeedback],
                      trigger_runs: int = 20,
                      min_effectiveness: float = 0.2) -> bool:
        """Determine if evolution should be triggered.

        Conditions:
        1. Every `trigger_runs` decisions (periodic check)
        2. If avg effectiveness of last 10 runs < min_effectiveness
        3. If context length consistently exceeds max_context_length
        """
        if len(feedback_history) < trigger_runs:
            return False

        # Periodic trigger
        if len(feedback_history) % trigger_runs == 0:
            return True

        # Effectiveness trigger
        recent = feedback_history[-10:]
        recent_scores = [f.effectiveness_score for f in recent if f.effectiveness_score is not None]
        if recent_scores and sum(recent_scores) / len(recent_scores) < min_effectiveness:
            return True

        # Context bloat trigger
        config = self.provider.get_config()
        long_context = [f for f in recent if f.memory_context_length > config.max_context_length]
        if len(long_context) > len(recent) * 0.7:
            return True

        return False

    def diagnose(self, feedback_history: List[EvolutionFeedback]) -> DiagnosisReport:
        """Analyze trajectory-level evidence to identify bottlenecks.

        Produces a structured defect profile D(Ω) characterizing
        architectural issues across the four memory components.
        """
        issues = []
        component_scores = {c: 0.5 for c in MemoryComponent}

        # Gather statistics
        total_runs = len(feedback_history)
        scores = [f.effectiveness_score for f in feedback_history if f.effectiveness_score is not None]
        avg_effectiveness = sum(scores) / len(scores) if scores else 0
        recent_scores = scores[-10:] if len(scores) >= 10 else scores
        recent_avg = sum(recent_scores) / len(recent_scores) if recent_scores else 0

        # Encode diagnosis
        context_lengths = [f.memory_context_length for f in feedback_history]
        avg_context = sum(context_lengths) / len(context_lengths) if context_lengths else 0
        if avg_context > 3000:
            issues.append({
                "component": "encode",
                "issue": "Encoded entries are too verbose, diluting signal",
                "evidence": f"Average context length: {avg_context:.0f} chars",
                "severity": "high" if avg_context > 4000 else "medium",
            })
            component_scores[MemoryComponent.ENCODE] = max(0, 1.0 - avg_context / 5000)

        # Store diagnosis
        file_size = self._get_file_size_kb()
        if file_size > 500:
            issues.append({
                "component": "store",
                "issue": "Storage file is large, increasing parse latency",
                "evidence": f"File size: {file_size:.0f} KB",
                "severity": "medium",
            })
            component_scores[MemoryComponent.STORE] = max(0, 1.0 - file_size / 1000)

        # Retrieve diagnosis
        if recent_avg < 0.3:
            issues.append({
                "component": "retrieve",
                "issue": "PM consistently ignores memory context",
                "evidence": f"Recent avg effectiveness: {recent_avg:.2f}",
                "severity": "high",
            })
            component_scores[MemoryComponent.RETRIEVE] = recent_avg
        elif recent_avg < 0.5:
            issues.append({
                "component": "retrieve",
                "issue": "Memory context has moderate influence, could be improved",
                "evidence": f"Recent avg effectiveness: {recent_avg:.2f}",
                "severity": "low",
            })
            component_scores[MemoryComponent.RETRIEVE] = recent_avg

        # Manage diagnosis
        config = self.provider.get_config()
        if config.rotation_max_entries is None:
            issues.append({
                "component": "manage",
                "issue": "No rotation configured — file will grow unbounded",
                "evidence": "rotation_max_entries is None",
                "severity": "low",
            })
            component_scores[MemoryComponent.MANAGE] = 0.3
        else:
            component_scores[MemoryComponent.MANAGE] = 0.7

        # LLM-driven deep diagnosis
        llm_analysis = self._llm_diagnose(feedback_history, issues, component_scores)

        # Generate recommended actions
        recommended_actions = self._generate_actions(issues, llm_analysis)

        return DiagnosisReport(
            issues=issues,
            llm_analysis=llm_analysis,
            component_scores=component_scores,
            recommended_actions=recommended_actions,
        )

    def design(self, diagnosis: DiagnosisReport) -> List[MemoryConfig]:
        """Generate new memory architecture variants conditioned on diagnosis.

        Produces S candidate configurations by modifying permissible
        components within the modular design space.
        """
        current_config = self.provider.get_config()

        # LLM-driven design proposal
        llm_proposal = self._llm_design(diagnosis, current_config)

        # Parse LLM output into concrete config variants
        candidates = self._parse_proposals(llm_proposal, current_config)

        # Always include current config as baseline
        candidates.append(current_config)

        return candidates

    def select_best(self, candidates: List[MemoryConfig],
                    feedback_history: List[EvolutionFeedback]) -> MemoryConfig:
        """Select best configuration via Pareto-optimal ranking.

        Ranks candidates on multiple objectives:
        1. Simulated effectiveness (based on historical data)
        2. Context cost (lower is better)
        3. Complexity (simpler is better)
        """
        scored = []
        for config in candidates:
            effectiveness = self._simulate_config(config, feedback_history)
            context_cost = self._estimate_context_cost(config)
            complexity = self._estimate_complexity(config)
            scored.append({
                "config": config,
                "effectiveness": effectiveness,
                "context_cost": context_cost,
                "complexity": complexity,
            })

        # Pareto sort: prefer higher effectiveness, lower cost, lower complexity
        scored.sort(key=lambda s: (-s["effectiveness"], s["context_cost"], s["complexity"]))

        return scored[0]["config"]

    def apply(self, config: MemoryConfig) -> bool:
        """Apply new configuration to the memory provider."""
        old_config = self.provider.get_config()
        if config == old_config:
            return False
        self.provider.update_config(config)
        self._log_evolution(old_config, config)
        return True

    # --- Private Methods ---

    def _get_file_size_kb(self) -> float:
        """Get current storage file size in KB."""
        provider = self.provider
        if hasattr(provider, '_log_path') and provider._log_path and provider._log_path.exists():
            return provider._log_path.stat().st_size / 1024
        return 0

    def _llm_diagnose(self, feedback_history: List[EvolutionFeedback],
                      issues: List[Dict], component_scores: Dict) -> str:
        """Use LLM for deep diagnosis beyond rule-based checks."""
        stats = {
            "total_runs": len(feedback_history),
            "avg_effectiveness": sum(f.effectiveness_score or 0 for f in feedback_history) / max(len(feedback_history), 1),
            "recent_10_avg": sum((f.effectiveness_score or 0) for f in feedback_history[-10:]) / min(len(feedback_history), 10),
            "avg_context_length": sum(f.memory_context_length for f in feedback_history) / max(len(feedback_history), 1),
            "memory_injection_rate": sum(1 for f in feedback_history if f.memory_injected) / max(len(feedback_history), 1),
            "pattern_match_rate": sum(1 for f in feedback_history if f.decision_matches_memory_pattern) / max(len(feedback_history), 1),
        }

        prompt = f"""You are a memory system architect analyzing the effectiveness of a trading agent's memory.

Current Statistics:
{json.dumps(stats, indent=2)}

Detected Issues:
{json.dumps(issues, indent=2)}

Component Scores (0.0 = broken, 1.0 = optimal):
{json.dumps({k.value: v for k, v in component_scores.items()}, indent=2)}

Analyze the data and provide:
1. Root cause analysis for the lowest-scoring component
2. Specific architectural changes that would improve effectiveness
3. Trade-offs between context richness and decision quality
4. Whether the current retrieval strategy (recency-based) is optimal for this trading pattern

Be concise. Focus on actionable insights."""

        response = self.llm.invoke([("system", "You are a memory architecture expert for financial trading agents."),
                                     ("human", prompt)])
        return response.content

    def _generate_actions(self, issues: List[Dict], llm_analysis: str) -> List[str]:
        """Generate prioritized action list from diagnosis."""
        actions = []
        severity_order = {"high": 0, "medium": 1, "low": 2}
        sorted_issues = sorted(issues, key=lambda i: severity_order.get(i.get("severity", "low"), 2))

        for issue in sorted_issues:
            component = issue["component"]
            if component == "encode":
                actions.append("Reduce encoding granularity: switch from full decision to key-point summary")
            elif component == "store":
                actions.append("Enable rotation: set max_entries to 50-100 to bound file growth")
            elif component == "retrieve":
                actions.append("Change retrieval strategy: try rating-grouped or outcome-weighted selection")
            elif component == "manage":
                actions.append("Configure periodic consolidation to remove redundant entries")

        return actions

    def _llm_design(self, diagnosis: DiagnosisReport, current_config: MemoryConfig) -> str:
        """Use LLM to propose new memory configurations."""
        prompt = f"""You are designing an improved memory architecture for a financial trading agent.

Current Configuration:
{json.dumps(asdict(current_config), indent=2)}

Diagnosis Report:
- Issues: {json.dumps(diagnosis.issues, indent=2)}
- LLM Analysis: {diagnosis.llm_analysis}
- Component Scores: {json.dumps({k.value: v for k, v in diagnosis.component_scores.items()}, indent=2)}

Propose 3 alternative configurations. For each, specify:
1. provider_type: "file" (only option currently)
2. n_same: int (1-10) — max same-ticker entries to retrieve
3. n_cross: int (1-10) — max cross-ticker entries to retrieve
4. max_context_length: int (1000-6000) — soft cap on retrieved context
5. format_style: "full" | "reflection_only" | "summary"
6. selection_strategy: "recency" | "rating_grouped" | "outcome_weighted"
7. rotation_max_entries: int or null
8. dedup_enabled: bool

Return as JSON array of config objects. Each config should address at least one diagnosed issue."""

        response = self.llm.invoke([("system", "You are a memory architecture designer. Output only valid JSON."),
                                     ("human", prompt)])
        return response.content

    def _parse_proposals(self, llm_output: str, current_config: MemoryConfig) -> List[MemoryConfig]:
        """Parse LLM JSON output into MemoryConfig objects."""
        try:
            # Extract JSON from possible markdown wrapping
            import re
            json_match = re.search(r'\[.*\]', llm_output, re.DOTALL)
            if json_match:
                proposals = json.loads(json_match.group())
            else:
                proposals = json.loads(llm_output)

            configs = []
            for p in proposals:
                config = MemoryConfig(
                    provider_type=p.get("provider_type", "file"),
                    n_same=p.get("n_same", current_config.n_same),
                    n_cross=p.get("n_cross", current_config.n_cross),
                    max_context_length=p.get("max_context_length", current_config.max_context_length),
                    format_style=p.get("format_style", current_config.format_style),
                    selection_strategy=p.get("selection_strategy", current_config.selection_strategy),
                    rotation_max_entries=p.get("rotation_max_entries", current_config.rotation_max_entries),
                    dedup_enabled=p.get("dedup_enabled", current_config.dedup_enabled),
                )
                configs.append(config)
            return configs
        except (json.JSONDecodeError, KeyError, TypeError):
            return []

    def _simulate_config(self, config: MemoryConfig,
                         feedback_history: List[EvolutionFeedback]) -> float:
        """Simulate effectiveness of a config on historical data."""
        # Simple simulation: weight by how well config params match historical patterns
        score = 0.5  # Baseline

        # Reward configs that would have reduced context bloat
        avg_context = sum(f.memory_context_length for f in feedback_history) / max(len(feedback_history), 1)
        if config.max_context_length < avg_context:
            score += 0.1  # Would have prevented bloat

        # Reward configs with appropriate n_same/n_cross
        if config.n_same >= 3 and config.n_same <= 7:
            score += 0.05
        if config.n_cross >= 2 and config.n_cross <= 5:
            score += 0.05

        # Reward rotation for large histories
        if config.rotation_max_entries and config.rotation_max_entries >= 20:
            score += 0.05

        return min(score, 1.0)

    def _estimate_context_cost(self, config: MemoryConfig) -> float:
        """Estimate context window cost of a config."""
        # Rough estimate: entries * avg_chars_per_entry
        avg_chars = 400
        total_chars = (config.n_same + config.n_cross) * avg_chars
        return total_chars

    def _estimate_complexity(self, config: MemoryConfig) -> float:
        """Estimate implementation complexity (lower = simpler)."""
        complexity = 0
        complexity += 1 if config.selection_strategy != "recency" else 0
        complexity += 1 if config.format_style != "full" else 0
        complexity += 1 if config.dedup_enabled else 0
        return complexity

    def _log_evolution(self, old_config: MemoryConfig, new_config: MemoryConfig) -> None:
        """Log evolution event."""
        if not self._log_path:
            return
        event = {
            "timestamp": datetime.now().isoformat(),
            "old_config": asdict(old_config),
            "new_config": asdict(new_config),
            "changes": {k: v for k, v in asdict(new_config).items()
                       if v != getattr(old_config, k, None)},
        }
        with open(self._log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(event) + "\n")
```

### 6.2 Evolution Trigger in Trading Graph

**File:** `tradingagents/graph/trading_graph.py` — additions

```python
# In __init__():
from tradingagents.memory.evolution import MemoryEvolver
evolution_log_path = os.path.join(
    os.path.expanduser("~"), ".tradingagents", "memory", "evolution_log.jsonl"
)
self.memory_evolver = MemoryEvolver(
    llm=self.quick_thinking_llm,  # Or deep_think_llm for higher quality
    provider=self.memory_provider,
    evolution_log_path=evolution_log_path,
)

# In _run_graph(), after effectiveness analysis:
# Check if evolution should trigger
feedback_history = self.effectiveness_analyzer.get_feedback_history()
evolution_config = self.config.get("memory", {})
if evolution_config.get("evolution_enabled", False):
    if self.memory_evolver.should_evolve(
        feedback_history,
        trigger_runs=evolution_config.get("evolution_trigger_runs", 20),
        min_effectiveness=evolution_config.get("evolution_min_effectiveness", 0.2),
    ):
        # Run evolution
        dry_run = evolution_config.get("dry_run", True)
        self._run_evolution(feedback_history, dry_run=dry_run)

def _run_evolution(self, feedback_history: List[EvolutionFeedback], dry_run: bool = True) -> None:
    """Execute the diagnose-and-design evolution loop."""
    # 1. Diagnose
    report = self.memory_evolver.diagnose(feedback_history)

    # 2. Design
    candidates = self.memory_evolver.design(report)

    # 3. Select
    best_config = self.memory_evolver.select_best(candidates, feedback_history)

    # 4. Apply (or log if dry run)
    if dry_run:
        logger.info(
            "[Memory Evolution - DRY RUN] Proposed config changes: %s",
            {k: v for k, v in asdict(best_config).items()
             if v != getattr(self.memory_provider.get_config(), k, None)},
        )
    else:
        changed = self.memory_evolver.apply(best_config)
        if changed:
            logger.info("[Memory Evolution] Applied new config: %s", asdict(best_config))
```

### 6.3 Phase 3 Deliverables Checklist

- [ ] `tradingagents/memory/evolution.py` — diagnose + design + select
- [ ] LLM prompts for diagnosis and design (embedded in evolver)
- [ ] Pareto selection implementation
- [ ] Evolution trigger logic in `_run_graph()`
- [ ] Dry-run mode (default enabled for safety)
- [ ] Evolution log file at `~/.tradingagents/memory/evolution_log.jsonl`
- [ ] Tests for evolution trigger conditions
- [ ] Tests for config parsing from LLM output

---

## 7. Phase 4: Advanced Memory Providers

**Timeline:** Week 5-6
**Goal:** Implement evolved memory strategies inspired by MemEvolve's successful architectures.

### 7.1 RatingGroupedProvider

**File:** `tradingagents/memory/rating_grouped_provider.py`

```python
"""Memory provider that groups entries by rating instead of pure recency.

Inspired by MemEvolve's finding that hierarchical organization improves
retrieval quality. Provides balanced view: entries matching current market
signal + contrarian perspective.
"""

from __future__ import annotations

from typing import List, Dict
from .provider import MemoryProvider, MemoryConfig, MemoryEntry, MemoryRequest, MemoryResponse
from .file_provider import FileMemoryProvider


class RatingGroupedProvider(FileMemoryProvider):
    """Groups memory by rating (Buy/Sell/Hold) for smarter retrieval."""

    def retrieve(self, request: MemoryRequest) -> MemoryResponse:
        import time
        start = time.time()
        entries = self._load_entries()
        resolved = [e for e in entries if not e.pending]

        if not resolved:
            return MemoryResponse(context="", entries=[], total_available=len(entries))

        # Group by rating
        by_rating: Dict[str, List[MemoryEntry]] = {}
        for e in reversed(resolved):
            by_rating.setdefault(e.rating, []).append(e)

        # Determine current market signal (from most recent same-ticker entry)
        same_ticker = [e for e in resolved if e.ticker == request.ticker]
        current_signal = same_ticker[0].rating if same_ticker else None

        # Select entries: 3 same-signal, 2 opposite-signal, 2 cross-ticker
        selected = []
        opposite_ratings = [r for r in ["Sell", "Underweight", "Hold", "Overweight", "Buy"]
                           if r != current_signal]

        # Same-signal entries
        if current_signal and current_signal in by_rating:
            selected.extend(by_rating[current_signal][:3])

        # Opposite-signal entries (contrarian view)
        for rating in opposite_ratings:
            if rating in by_rating and len(selected) < 5:
                selected.extend([e for e in by_rating[rating][:1] if e.ticker == request.ticker])

        # Cross-ticker entries (any rating)
        cross = [e for e in resolved if e.ticker != request.ticker and e not in selected]
        selected.extend(cross[:request.n_cross])

        context = self._format_context_grouped(request.ticker, selected, current_signal)
        elapsed = (time.time() - start) * 1000

        return MemoryResponse(
            context=context,
            entries=selected,
            total_available=len(entries),
            retrieval_time_ms=elapsed,
        )

    def _format_context_grouped(self, ticker: str, entries: List[MemoryEntry],
                                 current_signal: str) -> str:
        parts = []
        if current_signal:
            parts.append(f"Past analyses of {ticker} with '{current_signal}' signal:")
        else:
            parts.append(f"Past analyses of {ticker}:")

        for e in entries[:5]:
            parts.append(self._format_full(e))

        cross = [e for e in entries if e.ticker != ticker]
        if cross:
            parts.append("Cross-ticker lessons:")
            for e in cross[:self.config.n_cross]:
                parts.append(self._format_reflection_only(e))

        return "\n\n".join(parts)
```

### 7.2 OutcomeWeightedProvider

**File:** `tradingagents/memory/outcome_weighted_provider.py`

```python
"""Memory provider that weights retrieval by historical alpha performance.

High-alpha entries get priority. Includes both successful and failed
reflections for balanced learning.
"""

from __future__ import annotations

from typing import List
from .provider import MemoryProvider, MemoryConfig, MemoryEntry, MemoryRequest, MemoryResponse
from .file_provider import FileMemoryProvider


class OutcomeWeightedProvider(FileMemoryProvider):
    """Weights memory entries by their historical alpha return."""

    def retrieve(self, request: MemoryRequest) -> MemoryResponse:
        import time
        start = time.time()
        entries = self._load_entries()
        resolved = [e for e in entries if not e.pending]

        if not resolved:
            return MemoryResponse(context="", entries=[], total_available=len(entries))

        # Score entries by |alpha_return| (absolute performance magnitude)
        def entry_score(e: MemoryEntry) -> float:
            if e.alpha_return is None:
                return 0.0
            return abs(e.alpha_return)  # High magnitude = informative (win or loss)

        # Separate same-ticker and cross-ticker
        same = [e for e in resolved if e.ticker == request.ticker]
        cross = [e for e in resolved if e.ticker != request.ticker]

        # Sort by score descending
        same.sort(key=entry_score, reverse=True)
        cross.sort(key=entry_score, reverse=True)

        # Select top entries
        selected = same[:request.n_same] + cross[:request.n_cross]

        context = self._format_context_weighted(request.ticker, selected)
        elapsed = (time.time() - start) * 1000

        return MemoryResponse(
            context=context,
            entries=selected,
            total_available=len(entries),
            retrieval_time_ms=elapsed,
        )

    def _format_context_weighted(self, ticker: str, entries: List[MemoryEntry]) -> str:
        parts = []
        parts.append(f"Past analyses of {ticker} (ranked by outcome impact):")

        for e in entries:
            alpha_str = f"{e.alpha_return:+.1%}" if e.alpha_return else "pending"
            tag = f"[{e.date} | {e.ticker} | {e.rating} | alpha: {alpha_str}]"
            parts.append(tag)
            if e.reflection:
                parts.append(e.reflection)
            else:
                parts.append(e.decision[:200] + "...")
            parts.append("")

        return "\n".join(parts)
```

### 7.3 Provider Factory

**File:** `tradingagents/memory/factory.py`

```python
"""Factory for creating memory providers from config."""

from __future__ import annotations

from typing import Optional
from .provider import MemoryProvider, MemoryConfig


def create_provider(config: MemoryConfig, log_path: Optional[str] = None) -> MemoryProvider:
    """Create memory provider based on config.provider_type."""
    if config.provider_type == "file":
        from .file_provider import FileMemoryProvider
        return FileMemoryProvider(config, log_path=log_path)
    elif config.provider_type == "rating_grouped":
        from .rating_grouped_provider import RatingGroupedProvider
        return RatingGroupedProvider(config, log_path=log_path)
    elif config.provider_type == "outcome_weighted":
        from .outcome_weighted_provider import OutcomeWeightedProvider
        return OutcomeWeightedProvider(config, log_path=log_path)
    else:
        from .file_provider import FileMemoryProvider
        return FileMemoryProvider(config, log_path=log_path)
```

### 7.4 Phase 4 Deliverables Checklist

- [ ] `tradingagents/memory/rating_grouped_provider.py`
- [ ] `tradingagents/memory/outcome_weighted_provider.py`
- [ ] `tradingagents/memory/factory.py` — provider factory
- [ ] Provider selection in config (`memory.provider`)
- [ ] Benchmarking script to compare providers
- [ ] Tests for each provider's retrieval logic

---

## 8. Phase 5: Integration, CLI & Validation

**Timeline:** Week 7-8
**Goal:** User-facing features, CLI commands, comprehensive testing.

### 8.1 CLI Memory Report Command

**File:** `cli/memory_cmd.py`

```python
"""CLI commands for memory inspection and evolution reporting."""

import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from pathlib import Path
import os
import json

console = Console()
memory_app = typer.Typer(help="Memory system inspection and evolution management")


@memory_app.command("status")
def status():
    """Show current memory system status."""
    from tradingagents.memory.provider import MemoryConfig
    from tradingagents.memory.file_provider import FileMemoryProvider

    log_path = os.path.join(os.path.expanduser("~"), ".tradingagents", "memory", "trading_memory.md")
    config = MemoryConfig()
    provider = FileMemoryProvider(config, log_path=log_path)

    stats = provider.manage()
    feedback_log = os.path.join(os.path.expanduser("~"), ".tradingagents", "memory", "effectiveness_log.jsonl")

    table = Table(title="Memory System Status", show_header=True)
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")
    table.add_row("Total entries", str(stats["total_entries"]))
    table.add_row("Resolved (with outcome)", str(stats["resolved"]))
    table.add_row("Pending (awaiting outcome)", str(stats["pending"]))
    table.add_row("File size", f"{stats['file_size_kb']:.1f} KB")
    table.add_row("Provider type", config.provider_type)
    table.add_row("Selection strategy", config.selection_strategy)
    table.add_row("n_same / n_cross", f"{config.n_same} / {config.n_cross}")
    table.add_row("Rotation limit", str(config.rotation_max_entries or "unlimited"))

    # Effectiveness stats
    if Path(feedback_log).exists():
        from tradingagents.memory.analyzer import MemoryEffectivenessAnalyzer
        analyzer = MemoryEffectivenessAnalyzer(feedback_log)
        eff_stats = analyzer.get_stats()
        table.add_row("Total runs with analysis", str(eff_stats["total_runs"]))
        table.add_row("Avg effectiveness", f"{eff_stats['avg_effectiveness']:.3f}")
        table.add_row("Last 10 runs avg", f"{eff_stats['last_10_avg']:.3f}")

    console.print(table)


@memory_app.command("report")
def report():
    """Show memory evolution report."""
    evolution_log = os.path.join(os.path.expanduser("~"), ".tradingagents", "memory", "evolution_log.jsonl")

    if not Path(evolution_log).exists():
        console.print(Panel("No evolution events recorded yet.", border_style="yellow"))
        return

    events = []
    with open(evolution_log, "r") as f:
        for line in f:
            events.append(json.loads(line))

    table = Table(title="Memory Evolution History", show_header=True)
    table.add_column("Round", style="cyan")
    table.add_column("Timestamp", style="white")
    table.add_column("Changes", style="green")

    for i, event in enumerate(events, 1):
        changes = ", ".join(f"{k}: {v}" for k, v in event.get("changes", {}).items())
        table.add_row(str(i), event["timestamp"][:19], changes or "no changes")

    console.print(table)


@memory_app.command("entries")
def list_entries(ticker: str = typer.Option(None, "--ticker", "-t"),
                 limit: int = typer.Option(10, "--limit", "-n")):
    """List recent memory entries."""
    from tradingagents.memory.provider import MemoryConfig
    from tradingagents.memory.file_provider import FileMemoryProvider

    log_path = os.path.join(os.path.expanduser("~"), ".tradingagents", "memory", "trading_memory.md")
    config = MemoryConfig()
    provider = FileMemoryProvider(config, log_path=log_path)

    entries = provider._load_entries()
    if ticker:
        entries = [e for e in entries if e.ticker == ticker.upper()]

    entries = entries[-limit:]

    table = Table(title=f"Recent Entries ({len(entries)} shown)", show_header=True)
    table.add_column("Date", style="cyan")
    table.add_column("Ticker", style="green")
    table.add_column("Rating", style="yellow")
    table.add_column("Alpha", style="magenta")
    table.add_column("Status", style="white")

    for e in entries:
        alpha = f"{e.alpha_return:+.1%}" if e.alpha_return else "—"
        status = "resolved" if not e.pending else "pending"
        table.add_row(e.date, e.ticker, e.rating, alpha, status)

    console.print(table)
```

### 8.2 Config Schema Addition

**File:** `tradingagents/default_config.py` — additions

```python
DEFAULT_CONFIG = {
    # ... existing config ...

    # Memory evolution configuration
    "memory": {
        "provider": "file",                    # file, rating_grouped, outcome_weighted
        "evolution_enabled": False,            # Opt-in (default off for safety)
        "evolution_trigger_runs": 20,          # Check every N decisions
        "evolution_min_effectiveness": 0.2,    # Force evolve if below this
        "max_context_length": 4000,            # Soft cap for retrieved context
        "evolution_llm": None,                 # Uses deep_think_llm if None
        "dry_run": True,                       # Log proposals without applying
        "n_same": 5,                           # Default same-ticker entries
        "n_cross": 3,                          # Default cross-ticker entries
        "format_style": "full",                # full, reflection_only, summary
        "selection_strategy": "recency",       # recency, rating_grouped, outcome_weighted
        "rotation_max_entries": None,          # Max resolved entries (None = unlimited)
        "dedup_enabled": False,                # Enable semantic deduplication
    },
}
```

### 8.3 Test Suite

**File:** `tests/test_memory_evolution.py`

```python
"""Tests for memory evolution system."""

import pytest
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from tradingagents.memory.provider import MemoryConfig, MemoryEntry, MemoryRequest, EvolutionFeedback
from tradingagents.memory.file_provider import FileMemoryProvider
from tradingagents.memory.analyzer import MemoryEffectivenessAnalyzer
from tradingagents.memory.evolution import MemoryEvolver


# --- Fixtures ---

@pytest.fixture
def tmp_log(tmp_path):
    return str(tmp_path / "trading_memory.md")


@pytest.fixture
def tmp_feedback(tmp_path):
    return str(tmp_path / "effectiveness_log.jsonl")


@pytest.fixture
def tmp_evolution(tmp_path):
    return str(tmp_path / "evolution_log.jsonl")


@pytest.fixture
def provider(tmp_log):
    config = MemoryConfig(rotation_max_entries=10)
    return FileMemoryProvider(config, log_path=tmp_log)


@pytest.fixture
def analyzer(tmp_feedback):
    return MemoryEffectivenessAnalyzer(feedback_log_path=tmp_feedback)


# --- FileMemoryProvider Tests ---

class TestFileMemoryProvider:
    def test_encode_creates_entry(self, provider):
        entry = provider.encode("Rating: Buy\nEnter at $190.", "NVDA", "2026-01-10")
        assert entry.ticker == "NVDA"
        assert entry.rating == "Buy"
        assert entry.pending is True

    def test_store_and_retrieve(self, provider):
        entry = provider.encode("Rating: Buy\nBuy NVDA.", "NVDA", "2026-01-10")
        provider.store(entry)
        response = provider.retrieve(MemoryRequest(ticker="NVDA", trade_date="2026-01-11"))
        # Entry is pending, so not in context
        assert response.context == ""

    def test_idempotent_store(self, provider):
        entry = provider.encode("Rating: Buy", "NVDA", "2026-01-10")
        assert provider.store(entry) is True
        assert provider.store(entry) is True  # Second call is idempotent

    def test_rotation_prunes_oldest(self, tmp_log):
        config = MemoryConfig(rotation_max_entries=3)
        provider = FileMemoryProvider(config, log_path=tmp_log)
        for i in range(5):
            entry = provider.encode(f"Rating: Buy {i}", "NVDA", f"2026-01-{i+1:02d}")
            provider.store(entry)
            entry.pending = False  # Simulate resolved
            provider.update_entry(entry, f"Reflection {i}")
        stats = provider.manage()
        assert stats["resolved"] <= 3


# --- EffectivenessAnalyzer Tests ---

class TestEffectivenessAnalyzer:
    def test_analyze_returns_feedback(self, analyzer, provider):
        feedback = analyzer.analyze(
            past_context="Past analyses of NVDA...",
            pm_decision="Rating: Buy\nNVDA looks strong.",
            historical_entries=[],
            ticker="NVDA",
            trade_date="2026-01-10",
            rating="Buy",
        )
        assert feedback.effectiveness_score is not None
        assert 0.0 <= feedback.effectiveness_score <= 1.0

    def test_ticker_overlap_increases_score(self, analyzer):
        entries = [MemoryEntry(date="2026-01-01", ticker="AAPL", rating="Buy", decision="Buy AAPL", reflection="Good call", pending=False)]
        feedback = analyzer.analyze(
            past_context="[AAPL entry]",
            pm_decision="Rating: Buy\nAAPL momentum continues.",
            historical_entries=entries,
            ticker="NVDA",
            trade_date="2026-01-10",
            rating="Buy",
        )
        assert feedback.decision_matches_memory_pattern is True

    def test_feedback_persisted(self, analyzer, tmp_feedback):
        analyzer.analyze(
            past_context="context",
            pm_decision="Rating: Hold",
            historical_entries=[],
            ticker="NVDA",
            trade_date="2026-01-10",
            rating="Hold",
        )
        assert Path(tmp_feedback).exists()
        lines = Path(tmp_feedback).read_text().strip().splitlines()
        assert len(lines) == 1
        data = json.loads(lines[0])
        assert data["ticker"] == "NVDA"

    def test_stats_computation(self, analyzer):
        # Generate some feedback
        for i in range(5):
            analyzer.analyze(
                past_context="context",
                pm_decision=f"Rating: Buy decision {i}",
                historical_entries=[],
                ticker="NVDA",
                trade_date=f"2026-01-{i+1:02d}",
                rating="Buy",
            )
        stats = analyzer.get_stats()
        assert stats["total_runs"] == 5
        assert "avg_effectiveness" in stats


# --- MemoryEvolver Tests ---

class TestMemoryEvolver:
    def test_should_evolve_periodic(self, provider, tmp_evolution):
        mock_llm = MagicMock()
        evolver = MemoryEvolver(mock_llm, provider, evolution_log_path=tmp_evolution)

        # Not enough feedback
        feedback = [EvolutionFeedback(run_id=f"run_{i}", ticker="NVDA", trade_date="2026-01-10",
                                       decision="Buy", rating="Buy", memory_injected=True,
                                       memory_context_length=1000, outcome_known=False,
                                       effectiveness_score=0.5) for i in range(10)]
        assert evolver.should_evolve(feedback, trigger_runs=20) is False

        # Enough feedback (periodic trigger)
        feedback = [EvolutionFeedback(run_id=f"run_{i}", ticker="NVDA", trade_date="2026-01-10",
                                       decision="Buy", rating="Buy", memory_injected=True,
                                       memory_context_length=1000, outcome_known=False,
                                       effectiveness_score=0.5) for i in range(20)]
        assert evolver.should_evolve(feedback, trigger_runs=20) is True

    def test_should_evolve_low_effectiveness(self, provider, tmp_evolution):
        mock_llm = MagicMock()
        evolver = MemoryEvolver(mock_llm, provider, evolution_log_path=tmp_evolution)

        feedback = [EvolutionFeedback(run_id=f"run_{i}", ticker="NVDA", trade_date="2026-01-10",
                                       decision="Buy", rating="Buy", memory_injected=True,
                                       memory_context_length=1000, outcome_known=False,
                                       effectiveness_score=0.1) for i in range(15)]
        assert evolver.should_evolve(feedback, trigger_runs=20, min_effectiveness=0.2) is True

    def test_diagnose_produces_report(self, provider, tmp_evolution):
        mock_llm = MagicMock()
        mock_llm.invoke.return_value.content = "Analysis complete."
        evolver = MemoryEvolver(mock_llm, provider, evolution_log_path=tmp_evolution)

        feedback = [EvolutionFeedback(run_id=f"run_{i}", ticker="NVDA", trade_date="2026-01-10",
                                       decision="Buy", rating="Buy", memory_injected=True,
                                       memory_context_length=5000, outcome_known=False,
                                       effectiveness_score=0.15) for i in range(20)]
        report = evolver.diagnose(feedback)
        assert len(report.issues) > 0
        assert report.llm_analysis == "Analysis complete."
```

### 8.5 Phase 5 Deliverables Checklist

- [ ] `cli/memory_cmd.py` — status, report, entries commands
- [ ] Integration in `cli/main.py` (add `memory_app` as sub-app)
- [ ] `tradingagents/default_config.py` — memory evolution config
- [ ] `tests/test_memory_evolution.py` — comprehensive test suite
- [ ] Benchmarking script: `scripts/benchmark_providers.py`
- [ ] Documentation: update README with memory evolution features
- [ ] End-to-end test: run 50 decisions, verify evolution triggers and applies

---

## 9. File Structure

```
tradingagents/
├── memory/                          # NEW: Memory evolution system
│   ├── __init__.py
│   ├── provider.py                  # MemoryProvider protocol + dataclasses
│   ├── file_provider.py             # Current behavior (backward compat)
│   ├── rating_grouped_provider.py   # Phase 4: Group by rating
│   ├── outcome_weighted_provider.py # Phase 4: Weight by alpha
│   ├── factory.py                   # Phase 4: Provider factory
│   ├── feedback.py                  # EvolutionFeedback dataclass (in provider.py)
│   ├── analyzer.py                  # Phase 2: Effectiveness tracking
│   └── evolution.py                 # Phase 3: Diagnose-and-Design evolution
├── agents/
│   └── utils/
│       └── memory.py                # TradingMemoryLog → backward compat wrapper
├── graph/
│   └── trading_graph.py             # Updated: provider injection + evolution trigger
├── default_config.py                # Updated: memory evolution config section
└── cli/
    └── memory_cmd.py                # Phase 5: CLI commands

tests/
├── test_memory_log.py               # Existing tests (unchanged)
└── test_memory_evolution.py         # Phase 5: New evolution tests

scripts/
└── benchmark_providers.py           # Phase 5: Provider comparison benchmark

~/.tradingagents/memory/
├── trading_memory.md                # Existing decision log
├── effectiveness_log.jsonl          # Phase 2: Effectiveness feedback
└── evolution_log.jsonl              # Phase 3: Evolution events
```

---

## 10. Config Schema

```python
# Full memory config in DEFAULT_CONFIG
"memory": {
    # Provider selection
    "provider": "file",                    # file | rating_grouped | outcome_weighted

    # Retrieval parameters
    "n_same": 5,                           # Max same-ticker entries (1-10)
    "n_cross": 3,                          # Max cross-ticker entries (1-10)
    "max_context_length": 4000,            # Soft cap on context chars (1000-6000)
    "format_style": "full",                # full | reflection_only | summary
    "selection_strategy": "recency",       # recency | rating_grouped | outcome_weighted

    # Evolution settings
    "evolution_enabled": False,            # Master switch (opt-in)
    "evolution_trigger_runs": 20,          # Check every N decisions
    "evolution_min_effectiveness": 0.2,    # Force evolve below this score
    "evolution_llm": None,                 # LLM for evolution (None = deep_think_llm)
    "dry_run": True,                       # Log proposals without applying

    # Management
    "rotation_max_entries": None,          # Max resolved entries (None = unlimited)
    "dedup_enabled": False,                # Enable semantic deduplication
}
```

---

## 11. Migration Path

| Phase | User Experience | Risk | Rollback |
|-------|----------------|------|----------|
| **Phase 1** | Zero change — identical behavior | None | Delete new files, restore old import |
| **Phase 2** | Silent tracking, writes to sidecar file | None | Delete `effectiveness_log.jsonl` |
| **Phase 3** | Evolution runs in dry-run mode (logs only) | None | Set `dry_run: true` (default) |
| **Phase 4** | User selects provider via config | Low | Change `provider` back to `"file"` |
| **Phase 5** | User enables evolution, sees CLI reports | Low | Set `evolution_enabled: false` |

### Gradual Rollout

```
Week 1-2: Deploy Phase 1-2 → All users get backward compat + silent tracking
Week 3-4: Deploy Phase 3 → Dry-run evolution logs proposals (visible in logs)
Week 5-6: Deploy Phase 4 → Users can experiment with new providers
Week 7-8: Deploy Phase 5 → Full evolution active for opted-in users
```

---

## 12. Testing Strategy

### 12.1 Unit Tests

| Test File | Coverage |
|-----------|----------|
| `test_memory_log.py` | Existing tests — must pass unchanged |
| `test_memory_evolution.py` | Provider encode/store/retrieve, analyzer scoring, evolution triggers |
| `test_provider_factory.py` | All provider types create correctly |
| `test_rating_grouped.py` | Rating grouping logic, contrarian selection |
| `test_outcome_weighted.py` | Alpha-weighted sorting, pending entry handling |

### 12.2 Integration Tests

| Test | Description |
|------|-------------|
| `test_full_cycle` | Store → retrieve → analyze → evolve → apply |
| `test_50_decisions` | Run 50 decisions, verify evolution triggers at run 20 and 40 |
| `test_provider_switch` | Switch from file to rating_grouped, verify context changes |
| `test_dry_run` | Verify dry-run mode logs but doesn't modify provider |

### 12.3 Performance Tests

| Test | Metric | Threshold |
|------|--------|-----------|
| `test_retrieve_latency` | Time to retrieve context | < 50ms for 100 entries |
| `test_file_parse_time` | Time to parse markdown file | < 100ms for 500KB file |
| `test_evolution_cost` | LLM calls per evolution cycle | ≤ 2 calls (diagnose + design) |

---

## 13. Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| LLM proposes invalid config | Medium | Low | JSON validation + fallback to current config |
| Evolution degrades performance | Low | High | Dry-run default + effectiveness threshold gating |
| File corruption during rotation | Low | High | Atomic writes via `os.replace()` (existing) |
| Context window overflow | Medium | Medium | `max_context_length` soft cap + truncation |
| Cross-ticker pending accumulation | Medium | Low | Same-ticker-only resolution (existing behavior) |
| Provider switch breaks downstream | Low | Medium | All providers conform to same protocol |
| Effectiveness scoring is noisy | High | Low | Composite score (3 signals) + 10-run smoothing |

---

## 14. Success Metrics

### 14.1 Quantitative

| Metric | Baseline | Target | Measurement |
|--------|----------|--------|-------------|
| Memory effectiveness score | N/A | > 0.5 avg | `effectiveness_log.jsonl` |
| Context utilization rate | N/A | > 60% of runs reference memory | Analyzer pattern match |
| Evolution adoption | N/A | > 50% of active users enable | Config telemetry |
| Retrieval latency | ~30ms (100 entries) | < 50ms (500 entries) | `retrieval_time_ms` in response |
| File growth rate | Unbounded | < 100KB/month with rotation | `file_size_kb` in manage stats |

### 14.2 Qualitative

| Criterion | Success Signal |
|-----------|---------------|
| Backward compatibility | All existing tests pass, zero behavioral change in Phase 1 |
| User control | Evolution is opt-in, dry-run default, easy rollback |
| Actionable insights | Evolution log shows clear before/after config changes |
| Domain relevance | Evolved configs improve alpha return or rating accuracy |
| Cost efficiency | Evolution costs ≤ 2 LLM calls per cycle |

---

## Appendix A: MemEvolve Paper Mapping

| MemEvolve Concept | TradingAgents Implementation | Paper Section |
|-------------------|------------------------------|---------------|
| Encode (E) | `MemoryProvider.encode()` — extracts rating, parses decision | §3.2 |
| Store (U) | `MemoryProvider.store()` — appends to markdown file | §3.2 |
| Retrieve (R) | `MemoryProvider.retrieve()` — configurable strategy | §3.2 |
| Manage (G) | `MemoryProvider.manage()` — rotation, pruning | §3.2 |
| Inner Loop | Every run: encode → store → retrieve → manage | §4.1 |
| Outer Loop | Every N runs: diagnose → design → select → apply | §4.1 |
| Diagnose-and-Design | `MemoryEvolver.diagnose()` + `.design()` | §4.2 |
| Pareto Selection | `MemoryEvolver.select_best()` — multi-objective ranking | §4.2 |
| BaseMemoryProvider ABC | `MemoryProvider` abstract class | §A.1 |
| Evolution Feedback | `EvolutionFeedback` dataclass + JSONL log | §4.1 |

---

## Appendix B: Comparison with Existing Memory Systems

| System | Encode | Store | Retrieve | Manage | Evolves? |
|--------|--------|-------|----------|--------|----------|
| **TradingMemoryLog (current)** | Rating extraction | Markdown file | Recency (5+3) | Optional rotation | No |
| **FileMemoryProvider (Phase 1)** | Rating extraction | Markdown file | Recency (configurable) | Configurable rotation | No |
| **+ Effectiveness (Phase 2)** | + metadata scoring | + sidecar log | + effectiveness filter | — | Tracks only |
| **+ Evolution (Phase 3)** | LLM-analyzed | — | LLM-proposed configs | Auto-tuned | Yes (config) |
| **RatingGrouped (Phase 4)** | + rating grouping | Markdown file | By rating signal | — | No |
| **OutcomeWeighted (Phase 4)** | + alpha scoring | Markdown file | By \|alpha\| | — | No |
| **MemEvolve (paper)** | LLM-generated | Vector DB / JSON / Graph | Hybrid + LLM guard | LLM consolidation | Yes (code) |

---

*Document generated: 2026-05-17*
*Version: 1.0*
*Status: Ready for implementation*
