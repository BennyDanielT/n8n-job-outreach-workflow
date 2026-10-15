#!/usr/bin/env python3
"""
LinkedIn Scraper API Test Script (Python)
Tests all endpoints with sample data
"""

import requests
import json
from typing import Dict, Any
from fastapi import FastAPI, Body
from pydantic import BaseModel
from typing import List
from linkedin_functions import scrape_people, send_linkedin_messages

BASE_URL = "http://localhost:5000"


def print_header(text: str):
    """Print formatted header"""
    print(f"\n{'=' * 50}")
    print(f"{text}")
    print('=' * 50)


def print_test(test_name: str):
    """Print test name"""
    print(f"\n[TEST] {test_name}")
    print("-" * 50)


def test_health_check():
    """Test health check endpoint"""
    print_test("Health Check Endpoint")
    try:
        response = requests.get(f"{BASE_URL}/health")
        response.raise_for_status()
        data = response.json()
        print(f"✓ Status: {data['status']}")
        print(f"✓ Timestamp: {data['timestamp']}")
        return True
    except Exception as e:
        print(f"✗ Failed: {e}")
        return False


def test_root_endpoint():
    """Test root endpoint"""
    print_test("Root Endpoint (API Info)")
    try:
        response = requests.get(f"{BASE_URL}/")
        response.raise_for_status()
        data = response.json()
        print(f"✓ Service: {data['service']}")
        print(f"✓ Version: {data['version']}")
        print("✓ Available endpoints:")
        for name, endpoint in data['endpoints'].items():
            print(f"  - {name}: {endpoint}")
        return True
    except Exception as e:
        print(f"✗ Failed: {e}")
        return False


def test_scrape_get():
    """Test GET /scrape with query parameters"""
    print_test("GET /scrape - Job Scraping with URL Parameters")
    try:
        params = {
            "keywords": "data scientist",
            "location": "San Francisco",
            "limit": 3
        }
        
        print(f"Scraping jobs with keywords: '{params['keywords']}'...")
        response = requests.get(f"{BASE_URL}/scrape", params=params)
        response.raise_for_status()
        data = response.json()
        
        if data['success']:
            print(f"✓ Success: Found {data['count']} jobs")
            print(f"✓ Scraped at: {data['scraped_at']}")
            
            if data['jobs']:
                job = data['jobs'][0]
                print("\n  Sample Job:")
                print(f"  - Title: {job['title']}")
                print(f"  - Company: {job['company']}")
                print(f"  - Location: {job['location']}")
                print(f"  - Employment Type: {job['employment_type']}")
                print(f"  - Apply URL: {job['apply_url']}")
            return True
        else:
            print(f"✗ Scraping failed: {data.get('error', 'Unknown error')}")
            return False
    except Exception as e:
        print(f"✗ Failed: {e}")
        return False


def test_scrape_post():
    """Test POST /scrape with JSON body"""
    print_test("POST /scrape - Job Scraping with JSON Body")
    try:
        payload = {
            "keywords": "software engineer",
            "location": "Remote",
            "limit": 2
        }
        
        print("Scraping jobs with POST request...")
        response = requests.post(
            f"{BASE_URL}/scrape",
            json=payload,
            headers={"Content-Type": "application/json"}
        )
        response.raise_for_status()
        data = response.json()
        
        if data['success']:
            print(f"✓ Success: Found {data['count']} jobs")
            print(f"✓ Scraped at: {data['scraped_at']}")
            
            if data['jobs']:
                print("\n  Jobs Found:")
                for job in data['jobs']:
                    print(f"  - {job['title']} at {job['company']}")
            return True
        else:
            print(f"✗ Scraping failed: {data.get('error', 'Unknown error')}")
            return False
    except Exception as e:
        print(f"✗ Failed: {e}")
        return False


def test_company_info():
    """Test GET /company endpoint"""
    print_test("GET /company - Company Information")
    
    companies = ["microsoft", "apple", "netflix"]
    success_count = 0
    
    for company_id in companies:
        try:
            print(f"\nFetching info for: {company_id}...")
            response = requests.get(f"{BASE_URL}/company/{company_id}")
            response.raise_for_status()
            data = response.json()
            
            if data['success']:
                print(f"✓ Company: {data['name']}")
                print(f"  - Industry: {data.get('industry', 'N/A')}")
                print(f"  - Size: {data.get('company_size', 'N/A')}")
                print(f"  - Headquarters: {data.get('headquarters', 'N/A')}")
                print(f"  - Website: {data.get('website', 'N/A')}")
                print(f"  - Followers: {data.get('follower_count', 0)}")
                if data.get('specialties'):
                    print(f"  - Specialties: {', '.join(data['specialties'][:3])}")
                success_count += 1
            else:
                print(f"✗ Failed: {data.get('error', 'Unknown error')}")
        except Exception as e:
            print(f"✗ Failed to fetch {company_id}: {e}")
    
    return success_count > 0


app = FastAPI()

class ScrapeRequest(BaseModel):
    company_name: str
    query_params: str = ""
    min_results: int = 20
    max_clicks: int = 10

class MessageRequest(BaseModel):
    profile_urls: List[str]
    message: str
    li_at_cookie: str = None
    jsessionid_cookie: str = None

@app.post("/people/scrape")
def scrape_people_endpoint(req: ScrapeRequest):
    people = scrape_people(
        req.company_name,
        req.query_params,
        req.min_results,
        req.max_clicks
    )
    return {"results": people}

@app.post("/people/message")
def send_messages_endpoint(req: MessageRequest):
    result = send_linkedin_messages(
        req.profile_urls,
        req.message,
        req.li_at_cookie,
        req.jsessionid_cookie
    )
    return {"results": result}


# Example usage (for script/testing)
if __name__ == "__main__":
    # Example: scrape people and send a message
    company = "microsoft"
    people = scrape_people(company, min_results=2)
    profile_urls = [p["profile_url"] for p in people if p["profile_url"]]
    print("Scraped URLs:", profile_urls)
    if profile_urls:
        message = "Hello from the API!"
        send_results = send_linkedin_messages(profile_urls, message)
        print("Message send results:", send_results)

def run_all_tests():
    """Run all tests"""
    print_header("LinkedIn Scraper API Test Suite")
    
    results = {
        "Health Check": test_health_check(),
        "Root Endpoint": test_root_endpoint(),
        "GET /scrape": test_scrape_get(),
        "POST /scrape": test_scrape_post(),
        "GET /company": test_company_info(),
    }
    
    print_header("Test Results Summary")
    passed = sum(results.values())
    total = len(results)
    
    for test_name, passed_test in results.items():
        status = "✓ PASSED" if passed_test else "✗ FAILED"
        print(f"{test_name}: {status}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    print("=" * 50)
    
    return passed == total


if __name__ == "__main__":
    import sys
    success = run_all_tests()
    sys.exit(0 if success else 1)
