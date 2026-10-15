"""Deterministic fabrication checks.

The rule this whole app rests on: a tailored resume may reword, reorder and drop, but it
may never claim something the master resume doesn't. These checks are cheap, exact and run
on every attempt. The optional LLM judge (in the pipeline) catches softer, semantic drift.
"""

from __future__ import annotations

import re

from app.schemas import Issue, JobRequirements, MasterResume, TailoredContent

_NUM = re.compile(r"\d[\d,]*(?:\.\d+)?")


def numbers_in(text: str) -> set[str]:
    return {m.group(0).replace(",", "").rstrip(".") for m in _NUM.finditer(text)}


def contains_term(text: str, term: str) -> bool:
    """Case-insensitive whole-term match that also works for terms like 'C++' or '.NET'."""
    t = term.strip()
    if not t:
        return False
    pattern = r"(?<![A-Za-z0-9])" + re.escape(t) + r"(?![A-Za-z0-9])"
    return re.search(pattern, text, flags=re.IGNORECASE) is not None


def tailored_text(t: TailoredContent) -> str:
    parts = [t.headline, t.summary]
    for sec in [*t.experience, *t.projects]:
        parts += [b.text for b in sec.bullets]
    for g in t.skills:
        parts += g.items
    return "\n".join(parts)


def check(
    master: MasterResume,
    tailored: TailoredContent,
    requirements: JobRequirements | None = None,
    *,
    max_bullets_per_role: int = 4,
) -> list[Issue]:
    issues: list[Issue] = []
    index = master.bullet_index()
    role_ids = {r.id for r in master.experience}
    project_ids = {p.id for p in master.projects}
    master_text = master.all_text()
    master_numbers = numbers_in(master_text)

    # 1. Structure: every section and bullet traces back to the master.
    for kind, sections, valid in (
        ("experience", tailored.experience, role_ids),
        ("projects", tailored.projects, project_ids),
    ):
        seen: set[str] = set()
        for sec in sections:
            where = f"{kind}:{sec.source_id}"
            if sec.source_id not in valid:
                issues.append(Issue(severity="error", check="unknown_section", location=where,
                                    message=f"'{sec.source_id}' is not a {kind[:-1] if kind == 'projects' else 'role'} in the master resume"))
                continue
            if sec.source_id in seen:
                issues.append(Issue(severity="error", check="duplicate_section", location=where,
                                    message="Section appears twice"))
            seen.add(sec.source_id)
            if kind == "experience" and len(sec.bullets) > max_bullets_per_role:
                issues.append(Issue(severity="warning", check="too_many_bullets", location=where,
                                    message=f"{len(sec.bullets)} bullets; limit is {max_bullets_per_role}"))

            for i, b in enumerate(sec.bullets):
                loc = f"{where}#{i + 1}"
                if not b.source_ids:
                    issues.append(Issue(severity="error", check="no_source", location=loc,
                                        message="Bullet cites no master bullet"))
                    continue
                sources = []
                for sid in b.source_ids:
                    if sid not in index:
                        issues.append(Issue(severity="error", check="unknown_source", location=loc,
                                            message=f"Cites '{sid}', which doesn't exist"))
                    elif index[sid][0] != sec.source_id:
                        issues.append(Issue(severity="error", check="wrong_section_source", location=loc,
                                            message=f"Cites '{sid}' from '{index[sid][0]}', not '{sec.source_id}'"))
                    else:
                        sources.append(index[sid][1].text)
                if not sources:
                    continue

                # 2. Numbers: every figure must appear in the bullets it came from.
                source_numbers = numbers_in(" ".join(sources))
                invented = sorted(numbers_in(b.text) - source_numbers)
                if invented:
                    issues.append(Issue(severity="error", check="invented_number", location=loc,
                                        message=f"Figures not in the source bullet(s): {', '.join(invented)}"))

    # 3. Headline and summary: figures should exist somewhere in the master (warn: may be derived, e.g. years).
    for field in ("headline", "summary"):
        extra = sorted(numbers_in(getattr(tailored, field)) - master_numbers)
        if extra:
            issues.append(Issue(severity="warning", check="unverified_number", location=field,
                                message=f"Figures not found in master resume, verify by hand: {', '.join(extra)}"))

    # 4. Skills: only skills the user actually listed.
    vocab = master.skill_vocabulary()
    for g in tailored.skills:
        for item in g.items:
            if item.lower() not in vocab and not contains_term(master_text, item):
                issues.append(Issue(severity="error", check="invented_skill", location=f"skills:{g.category}",
                                    message=f"'{item}' isn't in your master resume"))

    # 5. Keyword stuffing: posting keywords that appear in the output but nowhere in the master.
    if requirements is not None:
        out = tailored_text(tailored)
        for kw in sorted(set(requirements.keywords)):
            if contains_term(out, kw) and not contains_term(master_text, kw):
                issues.append(Issue(severity="error", check="keyword_stuffing", location="document",
                                    message=f"'{kw}' comes from the job posting, not your experience"))
    return issues
