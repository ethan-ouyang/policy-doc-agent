"""Policy-driven EB-1 package generation agents."""

from __future__ import annotations

import itertools
import re
from typing import Dict, Iterable, List, Sequence

from .models import DraftDocument, DraftPackage, DraftSegment, PlannerPlan, Policy


class PlannerAgent:
    """Builds a deterministic generation plan based on policies and applicant data."""

    def build_plan(self, applicant_profile: Dict[str, str], policies: Sequence[Policy]) -> PlannerPlan:
        applicant_signature = self._signature(applicant_profile)
        document_plan: Dict[str, List[str]] = {
            "petition_letter": ["introduction", "achievements", "conclusion"],
            "recommendation_letters": ["authorship", "impact"],
            "exhibits": ["publications", "awards"],
        }

        for policy in policies:
            for criterion, requirement in policy.constraints.items():
                if requirement == "mandatory" and criterion not in document_plan.get("petition_letter", []):
                    document_plan.setdefault("petition_letter", []).append(criterion)

        retrieval_queries = [f"similar_cases:{applicant_profile.get('field', 'general')}"]
        retrieval_queries.extend(applicant_profile.get("keywords", "").split(","))

        return PlannerPlan(
            case_id=applicant_profile.get("case_id", "unknown"),
            applicant_signature=applicant_signature,
            document_plan=document_plan,
            retrieval_queries=[q.strip() for q in retrieval_queries if q],
        )

    def _signature(self, applicant_profile: Dict[str, str]) -> str:
        field = applicant_profile.get("field", "general").lower()
        country = applicant_profile.get("country", "unknown").lower()
        return f"{field}:{country}"


def _extract_field(resume_text: str) -> str:
    """Naively infer the applicant field from a resume string."""

    keywords = {
        "biology": ["biology", "biotech", "bio"],
        "computer_science": ["machine learning", "software", "ai", "data"],
        "physics": ["physics", "astronomy", "quantum"],
        "engineering": ["engineering", "mechanical", "civil", "electrical"],
    }

    lowered = resume_text.lower()
    for field, triggers in keywords.items():
        if any(trigger in lowered for trigger in triggers):
            return field
    return "general"


def profile_from_resume(resume_text: str, case_id: str) -> Dict[str, str]:
    """Convert a raw resume into the applicant profile used by the planner.

    This helper intentionally uses deterministic, regex-based extraction to satisfy
    the constraint that the system learns via policies rather than training.
    """

    country_match = re.search(r"\bCitizen(?:ship)?:\s*(?P<country>[A-Za-z ]+)", resume_text)
    country = country_match.group("country").strip().lower() if country_match else "unknown"

    keywords_match = re.findall(r"\b(skills|keywords):\s*(.+)", resume_text, flags=re.IGNORECASE)
    keywords = ",".join(match[1] for match in keywords_match) if keywords_match else ""

    return {
        "case_id": case_id,
        "field": _extract_field(resume_text),
        "country": country,
        "keywords": keywords,
    }


class DraftingAgent:
    """Creates draft content strictly following the planner plan."""

    def draft(self, plan: PlannerPlan) -> DraftPackage:
        documents: List[DraftDocument] = []

        for doc_type, criteria in plan.document_plan.items():
            segments = [
                DraftSegment(
                    segment_id=f"{doc_type}-{idx}",
                    criterion=criterion,
                    text=self._segment_text(plan.case_id, doc_type, criterion),
                )
                for idx, criterion in enumerate(criteria, start=1)
            ]
            documents.append(DraftDocument(doc_type=doc_type, segments=segments))

        return DraftPackage(case_id=plan.case_id, documents=documents)

    def _segment_text(self, case_id: str, doc_type: str, criterion: str) -> str:
        return (
            f"Case {case_id}: {doc_type.replace('_', ' ').title()} segment for {criterion}. "
            "All content generated under current policy constraints."
        )


class RAGAgent:
    """Retrieves related exhibits and precedent cases.

    In this deterministic implementation, retrieval is mocked via canned references
    tied to retrieval queries.
    """

    def retrieve(self, retrieval_queries: Iterable[str]) -> Dict[str, List[str]]:
        return {query: [f"retrieved:{query}:example"] for query in retrieval_queries}


class VerifierAgent:
    """Enforces hard constraints on generated drafts."""

    def verify(self, draft: DraftPackage, policies: Sequence[Policy]) -> Dict[str, List[str]]:
        issues: Dict[str, List[str]] = {}
        constraint_lookup = self._constraint_lookup(policies)

        for document in draft.documents:
            for segment in document.segments:
                required = constraint_lookup.get(segment.criterion)
                if required == "mandatory" and not segment.text.strip():
                    issues.setdefault(segment.segment_id, []).append("missing_mandatory_text")
                if required == "no-first-person" and " I " in segment.text:
                    issues.setdefault(segment.segment_id, []).append("first_person_violation")

        return issues

    def _constraint_lookup(self, policies: Sequence[Policy]) -> Dict[str, str]:
        merged = itertools.chain.from_iterable(policy.constraints.items() for policy in policies)
        return {criterion: rule for criterion, rule in merged}


def generate_package(applicant_profile: Dict[str, str], policies: Sequence[Policy]) -> DraftPackage:
    """High-level API for producing a constrained draft package."""

    planner = PlannerAgent()
    drafting = DraftingAgent()
    verifier = VerifierAgent()

    plan = planner.build_plan(applicant_profile, policies)
    draft = drafting.draft(plan)
    issues = verifier.verify(draft, policies)

    if issues:
        raise ValueError(f"Draft rejected by verifier due to policy violations: {issues}")

    return draft


def generate_package_from_resume(resume_text: str, policies: Sequence[Policy], case_id: str) -> DraftPackage:
    """Public API that accepts a raw resume and emits a verified EB-1 draft package."""

    profile = profile_from_resume(resume_text, case_id)
    return generate_package(profile, policies)
