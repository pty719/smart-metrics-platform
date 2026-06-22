# Smart Metrics Platform

> 轻量级、API-first 的时序指标分析引擎  
> Lightweight, API-first time-series metrics analytics engine

[![Python](https://img.shields.io/badge/Python-3.11+-blue)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-green)](https://fastapi.tiangolo.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15-blue)](https://www.postgresql.org/)
[![Redis](https://img.shields.io/badge/Redis-7-red)](https://redis.io/)
[![License](https://img.shields.io/badge/License-MIT-yellow)](LICENSE)

---

## 目录

- [功能概览](#功能概览)
- [快速开始（本地开发）](#快速开始本地开发)
- [生产环境部署](#生产环境部署)
- [环境变量参考](#环境变量参考)
- [数据库迁移](#数据库迁移)
- [API 文档](#api-文档)
- [监控：Grafana 仪表盘](#监控grafana-仪表盘)
- [测试](#测试)
- [常见问题排查](#常见问题排查)

---

## 功能概览

| 模块 | 描述 |
|------|------|
| **指标管理** | 创建、查询、删除指标 |
| **数据上传** | 批量上传时序数据点 |
| **统计分析** | 均值、最大/最小值、标准差、中位数 |
| **异常检测** | IQR 四分位距离方法，自动标记离群点 |
| **移动平均** | 可配置窗口的简单移动平均线 |
| **趋势预测** | 异步线性回归预测 + 置信区间 |
| **Redis 缓存** | 自动缓存统计结果，写入时失效 |

---

## 快速开始（本地开发）

### 前置要求

- Docker ≥ 24.0
- Docker Compose ≥ 2.20
- Python ≥ 3.11（用于本地测试）

### 1. 克隆仓库并配置环境

```bash
git clone https://github.com/your-org/smart-metrics-platform.git
cd smart-metrics-platform

# 复制示例配置（开发默认值已可用）
cp .env.example .env
```

### 2. 启动所有服务

```bash
# 启动 PostgreSQL + Redis + FastAPI + Celery worker
docker compose up -d

# 查看应用日志
docker compose logs -f app

# 查看所有服务状态
docker compose ps
```

### 3. 执行数据库迁移

```bash
# 等待 db 健康后执行（首次启动或有新迁移时）
docker compose exec app alembic upgrade head
```

### 4. 验证服务正常

```bash
# 健康检查
curl http://localhost:8000/health

# 访问交互式 API 文档
open http://localhost:8000/docs
```

### 5. 停止服务

```bash
docker compose down          # 保留数据库数据
docker compose down -v       # 同时删除 volume（清空数据）
```

---

## 生产环境部署

### 架构概览

```
Internet
    │
    ▼
[ Nginx :80/443 ]   ← 反向代理、TLS 终止、安全头
    │
    ▼ (backend internal network)
[ FastAPI app ]     ← Gunicorn + UvicornWorker（多进程）
    │          │
    ▼          ▼
[ PostgreSQL ] [ Redis ]   ← 仅在 backend 网络内可访问
    │
    ▼
[ Celery Worker ]   ← 异步预测任务
```

### 步骤 1：准备服务器

```bash
# 推荐 Ubuntu 22.04 LTS，安装 Docker
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
```

### 步骤 2：克隆代码

```bash
git clone https://github.com/your-org/smart-metrics-platform.git
cd smart-metrics-platform
```

### 步骤 3：配置生产环境变量

```bash
cp .env.example .env
vim .env  # 必须修改下方标注的变量
```

**必须修改的变量：**

```bash
# 生成强密码（示例）
openssl rand -hex 32

# 填入 .env
POSTGRES_PASSWORD=<your-strong-password>
REDIS_PASSWORD=<your-strong-password>
API_KEY=<your-strong-api-key>

# 限制 CORS 为你的前端域名
CORS_ORIGINS=https://dashboard.yourcompany.com

# 根据 CPU 数量设置（2 × CPU + 1）
WORKERS=3
```

### 步骤 4：构建并启动

```bash
# 使用生产 compose 文件
docker compose -f docker-compose.prod.yml up -d --build

# 查看启动状态
docker compose -f docker-compose.prod.yml ps

# 查看 app 日志
docker compose -f docker-compose.prod.yml logs -f app
```

### 步骤 5：执行数据库迁移

```bash
docker compose -f docker-compose.prod.yml exec app alembic upgrade head
```

### 步骤 6：验证部署

```bash
# 通过 Nginx 访问（端口 80）
curl http://your-server-ip/health

# 测试鉴权
curl -H "Authorization: Bearer $API_KEY" \
     http://your-server-ip/api/v1/metrics
```

### 配置 HTTPS（推荐）

```bash
# 1. 安装 Certbot
sudo apt install certbot

# 2. 获取证书（需先停止 Nginx 释放 80 端口）
docker compose -f docker-compose.prod.yml stop nginx
sudo certbot certonly --standalone -d your-domain.com
sudo certbot certonly --standalone -d your-domain.com

# 3. 复制证书到 nginx/ssl/
mkdir -p nginx/ssl
sudo cp /etc/letsencrypt/live/your-domain.com/fullchain.pem nginx/ssl/
sudo cp /etc/letsencrypt/live/your-domain.com/privkey.pem nginx/ssl/
sudo chown $USER:$USER nginx/ssl/*

# 4. 在 nginx/nginx.conf 中取消注释 HTTPS server 块
#    并注释掉 HTTP server 块

# 5. 在 docker-compose.prod.yml 中取消注释 "443:443" 端口映射

# 6. 重启 Nginx
docker compose -f docker-compose.prod.yml up -d nginx
```

### 更新部署

```bash
git pull origin main

# 重新构建并滚动更新（不停服）
docker compose -f docker-compose.prod.yml up -d --build --no-deps app worker

# 如有新迁移
docker compose -f docker-compose.prod.yml exec app alembic upgrade head
```

---

## 环境变量参考

| 变量 | 说明 | 开发默认值 | 生产要求 |
|------|------|-----------|---------|
| `APP_NAME` | 应用名称 | `Smart Metrics Platform` | 可选 |
| `DEBUG` | 调试模式 | `false` | 必须为 `false` |
| `LOG_LEVEL` | 日志级别 | `INFO` | `INFO` 或 `WARNING` |
| `LOG_FORMAT` | 日志格式 | `json` | `json`（结构化日志）|
| `POSTGRES_HOST` | 数据库主机 | `localhost` | 容器名 `db` |
| `POSTGRES_PORT` | 数据库端口 | `5432` | `5432` |
| `POSTGRES_USER` | 数据库用户 | `postgres` | 自定义用户名 |
| `POSTGRES_PASSWORD` | 数据库密码 | `postgres` | ⚠️ **强密码** |
| `POSTGRES_DB` | 数据库名 | `metrics` | 可选 |
| `REDIS_HOST` | Redis 主机 | `localhost` | 容器名 `redis` |
| `REDIS_PORT` | Redis 端口 | `6379` | `6379` |
| `REDIS_PASSWORD` | Redis 密码 | 空 | ⚠️ **必须设置** |
| `API_KEY` | API 认证密钥 | `dev-api-key` | ⚠️ **强密码** |
| `CORS_ORIGINS` | 允许的源 | `*` | 指定域名列表 |
| `WORKERS` | Gunicorn 进程数 | `2` | `2×CPU+1` |
| `CELERY_CONCURRENCY` | Celery 并发数 | `4` | `2~8` |
| `CACHE_TTL_STATS` | 统计缓存 TTL（秒）| `300` | 可调整 |
| `CACHE_TTL_ANOMALIES` | 异常检测缓存 TTL | `60` | 可调整 |
| `CACHE_TTL_MA` | 移动平均缓存 TTL | `600` | 可调整 |

---

## 数据库迁移

```bash
# 生成新迁移（修改 ORM 模型后）
docker compose exec app alembic revision --autogenerate -m "add new table"

# 应用所有未执行的迁移
docker compose exec app alembic upgrade head

# 查看迁移历史
docker compose exec app alembic history

# 回滚一个版本
docker compose exec app alembic downgrade -1

# 回滚到指定版本
docker compose exec app alembic downgrade <revision_id>
```

---

## API 文档

服务启动后，访问以下地址查看完整 API 文档：

| URL | 描述 |
|-----|------|
| `http://localhost:8000/docs` | Swagger UI（交互式，可直接测试） |
| `http://localhost:8000/redoc` | ReDoc（适合阅读和分享） |

### 认证

所有接口（`/health` 除外）需要 Bearer Token：

```bash
# 示例：创建指标
curl -X POST http://localhost:8000/api/v1/metrics \
  -H "Authorization: Bearer your-api-key" \
  -H "Content-Type: application/json" \
  -d '{"name": "daily_users", "unit": "人", "description": "每日活跃用户数"}'

# 示例：上传数据点
curl -X POST http://localhost:8000/api/v1/metrics/daily_users/data \
  -H "Authorization: Bearer your-api-key" \
  -H "Content-Type: application/json" \
  -d '[
    {"timestamp": "2026-06-01T00:00:00Z", "value": 1250.0},
    {"timestamp": "2026-06-02T00:00:00Z", "value": 1380.0}
  ]'

# 示例：查询统计数据
curl -H "Authorization: Bearer your-api-key" \
  http://localhost:8000/api/v1/metrics/daily_users/stats

# 示例：提交预测任务
curl -X POST http://localhost:8000/api/v1/metrics/daily_users/forecast \
  -H "Authorization: Bearer your-api-key" \
  -H "Content-Type: application/json" \
  -d '{"steps": 7, "conf_level": 0.95}'
```

更多示例见 [`docs/API_EXAMPLES.md`](docs/API_EXAMPLES.md)。

---

## 监控：Grafana 仪表盘

项目提供现成的 Grafana 仪表盘配置文件。

### 快速导入

1. 安装 Grafana（[官方文档](https://grafana.com/docs/grafana/latest/setup-grafana/installation/)）
2. 安装 **JSON API** 数据源插件：
   ```bash
   grafana cli plugins install marcusolsson-json-datasource
   ```
3. 在 Grafana 中配置数据源，URL 指向 API（如 `http://localhost:8000`），并在 Headers 中设置 `Authorization: Bearer your-api-key`
4. 导入仪表盘：
   - Grafana → **Dashboards → Import → Upload JSON file**
   - 选择 `docs/grafana_dashboard.json`

### 仪表盘面板

| 面板 | 描述 |
|------|------|
| Stats Overview | 统计概览（数量、均值、最大/最小值）|
| Raw + MA Series | 原始数据 + 移动平均时间序列 |
| Anomaly Table | 异常数据点列表（IQR 方法）|
| IQR Gauge | 当前数据相对阈值的分布 |
| Forecast Band | 线性预测 + 95% 置信区间 |

---

## 测试

```bash
# 安装开发依赖
pip install -r requirements/dev.txt

# 运行全部测试
pytest

# 仅单元测试（不依赖外部服务）
pytest tests/unit/ -v

# 集成测试（需要测试数据库）
pytest tests/integration/ -v

# 带覆盖率报告
pytest --cov=app --cov-report=html
open htmlcov/index.html

# 快速检查（--tb=short 压缩错误输出）
pytest -x --tb=short
```

---

## 常见问题排查

### 服务无法启动

```bash
# 查看详细日志
docker compose -f docker-compose.prod.yml logs db
docker compose -f docker-compose.prod.yml logs redis
docker compose -f docker-compose.prod.yml logs app

# 检查健康状态
docker compose -f docker-compose.prod.yml ps
```

### 数据库连接失败

```bash
# 确认 db 服务健康
docker compose -f docker-compose.prod.yml exec db pg_isready -U $POSTGRES_USER

# 手动连接测试
docker compose -f docker-compose.prod.yml exec db \
  psql -U $POSTGRES_USER -d $POSTGRES_DB -c "\dt"
```

### Redis 连接失败

```bash
# 测试连接（需要提供密码）
docker compose -f docker-compose.prod.yml exec redis \
  redis-cli -a $REDIS_PASSWORD ping
# 应返回: PONG
```

### API 返回 401 Unauthorized

确保请求头格式正确：

```bash
# ✅ 正确
curl -H "Authorization: Bearer your-api-key" ...

# ❌ 错误（缺少 Bearer 前缀）
curl -H "Authorization: your-api-key" ...
```

### 缓存未失效 / 数据更新后仍返回旧结果

1. 确认 `REDIS_PASSWORD` 在 app 和 redis 中一致
2. 查看 Redis 中的 key：
   ```bash
   docker compose -f docker-compose.prod.yml exec redis \
     redis-cli -a $REDIS_PASSWORD keys "stats:*"
   ```
3. 手动清除指标缓存：
   ```bash
   docker compose -f docker-compose.prod.yml exec redis \
     redis-cli -a $REDIS_PASSWORD del stats:your_metric_name:stats
   ```

### 内存不足 OOM

调整 `docker-compose.prod.yml` 中的 `deploy.resources.limits.memory` 值，建议：

| 服务 | 最小 | 建议 |
|------|------|------|
| nginx | 64 MB | 64 MB |
| db | 256 MB | 512 MB |
| redis | 128 MB | 256 MB |
| app | 256 MB | 512 MB |
| worker | 256 MB | 512 MB |

---

## 项目文档

| 文档 | 路径 | 说明 |
|------|------|------|
| 产品需求 | [`docs/PRD.md`](docs/PRD.md) | 功能规格与优先级 |
| 技术设计 | [`docs/TECH_DESIGN.md`](docs/TECH_DESIGN.md) | 架构选型与接口设计 |
| AI 开发指南 | [`AGENTS.md`](AGENTS.md) | 给 AI 和贡献者的开发规范 |
| Grafana 仪表盘 | [`docs/grafana_dashboard.json`](docs/grafana_dashboard.json) | 可直接导入的仪表盘配置 |

---

## License

MIT
