# ============================================================
# Stage 1 — Build React/Vite frontend
# ============================================================
FROM node:22-bookworm-slim AS frontend-builder

WORKDIR /frontend

COPY frontend/package.json ./
COPY frontend/package-lock.json ./

RUN npm ci

COPY frontend/ ./

RUN npm run build


# ============================================================
# Stage 2 — Production application
# ============================================================
FROM python:3.11-slim

# System dependencies for:
# - PaddleOCR
# - OpenCV
# - Nginx
# - healthchecks
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    libglib2.0-0 \
    libgl1 \
    libstdc++6 \
    fonts-noto-core \
    fonts-dejavu \
    curl \
    nginx \
    && rm -rf /var/lib/apt/lists/*

# Create Hugging Face Spaces non-root user (UID 1000)
RUN useradd -m -u 1000 user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH

# Set up storage, model cache, and runtime directories with permissive permissions for non-root execution
RUN mkdir -p /data/uploads /var/log/nginx /var/lib/nginx /run /home/user/.paddleocr /home/user/.paddlex \
    && chown -R 1000:1000 /home/user /data \
    && chmod -R 777 /data /data/uploads /var/log/nginx /var/lib/nginx /run /home/user

# ------------------------------------------------------------
# Backend
# ------------------------------------------------------------
WORKDIR /backend

COPY backend/requirements.txt ./

RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ ./

# Pre-cache PaddleOCR PP-OCRv4 models and verify inference during build
RUN python -c "import os, numpy as np, cv2; os.environ['PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK']='True'; from ocr.paddle_engine import _sync_paddle_extract; img = np.full((100, 300, 3), 255, dtype=np.uint8); cv2.putText(img, 'TEST OCR', (10, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 0), 2); cv2.imwrite('/tmp/test_build.png', img); lines, words, confs = _sync_paddle_extract('/tmp/test_build.png'); print('BUILD-TIME INFERENCE VERIFIED:', lines); assert len(words) > 0" \
    && chmod -R 777 /home/user

# ------------------------------------------------------------
# Frontend
# ------------------------------------------------------------
COPY --from=frontend-builder /frontend/dist /usr/share/nginx/html

# ------------------------------------------------------------
# Nginx configuration
# ------------------------------------------------------------
COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf

# Remove the default nginx configuration if present
RUN rm -f /etc/nginx/sites-enabled/default

# ------------------------------------------------------------
# Runtime configuration
# ------------------------------------------------------------
ENV PYTHONUNBUFFERED=1 \
    MALLOC_ARENA_MAX=2 \
    OMP_NUM_THREADS=1 \
    MKL_NUM_THREADS=1 \
    OPENBLAS_NUM_THREADS=1 \
    PADDLE_NUM_THREADS=1 \
    FLAGS_allocator_strategy=naive_best_fit \
    FLAGS_fraction_of_cpu_memory_to_use=0.05 \
    FLAGS_eager_delete_tensor_gb=0.0 \
    PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK=True \
    OCR_ENGINE=paddleocr \
    UPLOAD_DIR=/data/uploads \
    DATABASE_PATH=/data/metrcheck.db

EXPOSE 7860

# Start FastAPI and Nginx in the same container, dynamically adapting Nginx port to $PORT (Render/HF)
CMD ["bash", "-c", "export PORT=${PORT:-7860}; sed -i \"s/listen [0-9]*;/listen $PORT;/\" /etc/nginx/conf.d/default.conf; uvicorn main:app --host 127.0.0.1 --port 8000 & backend_pid=$!; for i in $(seq 1 20); do curl -s -f http://127.0.0.1:8000/api/health >/dev/null 2>&1 && break || sleep 0.5; done; nginx -g 'daemon off;' & nginx_pid=$!; trap 'kill $backend_pid $nginx_pid 2>/dev/null || true' SIGTERM SIGINT; wait -n $backend_pid $nginx_pid; status=$?; echo \"===> PROCESS EXITED WITH STATUS: $status\"; kill $backend_pid $nginx_pid 2>/dev/null || true; exit $status"]