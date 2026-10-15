"""Data contracts for Job Copilot.

Three families of models:
- Master resume: the user's full history, every bullet with a stable id.
- LLM outputs: what each pipeline step must return (used as structured-output schemas).
- API results: what the service hands back to the client.
"""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, HttpUrl


# --------------------------------------------------------------------------- master resume
class Link(BaseModel):
    label: str
    url: str
    icon: str | None = Field(None, description="linkedin | github | blog | youtube | globe; guessed from the URL if empty")


class Contact(BaseModel):
    name: str
    location: str | None = None
    phone: str | None = None
    email: str | None = None
    links: list[Link] = Field(default_factory=list)


class Bullet(BaseModel):
    id: str
    text: str
    in_base: bool = Field(True, description="Shown on the untailored resume; the tailor may use it either way")


class Role(BaseModel):
    id: str
    company: str
    title: str
    location: str | None = None
    start: str
    end: str
    bullets: list[Bullet]
    skills: list[str] = Field(default_factory=list)


class Project(BaseModel):
    id: str
    name: str
    url: str | None = None
    tech: list[str] = Field(default_factory=list)
    heading_tech: list[str] | None = Field(None, description="Stack shown in the heading; defaults to the first few of tech")
    date: str | None = None
    bullets: list[Bullet]


class Education(BaseModel):
    degree: str
    school: str
    location: str | None = None
    start: str | None = None
    end: str | None = None


class SkillGroup(BaseModel):
    category: str
    items: list[str]


class CertStatus(str, Enum):
    active = "active"
    in_progress = "in_progress"
    expired = "expired"


class Certification(BaseModel):
    name: str
    issuer: str | None = None
    date: str | None = None
    status: CertStatus = CertStatus.active


class Layout(BaseModel):
    """How the resume is laid out. Defaults reproduce Benny's LaTeX template."""

    section_order: list[str] = Field(
        default_factory=lambda: ["summary", "experience", "education", "skills", "projects", "certifications"]
    )
    show_headline: bool = False
    show_summary: bool = False
    show_role_skills: bool = True
    max_project_tech: int = 4
    max_pages: int = 1


class MasterResume(BaseModel):
    layout: Layout = Field(default_factory=Layout)
    contact: Contact
    headline: str | None = None
    summary: str | None = None
    experience: list[Role]
    projects: list[Project] = Field(default_factory=list)
    education: list[Education] = Field(default_factory=list)
    skills: list[SkillGroup] = Field(default_factory=list)
    certifications: list[Certification] = Field(default_factory=list)

    def bullet_index(self) -> dict[str, tuple[str, Bullet]]:
        """Map bullet id -> (owning role/project id, bullet)."""
        index: dict[str, tuple[str, Bullet]] = {}
        for role in self.experience:
            for b in role.bullets:
                index[b.id] = (role.id, b)
        for proj in self.projects:
            for b in proj.bullets:
                index[b.id] = (proj.id, b)
        return index

    def all_text(self) -> str:
        """Every word the user has ever claimed, for vocabulary checks."""
        parts: list[str] = [self.headline or "", self.summary or ""]
        for r in self.experience:
            parts += [r.company, r.title, *r.skills, *(b.text for b in r.bullets)]
        for p in self.projects:
            parts += [p.name, *p.tech, *(b.text for b in p.bullets)]
        for e in self.education:
            parts += [e.degree, e.school]
        for g in self.skills:
            parts += g.items
        for c in self.certifications:
            parts.append(c.name)
        return "\n".join(parts)

    def skill_vocabulary(self) -> set[str]:
        vocab: set[str] = set()
        for g in self.skills:
            vocab.update(i.lower() for i in g.items)
        for r in self.experience:
            vocab.update(s.lower() for s in r.skills)
        for p in self.projects:
            vocab.update(t.lower() for t in p.tech)
        return vocab


# --------------------------------------------------------------------------- job input
class JobPosting(BaseModel):
    title: str | None = None
    company: str | None = None
    location: str | None = None
    url: str | None = None
    text: str = Field(..., min_length=50, max_length=40_000, description="Full job description text")


class FetchJobRequest(BaseModel):
    url: HttpUrl


# --------------------------------------------------------------------------- LLM step outputs
class Requirement(BaseModel):
    id: str = Field(description="Short stable id, e.g. 'req-1'")
    text: str = Field(description="The requirement, in the job's own terms")
    kind: Literal["must_have", "nice_to_have"]
    keywords: list[str] = Field(description="Exact technical terms from the posting, e.g. 'Azure OpenAI', 'Kubernetes'")


class JobRequirements(BaseModel):
    role_title: str
    company: str | None = None
    seniority: str | None = None
    requirements: list[Requirement]
    keywords: list[str] = Field(description="Every distinct technical keyword in the posting")


class EvidenceLink(BaseModel):
    requirement_id: str
    bullet_ids: list[str] = Field(description="Master resume bullet ids that support this requirement")
    strength: Literal["strong", "partial", "none"]
    rationale: str = Field(description="One sentence on why")


class EvidenceMap(BaseModel):
    links: list[EvidenceLink]


class TailoredBullet(BaseModel):
    source_ids: list[str] = Field(description="Ids of the master bullets this bullet is rewritten from (at least one)")
    text: str


class TailoredSection(BaseModel):
    source_id: str = Field(description="Id of the role or project in the master resume")
    bullets: list[TailoredBullet]


class TailoredContent(BaseModel):
    headline: str
    summary: str
    experience: list[TailoredSection]
    projects: list[TailoredSection]
    skills: list[SkillGroup]


class JudgedBullet(BaseModel):
    text: str
    supported: bool
    unsupported_claims: list[str] = Field(default_factory=list)


class FaithfulnessJudgement(BaseModel):
    bullets: list[JudgedBullet]


# --------------------------------------------------------------------------- results
class Issue(BaseModel):
    severity: Literal["error", "warning"]
    check: str
    location: str
    message: str


class FaithfulnessReport(BaseModel):
    passed: bool
    issues: list[Issue] = Field(default_factory=list)


class FitReport(BaseModel):
    score: int = Field(ge=0, le=100, description="Weighted share of requirements backed by evidence")
    keyword_coverage: float = Field(ge=0, le=1, description="Share of posting keywords present in the tailored resume")
    covered_keywords: list[str]
    missing_keywords_you_have: list[str] = Field(description="In your master resume but not in this version")
    missing_keywords_you_lack: list[str] = Field(description="Not anywhere in your master resume: real gaps")
    gaps: list[str] = Field(description="Requirements with no supporting evidence")


class TailorRequest(BaseModel):
    job: JobPosting
    master_resume: MasterResume | None = Field(
        None, description="Omit to use the server's configured master resume"
    )
    show_expired_certs: bool = False


class TailorResult(BaseModel):
    run_id: str
    requirements: JobRequirements
    evidence: EvidenceMap
    tailored: TailoredContent
    faithfulness: FaithfulnessReport
    fit: FitReport
    attempts: int
    html: str


class RenderPdfRequest(BaseModel):
    html: str = Field(..., max_length=2_000_000)
    filename: str = "resume.pdf"
