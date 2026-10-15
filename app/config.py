from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Azure OpenAI through Microsoft Foundry.
    # Endpoint looks like https://<resource>.openai.azure.com or https://<resource>.services.ai.azure.com
    azure_openai_endpoint: str = ""
    # Leave empty to authenticate with Microsoft Entra ID (DefaultAzureCredential / managed identity).
    azure_openai_api_key: str = ""
    # The *deployment* name in Foundry, not the model family name.
    azure_openai_deployment: str = "gpt-4.1-mini"
    # A cheaper deployment for the judge step; falls back to the main one.
    azure_openai_judge_deployment: str = ""
    llm_temperature: float = 0.2
    llm_timeout_s: float = 60.0

    # "azure" for real calls, "fake" for tests and offline demos.
    llm_provider: str = "azure"

    # Pipeline behaviour
    max_rewrite_attempts: int = 2
    use_llm_judge: bool = True
    max_bullets_per_role: int = 4
    max_projects: int = 3

    # Rendering
    gotenberg_url: str = "http://localhost:3000"
    pdf_engine: str = "gotenberg"  # or "weasyprint" for local dev without Docker

    master_resume_path: Path = Path("data/master_resume.yaml")

    # Tracker database. SQLite file by default; any SQLAlchemy URL works (e.g. Postgres on Azure).
    database_url: str = "sqlite:///data/copilot.db"

    # LinkedIn (Selenium). Cookie first, password as fallback.
    linkedin_li_at: str = ""
    linkedin_jsessionid: str = ""
    linkedin_email: str = ""
    linkedin_password: str = ""
    linkedin_headless: bool = True
    chrome_profile_dir: str = ""
    chrome_binary: str = ""  # e.g. /usr/bin/chromium in Docker; empty = let Selenium find Chrome

    # Job fetching
    fetch_timeout_s: float = 15.0
    fetch_max_bytes: int = 3_000_000

    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()
