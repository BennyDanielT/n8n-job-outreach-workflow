# LinkedIn Scraper API Test Script
# Tests all endpoints with sample data

Write-Host "`n================================" -ForegroundColor Cyan
Write-Host "LinkedIn Scraper API Test Suite" -ForegroundColor Cyan
Write-Host "================================`n" -ForegroundColor Cyan

$baseUrl = "http://localhost:5000"

# Test 1: Health Check
Write-Host "[TEST 1] Health Check Endpoint" -ForegroundColor Yellow
try {
    $health = Invoke-RestMethod -Uri "$baseUrl/health" -Method Get
    Write-Host "✓ Status: $($health.status)" -ForegroundColor Green
    Write-Host "✓ Timestamp: $($health.timestamp)`n" -ForegroundColor Green
} catch {
    Write-Host "✗ Health check failed: $_`n" -ForegroundColor Red
}

# Test 2: Root Endpoint
Write-Host "[TEST 2] Root Endpoint (API Info)" -ForegroundColor Yellow
try {
    $info = Invoke-RestMethod -Uri "$baseUrl/" -Method Get
    Write-Host "✓ Service: $($info.service)" -ForegroundColor Green
    Write-Host "✓ Version: $($info.version)" -ForegroundColor Green
    Write-Host "✓ Available endpoints:" -ForegroundColor Green
    $info.endpoints.PSObject.Properties | ForEach-Object {
        Write-Host "  - $($_.Name): $($_.Value)" -ForegroundColor Cyan
    }
    Write-Host ""
} catch {
    Write-Host "✗ Root endpoint failed: $_`n" -ForegroundColor Red
}

# Test 3: GET /scrape (Query Parameters)
Write-Host "[TEST 3] GET /scrape - Job Scraping with URL Parameters" -ForegroundColor Yellow
try {
    $params = @{
        keywords = "machine learning engineer"
        location = "United States"
        limit = 3
    }
    
    Write-Host "Scraping jobs with keywords: '$($params.keywords)'..." -ForegroundColor Gray
    $result = Invoke-RestMethod -Uri "$baseUrl/scrape" -Method Get -Body $params
    
    if ($result.success) {
        Write-Host "✓ Success: Found $($result.count) jobs" -ForegroundColor Green
        Write-Host "✓ Scraped at: $($result.scraped_at)" -ForegroundColor Green
        
        if ($result.jobs.Count -gt 0) {
            Write-Host "`n  Sample Job:" -ForegroundColor Cyan
            $job = $result.jobs[0]
            Write-Host "  - Title: $($job.title)" -ForegroundColor White
            Write-Host "  - Company: $($job.company)" -ForegroundColor White
            Write-Host "  - Location: $($job.location)" -ForegroundColor White
            Write-Host "  - Employment Type: $($job.employment_type)" -ForegroundColor White
            Write-Host "  - Apply URL: $($job.apply_url)" -ForegroundColor White
        }
        Write-Host ""
    } else {
        Write-Host "✗ Scraping failed: $($result.error)`n" -ForegroundColor Red
    }
} catch {
    Write-Host "✗ GET /scrape failed: $_" -ForegroundColor Red
    Write-Host "Error details: $($_.Exception.Message)`n" -ForegroundColor Red
}

# Test 4: POST /scrape (JSON Body)
Write-Host "[TEST 4] POST /scrape - Job Scraping with JSON Body" -ForegroundColor Yellow
try {
    $body = @{
        keywords = "python developer"
        location = "Remote"
        limit = 2
    } | ConvertTo-Json
    
    Write-Host "Scraping jobs with POST request..." -ForegroundColor Gray
    $result = Invoke-RestMethod -Uri "$baseUrl/scrape" -Method Post -Body $body -ContentType "application/json"
    
    if ($result.success) {
        Write-Host "✓ Success: Found $($result.count) jobs" -ForegroundColor Green
        Write-Host "✓ Scraped at: $($result.scraped_at)" -ForegroundColor Green
        
        if ($result.jobs.Count -gt 0) {
            Write-Host "`n  Jobs Found:" -ForegroundColor Cyan
            foreach ($job in $result.jobs) {
                Write-Host "  - $($job.title) at $($job.company)" -ForegroundColor White
            }
        }
        Write-Host ""
    } else {
        Write-Host "✗ Scraping failed: $($result.error)`n" -ForegroundColor Red
    }
} catch {
    Write-Host "✗ POST /scrape failed: $_" -ForegroundColor Red
    Write-Host "Error details: $($_.Exception.Message)`n" -ForegroundColor Red
}

# Test 5: GET /company (Company Information)
Write-Host "[TEST 5] GET /company - Company Information" -ForegroundColor Yellow

$companies = @("microsoft", "google", "openai")

foreach ($companyId in $companies) {
    try {
        Write-Host "Fetching info for: $companyId..." -ForegroundColor Gray
        $company = Invoke-RestMethod -Uri "$baseUrl/company/$companyId" -Method Get
        
        if ($company.success) {
            Write-Host "✓ Company: $($company.name)" -ForegroundColor Green
            Write-Host "  - Industry: $($company.industry)" -ForegroundColor White
            Write-Host "  - Size: $($company.company_size)" -ForegroundColor White
            Write-Host "  - Headquarters: $($company.headquarters)" -ForegroundColor White
            Write-Host "  - Website: $($company.website)" -ForegroundColor White
            Write-Host "  - Followers: $($company.follower_count)" -ForegroundColor White
            if ($company.specialties -and $company.specialties.Count -gt 0) {
                Write-Host "  - Specialties: $($company.specialties -join ', ')" -ForegroundColor White
            }
            Write-Host ""
        } else {
            Write-Host "✗ Failed: $($company.error)`n" -ForegroundColor Red
        }
    } catch {
        Write-Host "✗ Failed to fetch $companyId : $_" -ForegroundColor Red
        Write-Host "  Error: $($_.Exception.Message)`n" -ForegroundColor Red
    }
    
    Start-Sleep -Seconds 1
}

Write-Host "`n================================" -ForegroundColor Cyan
Write-Host "Test Suite Complete!" -ForegroundColor Cyan
Write-Host "================================`n" -ForegroundColor Cyan
