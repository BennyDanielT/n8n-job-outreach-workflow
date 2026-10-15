import os
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup
from dotenv import load_dotenv

# Load LinkedIn credentials from .env
load_dotenv()
LINKEDIN_EMAIL = os.getenv("LINKEDIN_EMAIL")
LINKEDIN_PASSWORD = os.getenv("LINKEDIN_PASSWORD")

# Path to your Chrome user data (enables persistent login/session)
CHROME_PROFILE_PATH = os.getenv(
    "CHROME_PROFILE_PATH", None
)  # e.g. 'C:/Users/benny/AppData/Local/Google/Chrome/User Data'
CHROME_PROFILE_NAME = os.getenv("CHROME_PROFILE_NAME", "Default")

if not CHROME_PROFILE_PATH:
    print(
        "[WARNING] CHROME_PROFILE_PATH is not set. Persistent login/session will NOT work. Set it in your .env file."
    )
# For best results, use a dedicated Selenium profile (not your main Chrome profile).
# Example setup:
#   CHROME_PROFILE_PATH=C:/Users/benny/AppData/Local/Google/Chrome/SeleniumProfile
else:
    print(
        f"[INFO] Using Chrome profile: {CHROME_PROFILE_PATH} (profile name: {CHROME_PROFILE_NAME})"
    )
    print(
        "[ACTION REQUIRED] Make sure you have created this profile and logged in to LinkedIn at least once using this profile."
    )
    print("To do this, run:")
    print(
        f'  "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe" --user-data-dir="{CHROME_PROFILE_PATH}" --profile-directory="{CHROME_PROFILE_NAME}"'
    )
    print("Then log in to LinkedIn, close Chrome, and run this script again.")


def get_driver(headless=True):
    chrome_options = Options()
    # If using a Chrome profile, do NOT use headless mode (it will crash)
    if CHROME_PROFILE_PATH:
        if headless:
            print(
                "[INFO] Disabling headless mode because CHROME_PROFILE_PATH is set (headless + user profile will crash Chrome)."
            )
        headless = False
        chrome_options.add_argument(f"--user-data-dir={CHROME_PROFILE_PATH}")
        chrome_options.add_argument(f"--profile-directory={CHROME_PROFILE_NAME}")
    if headless:
        chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    return webdriver.Chrome(options=chrome_options)


def scrape_people(company_name, query_params="", min_results=20, max_clicks=10):
    url = f"https://www.linkedin.com/company/{company_name}/people/{query_params}"
    driver = get_driver(headless=True)
    try:
        driver.get(url)
        time.sleep(3)
        # If not logged in, perform login
        if "login" in driver.current_url:
            print("Logging in...")
            email_input = driver.find_element(By.ID, "username")
            password_input = driver.find_element(By.ID, "password")
            email_input.send_keys(LINKEDIN_EMAIL)
            password_input.send_keys(LINKEDIN_PASSWORD)
            password_input.send_keys(Keys.RETURN)
            time.sleep(3)
            driver.get(url)
            time.sleep(3)
        # Click 'Show more results' until enough results or max_clicks
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
                break  # No more button or can't click
        return results
    finally:
        driver.quit()


if __name__ == "__main__":
    company = "vtscada-by-trihedral"  # Change to your target company
    query_params = "?facetGeoRegion=90009533&keywords=llm"  # e.g. '?facetGeoRegion=us%3A0' for US region
    people = scrape_people(company, query_params=query_params, min_results=20)
    for idx, person in enumerate(people, 1):
        print(f"Person ---> {person}")
        if person["name"]:
            print(
                f"{idx}. {person['name']} | {person['title']} | {person['mutuals']} |"
            )
