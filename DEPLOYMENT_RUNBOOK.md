# MetrCheck AI — Production Cloud Deployment Runbook

## 1. Final Architecture

```
                                  [ User Browser ]
                                         │
                                         ▼ HTTPS
                        ┌─────────────────────────────────┐
                        │    Hugging Face Spaces (Cloud)  │
                        │    16 GB RAM • 2 vCPU (FREE)    │
                        │    Port 7860 (Public Ingress)   │
                        └────────────────┬────────────────┘
                                         │
                  ┌──────────────────────┴──────────────────────┐
                  ▼                                             ▼
       [ Nginx Reverse Proxy ]                       [ Static Assets ]
       • Listens on 0.0.0.0:7860                     • React 19 + Vite 8 SPA
       • Client Max Body: 50MB                       • /usr/share/nginx/html
       • Proxy Timeout: 300s                         • Client-side routing
                  │
                  ▼ (Internal 127.0.0.1:8000)
       [ FastAPI Python 3.11 Backend ]
       • PaddleOCR PP-OCRv4 (DBNet + SVTR with CPU MKLDNN acceleration)
       • OpenCV 4.x Headless Image Processing
       • ReportLab Multilingual PDF Engine (fonts-noto-core for 10 Indic languages)
       • SHA-256 Audit Trail & Tamper Detection
       • Async SQLite with WAL Mode (/data/metrcheck.db on persistent volume)
```

---

## 2. Cloud Providers Selected & Justification

| Component | Selected Provider | Free Tier Specifications | Why Selected |
|---|---|---|---|
| **All-in-One Cloud App (Backend + OCR + Frontend)** | **Hugging Face Spaces (Docker Engine)** | **16 GB RAM**, 2 vCPU, 50 GB Disk, 100% Free Forever | **PaddleOCR + OpenCV require ~1 GB RAM** during deep-learning text inference. Standard free tiers (Render/Koyeb at 512 MB) trigger Out-Of-Memory (OOM) crashes. Hugging Face provides massive 16 GB RAM for zero cost, native Docker, public HTTPS, and persistent disk mounting. |
| **Edge CDN Frontend (Optional Decoupled)** | **Vercel** | Unlimited Bandwidth, Global Edge Anycast CDN | For global edge caching if decoupled frontend hosting is desired. `VITE_API_URL` dynamically points to the backend Space. |
| **Database & Storage** | **Async SQLite (`aiosqlite`) with WAL Mode** | Persistent `/data` volume storage | Zero latency, zero external network hops, zero monthly cost, ACID compliant, and preserves the complete 18-table schema and tenant isolation without risk of syntax mismatch. |
| **CI / CD Pipeline** | **GitHub Actions** | 2,000 free minutes/month | Automated `pytest` (1,040 tests) and `npm run build` on every push to `main`, auto-syncing to Hugging Face Spaces. |

---

## 3. Production URLs & Endpoints

- **Public Production Web Application**:  
  `https://bhardwaj001-metrcheck-ai.hf.space`
- **Backend API Base**:  
  `https://bhardwaj001-metrcheck-ai.hf.space/api`
- **Health Check**:  
  `https://bhardwaj001-metrcheck-ai.hf.space/api/health`
- **API Documentation (Swagger UI)**:  
  `https://bhardwaj001-metrcheck-ai.hf.space/docs`
- **GitHub Repository**:  
  `https://github.com/omsainikaul/metrcheck-ai.git` (Branch: `main`)

---

## 4. Production Environment Variables

Configure these in your Hugging Face Space **Settings → Variables and Secrets** (or through `.env.production`):

| Variable | Value | Purpose |
|---|---|---|
| `ENVIRONMENT` | `production` | Enables production security policies |
| `SECRET_KEY` | `b9f3e4c810d7a6e5b4c3d2e1f0a9b8c7d6e5f4a3b2c1d0e9f8a7b6c5d4e3f2a1` | 64-char cryptographic key for JWT and audit hashing |
| `CORS_ORIGINS` | `https://omsainikaul-metrcheck-ai.hf.space,https://metrcheck-ai.vercel.app` | Explicit trusted origin whitelist (prevents wildcard CORS) |
| `DATABASE_PATH` | `/data/metrcheck.db` | Persistent SQLite path on container volume |
| `UPLOAD_DIR` | `/data/uploads` | Specimen image upload directory |
| `OCR_ENGINE` | `paddleocr` | Real deep learning text recognition |
| `METRCHECK_DEMO_MODE` | `true` | Seeds initial demonstration accounts and test commodities |
| `MAX_FILE_SIZE_MB` | `50` | Maximum upload limit |

---

## 5. Deployment Setup: 30-Second Activation

### Option A: 1-Click Launch on Hugging Face Spaces (Easiest)
1. Go to [huggingface.co/new-space](https://huggingface.co/new-space).
2. Space Name: `metrcheck-ai`
3. License: `mit`
4. SDK: Select **Docker** (Blank).
5. Visibility: **Public**
6. Click **Create Space**.
7. In **Settings → Secrets and variables**:
   - Add Secret: `SECRET_KEY` = `b9f3e4c810d7a6e5b4c3d2e1f0a9b8c7d6e5f4a3b2c1d0e9f8a7b6c5d4e3f2a1`
   - Add Variable: `ENVIRONMENT` = `production`
8. In GitHub repository **Settings → Secrets and variables → Actions**:
   - Add Secret: `HF_TOKEN` = (Your free Hugging Face User Access Token from [huggingface.co/settings/tokens](https://huggingface.co/settings/tokens) with Write permissions).
9. Push to GitHub:
   ```bash
   git add .
   git commit -m "deploy: configure cloud production"
   git push origin main
   ```
   GitHub Actions will automatically build, test, and push the code to Hugging Face Spaces!

---

## 6. How Future Changes Work (Git-Driven Automation)

For all future changes, simply commit and push from your machine:
```bash
git add .
git commit -m "feat: your new feature or rule update"
git push origin main
```
The automated CI/CD workflow in `.github/workflows/deploy.yml` will:
1. Run automated backend regression tests (`pytest`).
2. Verify TypeScript compilation and Vite build (`npm run build`).
3. Push to Hugging Face Spaces to trigger a live zero-downtime rolling container rebuild.

---

## 7. Operational Playbook

### Checking Production Health
```bash
curl -i https://omsainikaul-metrcheck-ai.hf.space/api/health
```
Expected HTTP 200 response:
```json
{
  "status": "healthy",
  "ocr_available": true,
  "ocr_engine": "PaddleOCREngine",
  "database": "connected",
  "version": "2.4.0"
}
```

### Viewing Cloud Logs
1. Open your Space at `https://huggingface.co/spaces/omsainikaul/metrcheck-ai`.
2. Click **Logs** at the top right to view real-time Uvicorn and Nginx access/error logs.

### Rolling Back a Deployment
If an update introduces an issue, roll back instantly using Git:
```bash
# Roll back to the previous commit
git revert HEAD --no-edit
git push origin main
```
The GitHub Action will immediately redeploy the previous working version.
