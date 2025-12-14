"""Policy evolution engine turning review events into constraints."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import asdict
from datetime import datetime
from typing import Dict, Iterable, List, Sequence

from .models import FailurePattern, Policy, ReviewEvent


class SignalStore:
    """Stores review events for later aggregation."""

    def __init__(self) -> None:
        self._events: List[ReviewEvent] = []

    def add_events(self, events: Iterable[ReviewEvent]) -> None:
        self._events.extend(events)

    def all_events(self) -> List[ReviewEvent]:
        return list(self._events)


class PatternAggregator:
    """Aggregates review events into failure patterns."""

    def aggregate(self, events: Sequence[ReviewEvent]) -> List[FailurePattern]:
        grouped: Dict[tuple, Counter] = defaultdict(Counter)

        for event in events:
            key = (event.criterion, event.applicant_signature)
            for reason in event.reason_codes:
                grouped[key][reason] += 1

        patterns: List[FailurePattern] = []
        for (criterion, signature), reason_counts in grouped.items():
            for reason_code, count in reason_counts.items():
                confidence = min(1.0, count / 10)
                pattern_id = f"{criterion}:{signature}:{reason_code}"
                patterns.append(
                    FailurePattern(
                        pattern_id=pattern_id,
                        criterion=criterion,
                        signature=signature,
                        reason_code=reason_code,
                        count=count,
                        confidence=confidence,
                    )
                )

        return patterns


class PolicyCompiler:
    """Deterministically translates patterns into policies."""

    def compile(self, patterns: Sequence[FailurePattern], version: int) -> List[Policy]:
        policies: List[Policy] = []
        for pattern in patterns:
            scope = pattern.signature
            constraints = {pattern.criterion: self._constraint_for_reason(pattern.reason_code)}
            verification = {pattern.criterion: "VerifierAgent"}

            policies.append(
                Policy(
                    policy_id=f"policy:{pattern.pattern_id}",
                    version=version,
                    scope=scope,
                    constraints=constraints,
                    verification=verification,
                    created_at=datetime.utcnow(),
                )
            )
        return policies

    def _constraint_for_reason(self, reason_code: str) -> str:
        mapping = {
            "expanded_detail": "mandatory",
            "trimmed_excess": "concise",
            "style_adjustment": "no-first-person",
        }
        return mapping.get(reason_code, "informational")


def evolve_and_activate_policies(
    events: Sequence[ReviewEvent],
    pattern_aggregator: PatternAggregator,
    compiler: PolicyCompiler,
    policy_store: PolicyStore,
    version: int,
) -> List[Policy]:
    """End-to-end helper to evolve policies and activate them for generation."""

    patterns = pattern_aggregator.aggregate(events)
    policies = compiler.compile(patterns, version=version)
    policy_store.add(policies)
    return policies


class PolicyStore:
    """Versioned, rollback-safe store for policies."""

    def __init__(self) -> None:
        self._policies: List[Policy] = []

    def add(self, policies: Iterable[Policy]) -> None:
        self._policies.extend(policies)

    def active_for_scope(self, applicant_signature: str) -> List[Policy]:
        return [p for p in self._policies if p.scope == applicant_signature]

    def all_policies(self) -> List[Policy]:
        return list(self._policies)

    def to_dict(self) -> List[Dict]:
        return [asdict(policy) for policy in self._policies]
