from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup
import os
from linkedin_api import Linkedin
from requests.cookies import RequestsCookieJar
import logging
from datetime import datetime
from typing import Optional, Dict, List
from dotenv import load_dotenv
import re
from urllib.parse import urlparse, parse_qs
import time


# --- Selenium-based LinkedIn Job Details Scraper ---
def scrape_job_details_with_selenium(job_url, headless=True):
    """
    Scrape job details from a LinkedIn job page using Selenium and BeautifulSoup.
    Args:
        job_url: LinkedIn job URL
        headless: Whether to run Chrome in headless mode (default True)
    Returns:
        Dict with job details (title, company, location, description, etc.)
    """
    import time
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import TimeoutException
    from selenium.webdriver.common.by import By
    from bs4 import BeautifulSoup

    result = {"success": False, "error": None, "job_url": job_url}
    driver = get_driver(headless=headless)
    try:
        # --- LOGIN HANDLING (like scrape_people) ---
        from selenium.webdriver.common.keys import Keys
        import os

        driver.get("https://www.linkedin.com/login")
        time.sleep(2)
        if "login" in driver.current_url:
            email_input = driver.find_element(By.ID, "username")
            password_input = driver.find_element(By.ID, "password")
            email_input.send_keys(os.getenv("LINKEDIN_EMAIL"))
            password_input.send_keys(os.getenv("LINKEDIN_PASSWORD"))
            password_input.send_keys(Keys.RETURN)
            time.sleep(3)
        # --- END LOGIN HANDLING ---
        driver.get(job_url)
        # Wait for the main job details container to load
        try:
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located(
                    (
                        By.CSS_SELECTOR,
                        ".jobs-search__job-details--wrapper, .jobs-details__main-content",
                    )
                )
            )
        except TimeoutException:
            result["error"] = "Timeout waiting for job details container"
            result["html_debug"] = driver.page_source
            return result
        time.sleep(1)
        soup = BeautifulSoup(driver.page_source, "html.parser")
        # Extract job title
        title_tag = soup.select_one(
            ".job-details-jobs-unified-top-card__job-title h1, h1.t-24"
        )
        title = title_tag.get_text(strip=True) if title_tag else None
        # Extract company name
        company_tag = soup.select_one(
            ".job-details-jobs-unified-top-card__company-name a, .jobs-unified-top-card__company-name a, .jobs-unified-top-card__company-name"
        )
        company = company_tag.get_text(strip=True) if company_tag else None
        # Extract location
        location_tag = soup.select_one(
            ".job-details-jobs-unified-top-card__primary-description-container span, .jobs-unified-top-card__primary-description"
        )
        location = location_tag.get_text(strip=True) if location_tag else None
        # Extract job description (HTML and text)
        desc_container = soup.select_one(
            ".jobs-description__content, .jobs-description-content__text--stretch, #job-details"
        )
        description_html = str(desc_container) if desc_container else None
        description_text = (
            desc_container.get_text("\n", strip=True) if desc_container else None
        )
        # Employment type (e.g., Full-time, Remote)
        employment_type = None
        for btn in soup.select(
            ".job-details-fit-level-preferences button, .jobs-unified-top-card__job-insight span"
        ):
            txt = btn.get_text(strip=True)
            if txt:
                if not employment_type:
                    employment_type = txt
                else:
                    employment_type += ", " + txt
        # Posted date
        posted_tag = soup.find(
            "span", string=lambda s: s and ("ago" in s or "Reposted" in s)
        )
        posted = posted_tag.get_text(strip=True) if posted_tag else None
        # Company logo
        logo_tag = soup.select_one(".ivm-view-attr__img-wrapper img")
        company_logo_url = (
            logo_tag["src"] if logo_tag and logo_tag.has_attr("src") else None
        )
        # Apply button link
        apply_btn = soup.select_one("button.jobs-apply-button, a.jobs-apply-button")
        apply_url = None
        if apply_btn and apply_btn.has_attr("href"):
            apply_url = apply_btn["href"]
        # Build result
        result.update(
            {
                "success": True,
                "title": title,
                "company": company,
                "location": location,
                "description_html": description_html,
                "description_text": description_text,
                "employment_type": employment_type,
                "posted": posted,
                "company_logo_url": company_logo_url,
                "apply_url": apply_url,
                "scraped_at": datetime.now().isoformat(),
            }
        )
        return result
    except Exception as e:
        result["error"] = str(e)
        result["html_debug"] = driver.page_source
        return result
    finally:
        driver.quit()


"""
LinkedIn helper functions for job scraping
"""

load_dotenv()
LINKEDIN_EMAIL = os.getenv("LINKEDIN_EMAIL")
LINKEDIN_PASSWORD = os.getenv("LINKEDIN_PASSWORD")
logger = logging.getLogger(__name__)

# Persistent Chrome profile for Selenium scraping
CHROME_PROFILE_PATH = os.getenv("CHROME_PROFILE_PATH", None)
CHROME_PROFILE_NAME = os.getenv("CHROME_PROFILE_NAME", "Default")


def get_driver(headless=True):
    chrome_options = Options()
    # If using a Chrome profile, do NOT use headless mode (it will crash)
    if CHROME_PROFILE_PATH:
        if headless:
            print(
                "[INFO] Disabling headless mode because CHROME_PROFILE_PATH is set (headless + user profile will crash Chrome)."
            )
        headless = False
        # chrome_options.add_argument(f"--user-data-dir={CHROME_PROFILE_PATH}")
        # chrome_options.add_argument(f"--profile-directory={CHROME_PROFILE_NAME}")
    if headless:
        chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    return webdriver.Chrome(options=chrome_options)


# def get_driver(headless: bool = True) -> webdriver.Chrome:
#     chrome_options = Options()

#     # Headless in container
#     # if headless:
#     #     chrome_options.add_argument("--headless=new")

#     # Critical Docker flags
#     # chrome_options.add_argument("--window-size=1920,1080")
#     chrome_options.add_argument("--disable-gpu")
#     chrome_options.add_argument("--no-sandbox")
#     chrome_options.add_argument("--disable-dev-shm-usage")
#     chrome_options.add_argument("--disable-extensions")
#     chrome_options.add_argument("--disable-dev-tools")
#     # chrome_options.add_argument("--remote-debugging-port=9222")
#     # chrome_options.add_argument(f"--user-data-dir={CHROME_PROFILE_PATH}")
#     # chrome_options.add_argument(f"--profile-directory={CHROME_PROFILE_NAME}")
#     # Use explicit chromedriver binary instead of Selenium Manager
#     # assuming chromedriver is in PATH inside the container
#     logging.info("Launching Chrome WebDriver...")
#     driver = webdriver.Chrome()
#     logging.info("Chrome WebDriver launched.")
#     return driver


def scrape_people(company_name, query_params="", min_results=20, max_clicks=10):
    """
    Scrape people from a LinkedIn company people page using Selenium and BeautifulSoup.
    Args:
        company_name: LinkedIn company slug (e.g., 'cgi')
        query_params: Query string for filtering (e.g., '?facetGeoRegion=90009533')
        min_results: Minimum number of people to scrape
        max_clicks: Max times to click 'Show more results'
    Returns:
        List of dicts with name, profile_url, title, mutuals
    """
    url = f"https://www.linkedin.com/company/{company_name}/people/{query_params}"
    driver = get_driver(headless=False)
    try:
        logging.info(f"Trying to get url")
        driver.get(url)
        time.sleep(2)
        if "login" in driver.current_url:
            print("Logging in...")
            email_input = driver.find_element(By.ID, "username")
            password_input = driver.find_element(By.ID, "password")
            email_input.send_keys(LINKEDIN_EMAIL)
            password_input.send_keys(LINKEDIN_PASSWORD)
            password_input.send_keys(Keys.RETURN)
            time.sleep(3)
            # driver.get(url)
            time.sleep(3)
        logging.info(f"Loaded url: {url}")
        results = []
        for i in range(max_clicks):
            soup = BeautifulSoup(driver.page_source, "html.parser")
            people_cards = soup.select(
                "li.org-people-profile-card__profile-card-spacing"
            )
            for card in people_cards:
                name_tag = card.select_one("div.artdeco-entity-lockup__title a")
                name = name_tag.get_text(strip=True) if name_tag else None
                profile_url = (
                    name_tag["href"] if name_tag and name_tag.has_attr("href") else None
                )
                title_tag = card.select_one("div.artdeco-entity-lockup__subtitle")
                title = title_tag.get_text(strip=True) if title_tag else None
                mutuals_tag = card.select_one("span.lt-line-clamp--multi-line")
                mutuals = mutuals_tag.get_text(strip=True) if mutuals_tag else None
                person = {
                    "name": name,
                    "profile_url": profile_url,
                    "title": title,
                    "mutuals": mutuals,
                }
                logger.info(f"Scraped person: {person}")
                if person not in results:
                    results.append(person)
            if len(results) >= min_results:
                break
            try:
                show_more = driver.find_element(
                    By.XPATH, "//button[contains(., 'Show more results')]"
                )
                driver.execute_script("arguments[0].click();", show_more)
                time.sleep(2)
            except Exception:
                break
        if len(results) == 0:
            print("[WARN] No results scraped.")
        return results
    finally:
        driver.quit()


def get_linkedin_client(
    li_at_cookie: Optional[str] = None, jsessionid_cookie: Optional[str] = None
) -> Optional[Linkedin]:
    """
    Create and return authenticated LinkedIn API client.

    Args:
        li_at_cookie: Optional li_at cookie (uses .env if not provided)
        jsessionid_cookie: Optional JSESSIONID cookie (uses .env if not provided)

    Returns:
        Authenticated Linkedin client or None if authentication fails
    """
    try:
        username = os.getenv("LINKEDIN_EMAIL", "")
        password = os.getenv("LINKEDIN_PASSWORD", "")

        if not username or not password:
            logger.error("LinkedIn credentials not found in environment variables")
            return None

        # Use provided cookies or get from environment
        li_at = li_at_cookie or os.getenv("LINKEDIN_LI_AT", "").strip('"')
        jsessionid = jsessionid_cookie or os.getenv("LINKEDIN_JSESSIONID", "").strip(
            '"'
        )

        # Create cookie jar if cookies are available
        cookie_jar = None
        if li_at or jsessionid:
            cookie_jar = RequestsCookieJar()
            if li_at:
                cookie_jar.set("li_at", li_at, domain=".linkedin.com")
            if jsessionid:
                cookie_jar.set("JSESSIONID", jsessionid, domain=".linkedin.com")

        api = Linkedin(username, password, cookies=cookie_jar)
        logger.info("✓ Successfully authenticated with LinkedIn")
        return api

    except Exception as e:
        logger.error(f"Failed to authenticate with LinkedIn: {str(e)}")
        return None


def get_company_info(api: Linkedin, company_id: str) -> Optional[Dict]:
    """
    Get detailed company information.

    Args:
        api: Authenticated LinkedIn API client
        company_id: LinkedIn company ID

    Returns:
        Company details dictionary or None
    """
    try:
        company = api.get_company(company_id)
        return company
    except Exception as e:
        logger.error(f"Error getting company info: {str(e)}")
        return None


def extract_person_info(person: Dict) -> Dict:
    """
    Extract and format person information from LinkedIn search results.

    Args:
        person: Raw person data from LinkedIn API

    Returns:
        Formatted person information dictionary
    """
    try:
        # Extract public identifier (profile URL slug)
        public_id = person.get("public_id", "")

        # Extract current position info
        headline = person.get("headline", "N/A")

        # Extract location
        location = person.get("location", "N/A")

        # Extract name
        first_name = person.get("firstName", "")
        last_name = person.get("lastName", "")
        full_name = f"{first_name} {last_name}".strip() or "N/A"

        # Extract profile URN
        urn_id = person.get("urn_id", "")
        profile_urn = person.get("entityUrn", "")

        # Extract tracking ID (useful for LinkedIn tracking)
        tracking_id = person.get("trackingId", "")

        # Extract connection degree
        distance = person.get("distance", "N/A")

        # Build profile URL
        profile_url = f"https://www.linkedin.com/in/{public_id}" if public_id else "N/A"

        return {
            "profile_id": public_id,
            "urn_id": urn_id,
            "full_name": full_name,
            "first_name": first_name,
            "last_name": last_name,
            "headline": headline,
            "location": location,
            "connection_degree": distance,
            "profile_url": profile_url,
            "profile_urn": profile_urn,
            "tracking_id": tracking_id,
            "scraped_at": datetime.now().isoformat(),
        }

    except Exception as e:
        logger.warning(f"Error extracting person info: {str(e)}")
        return {
            "profile_id": "N/A",
            "urn_id": "N/A",
            "full_name": "Error",
            "first_name": "N/A",
            "last_name": "N/A",
            "headline": f"Error extracting details: {str(e)}",
            "location": "N/A",
            "connection_degree": "N/A",
            "profile_url": "N/A",
            "profile_urn": "N/A",
            "tracking_id": "N/A",
            "scraped_at": datetime.now().isoformat(),
        }


# def get_jobs_by_ids(
#     job_ids: List[str],
#     li_at_cookie: Optional[str] = None,
#     jsessionid_cookie: Optional[str] = None,
# ) -> Dict:
#     """
#     Get job details for a list of job IDs.

#     Args:
#         job_ids: List of LinkedIn job IDs
#         li_at_cookie: Optional li_at cookie
#         jsessionid_cookie: Optional JSESSIONID cookie

#     Returns:
#         Dictionary with success status and job details
#     """
#     try:
#         if not job_ids:
#             return {
#                 "success": False,
#                 "error": "No job IDs provided",
#                 "jobs": [],
#             }

#         # Get authenticated client
#         api = get_linkedin_client(li_at_cookie, jsessionid_cookie)
#         if not api:
#             return {
#                 "success": False,
#                 "error": "Failed to authenticate with LinkedIn",
#                 "jobs": [],
#             }

#         logger.info(f"Fetching details for {len(job_ids)} job(s)")

#         # Extract details for each job ID
#         job_details = []
#         for i, job_id in enumerate(job_ids, 1):
#             try:
#                 logger.info(f"Processing job ID: {job_id}")
#                 job_detail = get_job_details(api, job_id)

#                 if job_detail:
#                     job_info = extract_job_info(job_detail, job_id)
#                     job_details.append(job_info)
#                     logger.info(f"✓ Successfully extracted details for job {job_id}")
#                 else:
#                     logger.warning(f"No details found for job ID: {job_id}")

#                 if i % 5 == 0:
#                     logger.info(f"Progress: {i}/{len(job_ids)} jobs processed")

#             except Exception as e:
#                 logger.warning(f"Skipped job {job_id}: {str(e)}")
#                 continue

#         logger.info(f"✓ Successfully fetched {len(job_details)} job(s)")

#         return {
#             "success": True,
#             "count": len(job_details),
#             "jobs": job_details,
#             "scraped_at": datetime.now().isoformat(),
#         }

#     except Exception as e:
#         logger.error(f"Error in get_jobs_by_ids: {str(e)}")
#         return {
#             "success": False,
#             "error": str(e),
#             "jobs": [],
#         }


# def extract_job_id_from_url(url: str) -> Optional[str]:
#     """
#     Extract job ID from LinkedIn job URL.

#     Supports various URL formats:
#     - https://www.linkedin.com/jobs/view/4325442308
#     - https://www.linkedin.com/jobs/search/?currentJobId=4325442308&...
#     - https://www.linkedin.com/jobs/collections/recommended/?currentJobId=4325442308

#     Args:
#         url: LinkedIn job URL

#     Returns:
#         Job ID string or None if not found
#     """
#     try:
#         # If it's already just a job ID (numeric string), return it
#         if url.isdigit():
#             return url

#         # Try to extract from /jobs/view/{job_id} pattern
#         view_match = re.search(r"/jobs/view/(\d+)", url)
#         if view_match:
#             return view_match.group(1)

#         # Try to extract from currentJobId query parameter
#         parsed = urlparse(url)
#         params = parse_qs(parsed.query)
#         if "currentJobId" in params:
#             return params["currentJobId"][0]

#         logger.warning(f"Could not extract job ID from URL: {url}")
#         return None

#     except Exception as e:
#         logger.error(f"Error extracting job ID from URL: {str(e)}")
#         return None
# def search_jobs(
#     api: Linkedin,
#     keywords: str,
#     location: str = "",
#     limit: int = 10,
#     listed_at: Optional[str] = 86400,
#     **kwargs,
# ) -> List[Dict]:
#     """
#     Search for jobs on LinkedIn.

#     Args:
#         api: Authenticated LinkedIn API client
#         keywords: Job search keywords
#         location: Job location (optional)
#         limit: Maximum number of jobs to return
#         **kwargs: Additional search parameters

#     Returns:
#         List of job dictionaries
#     """
#     try:
#         jobs = api.search_jobs(
#             keywords=keywords,
#             location_name=location,
#             limit=limit,
#             experience=[2, 3, 4],
#             job_type=["F", "C"],
#             listed_at=listed_at,
#             distance=50,
#             **kwargs,
#         )
#         logger.info(f"Found {len(jobs)} jobs for keywords: '{keywords}'")
#         return jobs
#     except Exception as e:
#         logger.error(f"Error searching jobs: {str(e)}")
#         return []


# def get_job_details(api: Linkedin, job_id: str) -> Optional[Dict]:
#     """
#     Get detailed information for a specific job.

#     Args:
#         api: Authenticated LinkedIn API client
#         job_id: LinkedIn job ID

#     Returns:
#         Job details dictionary or None if error
#     """
#     try:
#         job_detail = api.get_job(job_id)
#         logger.info(f"Job details - ID {job_id}: {job_detail}")
#         return job_detail
#     except Exception as e:
#         logger.error(f"Error getting job details for {job_id}: {str(e)}")
#         return None


# def extract_job_info(job_detail: Dict, job_id: str) -> Dict:
#     """
#     Extract and format job information from LinkedIn job details.

#     Args:
#         job_detail: Raw job details from LinkedIn API
#                         api.send_message(recipients=[urn_id], message_body=message)

#     Returns:
#         Formatted job information dictionary
#     """
#     try:
#         company_info = (
#             job_detail.get("companyDetails", {})
#             .get(
#                 "com.linkedin.voyager.deco.jobs.web.shared.WebCompactJobPostingCompany",
#                 {},
#             )
#             .get("companyResolutionResult", {})
#         )

#         # Extract company ID from company info
#         company_id = None
#         if company_info:
#             # Try to get company ID from entityUrn
#             entity_urn = company_info.get("entityUrn", "")
#             if entity_urn:
#                 # Format: urn:li:fs_miniCompany:1234 -> extract 1234
#                 company_id = entity_urn.split(":")[-1]

#         return {
#             "job_id": job_id,
#             "title": job_detail.get("title", "N/A"),
#             "company": company_info.get("name", "N/A"),
#             "company_id": company_id,
#             "location": job_detail.get("formattedLocation", "N/A"),
#             "description": job_detail.get("description", {}).get("text", "N/A"),
#             "employment_type": job_detail.get("formattedEmploymentStatus", "N/A"),
#             "seniority_level": job_detail.get("formattedExperienceLevel", "N/A"),
#             "industries": job_detail.get("formattedIndustries", "N/A"),
#             "apply_url": f"https://www.linkedin.com/jobs/view/{job_id}",
#             "scraped_at": datetime.now().isoformat(),
#         }
#     except Exception as e:
#         logger.warning(f"Error extracting job info: {str(e)}")
#         return {
#             "job_id": job_id,
#             "title": "Error",
#             "company": "N/A",
#             "company_id": None,
#             "location": "N/A",
#             "description": f"Error extracting details: {str(e)}",
#             "employment_type": "N/A",
#             "seniority_level": "N/A",
#             "industries": "N/A",
#             "apply_url": f"https://www.linkedin.com/jobs/view/{job_id}",
#             "scraped_at": datetime.now().isoformat(),
#         }


# def scrape_job_listings(
#     keywords: str,
#     location: str = "",
#     limit: int = 10,
#     li_at_cookie: Optional[str] = None,
#     jsessionid_cookie: Optional[str] = None,
# ) -> Dict:
#     """
#     Complete job scraping workflow.

#     Args:
#         keywords: Job search keywords
#         location: Job location (optional)
#         limit: Maximum number of jobs to scrape
#         li_at_cookie: Optional li_at cookie
#         jsessionid_cookie: Optional JSESSIONID cookie

#     Returns:
#         Dictionary with success status and job details
#     """
#     try:
#         # Get authenticated client
#         api = get_linkedin_client(li_at_cookie, jsessionid_cookie)
#         if not api:
#             return {
#                 "success": False,
#                 "error": "Failed to authenticate with LinkedIn",
#                 "jobs": [],
#             }

#         # Search for jobs
#         jobs = search_jobs(api, keywords, location, limit)
#         if not jobs:
#             return {
#                 "success": True,
#                 "count": 0,
#                 "jobs": [],
#                 "message": "No jobs found matching criteria",
#                 "scraped_at": datetime.now().isoformat(),
#             }

#         # Extract details for each job
#         job_details = []
#         for i, job in enumerate(jobs, 1):
#             try:
#                 job_id = job.get("entityUrn", "").split(":")[-1]
#                 job_detail = get_job_details(api, job_id)
#                 logger.info(f"Job details for {job_id}: {job_detail}")
#                 if job_detail:
#                     job_info = extract_job_info(job_detail, job_id)
#                     job_details.append(job_info)

#                 if i % 5 == 0:
#                     logger.info(f"Progress: {i}/{len(jobs)} jobs processed")

#             except Exception as e:
#                 logger.warning(f"Skipped job: {str(e)}")
#                 continue

#         logger.info(f"✓ Successfully scraped {len(job_details)} jobs")

#         return {
#             "success": True,
#             "count": len(job_details),
#             "jobs": job_details,
#             "scraped_at": datetime.now().isoformat(),
#         }

#     except Exception as e:
#         logger.error(f"Error in scraping workflow: {str(e)}")
#         return {
#             "success": False,
#             "error": str(e),
#             "jobs": [],
#         }
