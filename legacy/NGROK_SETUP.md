# Quick Setup Guide: Exposing Your API with ngrok

## 🚀 Quick Start

### 1. Get ngrok Auth Token

1. Go to https://dashboard.ngrok.com/signup (free account)
2. After signup, go to https://dashboard.ngrok.com/get-started/your-authtoken
3. Copy your authtoken

### 2. Configure ngrok

```bash
# Edit ngrok.yml and add your authtoken
# Replace YOUR_NGROK_AUTH_TOKEN_HERE with your actual token
```

Or use the `.env` file:

```bash
# Add to .env
NGROK_AUTHTOKEN=your_actual_token_here
```

### 3. Start Everything

```bash
# Start both API and ngrok
docker-compose up -d

# Check the ngrok public URL
docker logs ngrok-tunnel
```

### 4. Access ngrok Dashboard

Open http://localhost:4040 in your browser to see:

- Your public URL (e.g., `https://abc123.ngrok.io`)
- Live request inspection
- Request/response details

## 📋 Usage

### Get Your Public URL

**Option 1: Check logs**

```bash
docker logs ngrok-tunnel
```

Look for a line like: `url=https://xyz123.ngrok-free.app`

**Option 2: ngrok Web Interface**

- Go to http://localhost:4040
- See the "Forwarding" URL

**Option 3: API call**

```bash
curl http://localhost:4040/api/tunnels | python -m json.tool
```

### Test Your Public API

```bash
# Replace YOUR_NGROK_URL with your actual ngrok URL
curl "https://YOUR_NGROK_URL.ngrok-free.app/health"

# Test job scraping
curl "https://YOUR_NGROK_URL.ngrok-free.app/scrape?keywords=Python%20Developer&limit=5"
```

## 🔗 Using with n8n

### If n8n is on a different machine or cloud:

1. **Get your ngrok URL** (see above)
2. **In n8n HTTP Request node:**
   - URL: `https://YOUR_NGROK_URL.ngrok-free.app/scrape`
   - Method: GET or POST
   - Parameters: `keywords`, `location`, `limit`

### Example n8n Workflow

```
[Webhook/Schedule]
    → [HTTP Request to ngrok URL]
    → [Process Jobs]
    → [Send Notifications]
```

## 🛠️ Commands

```bash
# Start services
docker-compose up -d

# View ngrok logs (find your public URL here)
docker logs ngrok-tunnel -f

# View API logs
docker logs linkedin-job-scraper -f

# Stop everything
docker-compose down

# Restart ngrok only
docker-compose restart ngrok
```

## 🔍 Troubleshooting

### Can't find ngrok URL?

```bash
# Check logs
docker logs ngrok-tunnel

# Or access web interface
# Open: http://localhost:4040
```

### ngrok not connecting?

```bash
# Check if authtoken is set
docker exec ngrok-tunnel cat /etc/ngrok.yml

# Restart ngrok
docker-compose restart ngrok
```

### API not accessible via ngrok?

```bash
# Test local API first
curl http://localhost:5000/health

# Check if containers can communicate
docker exec ngrok-tunnel ping linkedin-scraper
```

## ⚠️ Important Notes

1. **Free ngrok URLs change** every time you restart (unless you have a paid plan)
2. **Free tier limitations:**
   - URL changes on restart
   - Limited requests per minute
   - ngrok branding page before first visit
3. **Security:** Don't expose credentials in URL parameters
4. **For production:** Use a proper domain or paid ngrok plan

## 💡 Alternative: Local Testing Without ngrok

If n8n is on the same machine:

```bash
# Just start the API
docker-compose up linkedin-scraper -d

# Use in n8n
# URL: http://localhost:5000/scrape
```

## 🎯 Pro Tips

- **Bookmark your ngrok dashboard:** http://localhost:4040
- **Save successful URLs** for testing during your session
- **Monitor requests** in real-time via ngrok dashboard
- **Use POST method** for sensitive data (not in URL)
- **Set up webhooks** in n8n to trigger workflows externally

## 📊 ngrok Dashboard Features

At http://localhost:4040 you can:

- ✅ See your public URL
- ✅ Inspect all HTTP requests
- ✅ Replay requests
- ✅ Check request/response headers
- ✅ Debug issues in real-time
