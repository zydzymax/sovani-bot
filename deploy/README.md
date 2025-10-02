# SoVAni Bot - Production Deployment Guide

## Stage 10 - Production Deployment Configuration

This directory contains production deployment configs for SoVAni Bot:
- FastAPI backend (uvicorn + systemd)
- Nginx reverse proxy + static file serving
- Telegram Mini App (React frontend)

---

## Prerequisites

1. **System requirements:**
   - Ubuntu 20.04+ or similar Linux
   - Python 3.11+
   - Node.js 18+ and npm
   - Nginx
   - PostgreSQL (recommended for production)

2. **Installed packages:**
   ```bash
   sudo apt update
   sudo apt install -y python3 python3-pip python3-venv nginx postgresql
   ```

---

## Deployment Steps

### 1. Install Python Dependencies

```bash
cd /root/sovani_bot
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure Environment Variables

Create `.env` file from `.env.example`:

```bash
cp .env.example .env
nano .env
```

**Important variables for production:**
- `DATABASE_URL` - Use PostgreSQL instead of SQLite
- `ALLOWED_TG_USER_IDS` - Admin user IDs
- `READONLY_TG_USER_IDs` - Viewer user IDs
- `TMA_ORIGIN` - Your domain for CORS (e.g., `https://your-domain.com`)

### 3. Build TMA Frontend

```bash
cd /root/sovani_bot/tma
npm ci
npm run build
```

This creates `tma/dist/` directory with optimized static files.

### 4. Install Systemd Service

```bash
sudo cp /root/sovani_bot/deploy/sovani-api.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable sovani-api
sudo systemctl start sovani-api
```

**Check status:**
```bash
sudo systemctl status sovani-api
sudo journalctl -u sovani-api -f
```

### 5. Configure Nginx

```bash
sudo cp /root/sovani_bot/deploy/nginx-sovani.conf /etc/nginx/sites-available/sovani
sudo ln -s /etc/nginx/sites-available/sovani /etc/nginx/sites-enabled/sovani
```

**Edit the config:**
```bash
sudo nano /etc/nginx/sites-available/sovani
# Update server_name to your actual domain
```

**Test and reload:**
```bash
sudo nginx -t
sudo systemctl reload nginx
```

### 6. Optional: Setup SSL with Let's Encrypt

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com
```

Certbot will automatically configure SSL in Nginx.

---

## Service Management

### Start/Stop/Restart API

```bash
sudo systemctl start sovani-api
sudo systemctl stop sovani-api
sudo systemctl restart sovani-api
```

### View Logs

```bash
# API logs
sudo journalctl -u sovani-api -f

# Nginx access logs
sudo tail -f /var/log/nginx/sovani-access.log

# Nginx error logs
sudo tail -f /var/log/nginx/sovani-error.log
```

### Update Code and Redeploy

```bash
cd /root/sovani_bot
git pull

# Update backend
source venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart sovani-api

# Update frontend
cd tma
npm ci
npm run build
sudo systemctl reload nginx
```

---

## Architecture

```
┌─────────────────┐
│  Telegram Bot   │  (main bot on port 8443)
│  (main.py)      │
└─────────────────┘

┌─────────────────┐
│   Nginx :80     │  ──┐
│   (reverse      │    │
│    proxy)       │    │
└─────────────────┘    │
        │              │
        ├─ /api/* ────>│ ┌─────────────────┐
        │              └─│ FastAPI :8080   │
        │                │ (uvicorn)       │
        │                └─────────────────┘
        │
        └─ /* (static) ──> TMA Frontend (React)
                           /root/sovani_bot/tma/dist/
```

---

## Monitoring

### Health Check

```bash
# API health
curl http://localhost:8080/health

# Via Nginx
curl http://your-domain.com/health
```

### Resource Usage

```bash
# CPU/Memory for API service
sudo systemctl status sovani-api

# Process stats
ps aux | grep uvicorn
```

---

## Troubleshooting

### API won't start

```bash
# Check logs
sudo journalctl -u sovani-api -n 100

# Common issues:
# - Missing .env file
# - Database connection error
# - Port 8080 already in use
```

### Nginx 502 Bad Gateway

```bash
# Check if API is running
sudo systemctl status sovani-api

# Check if API is listening on port 8080
sudo netstat -tulpn | grep 8080
```

### CORS errors in TMA

```bash
# Ensure TMA_ORIGIN in .env matches your domain
# Check Nginx CORS headers in nginx-sovani.conf
```

---

## Security Checklist

- [ ] `.env` file is NOT committed to git
- [ ] `ALLOWED_TG_USER_IDS` configured (only authorized admins)
- [ ] `READONLY_TG_USER_IDS` configured (viewers)
- [ ] SSL/HTTPS enabled with Let's Encrypt
- [ ] Firewall configured (ufw allow 80,443)
- [ ] Regular backups of PostgreSQL database
- [ ] Secrets rotation (API tokens, keys)

---

## Rollback

If deployment fails, rollback to previous version:

```bash
cd /root/sovani_bot
git log --oneline  # Find previous commit hash
git checkout <previous-commit-hash>
sudo systemctl restart sovani-api
cd tma && npm run build
sudo systemctl reload nginx
```

---

## Support

For issues, see:
- `/var/log/nginx/sovani-error.log`
- `sudo journalctl -u sovani-api -f`
- GitHub issues: https://github.com/your-repo/sovani-bot/issues
