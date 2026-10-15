import os
import tempfile
from pathlib import Path

# Settings are cached on first import, so the test environment is fixed here, before any app import.
_tmp = Path(tempfile.mkdtemp(prefix="copilot-tests-"))
os.environ.update({
    "LLM_PROVIDER": "fake",
    "PDF_ENGINE": "weasyprint",
    "DATABASE_URL": f"sqlite:///{_tmp / 'test.db'}",
    "LINKEDIN_LI_AT": "test-cookie",
})
