import sys
import os
import json
from linkedin_functions import scrape_job_details_with_selenium

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_scrape_job_details.py <linkedin_job_url>")
        sys.exit(1)
    job_url = sys.argv[1]
    print(f"Scraping job details for: {job_url}")
    result = scrape_job_details_with_selenium(job_url, headless=False)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    if not result.get("success"):
        print(
            "\n[ERROR] Scraping failed. See 'error' and 'html_debug' in output above."
        )
    else:
        print("\n[SUCCESS] Job details scraped successfully.")
