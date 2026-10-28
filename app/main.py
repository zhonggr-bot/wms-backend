import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.config import settings
from app.utils.response import fail, success
from app.utils.exceptions import BusinessException

from app.routers.auth import router as auth_router
from app.routers.category import router as category_router
from app.routers.product import router as product_router
from app.routers.inbound import router as inbound_router
from app.routers.outbound import router as outbound_router
from app.routers.log import router as log_router
from app.routers.stats import router as stats_router

# 日志：走标准 logging（输出格式可在部署时替换成文件或日志服务）
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("wms")

app = FastAPI(title="仓库管理系统后端", version="1.0.0")

# 只放行配置里的前端地址；allow_credentials 开启时不能用 "*"
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 挂载各业务模块的路由
app.include_router(auth_router)
app.include_router(category_router)
app.include_router(product_router)
app.include_router(inbound_router)
app.include_router(outbound_router)
app.include_router(log_router)
app.include_router(stats_router)

# ========== 全局异常处理 ==========

@app.exception_handler(BusinessException)
async def business_exception_handler(request: Request, exc: BusinessException):
    """捕获我们自己抛的业务异常"""
    return JSONResponse(
        status_code=200,
        content=fail(code=exc.code, message=exc.message)
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """捕获请求参数校验异常"""
    errors = exc.errors()
    messages = []
    for e in errors:
        if len(e['loc']) > 1:
            field_name = e['loc'][1]      # 取出字段名，比如 username
        else:
            field_name = '参数'
        messages.append(f"{field_name}: {e['msg']}")
    msg = "; ".join(messages)
    return JSONResponse(
        status_code=200,
        content=fail(code=400, message=msg)
    )

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """兜底——任何没被上面捕获的异常都走这里"""
    # 堆栈只写服务端日志，客户端只返回通用提示
    logger.exception("未捕获异常 %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=200,
        content=fail(code=500, message="服务器内部错误，请联系管理员")
    )

# ========== 一个测试接口 ==========

@app.get("/")
def root():
    return success(data={"project": "WMS Backend", "version": "1.0.0"}, message="欢迎使用仓库管理系统")

# 启动命令：uvicorn app.main:app --reload
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
