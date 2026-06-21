# AGENTS.md

## 智能指标分析平台 - AI代理开发指南

------

| 项目         | 内容                       |
| :----------- | :------------------------- |
| 文档版本     | v1.0                       |
| 创建日期     | 2026-06-21                 |
| 对应PRD      | v1.0                       |
| 对应技术设计 | v1.0                       |
| 目标读者     | AI编程助手、贡献者、维护者 |

------

## 一、项目概述

### 1.1 项目简介

**智能指标分析平台** 是一个轻量级、API优先的时序指标分析引擎。它提供从数据接入、存储、统计分析到异常检测、趋势预测的完整能力，并以RESTful API的形式对外提供服务。

### 1.2 核心定位

> API-first 后端服务，非前端应用。目标用户是开发者和数据工程师。

### 1.3 MVP核心功能（v1.0）

| 功能模块 | 核心接口                           | 优先级 |
| :------- | :--------------------------------- | :----- |
| 指标管理 | 创建指标、查询指标列表             | P0     |
| 数据上传 | 批量上传数据点                     | P0     |
| 数据查询 | 按时间范围查询原始数据、查询最新值 | P0     |
| 统计分析 | 均值/最大/最小/标准差/中位数       | P0     |
| 异常检测 | 3σ原则异常检测                     | P0     |
| 趋势预测 | 异步提交预测任务、查询任务状态     | P1     |
| 移动平均 | 指定窗口的移动平均线               | P1     |

------

## 二、开发环境与工具

### 2.1 必需工具

| 工具           | 版本要求 | 用途               |
| :------------- | :------- | :----------------- |
| Python         | ≥3.11    | 主要开发语言       |
| Docker         | ≥24.0    | 容器化运行环境     |
| Docker Compose | ≥2.20    | 多服务编排         |
| Git            | ≥2.40    | 版本控制           |
| make           | ≥4.0     | 任务自动化（可选） |

### 2.2 Python依赖管理

bash

```
# 安装依赖
pip install -r requirements/dev.txt

# 或使用uv（更快）
uv pip install -r requirements/dev.txt
```



### 2.3 一键启动开发环境

bash

```
# 启动所有服务（PostgreSQL + Redis + FastAPI + Celery）
docker-compose up -d

# 查看日志
docker-compose logs -f app

# 停止所有服务
docker-compose down
```



### 2.4 环境变量

复制 `.env.example` 为 `.env`，并根据需要修改：

bash

```
cp .env.example .env
```



**必须修改的生产环境变量：**

| 变量                | 说明         | 开发默认值    |
| :------------------ | :----------- | :------------ |
| `API_KEY`           | API认证密钥  | `dev-api-key` |
| `POSTGRES_PASSWORD` | 数据库密码   | `postgres`    |
| `SECRET_KEY`        | JWT/会话密钥 | 自动生成      |

------

## 三、代码组织规范

### 3.1 目录结构（必读）

text

```
app/
├── api/                    # API层 — 只处理HTTP请求/响应
│   ├── dependencies.py     # 依赖注入（认证、数据库会话）
│   ├── exceptions.py       # 异常处理器
│   └── v1/                 # API版本
│       ├── endpoints/      # 每个端点一个文件
│       └── schemas/        # Pydantic请求/响应模型
│
├── core/                   # 基础设施 — 不包含业务逻辑
│   ├── database.py         # 数据库连接
│   ├── redis_client.py     # Redis客户端
│   ├── celery_app.py       # Celery实例
│   ├── security.py         # 认证逻辑
│   └── logging.py          # 日志配置
│
├── models/                 # ORM模型 — 纯表定义
│
├── services/               # 业务逻辑层 — 核心算法 ✨
│   ├── statistics.py       # 统计分析
│   ├── anomaly.py          # 异常检测
│   ├── forecast.py         # 预测算法
│   └── cache.py            # 缓存服务
│
├── tasks/                  # Celery异步任务
│   └── forecast_tasks.py
│
└── utils/                  # 纯工具函数（无副作用）
```



### 3.2 分层职责（严格遵守）

| 层级          | 职责                            | 禁止                                        |
| :------------ | :------------------------------ | :------------------------------------------ |
| **API层**     | 参数校验、调用service、返回响应 | ❌ 直接操作数据库、❌ 包含业务逻辑            |
| **Service层** | 核心算法、业务逻辑              | ❌ 处理HTTP请求/响应、❌ 直接返回Pydantic模型 |
| **Model层**   | 表结构定义、关系                | ❌ 包含业务逻辑、❌ 包含序列化逻辑            |
| **Task层**    | 异步任务编排                    | ❌ 包含复杂业务逻辑（调用service）           |
| **Utils层**   | 纯函数（输入→输出）             | ❌ 依赖外部状态（数据库、Redis）             |

### 3.3 命名规范

| 类型      | 规范               | 示例                   |
| :-------- | :----------------- | :--------------------- |
| 文件名    | `snake_case.py`    | `anomaly_detection.py` |
| 类名      | `PascalCase`       | `MetricService`        |
| 函数/方法 | `snake_case`       | `compute_statistics`   |
| 变量      | `snake_case`       | `metric_id`            |
| 常量      | `UPPER_SNAKE_CASE` | `CACHE_TTL_STATS`      |
| 异步函数  | `async def` 前缀   | `async def get_metric` |
| 私有函数  | `_snake_case`      | `_validate_data`       |

------

## 四、代码风格规范

### 4.1 格式化与Lint

**强制使用 `ruff` 进行格式化和Lint检查：**

bash

```
# 检查所有代码
ruff check app/

# 自动修复可修复的问题
ruff check --fix app/

# 格式化代码
ruff format app/
```



**提交前必须通过：**

bash

```
ruff check app/ && ruff format --check app/
```



### 4.2 类型注解（强制）

**所有函数必须包含完整的类型注解：**

python

```
# ✅ 正确
async def compute_moving_average(
    metric_id: int,
    window: int,
    db: AsyncSession
) -> List[Dict[str, Union[datetime, float]]]:
    ...

# ❌ 错误（缺少返回类型）
async def compute_moving_average(metric_id, window, db):
    ...
```



### 4.3 Docstring规范

使用 **Google风格** docstring：

python

```
def detect_anomalies_3sigma(
    values: List[float],
    sigma_multiplier: float = 3.0
) -> List[Tuple[int, float, float]]:
    """
    基于3σ原则检测时序数据中的异常点。

    假设数据服从正态分布，超出均值 ± n*标准差 的点被标记为异常。

    Args:
        values: 数值列表，按时间顺序排列
        sigma_multiplier: 标准差倍数，默认3.0

    Returns:
        异常点列表，每个元素为 (索引, 数值, z-score)

    Raises:
        ValueError: 当values为空或长度小于3时

    Examples:
        >>> detect_anomalies_3sigma([1, 2, 3, 100, 4, 5])
        [(3, 100, 3.2)]
    """
    ...
```



### 4.4 Import排序

ruff会自动处理，规则：

1. 标准库
2. 第三方库
3. 本地模块

python

```
# ✅ 正确
import asyncio
from datetime import datetime
from typing import List, Optional

import numpy as np
from fastapi import APIRouter, Depends
from sqlalchemy import select

from app.core.database import AsyncSession
from app.models.metric import Metric
```



------

## 五、测试要求

### 5.1 测试覆盖率目标

| 模块        | 最低覆盖率 | 说明                            |
| :---------- | :--------- | :------------------------------ |
| `services/` | **90%**    | 核心业务逻辑，必须充分测试      |
| `api/`      | **80%**    | API层主要测试参数校验和错误处理 |
| `utils/`    | **90%**    | 纯函数，易于测试                |
| `models/`   | 不强制     | 由集成测试覆盖                  |
| **整体**    | **≥80%**   |                                 |

### 5.2 运行测试

bash

```
# 运行所有测试
pytest

# 运行并生成覆盖率报告
pytest --cov=app --cov-report=html

# 只运行单元测试（不依赖外部服务）
pytest tests/unit/

# 运行特定测试文件
pytest tests/unit/test_anomaly.py
```



### 5.3 测试文件命名

| 测试类型 | 文件命名             | 位置                 |
| :------- | :------------------- | :------------------- |
| 单元测试 | `test_<模块名>.py`   | `tests/unit/`        |
| 集成测试 | `test_api_<端点>.py` | `tests/integration/` |
| fixtures | `conftest.py`        | `tests/`             |

### 5.4 测试编写规范

**单元测试示例：** `tests/unit/test_anomaly.py`

python

```
import pytest
from app.services.anomaly import detect_anomalies_3sigma

class TestAnomalyDetection:
    """3σ异常检测算法测试"""
    
    def test_no_anomalies_in_normal_data(self):
        """正常数据应返回空列表"""
        data = [10, 11, 10, 12, 11, 10, 12, 11]
        result = detect_anomalies_3sigma(data)
        assert len(result) == 0
    
    def test_detects_outlier(self):
        """应检测出明显异常值"""
        data = [10, 11, 10, 100, 12, 11, 10]
        result = detect_anomalies_3sigma(data)
        assert len(result) == 1
        assert result[0][0] == 3  # 异常在第4个位置
        assert result[0][1] == 100  # 异常值
    
    def test_empty_data_returns_empty(self):
        """空数据应安全返回空列表，不抛出异常"""
        assert detect_anomalies_3sigma([]) == []
    
    def test_constant_data_returns_empty(self):
        """所有值相同时不应检测出异常"""
        data = [5, 5, 5, 5, 5]
        assert detect_anomalies_3sigma(data) == []
```



**集成测试示例：** `tests/integration/test_api_metrics.py`

python

```
import pytest
from httpx import AsyncClient

class TestMetricsAPI:
    """指标管理API集成测试"""
    
    async def test_create_metric(self, client: AsyncClient, api_key: str):
        """测试创建指标"""
        response = await client.post(
            "/api/v1/metrics",
            json={"name": "test_metric", "unit": "人", "description": "测试指标"},
            headers={"Authorization": f"Bearer {api_key}"}
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "test_metric"
        assert "id" in data
    
    async def test_create_duplicate_metric_fails(
        self, client: AsyncClient, api_key: str, existing_metric: dict
    ):
        """重复创建相同名称的指标应返回409错误"""
        response = await client.post(
            "/api/v1/metrics",
            json={"name": existing_metric["name"]},
            headers={"Authorization": f"Bearer {api_key}"}
        )
        assert response.status_code == 409
        assert "already exists" in response.json()["detail"]
```



### 5.5 Mock外部依赖

对于依赖数据库或Redis的service测试，使用 `pytest-asyncio` + `mock`：

python

```
import pytest
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
async def test_compute_stats_with_cache_hit():
    """测试缓存命中时直接返回缓存数据"""
    cache_service = AsyncMock()
    cache_service.get.return_value = '{"mean": 10, "count": 100}'
    
    result = await compute_stats(1, cache=cache_service)
    assert result["mean"] == 10
    cache_service.get.assert_called_once()
```



------

## 六、Git工作流

### 6.1 分支策略

text

```
main              # 生产分支（稳定）
  └── develop     # 开发分支
       ├── feature/add-metric-api    # 功能分支
       ├── feature/anomaly-detection
       ├── bugfix/cache-ttl
       └── docs/update-readme
```



### 6.2 Commit规范

使用 **Conventional Commits** 格式：

text

```
<type>(<scope>): <subject>

[optional body]

[optional footer]
```



**允许的type：**

| type       | 说明                   |
| :--------- | :--------------------- |
| `feat`     | 新功能                 |
| `fix`      | Bug修复                |
| `docs`     | 文档更新               |
| `style`    | 代码格式（不影响逻辑） |
| `refactor` | 重构（不改变功能）     |
| `perf`     | 性能优化               |
| `test`     | 测试相关               |
| `chore`    | 构建/工具相关          |

**示例：**

text

```
feat(anomaly): add 3-sigma anomaly detection API

- Implement detect_anomalies_3sigma service
- Add GET /api/v1/metrics/{name}/anomalies endpoint
- Unit tests with 92% coverage

Closes #12
```



### 6.3 提交前检查清单

- 所有测试通过：`pytest`
- 代码格式化：`ruff format app/`
- Lint检查通过：`ruff check app/`
- 类型检查通过：`mypy app/`
- 覆盖率不低于标准：`pytest --cov=app --cov-fail-under=80`
- 无硬编码敏感信息（API Key、密码等）

------

## 七、重要约定与约束

### 7.1 异步/同步边界

| 场景                | 方式                        | 原因                    |
| :------------------ | :-------------------------- | :---------------------- |
| API端点             | `async def`                 | FastAPI原生支持异步     |
| 数据库查询          | `await session.execute()`   | 使用asyncpg驱动，非阻塞 |
| 统计分析（CPU密集） | `await asyncio.to_thread()` | 避免阻塞事件循环        |
| Redis操作           | `await redis.get()`         | 使用redis.asyncio客户端 |
| Celery任务          | 同步函数                    | Celery worker独立进程   |

### 7.2 错误处理

**统一异常层次：**

python

```
# core/exceptions.py

class AppException(Exception):
    """基础异常"""
    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code

class MetricNotFoundError(AppException):
    def __init__(self, name: str):
        super().__init__(f"指标 '{name}' 不存在", status_code=404)

class DuplicateMetricError(AppException):
    def __init__(self, name: str):
        super().__init__(f"指标 '{name}' 已存在", status_code=409)

class InvalidDataError(AppException):
    def __init__(self, message: str):
        super().__init__(message, status_code=422)
```



**API层统一捕获：** 在 `api/exceptions.py` 中注册全局异常处理器。

### 7.3 响应格式规范

**成功响应：**

json

```
{
  "code": 0,
  "message": "success",
  "data": { ... }
}
```



**错误响应：**

json

```
{
  "code": 404,
  "message": "指标 'daily_users' 不存在",
  "detail": null
}
```



### 7.4 日志规范

使用 **结构化日志**（JSON格式），必须包含的字段：

| 字段          | 说明             | 示例                      |
| :------------ | :--------------- | :------------------------ |
| `timestamp`   | ISO 8601格式     | `2026-06-21T10:00:00Z`    |
| `level`       | 日志级别         | `INFO`, `ERROR`           |
| `logger`      | 模块名           | `app.services.statistics` |
| `request_id`  | 请求唯一ID       | `req_abc123`              |
| `message`     | 日志信息         | `"Query completed"`       |
| `duration_ms` | 操作耗时（毫秒） | `45.2`                    |

**示例：**

python

```
from structlog import get_logger

logger = get_logger(__name__)

async def compute_stats(metric_id: int):
    logger.info(
        "computing statistics",
        metric_id=metric_id,
        extra={"user_id": "xxx"}
    )
    # ...
    logger.info(
        "statistics computed",
        metric_id=metric_id,
        duration_ms=45.2
    )
```



------

## 八、AI协作指南

### 8.1 向AI提问时的最佳实践

**✅ 好的问题：**

> "请帮我实现 `app/services/anomaly.py` 中的 `detect_anomalies_mad` 函数，使用MAD（中位数绝对偏差）方法检测异常，要求：1) 纯函数无副作用 2) 类型注解完整 3) 包含Google风格docstring 4) 附上单元测试示例"

**❌ 需要避免：**

> "帮我写一个异常检测函数"（信息不足，无法给出高质量回答）

### 8.2 AI输出检查清单

当AI生成代码后，人工确认：

- 代码风格符合 `ruff` 规范
- 类型注解完整
- docstring存在且准确
- 无安全漏洞（SQL注入、硬编码密钥等）
- 异常处理恰当
- 性能合理（无明显O(n²)或N+1查询）

### 8.3 常用AI提示词模板

**实现新功能：**

text

```
请根据以下规格实现 [功能名称]：

功能描述：[从PRD中引用]
接口定义：[HTTP方法 + 路径 + 请求/响应格式]
业务逻辑：[详细步骤]
约束条件：[边界条件、性能要求]

参考：
- 已有类似实现：[文件路径]
- 技术设计文档：[具体章节]
```



**修复Bug：**

text

```
请修复以下问题：

问题描述：[用户反馈或错误日志]
复现步骤：[如何触发]
当前行为：[错误行为]
期望行为：[正确行为]

环境信息：
- Python版本：[x.x.x]
- 相关依赖：[package==version]
```



------

## 九、快速参考卡片

### 常用命令

bash

```
# 开发
docker-compose up -d              # 启动所有服务
docker-compose logs -f app        # 查看应用日志
make dev                          # 启动开发服务器（需定义）

# 代码质量
ruff check app/                   # Lint检查
ruff check --fix app/             # 自动修复
ruff format app/                  # 格式化
mypy app/                         # 类型检查

# 测试
pytest                            # 全部测试
pytest tests/unit/                # 仅单元测试
pytest --cov=app                  # 带覆盖率
pytest -v -k "test_anomaly"       # 运行匹配的测试

# 数据库
alembic revision --autogenerate   # 生成迁移脚本
alembic upgrade head              # 执行迁移
alembic downgrade -1              # 回滚一个版本
```



### 常用导入路径

python

```
# 数据库
from app.core.database import AsyncSession, get_db

# 模型
from app.models.metric import Metric
from app.models.datapoint import Datapoint

# 配置
from app.config import settings

# 日志
from structlog import get_logger

# 响应格式
from app.api.responses import success_response, error_response
```



------

## 十、附录

### A. 相关文档索引

| 文档     | 路径                   | 说明           |
| :------- | :--------------------- | :------------- |
| PRD      | `docs/PRD.md`          | 产品需求文档   |
| 技术设计 | `docs/TECH_DESIGN.md`  | 技术架构与选型 |
| 本文件   | `AGENTS.md`            | AI开发指南     |
| API示例  | `docs/API_EXAMPLES.md` | API调用示例    |
| 部署指南 | `docs/DEPLOYMENT.md`   | 生产部署步骤   |

### B. 参考资源

- [FastAPI官方文档](https://fastapi.tiangolo.com/)
- [SQLAlchemy异步文档](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html)
- [Celery最佳实践](https://docs.celeryq.dev/en/stable/userguide/tasks.html)
- [Ruff文档](https://docs.astral.sh/ruff/)
- [Conventional Commits](