"""Structured diff engine translating attorney edits into review events."""

from __future__ import annotations

import difflib
from datetime import datetime
from pathlib import Path
import sqlite3
from typing import Dict, Iterable, List, Sequence

from .models import DraftDocument, DraftPackage, DraftSegment, ReviewEvent


class DocumentParser:
    """Converts raw documents into comparable text segments."""

    def parse(self, package: DraftPackage) -> Dict[str, str]:
        parsed = {}
        for document in package.documents:
            for segment in document.segments:
                parsed[segment.segment_id] = segment.text
        return parsed


class PackageLoader:
    """Builds `DraftPackage` instances from text or PDF sources."""

    def from_path(self, path: Path, case_id: str, doc_type: str = "petition_letter") -> DraftPackage:
        if path.suffix.lower() == ".pdf":
            text = self._load_pdf(path)
        else:
            text = path.read_text(encoding="utf-8")

        segments = self._segment_text(text, doc_type)
        return DraftPackage(case_id=case_id, documents=[DraftDocument(doc_type=doc_type, segments=segments)])

    def _segment_text(self, text: str, doc_type: str) -> List[DraftSegment]:
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        if not paragraphs:
            paragraphs = [text.strip()]

        segments: List[DraftSegment] = []
        for idx, paragraph in enumerate(paragraphs, start=1):
            criterion = f"section_{idx}"
            segments.append(
                DraftSegment(
                    segment_id=f"{doc_type}-{idx}",
                    criterion=criterion,
                    text=paragraph,
                )
            )
        return segments

    def _load_pdf(self, path: Path) -> str:
        import importlib.util

        if importlib.util.find_spec("PyPDF2") is None:
            raise RuntimeError("PyPDF2 is required to parse PDF files.")

        import PyPDF2

        try:
            with path.open("rb") as f:
                reader = PyPDF2.PdfReader(f)
                return "\n".join(page.extract_text() or "" for page in reader.pages)
        except Exception as exc:  # pragma: no cover - defensive clause for runtime environments
            raise RuntimeError("Unable to load or parse PDF file") from exc


class SegmentAligner:
    """Aligns draft and final documents by segment id."""

    def align(self, draft_segments: Dict[str, str], final_segments: Dict[str, str]) -> Iterable[str]:
        return draft_segments.keys() & final_segments.keys()


class DiffExtractor:
    """Extracts edit signals using edit distance."""

    def extract(self, draft_text: str, final_text: str) -> int:
        if draft_text == final_text:
            return 0

        sequence = difflib.SequenceMatcher(a=draft_text, b=final_text)
        distance = int(1 - sequence.ratio() * max(len(draft_text), len(final_text)))
        return max(distance, 1)


class AttributionEngine:
    """Assigns deterministic reason codes based on simple heuristics."""

    def attribute(self, draft_text: str, final_text: str) -> List[str]:
        reasons: List[str] = []
        if draft_text == final_text:
            return ["no_change"]
        if len(final_text) > len(draft_text):
            reasons.append("expanded_detail")
        if len(final_text) < len(draft_text):
            reasons.append("trimmed_excess")
        if draft_text.lower() != final_text.lower():
            reasons.append("style_adjustment")
        return reasons or ["other"]


class StructuredDiffEngine:
    """Coordinated pipeline producing review events."""

    def __init__(self) -> None:
        self.parser = DocumentParser()
        self.aligner = SegmentAligner()
        self.diff = DiffExtractor()
        self.attribution = AttributionEngine()

    def diff_package(self, draft: DraftPackage, final: DraftPackage, applicant_signature: str) -> List[ReviewEvent]:
        draft_segments = self.parser.parse(draft)
        final_segments = self.parser.parse(final)

        aligned_ids = self.aligner.align(draft_segments, final_segments)
        review_events: List[ReviewEvent] = []

        for segment_id in aligned_ids:
            draft_text = draft_segments[segment_id]
            final_text = final_segments[segment_id]
            distance = self.diff.extract(draft_text, final_text)
            reason_codes = self.attribution.attribute(draft_text, final_text)
            severity = self._severity(distance)

            review_events.append(
                ReviewEvent(
                    case_id=draft.case_id,
                    segment_id=segment_id,
                    criterion=self._criterion_from_segment(segment_id),
                    applicant_signature=applicant_signature,
                    reason_codes=reason_codes,
                    edit_distance=distance,
                    severity=severity,
                    timestamp=datetime.utcnow(),
                )
            )

        return review_events

    def diff_and_store(
        self,
        draft: DraftPackage,
        final: DraftPackage,
        applicant_signature: str,
        database: "DiffDatabase",
    ) -> List[ReviewEvent]:
        events = self.diff_package(draft, final, applicant_signature)
        database.write_events(events)
        return events

    def _severity(self, distance: int) -> str:
        if distance == 0:
            return "none"
        if distance < 50:
            return "minor"
        if distance < 200:
            return "moderate"
        return "major"

    def _criterion_from_segment(self, segment_id: str) -> str:
        if "-" in segment_id:
            return segment_id.split("-")[1]
        return "unknown"


class DiffDatabase:
    """SQLite-backed storage for review events produced by the structured diff."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS review_events (
                    case_id TEXT,
                    segment_id TEXT,
                    criterion TEXT,
                    applicant_signature TEXT,
                    reason_codes TEXT,
                    edit_distance INTEGER,
                    severity TEXT,
                    timestamp TEXT
                )
                """
            )

    def write_events(self, events: Sequence[ReviewEvent]) -> None:
        with sqlite3.connect(self.path) as conn:
            conn.executemany(
                """
                INSERT INTO review_events (
                    case_id,
                    segment_id,
                    criterion,
                    applicant_signature,
                    reason_codes,
                    edit_distance,
                    severity,
                    timestamp
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        event.case_id,
                        event.segment_id,
                        event.criterion,
                        event.applicant_signature,
                        ",".join(event.reason_codes),
                        event.edit_distance,
                        event.severity,
                        event.timestamp.isoformat(),
                    )
                    for event in events
                ],
            )

    def load_events(self) -> List[ReviewEvent]:
        with sqlite3.connect(self.path) as conn:
            cursor = conn.execute(
                "SELECT case_id, segment_id, criterion, applicant_signature, reason_codes, edit_distance, severity, timestamp FROM review_events"
            )
            rows = cursor.fetchall()
        return [
            ReviewEvent(
                case_id=row[0],
                segment_id=row[1],
                criterion=row[2],
                applicant_signature=row[3],
                reason_codes=row[4].split(",") if row[4] else [],
                edit_distance=int(row[5]),
                severity=row[6],
                timestamp=datetime.fromisoformat(row[7]),
            )
            for row in rows
        ]
