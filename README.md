# WMS 仓库管理系统后端

基于 FastAPI + SQLAlchemy + MySQL 的仓库管理系统后端，覆盖用户认证、分类与商品管理、入库、出库审批、库存预警和操作日志。

## 技术栈

| 类别 | 选型 |
|---|---|
| Web 框架 | FastAPI + Uvicorn |
| ORM | SQLAlchemy 2.x（Query API） |
| 数据库 | MySQL 8.x + PyMySQL |
| 数据校验 | Pydantic v2 + pydantic-settings |
| 认证 | JWT（python-jose，HS256） |
| 密码 | bcrypt（passlib） |

## 功能与业务流程

| 模块 | 说明 |
|---|---|
| 用户认证 | 注册、登录获取 JWT，`/api/auth/me` 查看当前用户 |
| 分类 / 商品 | 管理员增删改，登录用户可查看；商品支持关键词、分类、库存预警筛选 |
| 入库 | 登录用户即可操作，创建入库单即增加总库存，无审批环节 |
| 出库 | 用户提交申请冻结库存 → 管理员审批 → 用户可撤回自己的待审批单 |
| 统计 | 库存预警列表（登录可看）、系统概览（仅管理员） |
| 操作日志 | 关键操作留痕，管理员可按操作人、类型、对象筛选 |

### 出库状态机

```text
pending ──审批通过──> approved   冻结释放，总库存扣减
   │
   ├────审批驳回──> rejected    冻结释放，总库存不变
   │
   └────用户撤回──> cancelled   冻结释放，总库存不变
```

- 只有 `pending` 可以流转，终态不可再次操作。
- 库存口径：`可用库存 = total_qty - frozen_qty`。
- 提交出库时校验可用库存并冻结；审批通过时同时扣减 `frozen_qty` 和 `total_qty`。

## 数据表

| 表 | 说明 |
|---|---|
| `users` | 用户，角色为 `ADMIN` / `USER` |
| `categories` | 商品分类，名称唯一 |
| `products` | 商品，`sku` 唯一，含总库存 / 冻结库存 / 预警阈值 |
| `inbound_orders` | 入库单，创建即生效 |
| `outbound_orders` | 出库单，含状态、申请人、审批人、驳回原因 |
| `operation_logs` | 操作日志，记录操作人、动作、对象、详情 |

## 目录结构

```text
app/
  main.py          # 应用入口：CORS、路由挂载、全局异常
  config.py        # 配置（读取 .env）
  database.py      # 引擎、会话、Base、get_db 依赖
  dependencies.py  # JWT 鉴权依赖（登录用户 / 管理员）
  constants.py     # 日志 action / target 常量
  models/          # SQLAlchemy 表定义
  schemas/         # Pydantic 请求 / 响应模型
  routers/         # 各业务模块接口
  utils/           # 统一响应、异常、JWT、密码、分页
scripts/
  seed.py          # 可选的初始化脚本
  smoke_test.py    # 端到端自动化测试（独立测试库）
```

## 快速开始

### 1. 环境与依赖

```bash
python -m venv venv
venv\Scripts\activate          # Windows
pip install -r requirements.txt
```

要求 Python 3.10+（代码使用了 `str | None` 写法）。

> **关于 `requirements.txt`**：
>
> - 这份文件列出了项目运行所需的**全部顶层依赖及其精确版本号**（`fastapi==0.156.6` 这种 `==` 写法）。
> - 只保留了核心依赖，**不含间接依赖**（如 `SQLAlchemy` 底层用到的 `typing-extensions` 会在安装时自动拉取）。
> - 去掉了开发/运维工具残留（如 `alembic`、`opentelemetry-api`），保持文件干净。
> - 每个包都有注释说明用途，方便新人快速理解技术栈。
>
> 换机部署时直接 `pip install -r requirements.txt` 即可复现相同环境，不需要手动逐个 `pip install`。

### 2. 创建数据库

```sql
CREATE DATABASE wms_db DEFAULT CHARSET utf8mb4;
```

### 3. 配置 `.env`

在项目根目录新建 `.env`（已在 `.gitignore` 中，不会提交）：

```dotenv
DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASSWORD=你的数据库密码
DB_NAME=wms_db

SECRET_KEY=换成一串随机的长字符串
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440

CORS_ORIGINS=["http://localhost:3000","http://localhost:5173"]
```

说明：

- `CORS_ORIGINS` 必须是 JSON 数组格式，元素是允许跨域的前端地址。
- `.env` 按绝对路径加载，从任意工作目录启动都能读到。
- `app/config.py` 中的默认值只是占位符，不配置 `.env` 会连不上数据库。

### 4. 初始化数据（可选）

```bash
python scripts/seed.py
```

### 5. 启动

```bash
uvicorn app.main:app --reload
```

- 接口文档：http://127.0.0.1:8000/docs
- 根路径：http://127.0.0.1:8000/

## 配置项

| 键 | 示例 | 说明 |
|---|---|---|
| `DB_HOST` / `DB_PORT` | `localhost` / `3306` | MySQL 地址与端口 |
| `DB_USER` / `DB_PASSWORD` | `root` / `123456` | 数据库账号 |
| `DB_NAME` | `wms_db` | 数据库名 |
| `SECRET_KEY` | 随机长字符串 | JWT 签名密钥，泄露等于所有 token 可伪造 |
| `ALGORITHM` | `HS256` | JWT 算法 |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `1440` | token 有效期（分钟） |
| `CORS_ORIGINS` | JSON 数组 | 允许跨域的前端地址 |

## 接口清单

| 方法 | 路径 | 权限 | 说明 |
|---|---|---|---|
| POST | `/api/auth/register` | 公开 | 注册（默认普通用户） |
| POST | `/api/auth/login` | 公开 | 登录，返回 JWT |
| GET | `/api/auth/me` | 登录 | 当前用户信息 |
| GET | `/api/categories` | 登录 | 分类列表 |
| GET | `/api/categories/{id}` | 登录 | 分类详情 |
| POST | `/api/categories` | 管理员 | 创建分类 |
| PUT | `/api/categories/{id}` | 管理员 | 更新分类 |
| DELETE | `/api/categories/{id}` | 管理员 | 删除分类（有商品时禁止） |
| GET | `/api/products` | 登录 | 商品列表（搜索 / 分类 / 预警筛选 / 分页） |
| GET | `/api/products/{id}` | 登录 | 商品详情 |
| POST | `/api/products` | 管理员 | 创建商品 |
| PUT | `/api/products/{id}` | 管理员 | 更新商品（部分字段） |
| DELETE | `/api/products/{id}` | 管理员 | 删除商品（有单据时禁止） |
| POST | `/api/inbound` | 登录 | 创建入库单，立即加库存 |
| GET | `/api/inbound` | 登录 | 入库单列表（普通用户只看自己） |
| GET | `/api/inbound/{id}` | 登录 | 入库单详情 |
| POST | `/api/outbound` | 登录 | 提交出库申请，冻结库存 |
| POST | `/api/outbound/{id}/approve` | 管理员 | 审批通过 / 驳回 |
| POST | `/api/outbound/{id}/cancel` | 登录（本人） | 撤回待审批申请 |
| GET | `/api/outbound` | 登录 | 出库单列表（普通用户只看自己） |
| GET | `/api/outbound/{id}` | 登录 | 出库单详情 |
| GET | `/api/logs` | 管理员 | 操作日志 |
| GET | `/api/stats/warning` | 登录 | 库存预警列表 |
| GET | `/api/stats/overview` | 管理员 | 系统概览 |

列表接口统一返回：

```json
{ "code": 0, "message": "ok", "data": { "total": 7, "page": 1, "page_size": 10, "items": [] } }
```

## 响应与错误码

所有响应统一为 `{code, message, data}`，**业务错误同样返回 HTTP 200**，用 `code` 区分：

| code | 含义 |
|---|---|
| 0 | 成功 |
| 400 | 参数校验失败 / 业务规则不满足 |
| 401 | 未登录、token 无效或过期 |
| 403 | 已登录但无权限 |
| 404 | 资源不存在 |
| 500 | 服务端异常（详情只写服务端日志） |

## 关于 `scripts/seed.py`

**该脚本只是初始化数据的辅助工具，不是运行项目的必需品，可以按需保留或删除。**

它做三件事：

1. 按模型创建所有表（`Base.metadata.create_all`）
2. 创建默认账号：`admin / 123456`（管理员）、`user01 / 123456`（普通用户）
3. 写入 3 个示例分类和 6 个示例商品

脚本是幂等的：已存在的数据会跳过，重复执行不会产生重复记录。

**不用示例数据或不想要这个脚本时：**

| 需求 | 做法 |
|---|---|
| 只想空库启动 | 不执行脚本即可，项目启动不依赖它 |
| 完全不要这个脚本 | 直接删除 `scripts/seed.py`；但删除后没有"一键建表"了，需自行建表（Alembic 或手动 `Base.metadata.create_all`） |
| 只要账号、不要示例商品 | 运行前清空脚本里的 `products_data` |
| 换成自己的初始数据 | 修改脚本里的 `categories_data` / `products_data` |

**默认密码必须修改。** 目前没有修改密码的接口，部署前请直接在数据库中更新：

```sql
UPDATE users SET password='<新的 bcrypt 哈希>' WHERE username='admin';
```

## 账号与角色

- 只有两种角色：`ADMIN`、`USER`，注册用户默认是 `USER`。
- 代码中没有"修改角色"的接口，需要管理员时手工执行（枚举列存的是名称，必须大写）：

```sql
UPDATE users SET role='ADMIN' WHERE username='你的用户名';
```

## 自动化测试

```bash
python scripts/smoke_test.py
```

脚本行为：

- 新建独立测试库 `wms_test`，**不触碰 `wms_db`**
- 启动临时服务（`127.0.0.1:8181`），通过真实 HTTP 请求调用接口
- 覆盖 9 组、90 余项断言：鉴权、权限矩阵、商品规则、入库、出库提交 / 审批 / 驳回 / 撤回、数据范围、分页、引用校验、并发防超卖
- 结束后删除测试库，业务数据不受影响

前置条件：MySQL 账号需有建库 / 删库权限。退出码 `0` 表示全部通过，`1` 表示存在失败项。

## 已知限制

- 自动化测试是独立脚本（`scripts/smoke_test.py`），未接入 pytest / CI。
- 没有修改密码、角色管理接口。
- 未接入 Alembic 迁移，表结构由 `create_all` 或手工建表维护。
- 没有库存流水表，`total_qty` 为汇总值。
- 未做重复提交幂等（依赖前端防抖）。
- `SQLALCHEMY echo=True` 仍开启，生产环境应关闭。
- 业务错误统一返回 HTTP 200，需要前端按 `code` 判断。
