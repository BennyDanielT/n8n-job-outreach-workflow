# Instructions.md

## 1. Clone the Repository

```bash
git clone <your-repo-url>
cd n8n
```

## 2. Set Up Environment Variables

- Copy the example env file (if present) or create a `.env` file with your credentials and configuration.

```bash
cp .env.example .env  # If .env.example exists
# Or create .env manually
```

## 3. Install Python Dependencies (for FastAPI app)

It is recommended to use a virtual environment:

```bash
sudo apt update
sudo apt install python3-venv python3-pip -y
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

## 4. Build and Run Docker Services (n8n, Gotenberg)

Make sure Docker and Docker Compose are installed:

```bash
sudo apt install docker.io docker-compose -y
sudo systemctl enable --now docker
```

Start the services:

```bash
sudo docker-compose up -d
```

- This will start n8n and Gotenberg as defined in `docker-compose.yml`.

## 5. Run the FastAPI App (Locally)

In a new terminal (with your virtual environment activated):

```bash
uvicorn app:app --host 0.0.0.0 --port 8000 --reload
```

- The API will be available at: http://<your-server-ip>:8000

## 6. Access n8n and Gotenberg

- n8n: http://<your-server-ip>:5678
- Gotenberg: http://<your-server-ip>:3000

## 7. (Optional) Manage Docker Services

- To stop services:
  ```bash
  sudo docker-compose down
  ```
- To view logs:
  ```bash
  sudo docker-compose logs -f
  ```

## 8. Configure Nginx as a Reverse Proxy

To proxy requests to n8n, Gotenberg, and the FastAPI (Uvicorn) app, add the following to your Nginx configuration (e.g., `/etc/nginx/sites-available/default` or a new site file):

```
server {
    listen 80;
    server_name your-domain.com;  # Change to your domain or server IP

    # Proxy to FastAPI (Uvicorn)
    location /api/ {
        proxy_pass http://127.0.0.1:8000/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Proxy to n8n
    location /n8n/ {
        proxy_pass http://127.0.0.1:5678/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Proxy to Gotenberg
    location /gotenberg/ {
        proxy_pass http://127.0.0.1:3000/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### Steps to Apply Nginx Changes

1. Edit your Nginx config:
   ```bash
   sudo nano /etc/nginx/sites-available/default
   # Or create a new file in /etc/nginx/sites-available/ and symlink to sites-enabled
   ```
2. Paste the above configuration, adjusting `server_name` and paths as needed.
3. Test the configuration:
   ```bash
   sudo nginx -t
   ```
4. Reload Nginx:
   ```bash
   sudo systemctl reload nginx
   ```

- Now, requests to `http://your-domain.com/api/` go to FastAPI, `/n8n/` to n8n, and `/gotenberg/` to Gotenberg.
- Adjust firewall and DNS as needed for your deployment.

---

**Note:**

- Ensure your `.env` is correctly configured for LinkedIn and other credentials.
- If you need to expose ports, ensure your firewall allows 8000, 5678, and 3000.
- For production, consider using a process manager (e.g., systemd, supervisor) for the FastAPI app.
