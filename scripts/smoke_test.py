"""
端到端自动化测试脚本（独立运行，不修改任何业务代码）

用法：
    python scripts/smoke_test.py

执行流程：
    1. 在 MySQL 中新建独立测试库 wms_test（不触碰 wms_db）
    2. 通过环境变量把应用指向测试库，建表并写入测试账号
    3. 启动临时 uvicorn 实例，用真实 HTTP 请求覆盖核心接口
    4. 校验库存数字、状态机、权限、参数校验与并发
    5. 停止服务并删除测试库

依赖：仅 Python 标准库 + 项目已有依赖（PyMySQL、uvicorn）
"""
import json
import logging
import os
import sys
import threading
import time
import urllib.error
import urllib.request

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

TEST_DB = "wms_test"
PORT = 8181
BASE_URL = f"http://127.0.0.1:{PORT}"

# 必须在导入 app.config 之前设置，环境变量优先级高于 .env
os.environ["DB_NAME"] = TEST_DB

from app.config import settings  # noqa: E402
from app.database import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models.user import Role, User  # noqa: E402
from app.utils.password_utils import hash_password  # noqa: E402

import pymysql  # noqa: E402
import uvicorn  # noqa: E402

# 复用项目的 engine，但关闭 SQL 回显，保持测试输出干净
engine.echo = False
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

FAILS: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    if cond:
        print(f"  PASS  {name}")
    else:
        print(f"  FAIL  {name}  {detail}")
        FAILS.append(name)


def api(method: str, path: str, body=None, token=None):
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(BASE_URL + path, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", "Bearer " + token)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8")
        try:
            return exc.code, json.loads(raw)
        except ValueError:
            return exc.code, {"raw": raw}


def expect(name: str, method: str, path: str, body=None, token=None, code: int = 0):
    status, resp = api(method, path, body, token)
    check(name, status == 200 and resp.get("code") == code, f"HTTP {status}, {resp}")
    return resp


def login(username: str, password: str = "123456") -> str:
    resp = expect(f"登录 {username}", "POST", "/api/auth/login",
                  {"username": username, "password": password})
    return resp["data"]["access_token"]


def make_product(token: str, sku: str, qty: int, warning: int = 0) -> int:
    resp = expect(f"创建商品 {sku}", "POST", "/api/products", {
        "sku": sku, "name": f"测试商品 {sku}", "category_id": CTX["category_id"],
        "unit": "件", "total_qty": qty, "warning_qty": warning,
    }, token)
    return resp["data"]["id"]


def stock(token: str, product_id: int) -> tuple[int, int]:
    resp = expect(f"查询商品 {product_id} 库存", "GET", f"/api/products/{product_id}",
                  token=token)
    return resp["data"]["total_qty"], resp["data"]["frozen_qty"]


def outbound(token: str, product_id: int, qty: int):
    return api("POST", "/api/outbound",
               {"product_id": product_id, "quantity": qty}, token)


CTX: dict = {}


def test_auth_and_permissions():
    print("\n[1] 基础与鉴权")
    expect("根路径可访问", "GET", "/")
    expect("未登录访问商品列表", "GET", "/api/products", code=401)
    expect("无 token 访问当前用户", "GET", "/api/auth/me", code=401)

    expect("注册新用户", "POST", "/api/auth/register",
           {"username": "t_new", "password": "123456"})
    expect("重复注册同名用户", "POST", "/api/auth/register",
           {"username": "t_new", "password": "123456"}, code=400)
    expect("用户名过短", "POST", "/api/auth/register",
           {"username": "ab", "password": "123456"}, code=400)
    expect("密码错误", "POST", "/api/auth/login",
           {"username": "t_admin", "password": "bad-pass"}, code=401)

    me = expect("获取当前用户", "GET", "/api/auth/me", token=CTX["admin"])
    check("当前用户是 t_admin", me["data"]["username"] == "t_admin", me)

    print("\n[2] 权限矩阵")
    expect("普通用户创建分类", "POST", "/api/categories",
           {"name": "越权分类"}, CTX["user"], code=403)
    expect("普通用户查看操作日志", "GET", "/api/logs", token=CTX["user"], code=403)
    expect("普通用户查看系统概览", "GET", "/api/stats/overview",
           token=CTX["user"], code=403)

    resp = expect("管理员创建分类", "POST", "/api/categories",
                  {"name": "测试分类", "description": "自动化测试"}, CTX["admin"])
    CTX["category_id"] = resp["data"]["id"]
    expect("分类重名", "POST", "/api/categories",
           {"name": "测试分类"}, CTX["admin"], code=400)
    expect("普通用户创建商品", "POST", "/api/products",
           {"sku": "NO-AUTH", "name": "越权", "category_id": CTX["category_id"]},
           CTX["user"], code=403)


def test_product_rules():
    print("\n[3] 商品规则")
    CTX["p1"] = make_product(CTX["admin"], "SMOKE-P1", 10, warning=2)
    expect("SKU 重复", "POST", "/api/products",
           {"sku": "SMOKE-P1", "name": "重复", "category_id": CTX["category_id"]},
           CTX["admin"], code=400)
    expect("商品名为空", "PUT", f"/api/products/{CTX['p1']}",
           {"name": ""}, CTX["admin"], code=400)
    expect("分类不存在", "PUT", f"/api/products/{CTX['p1']}",
           {"category_id": 999999}, CTX["admin"], code=404)
    expect("缺少必填字段", "POST", "/api/products",
           {"sku": "MISSING-NAME"}, CTX["admin"], code=400)

    resp = expect("更新时传 null 视为不修改", "PUT", f"/api/products/{CTX['p1']}",
                  {"unit": None}, CTX["admin"])
    check("单位未被改成 null", resp["data"]["unit"] == "件", resp["data"])

    CTX["p_tmp"] = make_product(CTX["admin"], "SMOKE-TMP", 1)
    expect("删除无单据商品", "DELETE", f"/api/products/{CTX['p_tmp']}",
           token=CTX["admin"])


def test_inbound():
    print("\n[4] 入库")
    expect("普通用户入库 5 件", "POST", "/api/inbound",
           {"product_id": CTX["p1"], "quantity": 5}, CTX["user"])
    check("入库后总库存 15", stock(CTX["admin"], CTX["p1"]) == (15, 0),
          stock(CTX["admin"], CTX["p1"]))
    expect("入库数量为 0", "POST", "/api/inbound",
           {"product_id": CTX["p1"], "quantity": 0}, CTX["user"], code=400)
    expect("入库商品不存在", "POST", "/api/inbound",
           {"product_id": 999999, "quantity": 1}, CTX["user"], code=404)


def test_outbound_flow():
    print("\n[5] 出库提交与审批")
    resp = expect("提交出库 4 件", "POST", "/api/outbound",
                  {"product_id": CTX["p1"], "quantity": 4}, CTX["user"])
    order1 = resp["data"]["id"]
    check("提交后冻结 4", stock(CTX["admin"], CTX["p1"]) == (15, 4),
          stock(CTX["admin"], CTX["p1"]))
    check("单据状态 pending", resp["data"]["status"] == "pending", resp["data"])

    expect("超出可用库存", "POST", "/api/outbound",
           {"product_id": CTX["p1"], "quantity": 99}, CTX["user"], code=400)
    check("失败后冻结不变", stock(CTX["admin"], CTX["p1"]) == (15, 4),
          stock(CTX["admin"], CTX["p1"]))

    expect("普通用户审批", "POST", f"/api/outbound/{order1}/approve",
           {"approve": True}, CTX["user"], code=403)
    expect("管理员审批通过", "POST", f"/api/outbound/{order1}/approve",
           {"approve": True}, CTX["admin"])
    check("通过后 15-4=11，冻结归零", stock(CTX["admin"], CTX["p1"]) == (11, 0),
          stock(CTX["admin"], CTX["p1"]))
    expect("重复审批", "POST", f"/api/outbound/{order1}/approve",
           {"approve": True}, CTX["admin"], code=400)
    expect("通过后再撤回", "POST", f"/api/outbound/{order1}/cancel",
           token=CTX["user"], code=400)

    resp = expect("管理员提交自己的申请", "POST", "/api/outbound",
                  {"product_id": CTX["p1"], "quantity": 1}, CTX["admin"])
    self_order = resp["data"]["id"]
    expect("管理员审批自己的申请", "POST", f"/api/outbound/{self_order}/approve",
           {"approve": True}, CTX["admin"], code=400)
    expect("管理员撤回自己的申请", "POST", f"/api/outbound/{self_order}/cancel",
           token=CTX["admin"])

    print("\n[6] 驳回与撤回")
    resp = expect("提交待驳回申请 2 件", "POST", "/api/outbound",
                  {"product_id": CTX["p1"], "quantity": 2}, CTX["user"])
    order2 = resp["data"]["id"]
    expect("驳回不填原因", "POST", f"/api/outbound/{order2}/approve",
           {"approve": False}, CTX["admin"], code=400)
    expect("驳回并填原因", "POST", f"/api/outbound/{order2}/approve",
           {"approve": False, "reject_reason": "测试驳回"}, CTX["admin"])
    check("驳回后总库存仍为 11、冻结为 0",
          stock(CTX["admin"], CTX["p1"]) == (11, 0), stock(CTX["admin"], CTX["p1"]))

    resp = expect("提交待撤回申请 3 件", "POST", "/api/outbound",
                  {"product_id": CTX["p1"], "quantity": 3}, CTX["user"])
    order3 = resp["data"]["id"]
    expect("别人撤回我的申请", "POST", f"/api/outbound/{order3}/cancel",
           token=CTX["user2"], code=403)
    expect("本人撤回", "POST", f"/api/outbound/{order3}/cancel", token=CTX["user"])
    check("撤回后冻结为 0", stock(CTX["admin"], CTX["p1"])[1] == 0,
          stock(CTX["admin"], CTX["p1"]))


def test_data_scope_and_pagination():
    print("\n[7] 数据权限与分页")
    resp = expect("user 提交一张新申请", "POST", "/api/outbound",
                  {"product_id": CTX["p1"], "quantity": 1}, CTX["user"])
    order4 = resp["data"]["id"]

    resp = expect("user2 查看出库列表", "GET", "/api/outbound",
                  token=CTX["user2"])
    check("user2 看不到别人的单据", resp["data"]["total"] == 0, resp["data"]["total"])
    expect("user2 查看别人的单据详情", "GET", f"/api/outbound/{order4}",
           token=CTX["user2"], code=403)
    resp = expect("user2 查看入库列表", "GET", "/api/inbound", token=CTX["user2"])
    check("user2 看不到别人的入库单", resp["data"]["total"] == 0, resp["data"]["total"])

    resp = expect("管理员查看全部出库单", "GET", "/api/outbound", token=CTX["admin"])
    check("管理员能看到单据", resp["data"]["total"] >= 1, resp["data"]["total"])

    expect("页码为 0", "GET", "/api/products?page=0", token=CTX["admin"], code=400)
    expect("每页超过 100", "GET", "/api/products?page_size=101",
           token=CTX["admin"], code=400)
    expect("非法状态筛选", "GET", "/api/outbound?status=unknown",
           token=CTX["admin"], code=400)
    resp = expect("每页 1 条", "GET", "/api/products?page=1&page_size=1",
                  token=CTX["admin"])
    check("分页结构正确",
          resp["data"]["page"] == 1 and len(resp["data"]["items"]) == 1, resp["data"])

    expect("撤回清理用的单据", "POST", f"/api/outbound/{order4}/cancel",
           token=CTX["user"])


def test_reference_guards_and_stats():
    print("\n[8] 引用校验与统计")
    expect("删除有单据的商品", "DELETE", f"/api/products/{CTX['p1']}",
           token=CTX["admin"], code=400)
    expect("删除有商品的分类", "DELETE", f"/api/categories/{CTX['category_id']}",
           token=CTX["admin"], code=400)

    expect("库存预警", "GET", "/api/stats/warning", token=CTX["user"])
    resp = expect("系统概览", "GET", "/api/stats/overview", token=CTX["admin"])
    check("概览包含商品数", resp["data"]["total_products"] >= 1, resp["data"])

    resp = expect("操作日志", "GET", "/api/logs?page_size=5", token=CTX["admin"])
    check("日志有记录", resp["data"]["total"] > 0, resp["data"]["total"])


def run_concurrently(fn, times: int = 2) -> list:
    results: list = []
    lock = threading.Lock()

    def worker():
        result = fn()
        with lock:
            results.append(result)

    threads = [threading.Thread(target=worker) for _ in range(times)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    return results


def test_concurrency():
    print("\n[9] 并发")
    p2 = make_product(CTX["admin"], "SMOKE-P2", 10)
    results = run_concurrently(
        lambda: api("POST", "/api/outbound",
                    {"product_id": p2, "quantity": 6}, CTX["user"]))
    codes = sorted(r[1].get("code") for r in results)
    check("并发提交只成功一笔（防超卖）", codes == [0, 400], codes)
    check("冻结量等于成功单数量 6", stock(CTX["admin"], p2)[1] == 6,
          stock(CTX["admin"], p2)[1])

    success = next(r for r in results if r[1].get("code") == 0)
    order_id = success[1]["data"]["id"]
    results = run_concurrently(
        lambda: api("POST", f"/api/outbound/{order_id}/approve",
                    {"approve": True}, CTX["admin"]))
    codes = sorted(r[1].get("code") for r in results)
    check("并发审批只成功一次", codes == [0, 400], codes)
    check("审批后库存 4、冻结 0", stock(CTX["admin"], p2) == (4, 0),
          stock(CTX["admin"], p2))


def prepare_database():
    if settings.DB_NAME != TEST_DB:
        raise SystemExit(f"安全校验失败：当前库为 {settings.DB_NAME}，已中止")
    conn = pymysql.connect(
        host=settings.DB_HOST, port=settings.DB_PORT,
        user=settings.DB_USER, password=settings.DB_PASSWORD,
        charset="utf8mb4", autocommit=True,
    )
    with conn.cursor() as cur:
        cur.execute(f"DROP DATABASE IF EXISTS `{TEST_DB}`")
        cur.execute(f"CREATE DATABASE `{TEST_DB}` DEFAULT CHARSET utf8mb4")
    conn.close()

    if engine.url.database != TEST_DB:
        raise SystemExit(f"引擎指向了 {engine.url.database}，已中止")

    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        for username, role in (("t_admin", Role.ADMIN),
                               ("t_user", Role.USER),
                               ("t_user2", Role.USER)):
            db.add(User(username=username,
                        password=hash_password("123456"), role=role))
        db.commit()


def drop_database():
    engine.dispose()
    conn = pymysql.connect(
        host=settings.DB_HOST, port=settings.DB_PORT,
        user=settings.DB_USER, password=settings.DB_PASSWORD,
        charset="utf8mb4", autocommit=True,
    )
    with conn.cursor() as cur:
        cur.execute(f"DROP DATABASE IF EXISTS `{TEST_DB}`")
    conn.close()


def main():
    started_at = time.time()
    server = None
    thread = None
    try:
        prepare_database()

        server = uvicorn.Server(uvicorn.Config(
            app, host="127.0.0.1", port=PORT, log_level="critical"))
        thread = threading.Thread(target=server.run, daemon=True)
        thread.start()
        for _ in range(100):
            if server.started:
                break
            time.sleep(0.1)
        else:
            raise SystemExit("临时服务启动失败")

        CTX["admin"] = login("t_admin")
        CTX["user"] = login("t_user")
        CTX["user2"] = login("t_user2")

        test_auth_and_permissions()
        test_product_rules()
        test_inbound()
        test_outbound_flow()
        test_data_scope_and_pagination()
        test_reference_guards_and_stats()
        test_concurrency()

    finally:
        if server is not None:
            server.should_exit = True
        if thread is not None:
            thread.join(timeout=10)
        try:
            drop_database()
        except Exception as exc:  # noqa: BLE001
            print(f"测试库清理失败: {exc}")

    duration = time.time() - started_at
    print("\n" + "=" * 50)
    if FAILS:
        print(f"结果：失败 {len(FAILS)} 项 / 用时 {duration:.1f}s")
        for name in FAILS:
            print(f"  - {name}")
        sys.exit(1)
    print(f"结果：全部通过 / 用时 {duration:.1f}s")
    print(f"测试库 {TEST_DB} 已删除，业务库未受影响")


if __name__ == "__main__":
    main()
