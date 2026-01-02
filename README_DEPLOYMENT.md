# Deployment Guide for Render

This guide will walk you through deploying your Flask backend to Render using Docker.

## Prerequisites

1. A GitHub account with your code pushed to a repository
2. A Render account (sign up at https://render.com)
3. Firebase credentials (service account JSON file)
4. Redis instance (can be provisioned on Render or use external service)
5. All required API keys (Gemini API key, etc.)

---

## Step 1: Prepare Your Code

### 1.1 Ensure Your Code is on GitHub

1. Initialize git repository (if not already done):
   ```bash
   git init
   git add .
   git commit -m "Initial commit"
   ```

2. Create a repository on GitHub and push your code:
   ```bash
   git remote add origin https://github.com/yourusername/your-repo-name.git
   git branch -M main
   git push -u origin main
   ```

### 1.2 Prepare Firebase Credentials

For Render deployment, you have two options:

**Option A: Use Environment Variable (Recommended)**
- Convert your `firebase-credentials.json` to a base64 string or JSON string
- Store it as an environment variable in Render

**Option B: Use Application Default Credentials**
- If deploying on Google Cloud, you can use application default credentials
- Set `FIREBASE_PROJECT_ID` environment variable

---

## Step 2: Create a Render Account and Web Service

### 2.1 Sign Up / Log In to Render

1. Go to https://render.com
2. Sign up or log in with your GitHub account

### 2.2 Create a New Web Service

1. Click **"New +"** button in the Render dashboard
2. Select **"Web Service"**
3. Connect your GitHub account if not already connected
4. Select the repository containing your backend code
5. Click **"Connect"**

### 2.3 Configure the Web Service

Fill in the following details:

- **Name**: `tourguide-backend` (or your preferred name)
- **Region**: Choose the closest region to your users
- **Branch**: `main` (or your default branch)
- **Root Directory**: Leave empty (or specify if your app is in a subdirectory)
- **Runtime**: Select **"Docker"**
- **Dockerfile Path**: `Dockerfile` (should auto-detect)
- **Docker Build Context**: `.` (root directory)

### 2.4 Set Environment Variables

Click on **"Environment"** tab and add the following variables:

#### Required Environment Variables:

```
FLASK_ENV=production
SECRET_KEY=<generate-a-random-secret-key>
PORT=5000
```

#### Bot Configuration:
```
BOT_NAME=Tour Guide AI Assistant
BOT_VERSION=1.0.0
BOT_DESCRIPTION=AI-powered tour guide chatbot
```

#### LLM Configuration:
```
GEMINI_FLASH_API_KEY=<your-gemini-api-key>
LLM_MODEL=gemini-2.5-flash
LLM_TEMPERATURE=0
```

#### Firebase Configuration:

**Option A - Using Environment Variable (Recommended for Render):**
1. Read your `firebase-credentials.json` file
2. Convert it to a single-line JSON string. You can use this Python command:
   ```python
   import json
   with open('firebase-credentials.json', 'r') as f:
       print(json.dumps(json.load(f)))
   ```
   Or use an online tool to minify JSON (remove newlines and extra spaces)
3. Add as environment variable in Render:
   ```
   FIREBASE_CREDENTIALS_JSON={"type":"service_account","project_id":"...","private_key":"...",...}
   FIREBASE_PROJECT_ID=<your-firebase-project-id>
   FIREBASE_STORAGE_BUCKET=<your-project-id>.appspot.com
   ```

**Option B - Using Credentials File Path:**
If you prefer to use a file (requires additional setup):
```
FIREBASE_CREDENTIALS_PATH=/app/firebase-credentials.json
FIREBASE_PROJECT_ID=<your-firebase-project-id>
FIREBASE_STORAGE_BUCKET=<your-project-id>.appspot.com
```

**Option C - Application Default Credentials:**
For Google Cloud environments:
```
FIREBASE_PROJECT_ID=<your-firebase-project-id>
FIREBASE_STORAGE_BUCKET=<your-project-id>.appspot.com
```
(No credentials file needed if using Google Cloud service account)

#### Redis Configuration:
```
REDIS_HOST=<your-redis-host>
REDIS_PORT=6379
REDIS_PASSWORD=<your-redis-password-if-any>
REDIS_DB=0
```

#### CORS Configuration:
```
CORS_ORIGINS=https://your-frontend-domain.com,https://www.your-frontend-domain.com
```

#### Other Configuration:
```
LOG_LEVEL=INFO
MAX_CONVERSATION_HISTORY_MESSAGES=10
RAG_TOP_K=4
SESSION_TTL_SECONDS=86400
```

### 2.5 Set Up Redis (if not already done)

1. In Render dashboard, click **"New +"** → **"Redis"**
2. Name it (e.g., `tourguide-redis`)
3. Select the same region as your web service
4. Choose a plan (Free tier available for testing)
5. Click **"Create Redis"**
6. Copy the **Internal Redis URL** or **External Redis URL**
7. Update your web service environment variables:
   - `REDIS_HOST`: Extract host from the Redis URL
   - `REDIS_PORT`: Usually `6379`
   - `REDIS_PASSWORD`: Extract from Redis URL if present

---

## Step 3: Handle Firebase Credentials

### Method 1: Using Environment Variable (Recommended - Already Implemented)

The code now supports reading Firebase credentials directly from an environment variable!

1. Read your `firebase-credentials.json` file
2. Convert it to a single-line JSON string. Use one of these methods:

   **Using the helper script (Easiest):**
   ```bash
   python scripts/convert_firebase_creds.py firebase-credentials.json
   ```
   This will output the credentials as a single-line string ready to copy.

   **Python method:**
   ```python
   import json
   with open('firebase-credentials.json', 'r') as f:
       creds = json.load(f)
       print(json.dumps(creds))
   ```
   Copy the output (it will be a single line)

   **Online method:**
   - Use a JSON minifier tool (e.g., https://jsonformatter.org/json-minify)
   - Paste your JSON and minify it
   - Copy the result

3. In Render, add environment variable:
   ```
   FIREBASE_CREDENTIALS_JSON=<paste-the-entire-minified-json-here>
   ```
   Make sure it's all on one line with no line breaks.

4. Also set:
   ```
   FIREBASE_PROJECT_ID=<your-firebase-project-id>
   FIREBASE_STORAGE_BUCKET=<your-project-id>.appspot.com
   ```

### Method 2: Using Render Disk (Alternative)

1. In your Render service settings, go to **"Disk"** tab
2. Mount a disk if needed
3. Upload `firebase-credentials.json` to the disk
4. Set `FIREBASE_CREDENTIALS_PATH=/path/to/firebase-credentials.json`

---

## Step 4: Deploy

1. Review all your settings
2. Click **"Create Web Service"**
3. Render will start building your Docker image
4. Monitor the build logs for any errors
5. Once deployed, your service will be available at: `https://your-service-name.onrender.com`

---

## Step 5: Verify Deployment

1. Check the health endpoint:
   ```
   https://your-service-name.onrender.com/health
   ```

2. Check detailed health:
   ```
   https://your-service-name.onrender.com/health/detailed
   ```

3. Test your API endpoints

---

## Step 6: Configure Custom Domain (Optional)

1. In your service settings, go to **"Custom Domains"**
2. Add your domain
3. Follow Render's instructions to configure DNS

---

## Troubleshooting

### Build Fails

- Check build logs for specific errors
- Ensure all dependencies are in `requirements.txt`
- Verify Dockerfile syntax

### Service Won't Start

- Check service logs in Render dashboard
- Verify all required environment variables are set
- Check that PORT environment variable is being used correctly

### Database Connection Issues

- Verify Redis connection details
- Check if Redis is accessible from your service
- For external Redis, ensure firewall rules allow connections

### Firebase Connection Issues

- Verify Firebase credentials are correctly formatted
- Check that `FIREBASE_PROJECT_ID` is set correctly
- Ensure Firebase service account has proper permissions

### Health Check Failing

- Check service logs
- Verify all dependencies are installed
- Ensure `/health` endpoint is accessible

---

## Environment Variables Summary

Here's a checklist of all environment variables you need to set:

- [ ] `FLASK_ENV=production`
- [ ] `SECRET_KEY` (generate a secure random string)
- [ ] `PORT=5000` (Render sets this automatically, but good to have)
- [ ] `GEMINI_FLASH_API_KEY`
- [ ] `FIREBASE_PROJECT_ID`
- [ ] `FIREBASE_STORAGE_BUCKET`
- [ ] `FIREBASE_CREDENTIALS_JSON` (recommended) or `FIREBASE_CREDENTIALS_PATH`
- [ ] `REDIS_HOST`
- [ ] `REDIS_PORT`
- [ ] `REDIS_PASSWORD` (if required)
- [ ] `CORS_ORIGINS` (comma-separated list of allowed origins)
- [ ] `BOT_NAME` (optional)
- [ ] `LOG_LEVEL` (optional, defaults to INFO)

---

## Additional Tips

1. **Auto-Deploy**: Render automatically deploys on every push to your main branch
2. **Manual Deploy**: You can trigger manual deploys from the dashboard
3. **Logs**: Access real-time logs from the Render dashboard
4. **Scaling**: Upgrade your plan if you need more resources
5. **Sleep Mode**: Free tier services sleep after 15 minutes of inactivity (first request will be slow)

---

## Security Best Practices

1. **Never commit** `firebase-credentials.json` to git
2. Use strong, randomly generated `SECRET_KEY`
3. Restrict `CORS_ORIGINS` to your actual frontend domains
4. Use Render's environment variable encryption for sensitive data
5. Regularly rotate API keys and credentials

---

## Support

- Render Documentation: https://render.com/docs
- Render Community: https://community.render.com
- Check service logs in Render dashboard for detailed error messages

