"""Small demonstration for the StructuredDiffEngine."""

from policy_doc_agent.models import DraftDocument, DraftPackage, DraftSegment
from policy_doc_agent.structured_diff import StructuredDiffEngine


def main() -> None:
    draft = DraftPackage(
        case_id="demo-case",
        documents=[
            DraftDocument(
                doc_type="petition_letter",
                segments=[
                    DraftSegment(segment_id="petition_letter-1", criterion="section_1", text="Initial wording."),
                    DraftSegment(segment_id="petition_letter-2", criterion="section_2", text="Details about the applicant."),
                ],
            )
        ],
    )

    final = DraftPackage(
        case_id="demo-case",
        documents=[
            DraftDocument(
                doc_type="petition_letter",
                segments=[
                    DraftSegment(
                        segment_id="petition_letter-1",
                        criterion="section_1",
                        text="Initial wording updated with stronger language.",
                    ),
                    DraftSegment(
                        segment_id="petition_letter-2",
                        criterion="section_2",
                        text="Details about the applicant.",
                    ),
                ],
            )
        ],
    )

    engine = StructuredDiffEngine()
    events = engine.diff_package(draft, final, applicant_signature="demo-sig")

    for event in events:
        print(
            f"Segment {event.segment_id} ({event.criterion}): distance={event.edit_distance}, "
            f"severity={event.severity}, reasons={','.join(event.reason_codes)}"
        )


if __name__ == "__main__":
    main()
