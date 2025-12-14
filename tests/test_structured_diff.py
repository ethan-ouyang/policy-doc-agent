import datetime
from pathlib import Path

from policy_doc_agent.models import DraftDocument, DraftPackage, DraftSegment
from policy_doc_agent.structured_diff import DiffDatabase, DiffExtractor, StructuredDiffEngine


def build_package(case_id: str, doc_type: str, segments: list[str]) -> DraftPackage:
    return DraftPackage(
        case_id=case_id,
        documents=[
            DraftDocument(
                doc_type=doc_type,
                segments=[
                    DraftSegment(segment_id=f"{doc_type}-{idx+1}", criterion=f"section_{idx+1}", text=text)
                    for idx, text in enumerate(segments)
                ],
            )
        ],
    )


def test_diff_package_outputs_expected_review_events():
    engine = StructuredDiffEngine()

    draft = build_package("case-123", "petition_letter", ["Original paragraph.", "Second part stays the same."])
    final = build_package(
        "case-123",
        "petition_letter",
        ["Original paragraph rewritten with more detail.", "Second part stays the same."],
    )

    events = engine.diff_package(draft, final, applicant_signature="signature-xyz")

    assert {event.segment_id for event in events} == {"petition_letter-1", "petition_letter-2"}

    changed_event = next(event for event in events if event.segment_id == "petition_letter-1")
    unchanged_event = next(event for event in events if event.segment_id == "petition_letter-2")

    expected_distance = DiffExtractor().extract(
        draft.documents[0].segments[0].text, final.documents[0].segments[0].text
    )

    assert changed_event.edit_distance == expected_distance
    assert changed_event.case_id == "case-123"
    assert changed_event.criterion == "1"
    assert "expanded_detail" in changed_event.reason_codes
    assert changed_event.severity in {"minor", "moderate", "major"}
    assert isinstance(changed_event.timestamp, datetime.datetime)

    assert unchanged_event.edit_distance == 0
    assert unchanged_event.severity == "none"
    assert unchanged_event.reason_codes == ["no_change"]


def test_diff_and_store_round_trip(tmp_path: Path):
    engine = StructuredDiffEngine()
    database = DiffDatabase(tmp_path / "events.db")

    draft = build_package("case-789", "petition_letter", ["Short text."])
    final = build_package("case-789", "petition_letter", ["Short text with extra detail."])

    events = engine.diff_and_store(draft, final, applicant_signature="sig-123", database=database)
    loaded_events = database.load_events()

    assert len(events) == len(loaded_events) == 1

    event = loaded_events[0]
    assert event.case_id == "case-789"
    assert event.segment_id == "petition_letter-1"
    assert "expanded_detail" in event.reason_codes
    assert event.edit_distance == events[0].edit_distance
    assert event.timestamp == events[0].timestamp
