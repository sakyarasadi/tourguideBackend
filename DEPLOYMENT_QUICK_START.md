# Quick Start: Deploy to Render

## Prerequisites Checklist
- [ ] Code pushed to GitHub
- [ ] Render account created
- [ ] Firebase credentials file ready
- [ ] Redis instance ready (or provision on Render)
- [ ] Gemini API key

## Quick Steps

### 1. Convert Firebase Credentials
```bash
python scripts/convert_firebase_creds.py firebase-credentials.json
```
Copy the output string.

### 2. Create Web Service on Render
1. Go to https://render.com
2. Click **"New +"** → **"Web Service"**
3. Connect GitHub repo
4. Select **"Docker"** as runtime
5. Set name: `tourguide-backend`

### 3. Set Environment Variables
Add these in Render dashboard:

**Required:**
```
FLASK_ENV=production
SECRET_KEY=<generate-random-string>
GEMINI_FLASH_API_KEY=<your-key>
FIREBASE_CREDENTIALS_JSON=<paste-from-step-1>
FIREBASE_PROJECT_ID=<your-project-id>
FIREBASE_STORAGE_BUCKET=<your-project-id>.appspot.com
REDIS_HOST=<redis-host>
REDIS_PORT=6379
REDIS_PASSWORD=<if-required>
CORS_ORIGINS=https://your-frontend.com
```

### 4. Create Redis (if needed)
1. **"New +"** → **"Redis"**
2. Copy connection details
3. Update `REDIS_HOST` and `REDIS_PASSWORD` in web service

### 5. Deploy
Click **"Create Web Service"** and wait for deployment.

### 6. Test
Visit: `https://your-service-name.onrender.com/health`

---

## Generate Secret Key
```python
import secrets
print(secrets.token_hex(32))
```

---

## Full Guide
See `README_DEPLOYMENT.md` for detailed instructions.

