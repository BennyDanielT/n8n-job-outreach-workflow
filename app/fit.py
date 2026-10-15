"""Fit scoring: deterministic, so the same evidence always gives the same number."""

from __future__ import annotations

from app.faithfulness import contains_term, tailored_text
from app.schemas import EvidenceMap, FitReport, JobRequirements, MasterResume, TailoredContent

_WEIGHT = {"must_have": 2.0, "nice_to_have": 1.0}
_STRENGTH = {"strong": 1.0, "partial": 0.5, "none": 0.0}


def score(
    master: MasterResume,
    requirements: JobRequirements,
    evidence: EvidenceMap,
    tailored: TailoredContent,
) -> FitReport:
    valid_bullets = set(master.bullet_index())
    by_req = {link.requirement_id: link for link in evidence.links}

    total = earned = 0.0
    gaps: list[str] = []
    for req in requirements.requirements:
        w = _WEIGHT[req.kind]
        total += w
        link = by_req.get(req.id)
        # Evidence only counts if it points at real bullets.
        strength = link.strength if link and any(b in valid_bullets for b in link.bullet_ids) else "none"
        earned += w * _STRENGTH[strength]
        if strength == "none":
            gaps.append(f"{'Must-have' if req.kind == 'must_have' else 'Nice-to-have'}: {req.text}")

    out = tailored_text(tailored)
    master_text = master.all_text()
    keywords = sorted({k.strip() for k in requirements.keywords if k.strip()}, key=str.lower)
    covered = [k for k in keywords if contains_term(out, k)]
    have_unused = [k for k in keywords if k not in covered and contains_term(master_text, k)]
    lack = [k for k in keywords if k not in covered and k not in have_unused]

    return FitReport(
        score=round(100 * earned / total) if total else 0,
        keyword_coverage=round(len(covered) / len(keywords), 3) if keywords else 0.0,
        covered_keywords=covered,
        missing_keywords_you_have=have_unused,
        missing_keywords_you_lack=lack,
        gaps=gaps,
    )
