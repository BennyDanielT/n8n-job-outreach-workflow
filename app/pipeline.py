"""The tailoring graph.

    extract_requirements -> match_evidence -> rewrite -> verify --(errors, attempts left)--> rewrite
                                                            \\--(clean or out of attempts)--> END

`verify` runs the deterministic checks first; the LLM judge only runs on drafts that pass them,
so we never pay for a judge call on something we already know is wrong.
"""

from __future__ import annotations

import logging
import uuid
from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from app import faithfulness, fit, prompts
from app.config import Settings
from app.llm import LLM
from app.schemas import (
    EvidenceMap,
    FaithfulnessJudgement,
    FaithfulnessReport,
    FitReport,
    Issue,
    JobPosting,
    JobRequirements,
    MasterResume,
    TailoredContent,
)

log = logging.getLogger(__name__)


class TailorState(TypedDict, total=False):
    master: MasterResume
    job: JobPosting
    requirements: JobRequirements
    evidence: EvidenceMap
    tailored: TailoredContent
    issues: list[Issue]
    attempts: int


class PipelineOutput(TypedDict):
    run_id: str
    requirements: JobRequirements
    evidence: EvidenceMap
    tailored: TailoredContent
    faithfulness: FaithfulnessReport
    fit: FitReport
    attempts: int


def build_graph(llm: LLM, settings: Settings):
    def extract_requirements(state: TailorState) -> TailorState:
        req = llm.structured(
            system=prompts.EXTRACT_SYSTEM,
            user=prompts.extract_user(state["job"]),
            schema=JobRequirements,
            step="extract",
        )
        return {"requirements": req}

    def match_evidence(state: TailorState) -> TailorState:
        ev = llm.structured(
            system=prompts.MATCH_SYSTEM,
            user=prompts.match_user(state["master"], state["requirements"]),
            schema=EvidenceMap,
            step="match",
        )
        return {"evidence": ev}

    def rewrite(state: TailorState) -> TailorState:
        attempts = state.get("attempts", 0) + 1
        draft = llm.structured(
            system=prompts.rewrite_system(settings.max_bullets_per_role, settings.max_projects),
            user=prompts.rewrite_user(
                state["master"],
                state["job"],
                state["requirements"],
                state["evidence"],
                state.get("tailored"),
                state.get("issues", []),
            ),
            schema=TailoredContent,
            step="rewrite",
        )
        return {"tailored": draft, "attempts": attempts}

    def verify(state: TailorState) -> TailorState:
        issues = faithfulness.check(
            state["master"],
            state["tailored"],
            state["requirements"],
            max_bullets_per_role=settings.max_bullets_per_role,
        )
        if settings.use_llm_judge and not any(i.severity == "error" for i in issues):
            issues += _judge(llm, state["master"], state["tailored"])
        errors = sum(i.severity == "error" for i in issues)
        log.info("verify attempt=%d errors=%d warnings=%d", state["attempts"], errors, len(issues) - errors)
        return {"issues": issues}

    def route(state: TailorState) -> str:
        has_errors = any(i.severity == "error" for i in state.get("issues", []))
        if has_errors and state["attempts"] < settings.max_rewrite_attempts:
            return "rewrite"
        return END

    g = StateGraph(TailorState)
    g.add_node("extract_requirements", extract_requirements)
    g.add_node("match_evidence", match_evidence)
    g.add_node("rewrite", rewrite)
    g.add_node("verify", verify)
    g.add_edge(START, "extract_requirements")
    g.add_edge("extract_requirements", "match_evidence")
    g.add_edge("match_evidence", "rewrite")
    g.add_edge("rewrite", "verify")
    g.add_conditional_edges("verify", route, {"rewrite": "rewrite", END: END})
    return g.compile()


def _judge(llm: LLM, master: MasterResume, tailored: TailoredContent) -> list[Issue]:
    index = master.bullet_index()
    pairs: list[tuple[str, list[str]]] = []
    locations: list[str] = []
    for kind, sections in (("experience", tailored.experience), ("projects", tailored.projects)):
        for sec in sections:
            for i, b in enumerate(sec.bullets):
                pairs.append((b.text, [index[s][1].text for s in b.source_ids if s in index]))
                locations.append(f"{kind}:{sec.source_id}#{i + 1}")
    if not pairs:
        return []
    verdict = llm.structured(
        system=prompts.JUDGE_SYSTEM,
        user=prompts.judge_user(pairs),
        schema=FaithfulnessJudgement,
        step="judge",
        judge=True,
    )
    issues: list[Issue] = []
    if len(verdict.bullets) != len(pairs):
        issues.append(Issue(severity="warning", check="judge_mismatch", location="document",
                            message=f"Judge returned {len(verdict.bullets)} verdicts for {len(pairs)} bullets"))
    for loc, jb in zip(locations, verdict.bullets):
        if not jb.supported:
            claims = "; ".join(jb.unsupported_claims) or "claims beyond the source"
            issues.append(Issue(severity="error", check="judge_unsupported", location=loc, message=claims))
    return issues


def run(llm: LLM, settings: Settings, master: MasterResume, job: JobPosting) -> PipelineOutput:
    graph = build_graph(llm, settings)
    final: TailorState = graph.invoke({"master": master, "job": job, "attempts": 0})
    issues = final.get("issues", [])
    return PipelineOutput(
        run_id=uuid.uuid4().hex[:12],
        requirements=final["requirements"],
        evidence=final["evidence"],
        tailored=final["tailored"],
        faithfulness=FaithfulnessReport(passed=not any(i.severity == "error" for i in issues), issues=issues),
        fit=fit.score(master, final["requirements"], final["evidence"], final["tailored"]),
        attempts=final["attempts"],
    )
