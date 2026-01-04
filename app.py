from fastapi import FastAPI, Query, HTTPException, status, UploadFile, File, Body
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
import json
from datetime import datetime
import logging
import os
import httpx
from dotenv import load_dotenv
from linkedin_functions import (
    get_linkedin_client,
    # scrape_job_listings,
    get_company_info,
    scrape_people,
    scrape_job_details_with_selenium,
)

# Load environment variables from .env file
load_dotenv()

app = FastAPI(
    title="LinkedIn Job Scraper API",
    description="REST API for scraping LinkedIn jobs, designed for n8n integration",
    version="1.0.0",
)


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


# Pydantic models
class PeopleScrapeRequest(BaseModel):
    company_name: str = Field(..., description="LinkedIn company slug (e.g. 'cgi')")
    query_params: str = Field(
        "", description="Query string for filtering (e.g. '?facetGeoRegion=90009533')"
    )
    min_results: int = Field(20, description="Minimum number of people to scrape")
    max_clicks: int = Field(
        10, description="Maximum number of 'Show more results' clicks"
    )


class PersonScrapeResponse(BaseModel):
    name: Optional[str]
    profile_url: Optional[str]
    title: Optional[str]
    mutuals: Optional[str]


# Job details scrape request/response models
class JobDetailsScrapeRequest(BaseModel):
    job_urls: list[str] = Field(..., description="List of LinkedIn job URLs to scrape")
    headless: Optional[bool] = Field(True, description="Run Chrome in headless mode")


class JobDetailsScrapeResponse(BaseModel):
    success: bool
    job_url: str
    job_id: Optional[str] = None
    title: Optional[str] = None
    company: Optional[str] = None
    location: Optional[str] = None
    description_html: Optional[str] = None
    description_text: Optional[str] = None
    employment_type: Optional[str] = None
    posted: Optional[str] = None
    company_logo_url: Optional[str] = None
    apply_url: Optional[str] = None
    scraped_at: Optional[str] = None
    error: Optional[str] = None
    html_debug: Optional[str] = None


# Add the /jobs/scrape/details endpoint (batch)

import re


def extract_job_id_from_url(url: str) -> str:
    # LinkedIn job URLs typically contain /jobs/view/<job_id>
    match = re.search(r"/jobs/view/(\d+)", url)
    if match:
        return match.group(1)
    # Fallback: try to find a long number in the URL
    match = re.search(r"(\d{7,})", url)
    if match:
        return match.group(1)
    return None


@app.post(
    "/jobs/scrape/details", tags=["Jobs"], response_model=list[JobDetailsScrapeResponse]
)
async def scrape_job_details_endpoint(request: JobDetailsScrapeRequest = Body(...)):
    """
    Scrape job details from a list of LinkedIn job pages using Selenium and BeautifulSoup.
    Returns a list of job details (title, company, location, description, etc.).
    Adds job_id extracted from the URL.
    """
    results = []
    for job_url in request.job_urls:
        job_id = extract_job_id_from_url(job_url)
        try:
            result = scrape_job_details_with_selenium(
                job_url, headless=request.headless
            )
            # Insert job_id into the result
            if isinstance(result, dict):
                result["job_id"] = job_id
            results.append(result)
        except Exception as e:
            logger.error(f"Error scraping job {job_url}: {str(e)}")
            results.append(
                {
                    "success": False,
                    "job_url": job_url,
                    "job_id": job_id,
                    "error": str(e),
                }
            )
    return results


# Add the /people/scrape endpoint after app and logger setup
@app.post("/people/scrape", tags=["People"], response_model=list[PersonScrapeResponse])
async def scrape_people_endpoint(request: PeopleScrapeRequest = Body(...)):
    """
    Scrape people from a LinkedIn company people page using Selenium and BeautifulSoup.
    Returns a list of people with name, profile_url, title, and mutuals.
    """
    try:
        people = scrape_people(
            company_name=request.company_name,
            query_params=request.query_params,
            min_results=request.min_results,
            max_clicks=request.max_clicks,
        )
        return people
    except Exception as e:
        logger.error(f"Error in people scrape endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


"""
FastAPI wrapper for LinkedIn Job Scraper
Designed for n8n integration
"""


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


# Pydantic models
class JobIDRequest(BaseModel):
    job_urls: list[str] = Field(
        ...,
        description="List of LinkedIn job URLs or job IDs",
        example=["https://www.linkedin.com/jobs/view/4325442308", "4325442309"],
    )
    listed_at: Optional[str] = Field(
        None, description="Filter jobs listed within the last X seconds", example=86400
    )


class JobInfo(BaseModel):
    job_id: str
    title: str
    company: str
    company_id: Optional[str] = None
    location: str
    description: str
    employment_type: str
    seniority_level: str
    industries: str
    apply_url: str
    scraped_at: str


class JobsResponse(BaseModel):
    success: bool
    count: Optional[int] = None
    jobs: list[JobInfo] = []
    scraped_at: Optional[str] = None
    error: Optional[str] = None


class CompanyResponse(BaseModel):
    success: bool
    company_id: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None
    industry: Optional[str] = None
    company_size: Optional[str] = None
    headquarters: Optional[str] = None
    website: Optional[str] = None
    specialties: Optional[list[str]] = None
    follower_count: Optional[int] = None
    error: Optional[str] = None


class PersonInfo(BaseModel):
    profile_id: str
    urn_id: str
    full_name: str
    first_name: str
    last_name: str
    headline: str
    location: str
    connection_degree: str
    profile_url: str
    profile_urn: str
    tracking_id: str
    scraped_at: str


@app.get("/", tags=["Info"])
async def home():
    """Root endpoint with API information"""
    return {
        "status": "online",
        "service": "LinkedIn Job Scraper API",
        "version": "1.0.0",
        "docs": "/docs",
        "endpoints": {
            "health": "/health",
            # "jobs_post": "/jobs (POST) - Get details for multiple job IDs",
            # "jobs_get": "/jobs (GET) - Get details for job IDs via query params",
            # "job_single": "/jobs/{job_id} (GET) - Get details for single job ID",
            "company": "/company/{company_id} (GET)",
            "people_search": "/people/search (POST) - Search people by company/region",
            "gotenberg_health": "/gotenberg/health (GET) - Check Gotenberg status",
            "convert_url": "/gotenberg/convert/url (POST) - Convert URL to PDF",
            "convert_html": "/gotenberg/convert/html (POST) - Convert HTML to PDF",
        },
    }


@app.get("/health", tags=["Health"])
async def health():
    """Health check endpoint for monitoring"""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}


# @app.post("/jobs", tags=["Jobs"], response_model=JobsResponse)
# async def get_jobs_post(request: JobIDRequest):
#     """
#     POST endpoint to get job details by URLs or IDs

#     Pass a list of LinkedIn job URLs or job IDs to retrieve detailed information.
#     Returns job details including company_id for each job.

#     Example body:
#     {
#         "job_urls": [
#             "https://www.linkedin.com/jobs/view/4325442308",
#             "https://www.linkedin.com/jobs/search/?currentJobId=4325442309&...",
#             "4325442310"
#         ]
#     }
#     """
#     try:
#         from linkedin_functions import get_jobs_by_ids, extract_job_id_from_url

#         # Extract job IDs from URLs
#         job_ids = []
#         for url in request.job_urls:
#             job_id = extract_job_id_from_url(url)
#             if job_id:
#                 job_ids.append(job_id)
#             else:
#                 logger.warning(f"Could not extract job ID from: {url}")

#         if not job_ids:
#             raise HTTPException(
#                 status_code=status.HTTP_400_BAD_REQUEST,
#                 detail="No valid job IDs could be extracted from provided URLs",
#             )

#         result = get_jobs_by_ids(job_ids)

#         if not result["success"]:
#             raise HTTPException(
#                 status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
#                 detail=result.get("error", "Unknown error occurred"),
#             )

#         return result

#     except HTTPException:
#         raise
#     except Exception as e:
#         logger.error(f"Error in jobs endpoint: {str(e)}")
#         raise HTTPException(
#             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
#         )


# @app.get("/jobs", tags=["Jobs"], response_model=JobsResponse)
# async def get_jobs_get(
#     job_urls: str = Query(
#         ...,
#         description="Comma-separated LinkedIn job URLs or IDs",
#         example="https://www.linkedin.com/jobs/view/4325442308,4325442309",
#     ),
# ):
#     """
#     GET endpoint to get job details by URLs or IDs via query parameters

#     Pass comma-separated job URLs or IDs in the query string.
#     Returns job details including company_id for each job.

#     Example: /jobs?job_urls=https://www.linkedin.com/jobs/view/4325442308,4325442309
#     """
#     try:
#         from linkedin_functions import get_jobs_by_ids, extract_job_id_from_url

#         # Split comma-separated URLs/IDs and strip whitespace
#         urls_list = [url.strip() for url in job_urls.split(",") if url.strip()]

#         # Extract job IDs from URLs
#         job_ids = []
#         for url in urls_list:
#             job_id = extract_job_id_from_url(url)
#             if job_id:
#                 job_ids.append(job_id)
#             else:
#                 logger.warning(f"Could not extract job ID from: {url}")

#         if not job_ids:
#             raise HTTPException(
#                 status_code=status.HTTP_400_BAD_REQUEST,
#                 detail="No valid job IDs could be extracted from provided URLs",
#             )

#         result = get_jobs_by_ids(job_ids)

#         if not result["success"]:
#             raise HTTPException(
#                 status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
#                 detail=result.get("error", "Unknown error occurred"),
#             )

#         return result

#     except HTTPException:
#         raise
#     except Exception as e:
#         logger.error(f"Error in jobs endpoint: {str(e)}")
#         raise HTTPException(
#             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
#         )


# @app.get("/jobs/{job_id}", tags=["Jobs"], response_model=JobsResponse)
# async def get_single_job(job_id: str):
#     """
#     GET endpoint to get details for a single job by ID

#     Pass job ID in the URL path.
#     Returns job details including company_id.

#     Example: /jobs/4325442308
#     """
#     try:
#         from linkedin_functions import get_jobs_by_ids, extract_job_id_from_url

#         # Extract job ID if it's a URL
#         extracted_id = extract_job_id_from_url(job_id)
#         if not extracted_id:
#             raise HTTPException(
#                 status_code=status.HTTP_400_BAD_REQUEST,
#                 detail=f"Could not extract job ID from: {job_id}",
#             )

#         result = get_jobs_by_ids([extracted_id])

#         if not result["success"]:
#             raise HTTPException(
#                 status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
#                 detail=result.get("error", "Unknown error occurred"),
#             )

#         return result

#     except HTTPException:
#         raise
#     except Exception as e:
#         logger.error(f"Error in job endpoint: {str(e)}")
#         raise HTTPException(
#             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
#         )


@app.get("/company/{company_id}", tags=["Company"], response_model=CompanyResponse)
async def get_company(company_id: str):
    """
    GET endpoint for retrieving company information

    Fetches detailed information about a LinkedIn company by its ID.
    Use company name or universal-name (slug) as the company_id.

    Example: /company/microsoft or /company/1035 (numeric ID)
    """
    try:
        logger.info(f"Fetching company info for: {company_id}")

        # Get authenticated LinkedIn client
        api = get_linkedin_client()
        if not api:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to authenticate with LinkedIn. Check .env credentials.",
            )

        # Get company information
        company_data = get_company_info(api, company_id)
        logger.info(f"Company data: {company_data}")

        if not company_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Company '{company_id}' not found",
            )

        # Extract and format company details
        response = {
            "success": True,
            "company_id": company_id,
            "name": company_data.get("name", "N/A"),
            "description": company_data.get("description", "N/A"),
            "industry": company_data.get("industry", "N/A"),
            "company_size": company_data.get("companyPageSize", "N/A"),
            "headquarters": company_data.get("headquarters", {}).get("city", "N/A"),
            "website": company_data.get("website", "N/A"),
            "specialties": company_data.get("specialities", []),
            "follower_count": company_data.get("followerCount", 0),
        }

        logger.info(f"✓ Retrieved info for company: {response['name']}")
        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching company info: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving company information: {str(e)}",
        )


@app.get("/gotenberg/health", tags=["Gotenberg"])
async def gotenberg_health():
    """
    Check Gotenberg service health

    Returns the health status of the Gotenberg PDF service.
    """
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get("http://gotenberg:3000/health", timeout=5.0)
            return {
                "success": True,
                "gotenberg_status": (
                    "healthy" if response.status_code == 200 else "unhealthy"
                ),
                "status_code": response.status_code,
            }
    except Exception as e:
        logger.error(f"Gotenberg health check failed: {str(e)}")
        return {"success": False, "gotenberg_status": "unreachable", "error": str(e)}


@app.post("/gotenberg/convert/url", tags=["Gotenberg"])
async def convert_url_to_pdf(
    url: str = Query(..., description="URL to convert to PDF")
):
    """
    Convert a URL to PDF using Gotenberg

    Pass a URL and get back a PDF file.
    Example: /gotenberg/convert/url?url=https://example.com
    """
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Prepare form data for Gotenberg
            files = {"url": (None, url)}

            response = await client.post(
                "http://gotenberg:3000/forms/chromium/convert/url", files=files
            )

            if response.status_code != 200:
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"Gotenberg conversion failed: {response.text}",
                )

            return StreamingResponse(
                iter([response.content]),
                media_type="application/pdf",
                headers={"Content-Disposition": f"attachment; filename=converted.pdf"},
            )

    except httpx.TimeoutException:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Gotenberg service timeout",
        )
    except Exception as e:
        logger.error(f"PDF conversion error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@app.post("/gotenberg/convert/html", tags=["Gotenberg"])
async def convert_html_to_pdf(html_file: UploadFile = File(...)):
    """
    Convert HTML to PDF using Gotenberg

    Upload an HTML file and get back a PDF.
    """
    try:
        html_content = await html_file.read()

        async with httpx.AsyncClient(timeout=30.0) as client:
            files = {"files": ("index.html", html_content, "text/html")}

            response = await client.post(
                "http://gotenberg:3000/forms/chromium/convert/html", files=files
            )

            if response.status_code != 200:
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"Gotenberg conversion failed: {response.text}",
                )

            return StreamingResponse(
                iter([response.content]),
                media_type="application/pdf",
                headers={
                    "Content-Disposition": f"attachment; filename={html_file.filename.replace('.html', '.pdf')}"
                },
            )

    except httpx.TimeoutException:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Gotenberg service timeout",
        )
    except Exception as e:
        logger.error(f"PDF conversion error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@app.post("/gotenberg/convert/html/string", tags=["Gotenberg"])
async def convert_html_string_to_pdf(
    html_content: str = Query(..., description="HTML content as string")
):
    """
    Convert HTML string to PDF using Gotenberg

    Pass HTML content as a query parameter and get back a PDF file.
    Example: /gotenberg/convert/html/string?html_content=<html><body>Hello</body></html>
    """
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            files = {"files": ("index.html", html_content.encode(), "text/html")}

            response = await client.post(
                "http://gotenberg:3000/forms/chromium/convert/html", files=files
            )

            if response.status_code != 200:
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"Gotenberg conversion failed: {response.text}",
                )

            return StreamingResponse(
                iter([response.content]),
                media_type="application/pdf",
                headers={"Content-Disposition": "attachment; filename=converted.pdf"},
            )

    except httpx.TimeoutException:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Gotenberg service timeout",
        )
    except Exception as e:
        logger.error(f"PDF conversion error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", 5000))
    uvicorn.run("app:app", host="0.0.0.0", port=port, reload=False)
