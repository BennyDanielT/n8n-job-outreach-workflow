"""Offline demo: canned LLM answers for one sample posting, so the app runs end to end
with LLM_PROVIDER=fake and no Azure account. Also used by the tests."""

from __future__ import annotations

from app.llm import FakeLLM
from app.schemas import (
    EvidenceLink,
    EvidenceMap,
    FaithfulnessJudgement,
    JobPosting,
    JobRequirements,
    JudgedBullet,
    Requirement,
    SkillGroup,
    TailoredBullet,
    TailoredContent,
    TailoredSection,
)

SAMPLE_JOB = JobPosting(
    title="AI Engineer (LLM Applications)",
    company="Northwind Health (sample)",
    location="Remote, Canada",
    text="""We're hiring an AI Engineer to build LLM-powered features for clinicians.

What you'll do
- Design and ship RAG and agentic workflows in Python on Azure OpenAI.
- Build evaluation pipelines to measure retrieval quality and answer faithfulness.
- Deploy services with FastAPI, Docker and CI/CD, and monitor them in production.
- Integrate LLMs with internal databases and tools (function calling, MCP a plus).

What you bring
- 3+ years of software engineering in Python.
- Hands-on experience with LangChain or LangGraph.
- Experience with a major cloud (Azure preferred, AWS fine).
- Nice to have: Kubernetes, Terraform, healthcare data experience.""",
)


def _requirements() -> JobRequirements:
    R = Requirement
    return JobRequirements(
        role_title="AI Engineer (LLM Applications)",
        company="Northwind Health",
        seniority="Mid",
        requirements=[
            R(id="req-1", text="Build RAG and agentic workflows in Python on Azure OpenAI", kind="must_have",
              keywords=["RAG", "Python", "Azure OpenAI"]),
            R(id="req-2", text="Build evaluation pipelines for retrieval and faithfulness", kind="must_have",
              keywords=["evaluation"]),
            R(id="req-3", text="Deploy with FastAPI, Docker and CI/CD", kind="must_have",
              keywords=["FastAPI", "Docker", "CI/CD"]),
            R(id="req-4", text="Integrate LLMs with databases and tools", kind="must_have",
              keywords=["function calling", "MCP"]),
            R(id="req-5", text="LangChain or LangGraph experience", kind="must_have",
              keywords=["LangChain", "LangGraph"]),
            R(id="req-6", text="Cloud experience, Azure preferred", kind="must_have", keywords=["Azure", "AWS"]),
            R(id="req-7", text="Kubernetes and Terraform", kind="nice_to_have", keywords=["Kubernetes", "Terraform"]),
            R(id="req-8", text="Healthcare data experience", kind="nice_to_have", keywords=["healthcare"]),
        ],
        keywords=["Python", "RAG", "Azure OpenAI", "FastAPI", "Docker", "CI/CD", "MCP", "LangChain",
                  "LangGraph", "Azure", "AWS", "Kubernetes", "Terraform", "function calling"],
    )


def _evidence() -> EvidenceMap:
    L = EvidenceLink
    return EvidenceMap(links=[
        L(requirement_id="req-1", bullet_ids=["autonomy-full", "insights-full"], strength="partial",
          rationale="Agentic workflows built; RAG and Azure OpenAI only partly shown."),
        L(requirement_id="req-2", bullet_ids=["autonomy-full"], strength="partial",
          rationale="Agents include an evaluate step; no dedicated eval pipeline in the master yet."),
        L(requirement_id="req-3", bullet_ids=["bluegrid-cicd", "autonomy-full", "bluegrid-iac"], strength="strong",
          rationale="CI/CD and Docker deployments at BlueGrid and on the autonomy platform."),
        L(requirement_id="req-4", bullet_ids=["trihedral-mcp"], strength="strong",
          rationale="Production MCP server connecting an LLM to an ODBC database."),
        L(requirement_id="req-5", bullet_ids=["autonomy-full", "retro-summaries"], strength="strong",
          rationale="LangGraph state machine and LangChain agent."),
        L(requirement_id="req-6", bullet_ids=["insights-full", "bluegrid-cicd"], strength="strong",
          rationale="Azure App Service and AI Foundry; AWS ECS."),
        L(requirement_id="req-7", bullet_ids=[], strength="none", rationale="Listed as skills, no bullet shows them."),
        L(requirement_id="req-8", bullet_ids=["az-kpis"], strength="partial",
          rationale="AstraZeneca is pharma, adjacent to healthcare."),
    ])


def _tailored() -> TailoredContent:
    B, S = TailoredBullet, TailoredSection
    return TailoredContent(
        headline="AI Engineer | LLM apps and agents, MCP, LangGraph, FastAPI, Azure and AWS",
        summary=(
            "Software engineer who designed and deployed an MCP server that lets an LLM query a proprietary "
            "industrial database in natural language. Builds governed multi-agent systems with LangGraph and "
            "ships them with CI/CD on Azure and AWS."
        ),
        experience=[
            S(source_id="trihedral", bullets=[
                B(source_ids=["trihedral-mcp"], text=(
                    "Designed and deployed an MCP server in Python (FastMCP) that lets an LLM query VTScada's "
                    "proprietary ODBC database in natural language, generate operational reports and surface system "
                    "insights, reducing manual data access and speeding up troubleshooting.")),
                B(source_ids=["trihedral-debugger"], text=(
                    "Increased debugging efficiency by 35% by adding dynamic data structure updates and real-time "
                    "formatting to the VTScada Source Debugger.")),
                B(source_ids=["trihedral-testing"], text=(
                    "Led debugging and testing efforts that reduced post-release defects by 15%.")),
            ]),
            S(source_id="bluegrid", bullets=[
                B(source_ids=["bluegrid-cicd"], text=(
                    "Built automated CI/CD pipelines for Python services on AWS Elastic Container Service with "
                    "Bitbucket Pipelines, reducing manual deployment effort by 80%.")),
                B(source_ids=["bluegrid-membertou"], text=(
                    "Automated an end-to-end Python analytics app on AWS (S3, SNS, SQS, SES) deriving voyage "
                    "metrics from boat sensor data for the Membertou First Nations fleet, eliminating 100% of manual "
                    "analytics.")),
                B(source_ids=["bluegrid-iac"], text=(
                    "Maintained infrastructure as code with AWS CDK and Docker Compose for repeatable deployments.")),
            ]),
            S(source_id="astrazeneca", bullets=[
                B(source_ids=["az-airflow"], text=(
                    "Orchestrated Spark data pipelines and automated Apache Airflow ETL jobs, cutting manual "
                    "deployment tasks by over 70%.")),
                B(source_ids=["az-databricks"], text=(
                    "Accelerated parquet processing on AWS S3 and Azure Databricks by 45% with automated "
                    "YAML-based jobs.")),
            ]),
        ],
        projects=[
            S(source_id="autonomy-platform", bullets=[
                B(source_ids=["autonomy-full"], text=(
                    "Built three autonomous agents on one governance spine (assess, gate, act, evaluate), using an "
                    "LLM for support triage, SQL over Postgres catalogs for index hygiene, and a LangGraph state "
                    "machine for pipeline self-healing.")),
                B(source_ids=["autonomy-full"], text=(
                    "Enforced policy-as-data autonomy with a kill switch, prompt-injection screening and PII "
                    "masking; deployed on AWS ECS Fargate and RDS with OIDC-based GitHub Actions CI/CD.")),
            ]),
            S(source_id="insights-dashboard", bullets=[
                B(source_ids=["insights-full"], text=(
                    "Migrated an LLM insights app to Azure App Service and Azure AI Foundry with CI/CD, guardrails, "
                    "monitoring and evaluation.")),
            ]),
            S(source_id="retro-agent", bullets=[
                B(source_ids=["retro-summaries"], text=(
                    "Developed a Slack-integrated AI agent that linked notes to JIRA tickets and generated sprint "
                    "retrospectives, reducing manual reporting time by at least 70%.")),
            ]),
        ],
        skills=[
            SkillGroup(category="AI/ML", items=["LangGraph", "LangChain", "MCP", "RAG", "Azure AI Foundry",
                                                "NVIDIA NeMo Agent Toolkit"]),
            SkillGroup(category="Languages", items=["Python", "Java", "SQL"]),
            SkillGroup(category="Cloud and DevOps", items=["Azure", "AWS", "Docker", "Kubernetes",
                                                           "GitHub Actions", "Bitbucket"]),
            SkillGroup(category="Backend and Data", items=["FastAPI", "REST APIs", "PostgreSQL", "MongoDB",
                                                          "Redis", "Airflow", "Databricks"]),
        ],
    )


def _judge(user: str) -> FaithfulnessJudgement:
    n = sum(1 for line in user.splitlines() if ". rewrite: " in line)
    return FaithfulnessJudgement(bullets=[JudgedBullet(text="", supported=True) for _ in range(n)])


def demo_llm() -> FakeLLM:
    return FakeLLM({
        "extract": _requirements(),
        "match": _evidence(),
        "rewrite": _tailored(),
        "judge": _judge,
    })
