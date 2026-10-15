# LinkedIn Job Scraper API

A containerized REST API for scraping LinkedIn jobs, designed for n8n integration.

## 🚀 Quick Start

### 1. Setup Environment Variables

```bash
# Copy the example env file
cp .env.example .env

# Edit .env with your credentials
LINKEDIN_EMAIL=your_email@example.com
LINKEDIN_PASSWORD=your_password
NGROK_AUTHTOKEN=your_ngrok_token  # Get from https://dashboard.ngrok.com
```

### 2. Run with Docker Compose (includes ngrok)

```bash
# Build and start both API and ngrok
docker-compose up -d

# Get your public ngrok URL
docker logs ngrok-tunnel

# Or visit ngrok dashboard
# Open: http://localhost:4040

# Check logs
docker-compose logs -f

# Stop everything
docker-compose down
```

### 3. Run with Docker (manual, without ngrok)

```bash
# Build the image
docker build -t linkedin-scraper:latest .

# Run the container
docker run -d \
  -p 5000:5000 \
  -e LINKEDIN_EMAIL=your_email@example.com \
  -e LINKEDIN_PASSWORD=your_password \
  --name linkedin-scraper \
  linkedin-scraper:latest

# Check if it's running
curl http://localhost:5000/health
```

## 🌐 Exposing Your API (ngrok)

**Want to access your API from anywhere or integrate with cloud n8n?**

See [NGROK_SETUP.md](NGROK_SETUP.md) for detailed instructions.

**Quick:**

1. Get free authtoken from https://dashboard.ngrok.com
2. Add to `ngrok.yml` or `.env`
3. Run `docker-compose up -d`
4. Get your public URL from http://localhost:4040

## 📡 API Endpoints

### Health Check

```
GET /health
```

**Response:**

```json
{
  "status": "healthy",
  "timestamp": "2025-12-23T12:00:00.000000"
}
```

### Scrape Jobs (GET)

```
GET /scrape?keywords=Machine%20Learning&location=United%20States&limit=25
```

**Query Parameters:**

- `keywords` (required): Job search keywords
- `location` (optional): Job location
- `limit` (optional): Number of jobs (1-100, default: 10)
- `li_at_cookie` (optional): LinkedIn li_at cookie for better reliability
- `jsessionid_cookie` (optional): LinkedIn JSESSIONID cookie

**Response:**

```json
{
  "success": true,
  "count": 25,
  "scraped_at": "2025-12-23T12:00:00.000000",
  "jobs": [
    {
      "job_id": "123456789",
      "title": "Machine Learning Engineer",
      "company": "Tech Company",
      "location": "San Francisco, CA",
      "description": "...",
      "employment_type": "Full-time",
      "seniority_level": "Mid-Senior level",
      "industries": "Technology",
      "apply_url": "https://www.linkedin.com/jobs/view/123456789",
      "scraped_at": "2025-12-23T12:00:00.000000"
    }
  ]
}
```

### Scrape Jobs (POST)

```
POST /scrape
Content-Type: application/json
```

**Request Body:**

```json
{
  "keywords": "Machine Learning Engineer",
  "location": "United States",
  "limit": 25,
  "li_at_cookie": "optional_cookie_value",
  "jsessionid_cookie": "optional_cookie_value"
}
```

**Response:** Same as GET endpoint

## 🔧 n8n Integration

### Method 1: HTTP Request Node (GET)

1. Add **HTTP Request** node in n8n
2. Configure:
   - **Method**: GET
   - **URL**: `http://localhost:5000/scrape`
   - **Query Parameters**:
     - `keywords`: `Machine Learning Engineer`
     - `location`: `United States`
     - `limit`: `25`
3. The response will contain all job data in `json.jobs`

### Method 2: HTTP Request Node (POST)

1. Add **HTTP Request** node in n8n
2. Configure:
   - **Method**: POST
   - **URL**: `http://localhost:5000/scrape`
   - **Body Content Type**: JSON
   - **Body**:
     ```json
     {
       "keywords": "{{ $json.keywords }}",
       "location": "{{ $json.location }}",
       "limit": 25
     }
     ```

### Method 3: Webhook Trigger

1. Use n8n **Webhook** node to receive external triggers
2. Connect to **HTTP Request** node calling your API
3. Process results with n8n nodes (Filter, Set, etc.)

### Example n8n Workflow

```
[Schedule Trigger]
    ↓
[Set Parameters]
    ↓
[HTTP Request] → Call LinkedIn API
    ↓
[Split In Batches] → Process jobs
    ↓
[Filter] → Filter by criteria
    ↓
[Send Email/Slack] → Notify about matches
```

## 🔐 Using Cookies (Recommended)

For better reliability, pass LinkedIn cookies:

```bash
# GET request with cookies
curl "http://localhost:5000/scrape?keywords=Data%20Scientist&li_at_cookie=YOUR_LI_AT_COOKIE&jsessionid_cookie=YOUR_JSESSIONID_COOKIE"

# POST request with cookies
curl -X POST http://localhost:5000/scrape \
  -H "Content-Type: application/json" \
  -d '{
    "keywords": "Data Scientist",
    "location": "Canada",
    "limit": 10,
    "li_at_cookie": "YOUR_LI_AT_COOKIE",
    "jsessionid_cookie": "YOUR_JSESSIONID_COOKIE"
  }'
```

## 🐛 Troubleshooting

### Check container logs

```bash
docker logs linkedin-scraper -f
```

### Test the API

```bash
# Health check
curl http://localhost:5000/health

# Simple scrape test
curl "http://localhost:5000/scrape?keywords=Python%20Developer&limit=5"
```

### Common Issues

1. **Authentication Failed**: Update credentials in `.env` or use cookies
2. **Port Already in Use**: Change port in `docker-compose.yml`
3. **Timeout**: Increase limit parameter or check LinkedIn rate limits

## 📊 Production Deployment

### Deploy to Cloud

**Docker Hub:**

```bash
docker tag linkedin-scraper:latest your-username/linkedin-scraper:latest
docker push your-username/linkedin-scraper:latest
```

**AWS ECS, Google Cloud Run, Azure Container Instances:**

- Use the Docker image
- Set environment variables for credentials
- Expose port 5000
- Use health check endpoint `/health`

### Security Best Practices

1. **Never commit credentials** to Git
2. Use **environment variables** or secrets management
3. Add **rate limiting** in production
4. Use **HTTPS** with reverse proxy (nginx/traefik)
5. Implement **authentication** for API access

## 📝 Notes

- LinkedIn may rate-limit requests - use reasonable limits
- Cookie-based auth is more reliable than username/password
- Consider caching results to reduce API calls
- Monitor logs for blocked requests or session expiry
