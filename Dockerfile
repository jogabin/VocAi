# axhub 배포용: Vue 빌드 결과를 FastAPI static 으로 묶은 단일 이미지
# (GCP Cloud Run 은 deploy.ps1 이 backend/Dockerfile 로 따로 배포)

# 1) Vue 빌드
FROM node:22-slim AS frontend
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# 2) FastAPI + Vue 빌드 결과
FROM python:3.12-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ ./
COPY --from=frontend /frontend/dist ./static

CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080}"]
