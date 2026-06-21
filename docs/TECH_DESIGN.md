# 技术设计文档 (TECH_DESIGN.md)

## 智能指标分析平台

------

| 项目     | 内容       |
| :------- | :--------- |
| 文档版本 | v1.0       |
| 创建日期 | 2026-06-21 |
| 对应PRD  | v1.0       |
| 文档状态 | 草稿       |

------

## 一、技术栈选择

### 1.1 整体架构图

text

```
┌─────────────────────────────────────────────────────────────────┐
│                         客户端层                                │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐      │
│  │ cURL     │  │ Python   │  │ JavaScript│  │ Swagger  │      │
│  │          │  │ Client   │  │ Client   │  │ UI       │      │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘      │
└────────────────────────┬────────────────────────────────────────┘
                         │ HTTPS / RESTful API
┌────────────────────────▼────────────────────────────────────────┐
│                        网关层（可选，生产环境）                   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │              Nginx / Kong (限流、SSL终止、路由)           │   │
│  └──────────────────────────────────────────────────────────┘   │
└────────────────────────┬────────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────────┐
│                       应用服务层                                │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                  FastAPI 应用实例                         │   │
│  │  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐           │   │
│  │  │ API层  │ │ 服务层 │ │ 模型层 │ │ 工具层 │           │   │
│  │  └────────┘ └────────┘ └────────┘ └────────┘           │   │
│  └──────────────────────────────────────────────────────────┘   │
│                         │                                       │
│  ┌──────────────────────▼──────────────────────────────────┐   │
│  │              Celery Worker (异步任务)                    │   │
│  │  ┌────────────────────────────────────────────────┐     │   │
│  │  │  预测任务  │  数据预处理  │  批量分析任务      │     │   │
│  │  └────────────────────────────────────────────────┘     │   │
│  └──────────────────────────────────────────────────────────┘   │
└────────────────────────┬────────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────────┐
│                        数据层                                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐        │
│  │  PostgreSQL  │  │    Redis     │  │   MinIO /    │        │
│  │  (主存储)    │  │ (缓存+消息)  │  │   S3 (可选)  │        │
│  └──────────────┘  └──────────────┘  └──────────────┘        │
└─────────────────────────────────────────────────────────────────┘
```



### 1.2 后端技术选型

| 类别            | 技术                    | 版本     | 选型理由                                                     |
| :-------------- | :---------------------- | :------- | :----------------------------------------------------------- |
| **Web框架**     | FastAPI                 | ≥0.100.0 | • 异步原生支持，性能出色 • 自动生成OpenAPI文档 • 基于Pydantic的类型校验 • 依赖注入机制优雅 |
| **ORM**         | SQLAlchemy              | ≥2.0     | • 异步支持（async/await） • 声明式模型清晰 • 功能最完整的Python ORM |
| **数据库迁移**  | Alembic                 | ≥1.12    | • SQLAlchemy官方工具 • 支持自动生成迁移脚本 • 支持回滚       |
| **数据校验**    | Pydantic                | ≥2.0     | • FastAPI深度集成 • 类型安全 • 性能优秀（Rust实现核心）      |
| **异步任务**    | Celery                  | ≥5.3     | • Python生态最成熟 • 支持多种broker • 任务重试、定时任务     |
| **Broker/缓存** | Redis                   | ≥7.0     | • 高性能内存数据库 • 同时作为Celery broker和缓存 • 支持持久化 |
| **数据库**      | PostgreSQL              | ≥15      | • 功能最丰富的关系型数据库 • 支持JSON字段 • 可扩展TimescaleDB |
| **HTTP客户端**  | httpx                   | ≥0.25    | • 支持异步 • API简洁 • 兼容requests                          |
| **日志**        | structlog               | ≥23.0    | • 结构化日志（JSON格式） • 便于日志聚合 • 支持上下文绑定     |
| **配置管理**    | pydantic-settings       | ≥2.0     | • Pydantic v2官方配置方案 • 支持.env文件 • 类型安全          |
| **测试**        | pytest + pytest-asyncio | ≥7.0     | • Python测试事实标准 • 异步测试支持 • 丰富的插件生态         |
| **代码质量**    | ruff                    | ≥0.1     | • 极快的linter（Rust实现） • 替代Flake8 + isort + Black      |
| **类型检查**    | mypy                    | ≥1.0     | • Python静态类型检查 • 与Pydantic配合良好                    |
| **容器化**      | Docker + Docker Compose | ≥24.0    | • 环境一致性 • 一键启动所有服务 • 便于CI/CD集成              |

### 1.3 为什么不用前端框架？

本产品定位为 **API优先的后端服务**，v1.0不提供前端界面。理由：

1. **聚焦核心**：后端分析引擎才是产品的核心竞争力，前端会分散精力
2. **API即产品**：目标用户是开发者和数据工程师，他们习惯用API/Postman/Swagger
3. **可集成性**：API-first设计使得本产品可以嵌入任何前端系统（Grafana、自有Dashboard等）
4. **后续可扩展**：v2.0如需管理界面，可选择 **Vue3 + Element Plus** 或直接复用 **Grafana** 做可视化

------

## 二、项目结构

### 2.1 完整目录结构

text

```
smart-metrics-platform/
├── .env.example                    # 环境变量模板
├── .gitignore
├── .dockerignore
├── pyproject.toml                  # 项目配置（ruff, mypy, pytest）
├── README.md                       # 项目说明
├── docker-compose.yml              # 服务编排（FastAPI + Redis + PostgreSQL + Celery）
├── Dockerfile                      # FastAPI应用镜像
├── Dockerfile.celery               # Celery Worker镜像（可复用同一Dockerfile）
│
├── requirements/
│   ├── base.txt                    # 通用依赖
│   ├── dev.txt                     # 开发依赖（+pytest, ruff, mypy）
│   └── prod.txt                    # 生产依赖（+gunicorn, uvloop）
│
├── scripts/
│   ├── import_csv.py               # CSV数据导入脚本
│   └── generate_demo_data.py       # 生成演示数据
│
├── app/                            # 应用主目录
│   ├── __init__.py
│   ├── main.py                     # FastAPI应用入口
│   ├── config.py                   # 配置管理（pydantic-settings）
│   │
│   ├── api/                        # API层
│   │   ├── __init__.py
│   │   ├── dependencies.py         # 依赖注入（数据库会话、认证等）
│   │   ├── responses.py            # 统一响应格式
│   │   ├── exceptions.py           # API异常处理器
│   │   └── v1/                     # API v1版本
│   │       ├── __init__.py
│   │       ├── router.py           # 路由聚合
│   │       ├── endpoints/
│   │       │   ├── __init__.py
│   │       │   ├── health.py       # GET /health
│   │       │   ├── metrics.py      # 指标CRUD
│   │       │   ├── datapoints.py   # 数据上传/查询
│   │       │   ├── analysis.py     # 统计分析
│   │       │   ├── anomalies.py    # 异常检测
│   │       │   ├── forecast.py     # 预测任务
│   │       │   └── tasks.py        # 任务状态查询
│   │       └── schemas/            # Pydantic模型（请求/响应）
│   │           ├── __init__.py
│   │           ├── metric.py
│   │           ├── datapoint.py
│   │           ├── analysis.py
│   │           └── task.py
│   │
│   ├── core/                       # 核心基础设施
│   │   ├── __init__.py
│   │   ├── database.py             # PostgreSQL连接（async SQLAlchemy）
│   │   ├── redis_client.py         # Redis连接（缓存 + Celery broker）
│   │   ├── celery_app.py           # Celery应用实例
│   │   ├── security.py             # API Key认证
│   │   ├── logging.py              # 日志配置（structlog）
│   │   └── exceptions.py           # 自定义异常类
│   │
│   ├── models/                     # SQLAlchemy ORM模型
│   │   ├── __init__.py
│   │   ├── metric.py               # Metric模型
│   │   ├── datapoint.py            # Datapoint模型
│   │   ├── task.py                 # Task模型（预测任务记录）
│   │   └── apikey.py               # API Key模型（v2.0）
│   │
│   ├── services/                   # 业务逻辑层（核心算法）
│   │   ├── __init__.py
│   │   ├── statistics.py           # 统计分析服务
│   │   ├── anomaly.py              # 异常检测服务（3σ, IQR等）
│   │   ├── forecast.py             # 预测服务（线性回归、季节性分解）
│   │   ├── correlation.py          # 相关性分析
│   │   └── cache.py                # 缓存服务（Redis操作封装）
│   │
│   ├── tasks/                      # Celery异步任务
│   │   ├── __init__.py
│   │   └── forecast_tasks.py       # 预测任务定义
│   │
│   └── utils/                      # 工具函数
│       ├── __init__.py
│       ├── time_utils.py           # 时间处理工具
│       ├── math_utils.py           # 数学工具（分位数、滑动窗口等）
│       └── validators.py           # 自定义校验器
│
├── tests/                          # 测试目录
│   ├── __init__.py
│   ├── conftest.py                 # pytest fixtures（数据库、客户端等）
│   ├── unit/                       # 单元测试
│   │   ├── test_statistics.py
│   │   ├── test_anomaly.py
│   │   └── test_forecast.py
│   └── integration/                # 集成测试
│       ├── test_api_metrics.py
│       ├── test_api_datapoints.py
│       └── test_api_analysis.py
│
└── docs/                           # 额外文档
    ├── PRD.md
    ├── TECH_DESIGN.md
    └── API_EXAMPLES.md             # API调用示例
```



### 2.2 核心文件说明

#### `app/main.py` — 应用入口

python

```
from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.api.v1.router import router as v1_router
from app.core.database import engine
from app.core.logging import setup_logging

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时：初始化数据库连接池
    await engine.connect()
    yield
    # 关闭时：清理资源
    await engine.dispose()

app = FastAPI(
    title="Smart Metrics Analytics Platform",
    description="智能指标分析平台 API",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)

app.include_router(v1_router, prefix="/api/v1")
```



#### `app/config.py` — 配置管理

python

```
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # 应用配置
    APP_NAME: str = "Smart Metrics Platform"
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"
    
    # 数据库配置
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_DB: str = "metrics"
    
    @property
    def DATABASE_URL(self) -> str:
        return f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
    
    # Redis配置
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    
    @property
    def REDIS_URL(self) -> str:
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
    
    # Celery配置
    CELERY_BROKER_URL: str = None  # 默认使用REDIS_URL
    CELERY_RESULT_BACKEND: str = None
    
    # API认证
    API_KEY: str = "dev-api-key-please-change-in-production"
    
    # 缓存配置
    CACHE_TTL_STATS: int = 300  # 统计缓存5分钟
    CACHE_TTL_ANOMALIES: int = 60  # 异常缓存1分钟
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = Settings()
```



------

## 三、数据模型

### 3.1 ER图

text

```
┌─────────────────────────────────────────────────────────────────────┐
│                                                                     │
│  ┌──────────────┐        1      ┌─────────────────────────┐       │
│  │   metrics    │──────────────▶│      datapoints         │       │
│  │──────────────│   has many    │─────────────────────────│       │
│  │ id (PK)      │               │ id (PK)                 │       │
│  │ name (UK)    │               │ metric_id (FK)          │       │
│  │ description  │               │ timestamp (idx)         │       │
│  │ unit         │               │ value (DECIMAL)         │       │
│  │ created_at   │               │ created_at              │       │
│  │ updated_at   │               └─────────────────────────┘       │
│  └──────────────┘                                                  │
│         │                                                          │
│         │ 1                                                        │
│         │                                                          │
│         │                                                          │
│  ┌──────▼───────┐        1      ┌─────────────────────────┐       │
│  │    tasks     │──────────────▶│   task_results (可选)   │       │
│  │──────────────│   has one     │─────────────────────────│       │
│  │ id (PK)      │               │ id (PK)                 │       │
│  │ metric_id (FK)               │ task_id (FK, UK)        │       │
│  │ task_type    │               │ result (JSONB)          │       │
│  │ status       │               │ error_message           │       │
│  │ parameters   │               │ created_at              │       │
│  │ created_at   │               └─────────────────────────┘       │
│  │ started_at   │                                                 │
│  │ completed_at │                                                 │
│  └──────────────┘                                                 │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```



### 3.2 SQLAlchemy模型详细设计

#### `models/metric.py` — 指标表

python

```
from sqlalchemy import String, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base

class Metric(Base):
    __tablename__ = "metrics"
    
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    description: Mapped[str] = mapped_column(String(500), nullable=True)
    unit: Mapped[str] = mapped_column(String(50), nullable=True)  # 如 "人", "ms", "℃"
    
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
    
    # 关系
    datapoints: Mapped[List["Datapoint"]] = relationship(back_populates="metric", cascade="all, delete-orphan")
    tasks: Mapped[List["Task"]] = relationship(back_populates="metric")
```



#### `models/datapoint.py` — 数据点表

python

```
from sqlalchemy import ForeignKey, DateTime, Numeric, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base

class Datapoint(Base):
    __tablename__ = "datapoints"
    
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    metric_id: Mapped[int] = mapped_column(ForeignKey("metrics.id"), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    value: Mapped[float] = mapped_column(Numeric(20, 6), nullable=False)  # 支持高精度
    
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    
    # 关系
    metric: Mapped["Metric"] = relationship(back_populates="datapoints")
    
    # 复合索引：加速按指标+时间的查询
    __table_args__ = (
        Index("idx_metric_timestamp", "metric_id", "timestamp"),
    )
```



#### `models/task.py` — 任务表

python

```
from sqlalchemy import ForeignKey, String, DateTime, JSON, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base
import enum

class TaskStatus(str, enum.Enum):
    PENDING = "pending"
    STARTED = "started"
    SUCCESS = "success"
    FAILURE = "failure"

class TaskType(str, enum.Enum):
    FORECAST = "forecast"
    BATCH_ANALYSIS = "batch_analysis"

class Task(Base):
    __tablename__ = "tasks"
    
    id: Mapped[str] = mapped_column(String(36), primary_key=True)  # UUID
    metric_id: Mapped[int] = mapped_column(ForeignKey("metrics.id"), nullable=False)
    task_type: Mapped[TaskType] = mapped_column(Enum(TaskType), nullable=False)
    status: Mapped[TaskStatus] = mapped_column(Enum(TaskStatus), default=TaskStatus.PENDING)
    
    parameters: Mapped[dict] = mapped_column(JSON, nullable=True)  # 任务参数（如预测步长）
    result: Mapped[dict] = mapped_column(JSON, nullable=True)  # 任务结果
    error_message: Mapped[str] = mapped_column(String(1000), nullable=True)
    
    celery_task_id: Mapped[str] = mapped_column(String(100), nullable=True)  # Celery任务ID
    
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    
    # 关系
    metric: Mapped["Metric"] = relationship(back_populates="tasks")
```



### 3.3 索引策略

| 表         | 索引字段                | 类型               | 目的                    |
| :--------- | :---------------------- | :----------------- | :---------------------- |
| metrics    | name                    | UNIQUE             | 按名称快速查找指标      |
| datapoints | (metric_id, timestamp)  | 复合索引（B-tree） | 加速按指标+时间范围查询 |
| datapoints | timestamp               | 单独索引           | 支持按全局时间查询      |
| tasks      | status                  | 索引               | 查询待处理任务          |
| tasks      | (metric_id, created_at) | 复合索引           | 按指标查询任务历史      |

### 3.4 数据量预估与分区策略

| 规模     | 数据量         | 建议                                     |
| :------- | :------------- | :--------------------------------------- |
| **小型** | < 1000万数据点 | 单表 + 标准索引即可                      |
| **中型** | 1000万 - 1亿   | 按时间分区（按月或按季度）               |
| **大型** | > 1亿          | 考虑迁移到 TimescaleDB（PostgreSQL扩展） |

**分区示例（PostgreSQL原生分区）：**

sql

```
-- 按月分区
CREATE TABLE datapoints (
    id SERIAL,
    metric_id INT NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    value NUMERIC(20,6)
) PARTITION BY RANGE (timestamp);

-- 创建每月分区
CREATE TABLE datapoints_2026_01 PARTITION OF datapoints
    FOR VALUES FROM ('2026-01-01') TO ('2026-02-01');
```



------

## 四、关键技术点

### 4.1 异步架构设计

**挑战**：Python异步编程容易踩坑（阻塞操作、事件循环管理）。

**解决方案**：

| 场景                          | 处理方式                                                    |
| :---------------------------- | :---------------------------------------------------------- |
| **数据库操作**                | 使用 `asyncpg` 驱动 + SQLAlchemy 异步API (`async_session`)  |
| **HTTP请求**                  | 使用 `httpx.AsyncClient`                                    |
| **CPU密集型计算**（统计分析） | 使用 `asyncio.to_thread()` 放到线程池执行，避免阻塞事件循环 |
| **Redis操作**                 | 使用 `redis.asyncio` 客户端                                 |

**示例：** `services/statistics.py`

python

```
import asyncio
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

async def compute_stats(
    metric_id: int,
    db: AsyncSession
) -> dict:
    # 数据库查询是异步的
    result = await db.execute(
        select(
            func.avg(Datapoint.value),
            func.max(Datapoint.value),
            func.min(Datapoint.value),
            func.stddev(Datapoint.value),
            func.count(Datapoint.id)
        ).where(Datapoint.metric_id == metric_id)
    )
    raw_stats = result.one()
    
    # CPU密集型计算（如分位数）放到线程池
    median = await asyncio.to_thread(
        compute_median,
        metric_id,
        db
    )
    
    return {
        "mean": raw_stats[0],
        "median": median,
        "max": raw_stats[1],
        "min": raw_stats[2],
        "std": raw_stats[3],
        "count": raw_stats[4]
    }
```



### 4.2 缓存策略

**挑战**：统计查询计算量大，但数据变化后缓存需要及时失效。

**策略**：

| 接口              | 缓存Key                             | TTL    | 失效策略                  |
| :---------------- | :---------------------------------- | :----- | :------------------------ |
| `/stats`          | `stats:{metric_id}`                 | 5分钟  | 写入新数据点时主动删除    |
| `/moving-average` | `ma:{metric_id}:{window}`           | 10分钟 | 写入新数据点时主动删除    |
| `/anomalies`      | `anomaly:{metric_id}:{params_hash}` | 1分钟  | 短TTL，人工判定可能变化快 |

**缓存服务封装：** `services/cache.py`

python

```
import json
from redis.asyncio import Redis

class CacheService:
    def __init__(self, redis: Redis):
        self.redis = redis
    
    async def get_or_set(
        self,
        key: str,
        fetch_func,
        ttl: int = 300
    ):
        """缓存穿透保护的get_or_set模式"""
        cached = await self.redis.get(key)
        if cached:
            return json.loads(cached)
        
        # 缓存未命中，执行函数获取数据
        data = await fetch_func()
        await self.redis.setex(key, ttl, json.dumps(data))
        return data
    
    async def invalidate(self, pattern: str):
        """按模式删除缓存"""
        keys = await self.redis.keys(pattern)
        if keys:
            await self.redis.delete(*keys)
```



### 4.3 异步任务处理（Celery）

**挑战**：预测任务耗时较长，需要异步执行；Celery与FastAPI的整合需要协调。

**架构方案：**

text

```
┌─────────────────────────────────────────────────────────────┐
│                     FastAPI 应用                            │
│                                                             │
│  1. 接收 POST /forecast 请求                                │
│  2. 在数据库中创建 Task 记录 (status=PENDING)              │
│  3. 调用 Celery 任务，传入 task_id                         │
│  4. 立即返回 task_id 给客户端                              │
│                                                             │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                    Celery Worker                            │
│                                                             │
│  1. 接收任务，更新 Task 状态为 STARTED                     │
│  2. 执行预测算法                                            │
│  3. 更新 Task 结果为 SUCCESS 或 FAILURE                    │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```



**Celery配置：** `core/celery_app.py`

python

```
from celery import Celery
from app.config import settings

celery_app = Celery(
    "metrics_platform",
    broker=settings.CELERY_BROKER_URL or settings.REDIS_URL,
    backend=settings.CELERY_RESULT_BACKEND or settings.REDIS_URL,
    include=["app.tasks.forecast_tasks"]
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Shanghai",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=300,  # 5分钟超时
    task_soft_time_limit=280,
    broker_connection_retry_on_startup=True,
)
```



**任务定义：** `tasks/forecast_tasks.py`

python

```
from app.core.celery_app import celery_app
from app.core.database import async_session_factory
from app.services.forecast import forecast_linear
from app.models.task import Task, TaskStatus
import asyncio

@celery_app.task(bind=True)
def forecast_task(self, task_id: str, metric_id: int, steps: int):
    """预测任务"""
    # Celery任务中运行异步代码需要特殊处理
    async def _run():
        async with async_session_factory() as db:
            # 更新状态为STARTED
            task = await db.get(Task, task_id)
            task.status = TaskStatus.STARTED
            task.started_at = datetime.utcnow()
            await db.commit()
            
            try:
                # 执行预测
                result = await forecast_linear(db, metric_id, steps)
                task.status = TaskStatus.SUCCESS
                task.result = result
            except Exception as e:
                task.status = TaskStatus.FAILURE
                task.error_message = str(e)
            finally:
                task.completed_at = datetime.utcnow()
                await db.commit()
    
    # 在Celery worker中运行异步函数
    asyncio.run(_run())
    return {"task_id": task_id}
```



### 4.4 异常检测算法实现

**3σ原则** 是最核心的算法，需特别注意：

1. **数据分布假设**：3σ假设数据服从正态分布。实际数据可能偏态，可增加对数变换预处理。
2. **异常污染**：如果数据本身包含大量异常，均值和标准差会被污染。考虑使用 **MAD（中位数绝对偏差）** 作为鲁棒替代。
3. **性能优化**：计算标准差需要两次遍历数据，对于大数据集，使用 **Welford算法** 一次遍历完成。

**实现示例：** `services/anomaly.py`

python

```
import numpy as np
from typing import List, Tuple

def detect_anomalies_3sigma(
    values: List[float],
    sigma_multiplier: float = 3.0
) -> List[Tuple[int, float, float]]:
    """
    基于3σ原则检测异常点
    
    Returns:
        List of (index, value, z_score)
    """
    n = len(values)
    if n < 3:
        return []
    
    # 使用Welford算法一次遍历计算均值和标准差
    mean = 0.0
    m2 = 0.0  # 平方差累积
    
    for i, x in enumerate(values):
        delta = x - mean
        mean += delta / (i + 1)
        delta2 = x - mean
        m2 += delta * delta2
    
    variance = m2 / (n - 1) if n > 1 else 0
    std = np.sqrt(variance)
    
    if std == 0:
        return []
    
    anomalies = []
    for i, x in enumerate(values):
        z_score = abs(x - mean) / std
        if z_score > sigma_multiplier:
            anomalies.append((i, x, z_score))
    
    return anomalies
```



### 4.5 数据库性能优化

| 优化点       | 方法                                                         |
| :----------- | :----------------------------------------------------------- |
| **批量插入** | 使用 `bulk_insert_mappings` 或 `insert().values()` 批量写入，避免逐条insert |
| **N+1查询**  | 使用 SQLAlchemy 的 `joinedload()` 预先加载关联数据           |
| **统计查询** | 缓存频繁查询的统计结果（见4.2）                              |
| **分页查询** | 使用 `limit/offset` 或 `cursor-based` 分页（后者更高效）     |
| **连接池**   | 配置合适的连接池大小（`pool_size=20, max_overflow=10`）      |

**批量插入示例：**

python

```
from sqlalchemy import insert

async def bulk_insert_datapoints(
    db: AsyncSession,
    metric_id: int,
    datapoints: List[dict]
):
    """批量插入数据点，性能提升10倍以上"""
    stmt = insert(Datapoint).values([
        {"metric_id": metric_id, "timestamp": d["timestamp"], "value": d["value"]}
        for d in datapoints
    ])
    await db.execute(stmt)
    await db.commit()
```



### 4.6 API认证与安全

| 安全措施        | 实现方式                                                     |
| :-------------- | :----------------------------------------------------------- |
| **API Key认证** | 在 `dependencies.py` 中实现 `get_current_user`，从 `Authorization: Bearer <key>` 提取并验证 |
| **限流**        | 使用 `slowapi` 或 Redis + 滑动窗口实现                       |
| **输入校验**    | Pydantic模型自动校验；额外业务校验在service层                |
| **CORS**        | FastAPI的 `CORSMiddleware` 配置允许的源                      |
| **SQL注入**     | SQLAlchemy ORM自动参数化，天然防止注入                       |

**认证依赖：** `api/dependencies.py`

python

```
from fastapi import Depends, HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.config import settings

security = HTTPBearer()

async def verify_api_key(
    credentials: HTTPAuthorizationCredentials = Security(security)
) -> str:
    """验证API Key"""
    api_key = credentials.credentials
    if api_key != settings.API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API Key")
    return api_key

# 在端点中使用
@router.get("/metrics")
async def list_metrics(
    api_key: str = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db)
):
    ...
```



### 4.7 可观测性设计

| 维度           | 工具/方法                                                    |
| :------------- | :----------------------------------------------------------- |
| **结构化日志** | structlog 输出JSON格式，包含 `request_id`、`user_id`、`duration` |
| **指标监控**   | 使用 `prometheus_fastapi_instrumentator` 暴露： - `http_requests_total` (按method/endpoint/status) - `http_request_duration_seconds` - `tasks_pending_total` - `cache_hit_ratio` |
| **链路追踪**   | 每个请求生成 `X-Request-ID`，在日志和响应头中返回            |
| **健康检查**   | `/health` 返回 `{"status": "ok"}`，同时检查数据库和Redis连接 |

### 4.8 开发与部署注意事项

| 阶段     | 注意事项                                                     |
| :------- | :----------------------------------------------------------- |
| **开发** | • 使用 `--reload` 热重载 • 使用 `docker-compose.yml` 启动所有依赖服务 • 用 `pytest-watch` 自动运行测试 |
| **生产** | • 使用 `gunicorn + uvicorn.workers.UvicornWorker` 多进程 • Celery worker数量与CPU核心数匹配 • 使用环境变量或Secrets管理敏感配置 |
| **迁移** | • `alembic revision --autogenerate -m "message"` • 生产环境迁移前先备份数据库 |