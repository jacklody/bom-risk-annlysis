# ── BOM-Risk-Analyzer Docker 配置 ──
# 构建：docker build -t bom-risk-analyzer .
# 运行：docker-compose up -d

FROM python:3.11-slim

WORKDIR /app

# 系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Python 依赖
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 后端源码
COPY backend/ /app/backend/

# 前端（构建好的 dist）
COPY frontend/dist/ /app/frontend/dist/

# 数据目录
RUN mkdir -p /app/backend/data

WORKDIR /app/backend

# 健康检查
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/api/health || exit 1

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
